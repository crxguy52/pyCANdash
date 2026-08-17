"""
Cruise Control Gateway Emulator
================================
Impersonates the GM Gateway module on HS-GMLAN to provide cruise control
switch states and brake pedal status to the E39 ECM (LFX V6).

HOW IT WORKS (GMW8769 Sec 3.1.1, GMW8762 Sec 4.2.3.62):
- The ECM owns ALL cruise control logic (state machines, speed PID, throttle
  control). It will NOT engage cruise without receiving switch states from
  a Gateway module over GMLAN.
- We transmit frame 0x1E1 (Cruise Control Switch Status) every 30ms with
  the physical button states, a Protection Value, and Alive Rolling Count.
- We transmit frame 0x0F1 (Brake Apply Status) every 10ms with the brake
  pedal switch state, Protection Value, and Alive Rolling Count.
- We transmit frame 0x1F1 (Platform General Status) every 100ms declaring
  System Power Mode = Run and Park Brake state.
- We transmit frame 0x4E9 (Platform Configuration Data) every 1000ms
  declaring Vehicle Speed Control System Type = Conventional Cruise Control.

CRUISE SWITCH MODING (GMW8769 Sec 4.1.4.1.1, Figures 2-6):
- The ECM interprets switch states internally. Our job is just to relay
  the physical button state truthfully.
- ON/OFF: Latched toggle. Momentary press toggles the "On Switch Active"
  state. ECM transitions between Disabled/Enabled.
- SET/COAST: When pressed, Set Switch Active=True AND Speed Decrease Switch
  Active=True. This engages cruise at current vehicle speed OR decreases
  the set speed if already engaged.
- RESUME/ACCEL: When pressed, Resume Switch Active=True AND Speed Increase
  Switch Active=True. This resumes to stored speed OR increases set speed.
- CANCEL: Sets Cancel Switch Active=True. Disengages without clearing
  stored speed.

ECM WILL REFUSE TO ENGAGE IF (GMW8769 Sec 4.1.4.2.1.3):
- Vehicle speed below K_AccLowSpeedDisengage (typical 40 km/h)
- On Switch Active is False
- Brake pedal applied (CAN or discrete)
- Cancel switch active
- Engine not running for minimum time (~5s)
- ETC fault present
- Clutch pedal pressed (manual trans - hardwired to ECM)

PROTECTION VALUE ALGORITHM (GMW8772 Sec 3.3.1.3.2.2):
- PV = two's complement of (signal_data + alive_rolling_count), n-bit result
- For 8-bit cruise switch packet: PV = (~(byte0 + ARC) + 1) & 0xFF
- For 2-bit brake signal (1-bit + ARC): PV = (~(signal + ARC) + 1) & 0x03

KEYBOARD CONTROLS:
    o = Toggle ON/OFF        s = Toggle SET/COAST
    r = Toggle RESUME/ACCEL  c = Toggle CANCEL
    b = Toggle BRAKE         p = Toggle PARK BRAKE
    q = Quit

Usage:
    pdm run python cruise_control.py            # Live on SocketCAN
    pdm run python cruise_control.py --debug    # Simulated (no CAN hardware)
"""

import atexit
import can
import cantools
import logging
import threading
import time
import os
import sys

# === CONFIGURATION ===
CAN_INTERFACE = "socketcan"
CAN_CHANNEL = "can0"
CAN_BITRATE = 500_000

DBC_PATH = os.path.join(os.path.dirname(__file__), "../../../dbc/gmlan_v1.8_custom.dbc")

# TX periods (GMW8762 frame tables)
CRUISE_SWITCH_PERIOD_S = 30e-3       # 0x1E1 per GMW8762 p.239
BRAKE_STATUS_PERIOD_S = 10e-3        # 0x0F1 per GMW8762 p.231
PLATFORM_STATUS_PERIOD_S = 100e-3    # 0x1F1 per GMW8762 p.244
PLATFORM_CONFIG_PERIOD_S = 1.0       # 0x4E9 per GMW8762 p.263

# Vehicle Speed Control System Type (GMW8762 Sec 4.2.3.185)
CRUISE_SYSTEM_TYPE_CONVENTIONAL = 1  # $1 = Conventional Cruise Control

# Startup settling time: allow platform status/config frames to propagate
# before the ECM will trust switch frames
STARTUP_SETTLE_S = 0.5

DEBUG_MODE = "--debug" in sys.argv

# === LOGGING ===
LOG_FORMAT_FILE = "%(asctime)s - %(name)-40s - %(levelname)-8s - %(message)s"
LOG_FORMAT_CONSOLE = "%(levelname)-8s %(message)s"

log = logging.getLogger("cruise_control")
log.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter(LOG_FORMAT_CONSOLE))
log.addHandler(_console_handler)

_file_handler = logging.FileHandler("cruise_control.log")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(LOG_FORMAT_FILE))
log.addHandler(_file_handler)


# === THREAD-SAFE STATE ===

class SwitchState:
    """Thread-safe container for all switch/button states.

    All TX threads call snapshot() to get a consistent copy of all values.
    The keyboard thread mutates state under lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.cruise_on_latched = False
        self.set_switch_pressed = False
        self.resume_switch_pressed = False
        self.cancel_switch_pressed = False
        self.brake_applied = False
        self.park_brake_applied = False

    def snapshot(self):
        """Return a consistent copy of all states under lock."""
        with self._lock:
            return {
                'cruise_on': self.cruise_on_latched,
                'set': self.set_switch_pressed,
                'resume': self.resume_switch_pressed,
                'cancel': self.cancel_switch_pressed,
                'brake': self.brake_applied,
                'park_brake': self.park_brake_applied,
            }

    def toggle(self, attr):
        """Toggle a boolean attribute under lock. Returns new value."""
        with self._lock:
            new_val = not getattr(self, attr)
            setattr(self, attr, new_val)
            return new_val


switches = SwitchState()
shutdown_event = threading.Event()


# === PROTECTION VALUE (GMW8772 Sec 3.3.1.3.2.2) ===

def compute_protection_value(signal_data, arc, n_bits):
    """Compute PPEI protection value per GMW8772 Sec 3.3.1.3.2.2.

    PV = two's complement of (signal_data + alive_rolling_count), truncated
    to n_bits. The two's complement is: bitwise invert, then add 1, discard
    carries beyond n_bits.

    Args:
        signal_data: Binary value of the protected signal/packet.
        arc: Current Alive Rolling Count value (0-3).
        n_bits: Length of the protection value field in bits.

    Returns:
        Protection value as an integer, masked to n_bits.
    """
    mask = (1 << n_bits) - 1
    sum_val = (signal_data + arc) & mask
    pv = (~sum_val + 1) & mask
    return pv


# === TX THREADS ===

def tx_cruise_switch_status(bus):
    """Periodic TX of 0x1E1 (Cruise Control Switch Status) at 30ms.

    Frame layout per GMW8762 Sec 4.2.3.62, page 239:
    - Byte 0: Switch status packet (Cancel|On|Resume|Set|Increase|Decrease|Integrity)
    - Byte 1: Protection Value covering Byte 0
    - Byte 2: [reserved|reserved|reserved|reserved|reserved|Cancel Req|ARC(2)]

    The Protection Value protects the 8-bit switch status packet (Byte 0).
    PV = twos_complement_8bit(Byte0 + ARC) per GMW8772 Sec 3.3.1.3.2.2.
    """
    arc = 0  # Alive Rolling Count, increments 0->1->2->3->0 each TX

    while not shutdown_event.is_set():
        state = switches.snapshot()

        # GMW8762 Sec 4.2.3.62: Build switch status byte
        # Bit 7: Cancel, Bit 6: On, Bit 5: Resume, Bit 4: Set,
        # Bit 3: Speed Increase, Bit 2: Speed Decrease, Bits 1-0: Data Integrity
        switch_byte = 0
        if state['cancel']:
            switch_byte |= (1 << 7)
        if state['cruise_on']:
            switch_byte |= (1 << 6)
        if state['resume']:
            switch_byte |= (1 << 5)
            switch_byte |= (1 << 3)  # Speed Increase = Resume (GMW8762 Sec 4.2.3.62.2)
        if state['set']:
            switch_byte |= (1 << 4)
            switch_byte |= (1 << 2)  # Speed Decrease = Set (GMW8762 Sec 4.2.3.62.2)
        # Bits 1-0: Switch Data Integrity = 0 (Data Valid)

        # GMW8772 Sec 3.3.1.3.2.2: Protection Value for 8-bit packet
        pv = compute_protection_value(switch_byte, arc, n_bits=8)

        # GMW8762 p.239: Cancel Request in byte 2 bit 2
        cancel_req = 1 if state['cancel'] else 0

        # Build frame: Byte0=switches, Byte1=PV, Byte2=[0|0|0|0|0|cancel_req|ARC]
        byte2 = (cancel_req << 2) | (arc & 0x03)
        frame_data = bytes([switch_byte, pv, byte2, 0x00, 0x00])

        if not DEBUG_MODE:
            msg = can.Message(
                arbitration_id=0x1E1,
                data=frame_data,
                is_extended_id=False
            )
            try:
                bus.send(msg)
            except can.CanError as e:
                log.error(f"TX 0x1E1: {e}")
        else:
            log.debug(f"TX 0x1E1: {frame_data.hex(' ')}")

        # GMW8772 Sec 3.3.1.3.1.2: Increment ARC after each TX
        arc = (arc + 1) % 4
        shutdown_event.wait(timeout=CRUISE_SWITCH_PERIOD_S)


def tx_brake_apply_status(bus):
    """Periodic TX of 0x0F1 (Brake Apply Status) at 10ms.

    Frame layout per GMW8762 p.231-232:
    - Byte 0 Bit 7: Moderate Travel Achieved Validity (0=Valid)
    - Byte 0 Bit 6: Moderate Travel Achieved
    - Byte 0 Bits 5-4: Position Alive Rolling Count
    - Byte 0 Bits 3-2: Initial Travel Achieved Protection (2-bit PV)
    - Byte 0 Bit 1: Initial Travel Achieved (brake applied = True)
    - Byte 0 Bit 0: Initial Travel Achieved Validity (0=Valid)
    - Byte 1: Brake Pedal Position (0-100%)

    The Protection Value is 2 bits (single-bit signal with ARC per GMW8772
    Sec 3.3.1.3.2.2 exception for single-bit signals).
    """
    arc = 0

    while not shutdown_event.is_set():
        state = switches.snapshot()
        brake_bit = 1 if state['brake'] else 0

        # GMW8772 Sec 3.3.1.3.2.2: For single-bit signal with ARC, PV is 2 bits
        pv = compute_protection_value(brake_bit, arc, n_bits=2)

        # Build byte 0: [ModTrvlVld|ModTrvl|ARC(2)|PV(2)|InitTrvl|InitTrvlVld]
        byte0 = 0
        # Bit 7: Moderate Travel Validity = 0 (Valid)
        # Bit 6: Moderate Travel Achieved = same as brake_applied
        byte0 |= (brake_bit << 6)
        # Bits 5-4: ARC
        byte0 |= ((arc & 0x03) << 4)
        # Bits 3-2: Protection Value
        byte0 |= ((pv & 0x03) << 2)
        # Bit 1: Initial Travel Achieved
        byte0 |= (brake_bit << 1)
        # Bit 0: Validity = 0 (Valid)

        # Byte 1: Brake pedal position (switch-based: 0% or 100%)
        # Physical encoding: E = N * 100/255, so N = E * 255/100
        byte1 = 255 if state['brake'] else 0

        frame_data = bytes([byte0, byte1])

        if not DEBUG_MODE:
            msg = can.Message(
                arbitration_id=0x0F1,
                data=frame_data,
                is_extended_id=False
            )
            try:
                bus.send(msg)
            except can.CanError as e:
                log.error(f"TX 0x0F1: {e}")
        else:
            log.debug(f"TX 0x0F1: {frame_data.hex(' ')}")

        arc = (arc + 1) % 4
        shutdown_event.wait(timeout=BRAKE_STATUS_PERIOD_S)


def tx_platform_general_status(bus, msg_def):
    """Periodic TX of 0x1F1 (Platform General Status) at 100ms.

    Frame layout per GMW8762 p.244-245. Critical signals for cruise:
    - System Power Mode = Run ($2) — byte 0 bits 1-0 (GMW8762 Sec 4.2.3.180)
    - Park Brake Switch Active — byte 4 bit 4 (GMW8762 Sec 4.2.3.125)
    - Park Brake VDA = Available — byte 4 bit 3 (GMW8762 Sec 4.2.3.126)
    """
    while not shutdown_event.is_set():
        state = switches.snapshot()

        vals = {sig.name: 0 for sig in msg_def.signals}
        vals['system_power_mode'] = 2  # Run
        vals['park_brake_switch_active'] = 1 if state['park_brake'] else 0
        vals['park_brake_vda'] = 1  # Virtual Device Available
        vals['ac_comp_sys_vda'] = 1  # Keep AC VDA active

        data = msg_def.encode(vals)
        if not DEBUG_MODE:
            msg = can.Message(
                arbitration_id=msg_def.frame_id,
                data=data,
                is_extended_id=False
            )
            try:
                bus.send(msg)
            except can.CanError as e:
                log.error(f"TX 0x1F1: {e}")
        else:
            log.debug(f"TX 0x1F1: {data.hex(' ')}")

        shutdown_event.wait(timeout=PLATFORM_STATUS_PERIOD_S)


def tx_platform_config(bus, msg_def):
    """Periodic TX of 0x4E9 (Platform Configuration Data) at 1000ms.

    Declares Vehicle Speed Control System Type = Conventional Cruise Control
    per GMW8762 Sec 4.2.3.185. The ECM checks this against its internal
    calibration K_CruzCruiseSysType (GMW8769 Sec 4.1.4.1.1.1). If they don't
    match, cruise is inhibited.
    """
    while not shutdown_event.is_set():
        vals = {sig.name: 0 for sig in msg_def.signals}
        vals['veh_speed_ctrl_system_type'] = CRUISE_SYSTEM_TYPE_CONVENTIONAL
        vals['ac_compressor_type'] = 1  # Fixed Displacement Clutched

        data = msg_def.encode(vals)
        if not DEBUG_MODE:
            msg = can.Message(
                arbitration_id=msg_def.frame_id,
                data=data,
                is_extended_id=False
            )
            try:
                bus.send(msg)
            except can.CanError as e:
                log.error(f"TX 0x4E9: {e}")
        else:
            log.debug(f"TX 0x4E9: {data.hex(' ')}")

        shutdown_event.wait(timeout=PLATFORM_CONFIG_PERIOD_S)


# === RX THREAD ===

class EcmFeedback:
    """Thread-safe container for ECM feedback signals (RX data)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.cruise_active = False
        self.cruise_enabled = False
        self.vehicle_speed_kph = 0.0

    def snapshot(self):
        """Return a consistent copy of all ECM feedback under lock."""
        with self._lock:
            return {
                'cruise_active': self.cruise_active,
                'cruise_enabled': self.cruise_enabled,
                'vehicle_speed_kph': self.vehicle_speed_kph,
            }

    def update_cruise(self, active, enabled):
        with self._lock:
            self.cruise_active = active
            self.cruise_enabled = enabled

    def update_speed(self, speed_kph):
        with self._lock:
            self.vehicle_speed_kph = speed_kph


ecm_feedback = EcmFeedback()


def rx_monitor(bus, db):
    """RX thread: monitor ECM cruise feedback from 0x0C9 and vehicle speed."""

    id_eng_status_1 = db.get_message_by_name('engine_general_status_1').frame_id
    id_veh_speed = db.get_message_by_name('vehicle_speed_and_distance').frame_id
    watch_ids = {id_eng_status_1, id_veh_speed}

    while not shutdown_event.is_set():
        if DEBUG_MODE:
            shutdown_event.wait(timeout=0.5)
            continue

        msg = bus.recv(timeout=0.5)
        if msg is None:
            continue
        if msg.arbitration_id not in watch_ids:
            continue
        try:
            decoded = db.decode_message(msg.arbitration_id, msg.data)
            if msg.arbitration_id == id_eng_status_1:
                ecm_feedback.update_cruise(
                    active=bool(decoded.get('cruise_control_active', 0)),
                    enabled=bool(decoded.get('cruise_control_enabled', 0)),
                )
            elif msg.arbitration_id == id_veh_speed:
                ecm_feedback.update_speed(
                    decoded.get('vehicle_speed_avg_driven', 0.0)
                )
        except Exception as e:
            log.warning(f"RX decode error (0x{msg.arbitration_id:03X}): {e}")


# === KEYBOARD INPUT THREAD ===

KEYBOARD_HELP = """\
KEYBOARD CONTROLS:
  o = Toggle ON/OFF        s = Toggle SET/COAST
  r = Toggle RESUME/ACCEL  c = Toggle CANCEL
  b = Toggle BRAKE         p = Toggle PARK BRAKE
  q = Quit
"""


def keyboard_input_thread():
    """Read single keypresses and toggle switch states.

    Works on both Windows (msvcrt) and Linux (termios/select).
    This is the PRIMARY input method — not just for debug.
    """
    try:
        import msvcrt

        def get_key():
            if msvcrt.kbhit():
                return msvcrt.getch().decode('utf-8', errors='ignore').lower()
            return None
    except ImportError:
        import select
        import tty
        import termios

        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

        def _restore_terminal():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

        atexit.register(_restore_terminal)

        def get_key():
            if select.select([sys.stdin], [], [], 0.1)[0]:
                return sys.stdin.read(1).lower()
            return None

    KEY_MAP = {
        'o': ('cruise_on_latched', 'ON/OFF'),
        's': ('set_switch_pressed', 'SET/COAST'),
        'r': ('resume_switch_pressed', 'RESUME/ACCEL'),
        'c': ('cancel_switch_pressed', 'CANCEL'),
        'b': ('brake_applied', 'BRAKE'),
        'p': ('park_brake_applied', 'PARK BRAKE'),
    }

    while not shutdown_event.is_set():
        key = get_key()
        if key is None:
            time.sleep(0.02)
            continue

        if key == 'q':
            print("\r\033[K", end='', flush=True)
            log.info("Quit requested")
            shutdown_event.set()
        elif key in KEY_MAP:
            attr, label = KEY_MAP[key]
            new_val = switches.toggle(attr)
            state_str = "ON" if new_val else "OFF"
            print("\r\033[K", end='', flush=True)
            log.info(f"{label} -> {state_str}")


# === MAIN ===

def main():
    dbc_path = os.path.normpath(DBC_PATH)
    log.info(f"Loading DBC: {dbc_path}")
    db = cantools.database.load_file(dbc_path)

    msg_platform_status = db.get_message_by_name('platform_general_status')
    msg_platform_config = db.get_message_by_name('platform_configuration_data')

    bus = None
    if not DEBUG_MODE:
        log.info(f"Opening CAN bus: {CAN_INTERFACE} / {CAN_CHANNEL}")
        bus = can.interface.Bus(channel=CAN_CHANNEL, interface=CAN_INTERFACE)
    else:
        log.info("DEBUG MODE: CAN frames logged to console only (no hardware)")

    # Start platform status/config first so ECM sees them before switch frames
    t_platform_status = threading.Thread(
        target=tx_platform_general_status, args=(bus, msg_platform_status),
        daemon=True, name="tx_0x1F1"
    )
    t_platform_config = threading.Thread(
        target=tx_platform_config, args=(bus, msg_platform_config),
        daemon=True, name="tx_0x4E9"
    )
    t_platform_status.start()
    t_platform_config.start()

    # Let platform frames propagate before starting switch/brake TX
    log.info(
        f"Waiting {STARTUP_SETTLE_S * 1e3:.0f}ms for platform frames to "
        f"propagate before starting switch TX..."
    )
    time.sleep(STARTUP_SETTLE_S)

    t_cruise_sw = threading.Thread(
        target=tx_cruise_switch_status, args=(bus,),
        daemon=True, name="tx_0x1E1"
    )
    t_brake = threading.Thread(
        target=tx_brake_apply_status, args=(bus,),
        daemon=True, name="tx_0x0F1"
    )
    t_rx = threading.Thread(
        target=rx_monitor, args=(bus, db),
        daemon=True, name="rx_monitor"
    )
    t_keyboard = threading.Thread(
        target=keyboard_input_thread, daemon=True, name="keyboard_input"
    )

    t_cruise_sw.start()
    t_brake.start()
    t_rx.start()
    t_keyboard.start()

    log.info("=" * 60)
    log.info("Cruise Control Gateway Emulator")
    log.info(f"  TX 0x1E1 every {CRUISE_SWITCH_PERIOD_S * 1e3:.0f}ms (switch status)")
    log.info(f"  TX 0x0F1 every {BRAKE_STATUS_PERIOD_S * 1e3:.0f}ms (brake status)")
    log.info(f"  TX 0x1F1 every {PLATFORM_STATUS_PERIOD_S * 1e3:.0f}ms (platform status)")
    log.info(f"  TX 0x4E9 every {PLATFORM_CONFIG_PERIOD_S * 1e3:.0f}ms (config)")
    log.info(f"  Cruise System Type: Conventional ($1)")
    if DEBUG_MODE:
        log.info("  *** DEBUG MODE — no frames leave the box ***")
    log.info(KEYBOARD_HELP)
    log.info("=" * 60)

    try:
        while not shutdown_event.is_set():
            state = switches.snapshot()
            ecm = ecm_feedback.snapshot()
            on_str = "ON" if state['cruise_on'] else "OFF"
            active_str = "ACTIVE" if ecm['cruise_active'] else "standby"
            enabled_str = "ENABLED" if ecm['cruise_enabled'] else "disabled"
            brake_str = "BRAKE" if state['brake'] else "     "
            print(
                f"\r  Cruise: {on_str} | ECM: {enabled_str}/{active_str} | "
                f"{brake_str} | Speed: {ecm['vehicle_speed_kph']:.1f} km/h\033[K",
                end='', flush=True
            )
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        shutdown_event.set()
        t_cruise_sw.join(timeout=1.0)
        t_brake.join(timeout=1.0)
        t_platform_status.join(timeout=1.0)
        t_platform_config.join(timeout=1.5)
        t_rx.join(timeout=1.0)
        t_keyboard.join(timeout=0.5)
        if bus is not None:
            bus.shutdown()
        log.info("Bus closed. Done.")


if __name__ == '__main__':
    main()