"""
Clutch / DFCO State Monitor
===========================
Diagnostic for investigating why clutch-based fuel cutoff and rev-drop behavior
is not working on a standalone LFX / E92 ECM (no BCM, no TCM on the bus).

WHY THIS SCRIPT EXISTS (GMW8762 Sec 4.2.3.54, 4.2.3.55, 4.2.3.253; GMW8769 Sec 3.3.4)
-------------------------------------------------------------------------------------
The ECM has THREE independent clutch inputs, all hardwired, all read by the ECM
itself (there is no CAN input for clutch state on a manual application):

  1. Top of Travel Clutch Switch  - discrete, trips EARLY in pedal travel.
     GMW8769 Sec 3.5.2.1: "normally closed switch, sourced by Run/Crank, which
     OPENS when the clutch is depressed."  Note the inverted sense.
     GMW8769 Sec 3.3.4: powertrain uses this for cruise disable, IDLE SPEED
     CONTROL, and gear estimation.  <-- this is the one that matters for rev drop

  2. Clutch Start Switch          - discrete, trips LATE in pedal travel
     (bottom of travel). Starter enable only (GMW8767).

  3. Clutch Pedal Position sensor - analog 3 kOhm potentiometer on 5Vref /
     signal / return (GMW8769 Sec 3.5.2.2, GMW8777 Sec 3.5.2.2).
     Alternative to input 1; reports 0-100%.

The ECM re-broadcasts its interpretation of all three in frame $1F5
(PPEI Transmission General Status 2, 25 ms). That makes $1F5 the ground truth
for what the ECM actually BELIEVES about the clutch, as opposed to what the
sensor is doing. Frame $1F5 signal positions per GMW8762 pp.246-250.

An unwired Top of Travel input reads as an OPEN circuit, which the switch spec
defines as "clutch depressed" - and the ECM reports it as VALID, because an
open contact is a legal switch state and cannot be distinguished from a broken
wire. So a missing or inverted-polarity Top of Travel switch presents as
"clutch permanently depressed" with no fault.

WHAT TO LOOK FOR
----------------
- top_of_travel_clutch_sw_active should toggle False -> True as you begin to
  press the pedal, and back to False as you release. If it is stuck True (or
  moves backwards relative to the pedal), that input is unwired or inverted.
- clutch_pedal_actual_pos_validity must read Valid for the CPP analog path to
  be usable at all. Invalid means the ECM has a DTC on it and is ignoring it.
- trans_estimated_gear should fall to "Neutral Gear" when the clutch is
  depressed (GMW8762 Sec 4.2.3.257) - a cross-check that clutch state is
  reaching the transmission logic.
- eng_coast_fuel_cutoff_active (frame $3D1, GMW8762 Sec 4.2.3.86) is the ECM's
  own DFCO status bit. Correlate it against clutch state and pedal position.

The --tx-platform flag transmits $1F1 with System Power Mode = Run and Power
Mode Master Run/Crank Terminal Status = Active, plus $4E9, as
ac_compressor_cycle.py does. This exists to test
whether the ECM gates any of this behavior behind platform presence, the way
it gates the A/C subsystem. Note GMW8762 Sec 4.2.3.249.1 states System Power
Mode "shall not be used by powertrain to shut down the engine" - the Run/Crank
HARDWIRE is authoritative for run state - so this is a long shot, but it is a
free experiment.

Usage:
    pdm run python clutch_state_monitor.py                  # Live on SocketCAN
    pdm run python clutch_state_monitor.py --tx-platform    # Also impersonate the Platform
    pdm run python clutch_state_monitor.py --debug          # No hardware
"""

import can
import cantools
import csv
import logging
import os
import sys
import threading
import time

# === CONFIGURATION ===
CAN_INTERFACE = "socketcan"
CAN_CHANNEL = "can0"
CAN_BITRATE = 500_000  # Configured at OS level for SocketCAN (ip link set)

DBC_PATH = os.path.join(os.path.dirname(__file__), "../../../dbc/gmlan_v1.8_custom.dbc")
CSV_PATH = "clutch_state_monitor.csv"

DISPLAY_PERIOD_S = 200e-3  # Console refresh rate
CSV_PERIOD_S = 50e-3       # Row capture rate for post-drive review

# Impersonate the Platform/Gateway while monitoring (--tx-platform), so you can
# A/B test whether platform presence changes any clutch or DFCO behavior.
TX_PLATFORM_FRAMES = "--tx-platform" in sys.argv
PLATFORM_STATUS_PERIOD_S = 100e-3  # $1F1
PLATFORM_CONFIG_PERIOD_S = 1.0     # $4E9

SYSTEM_POWER_MODE_RUN = 2  # GMW8762 Sec 4.2.3.249
# GMW8762 Sec 4.2.3.209: Run/Crank terminal state at the Power Mode Master.
# "Diagnostic purposes only" for powertrain; set Active so the frame is
# self-consistent with System Power Mode = Run.
RUN_CRANK_ACTIVE = 1
AC_MODE_REQUEST_DISENGAGE_IMMEDIATELY = 0
AC_COMPRESSOR_TYPE_FIXED_DISPLACEMENT_CLUTCHED = 1

DEBUG_MODE = "--debug" in sys.argv

# Frames we decode, by DBC message name. Signal IDs are resolved from the DBC
# at startup so no arbitration IDs are hardcoded here.
MONITORED_MESSAGES = (
    'engine_general_status_1',      # $C9  - RPM, pedal, idle active
    'engine_general_status_2',      # $3D1 - DFCO active, throttle position
    'trans_general_status_2',       # $1F5 - all clutch signals, gear
    'PTEI_engine_general_status',   # $1A1 - idle target (may not be on the bus)
)

# Signals shown on the console, in display order: (dbc_signal, column label)
DISPLAY_SIGNALS = (
    ('eng_speed', 'RPM'),
    ('accelerator_actual_pos', 'Pedal%'),
    ('throttle_pos', 'Thr%'),
    ('eng_idle_active', 'IdleActv'),
    ('eng_base_trgt_idle_speed', 'IdleTgt'),
    ('eng_coast_fuel_cutoff_active', 'DFCO'),
    ('top_of_travel_clutch_sw_active', 'TopTravelClutch'),
    ('top_of_travel_clutch_sw_actv_vld', 'TTC_Vld'),
    ('clutch_pedal_actual_pos', 'CPP%'),
    ('clutch_pedal_actual_pos_validity', 'CPP_Vld'),
    ('clutch_start_switch_active', 'StartSw'),
    ('trans_estimated_gear', 'Gear'),
    ('trans_engaged_state', 'Engaged'),
)

# === LOGGING ===
LOG_FORMAT_FILE = "%(asctime)s - %(name)-40s - %(levelname)-8s - %(message)s"
LOG_FORMAT_CONSOLE = "%(levelname)-8s %(message)s"

log = logging.getLogger("clutch_state_monitor")
log.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter(LOG_FORMAT_CONSOLE))
log.addHandler(_console_handler)

_file_handler = logging.FileHandler("clutch_state_monitor.log")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(LOG_FORMAT_FILE))
log.addHandler(_file_handler)

# === SHARED STATE ===
signal_values = {}                  # dbc signal name -> most recent decoded value
signal_values_lock = threading.Lock()
frames_seen = set()                 # arbitration IDs actually observed
shutdown_event = threading.Event()


def build_frame_id_map(db):
    """Resolve monitored message names to arbitration IDs via the DBC."""
    id_map = {}
    for name in MONITORED_MESSAGES:
        try:
            id_map[db.get_message_by_name(name).frame_id] = name
        except KeyError:
            log.warning(f"DBC has no message named '{name}' - skipping")
    return id_map


def rx_monitor(bus, db, id_map):
    """Decode every monitored frame into signal_values."""
    while not shutdown_event.is_set():
        if DEBUG_MODE:
            shutdown_event.wait(timeout=DISPLAY_PERIOD_S)
            continue

        msg = bus.recv(timeout=DISPLAY_PERIOD_S)
        if msg is None or msg.arbitration_id not in id_map:
            continue

        frames_seen.add(msg.arbitration_id)
        try:
            decoded = db.decode_message(msg.arbitration_id, msg.data)
        except Exception as e:
            log.warning(f"RX decode error (0x{msg.arbitration_id:03X}): {e}")
            continue

        with signal_values_lock:
            signal_values.update(decoded)


def tx_platform_status(bus, msg_def):
    """Periodic TX of $1F1 with System Power Mode = Run, Run/Crank active, A/C not requested."""
    vals = {sig.name: 0 for sig in msg_def.signals}
    vals['system_power_mode'] = SYSTEM_POWER_MODE_RUN
    vals['pwr_mode_master_run_crank_stat'] = RUN_CRANK_ACTIVE
    vals['ac_comp_mode_request'] = AC_MODE_REQUEST_DISENGAGE_IMMEDIATELY
    data = msg_def.encode(vals)

    while not shutdown_event.is_set():
        if not DEBUG_MODE:
            try:
                bus.send(can.Message(arbitration_id=msg_def.frame_id,
                                     data=data, is_extended_id=False))
            except can.CanError as e:
                log.error(f"TX 0x{msg_def.frame_id:03X}: {e}")
        shutdown_event.wait(timeout=PLATFORM_STATUS_PERIOD_S)


def tx_platform_config(bus, msg_def):
    """Periodic TX of $4E9 declaring the compressor type."""
    vals = {sig.name: 0 for sig in msg_def.signals}
    vals['ac_compressor_type'] = AC_COMPRESSOR_TYPE_FIXED_DISPLACEMENT_CLUTCHED
    data = msg_def.encode(vals)

    while not shutdown_event.is_set():
        if not DEBUG_MODE:
            try:
                bus.send(can.Message(arbitration_id=msg_def.frame_id,
                                     data=data, is_extended_id=False))
            except can.CanError as e:
                log.error(f"TX 0x{msg_def.frame_id:03X}: {e}")
        shutdown_event.wait(timeout=PLATFORM_CONFIG_PERIOD_S)


def format_value(value):
    """Compact console rendering for enums, floats and ints."""
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.1f}"
    text = str(value)
    # DBC value tables give verbose names; keep the distinguishing part only.
    if text.startswith("True - "):
        return "DEPRESSED"
    if text.startswith("False - "):
        return "released"
    return text.replace(" Gear", "").replace("Transmission ", "")


def csv_writer_thread():
    """Capture every tracked signal to CSV for post-drive review."""
    columns = ['t_s'] + [name for name, _ in DISPLAY_SIGNALS]
    t_start = time.time()

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        while not shutdown_event.is_set():
            with signal_values_lock:
                snapshot = dict(signal_values)
            row = {'t_s': round(time.time() - t_start, 3)}
            for name, _ in DISPLAY_SIGNALS:
                value = snapshot.get(name)
                row[name] = '' if value is None else str(value)
            writer.writerow(row)
            fh.flush()
            shutdown_event.wait(timeout=CSV_PERIOD_S)


def display_loop():
    """Print a live one-line-per-sample table of the tracked signals."""
    widths = [max(len(label), 9) for _, label in DISPLAY_SIGNALS]
    header = "  ".join(
        label.ljust(w) for (_, label), w in zip(DISPLAY_SIGNALS, widths)
    )
    print()
    print(header)
    print("-" * len(header))

    while not shutdown_event.is_set():
        with signal_values_lock:
            snapshot = dict(signal_values)
        row = "  ".join(
            format_value(snapshot.get(name))[:w].ljust(w)
            for (name, _), w in zip(DISPLAY_SIGNALS, widths)
        )
        print(row)
        shutdown_event.wait(timeout=DISPLAY_PERIOD_S)


def main():
    dbc_path = os.path.normpath(DBC_PATH)
    log.info(f"Loading DBC: {dbc_path}")
    db = cantools.database.load_file(dbc_path)
    id_map = build_frame_id_map(db)

    bus = None
    if not DEBUG_MODE:
        log.info(f"Opening CAN bus: {CAN_INTERFACE} / {CAN_CHANNEL} @ {CAN_BITRATE} bps")
        bus = can.interface.Bus(channel=CAN_CHANNEL, interface=CAN_INTERFACE)
    else:
        log.info("DEBUG MODE: no CAN hardware required")

    threads = [threading.Thread(target=rx_monitor, args=(bus, db, id_map), daemon=True),
               threading.Thread(target=csv_writer_thread, daemon=True)]

    if TX_PLATFORM_FRAMES:
        log.info("Platform impersonation ENABLED (TX $1F1 + $4E9)")
        threads.append(threading.Thread(
            target=tx_platform_status,
            args=(bus, db.get_message_by_name('platform_general_status')),
            daemon=True))
        threads.append(threading.Thread(
            target=tx_platform_config,
            args=(bus, db.get_message_by_name('platform_configuration_data')),
            daemon=True))
    else:
        log.info("Platform impersonation disabled (listen only)")

    for t in threads:
        t.start()

    log.info("=" * 72)
    log.info("Clutch / DFCO State Monitor")
    log.info(f"  Monitoring frames: " +
             ", ".join(f"0x{fid:03X} ({name})" for fid, name in sorted(id_map.items())))
    log.info(f"  CSV output: {CSV_PATH}")
    log.info("  Press and release the clutch pedal slowly and watch")
    log.info("  TopTravelClutch, CPP% and Gear.  Ctrl+C to stop.")
    log.info("=" * 72)

    try:
        display_loop()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_event.set()
        for t in threads:
            t.join(timeout=1.5)
        if bus is not None:
            bus.shutdown()

        missing = set(id_map) - frames_seen
        if missing and not DEBUG_MODE:
            log.warning("Never saw these monitored frames on the bus: " +
                        ", ".join(f"0x{fid:03X} ({id_map[fid]})" for fid in sorted(missing)))
        log.info(f"Bus closed. CSV written to {CSV_PATH}. Done.")


if __name__ == '__main__':
    main()
