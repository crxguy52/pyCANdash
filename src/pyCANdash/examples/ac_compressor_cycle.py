"""
AC Compressor Cycle Test Script
================================
Impersonates the GM Platform/Gateway on HS-GMLAN to request AC compressor
engagement from the E92 ECM (LFX V6).

HOW IT WORKS (GMW8771 Section 4.1, GMW8762 Section 4.2.3):
- The ECM owns the AC compressor relay. It will NOT energize it without a
  request from the Platform (Gateway/BCM/HVAC controller).
- We transmit frame 0x1F1 (Platform General Status) every 100ms with the
  "AC Compressor Mode Request" signal set to "Engage" (GMW8762 Sec 4.2.3.19).
- We also transmit frame 0x4E9 (Platform Configuration Data) every 1000ms
  declaring the compressor type (GMW8762 Sec 4.2.3.23).
- The ECM evaluates protections (GMW8771 Sec 4.1.3.13) and, if satisfied,
  sets "AC Compressor Command" = On in frame 0x3D1 and energizes the relay.

ECM WILL REFUSE IF (GMW8771 Sec 4.1.3.13.3-13.9):
- Engine speed outside ~450-4600 RPM
- Battery voltage < 9.5V or > 16V
- AC high-side pressure < 180 kPa or > 3000 kPa (hardwired analog sensor)
- Wide-open throttle (>95% pedal)
- Coolant temp > ~115 degC
- Minimum compressor off-time (~8s) not elapsed

ENGAGEMENT SEQUENCE (GMW8771 Sec 4.1.8.3):
1. Platform TX: Mode Request = Engage, VDA = Available
2. ECM prep: adjusts idle for expected load (Command still Off)
3. ECM TX: Compressor Command = On (relay energizes)
4. Normal operation until disengage requested or protection triggered

Usage:
    pdm run python ac_compressor_cycle.py            # Live on SocketCAN
    pdm run python ac_compressor_cycle.py --debug    # Simulated (no hardware)
"""

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
CAN_BITRATE = 500_000  # Configured at OS level for SocketCAN (ip link set)

DBC_PATH = os.path.join(os.path.dirname(__file__), "../../../dbc/gmlan_v1.7_custom.dbc")

PLATFORM_STATUS_PERIOD_S = 100e-3
PLATFORM_CONFIG_PERIOD_S = 1.0
COMPRESSOR_ON_TIME_S = 15.0
COMPRESSOR_OFF_TIME_S = 15.0

AC_COMPRESSOR_TYPE = 1  # 0=None, 1=Fixed Displacement Clutched, 2=Var Mech, 3=Var Electronic

DEBUG_MODE = "--debug" in sys.argv  # Run without CAN hardware for logic verification

# === LOGGING ===
LOG_FORMAT_FILE = "%(asctime)s - %(name)-40s - %(levelname)-8s - %(message)s"
LOG_FORMAT_CONSOLE = "%(levelname)-8s %(message)s"

log = logging.getLogger("ac_compressor_cycle")
log.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter(LOG_FORMAT_CONSOLE))
log.addHandler(_console_handler)

_file_handler = logging.FileHandler("ac_compressor_cycle.log")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(LOG_FORMAT_FILE))
log.addHandler(_file_handler)

# === GLOBAL STATE ===
ac_mode_request = 0  # 0=Disengage Immediately, 1=Disengage, 2=Engage
ecm_ac_command = 0
ecm_gradient_allowed = 0.0
ac_high_side_pressure_kpa = 0.0
shutdown_event = threading.Event()


def tx_platform_status(bus, msg_def):
    """Periodic TX of 0x1F1 (Platform General Status) at 100ms."""
    vals = {sig.name: 0 for sig in msg_def.signals}
    while not shutdown_event.is_set():
        vals['system_power_mode'] = 2  # Run
        vals['ac_comp_mode_request'] = ac_mode_request
        vals['ac_comp_sys_vda'] = 1  # Virtual Device Available
        vals['ac_comp_norm_load_validity'] = 0  # Valid
        vals['ac_comp_normalized_load'] = 0
        vals['ac_comp_failed_on'] = 0

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
    """Periodic TX of 0x4E9 (Platform Configuration Data) at 1000ms."""
    vals = {sig.name: 0 for sig in msg_def.signals}
    vals['ac_compressor_type'] = AC_COMPRESSOR_TYPE

    while not shutdown_event.is_set():
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


def rx_monitor(bus, db):
    """RX thread: decode ECM responses from engine_general_status_2 and _3."""
    global ecm_ac_command, ecm_gradient_allowed, ac_high_side_pressure_kpa

    id_eng_status_2 = db.get_message_by_name('engine_general_status_2').frame_id
    id_eng_status_3 = db.get_message_by_name('engine_general_status_3').frame_id
    watch_ids = {id_eng_status_2, id_eng_status_3}

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
            if msg.arbitration_id == id_eng_status_2:
                ecm_ac_command = decoded.get('ac_comp_command', 0)
                ecm_gradient_allowed = decoded.get('ac_comp_norm_load_grad_allowed', 0.0)
                log.debug(
                    f"RX 0x3D1: ac_cmd={ecm_ac_command} "
                    f"grad={ecm_gradient_allowed:.1f}"
                )
            elif msg.arbitration_id == id_eng_status_3:
                ac_high_side_pressure_kpa = decoded.get(
                    'ac_refrigerant_high_side_press', 0.0
                )
                log.debug(
                    f"RX 0x3F9: hi_side_press={ac_high_side_pressure_kpa:.0f} kPa"
                )
        except Exception as e:
            log.warning(f"RX decode error (0x{msg.arbitration_id:03X}): {e}")


def main():
    global ac_mode_request

    dbc_path = os.path.normpath(DBC_PATH)
    log.info(f"Loading DBC: {dbc_path}")
    db = cantools.database.load_file(dbc_path)

    msg_platform_status = db.get_message_by_name('platform_general_status')
    msg_platform_config = db.get_message_by_name('platform_configuration_data')

    bus = None
    if not DEBUG_MODE:
        log.info(
            f"Opening CAN bus: {CAN_INTERFACE} / {CAN_CHANNEL} @ {CAN_BITRATE} bps"
        )
        bus = can.interface.Bus(channel=CAN_CHANNEL, interface=CAN_INTERFACE)
    else:
        log.info("DEBUG MODE: no CAN hardware required, encoding/timing only")

    t_status = threading.Thread(
        target=tx_platform_status, args=(bus, msg_platform_status), daemon=True
    )
    t_config = threading.Thread(
        target=tx_platform_config, args=(bus, msg_platform_config), daemon=True
    )
    t_rx = threading.Thread(
        target=rx_monitor, args=(bus, db), daemon=True
    )

    t_status.start()
    t_config.start()
    t_rx.start()

    log.info("=" * 60)
    log.info("AC Compressor Cycle Test")
    log.info(f"  ON time:  {COMPRESSOR_ON_TIME_S}s")
    log.info(f"  OFF time: {COMPRESSOR_OFF_TIME_S}s")
    log.info(f"  TX 0x1F1 every {PLATFORM_STATUS_PERIOD_S * 1e3:.0f}ms")
    log.info(f"  TX 0x4E9 every {PLATFORM_CONFIG_PERIOD_S * 1e3:.0f}ms")
    if DEBUG_MODE:
        log.info("  *** DEBUG MODE — no frames leave the box ***")
    log.info("  Ctrl+C to stop")
    log.info("=" * 60)

    cycle_count = 0

    try:
        while True:
            # === ENGAGE phase ===
            ac_mode_request = 2
            cycle_count += 1
            t_start = time.time()
            log.info(f"[Cycle {cycle_count}] REQUEST: ENGAGE")

            while time.time() - t_start < COMPRESSOR_ON_TIME_S:
                elapsed = time.time() - t_start
                state_str = "ON" if ecm_ac_command else "OFF"
                print(
                    f"  [{elapsed:5.1f}s] ECM AC Cmd: {state_str} | "
                    f"Grad: {ecm_gradient_allowed:.1f} | "
                    f"HiPress: {ac_high_side_pressure_kpa:.0f} kPa",
                    end='\r'
                )
                time.sleep(1.0)
            print()

            # === DISENGAGE phase ===
            ac_mode_request = 1  # Graceful disengage (not immediate)
            t_start = time.time()
            log.info(f"[Cycle {cycle_count}] REQUEST: DISENGAGE")

            while time.time() - t_start < COMPRESSOR_OFF_TIME_S:
                elapsed = time.time() - t_start
                state_str = "ON" if ecm_ac_command else "OFF"
                print(
                    f"  [{elapsed:5.1f}s] ECM AC Cmd: {state_str} | "
                    f"Grad: {ecm_gradient_allowed:.1f} | "
                    f"HiPress: {ac_high_side_pressure_kpa:.0f} kPa",
                    end='\r'
                )
                time.sleep(1.0)
            print()

    except KeyboardInterrupt:
        log.info("Shutting down — sending Disengage Immediately...")
        ac_mode_request = 0
        time.sleep(0.3)  # Let at least 3 status frames TX with disengage-immediate
    finally:
        shutdown_event.set()
        t_status.join(timeout=1.0)
        t_config.join(timeout=1.5)
        t_rx.join(timeout=1.0)
        if bus is not None:
            bus.shutdown()
        log.info("Bus closed. Done.")


if __name__ == '__main__':
    main()