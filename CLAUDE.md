# pyCANdash - Project Notes

CAN dash / control tooling for a GM LFX (3.6L V6, E39 ECM, OS 12648907) swapped into a Miata.

## Vehicle / Bus Context

- **ECM**: E39, OS 12648907, LFX. Standalone swap - **there is no BCM, no Gateway, and no TCM
  on the bus.** Several ECM subsystems are gated behind CAN frames that a factory
  Platform module would normally transmit, so they must be impersonated.
- **Transmission**: manual.
- **Bus**: HS-GMLAN, 500 kbps, 11-bit IDs. SocketCAN `can0` on a Raspberry Pi
  with an SPI CAN transceiver (Linux brings the interface up).
- **Other nodes**: Spartan 3 v2 wideband.
- **A/C high-side pressure**: no real sensor. Faked with a resistor divider on the
  ECM analog input.
- **Reference standards**: `Z:\My Drive\fastboi\GM_standards\`. GMW8762 is the
  signal/framing bible. Cached page-numbered text extracts live in
  `GM_standards\.claude\pdftext\` - grep those rather than re-parsing the PDFs.

## Frame IDs of Interest

| Frame | DBC message | TX by | Notes |
|-------|-------------|-------|-------|
| $1F1 / 497 | `platform_general_status` | Gateway (we impersonate) | A/C mode request, System Power Mode |
| $4E9 / 1257 | `platform_configuration_data` | Gateway (we impersonate) | A/C compressor type |
| $1F5 / 501 | `trans_general_status_2` | ECM | All clutch signals, estimated gear, engaged state |
| $3D1 / 977 | `engine_general_status_2` | ECM | A/C command, DFCO active, throttle position |
| $3F9 / 1017 | `engine_general_status_3` | ECM | A/C high-side pressure, oil life |
| $C9 / 201 | `engine_general_status_1` | ECM | RPM, pedal position, idle active |

## DBC History

`dbc/` holds versioned custom DBCs. Always copy forward to a new version rather
than editing in place.

**Ownership:** pyCANdash owns everything in its `dbc/`; the dash uses
`gmlan_v1.9_custom.dbc`. `gmlan_dpid_logger` keeps its own copies in its `dbc/`
(v1.9, `e39_12648907_broadcast.dbc`, and v1.10 = v1.9 + the functional request IDs
$101/$7DF). The two projects are not kept in sync. Both are copy-forward: never edit
one project's DBC from the other.

- **v1.6** - baseline.
- **v1.7** - added `platform_general_status` ($1F1) and
  `platform_configuration_data` ($4E9) so the Pi can impersonate the Gateway.
  Fixed scaling on `eng_oil_life_remaining` (factor 100/255) and
  `ac_refrigerant_high_side_press` (factor 14, range 0-3570 kPa).
- **v1.8** - added the full clutch signal set to `trans_general_status_2` ($1F5)
  per GMW8762 pp.246-250: `top_of_travel_clutch_sw_active` (+validity),
  `clutch_start_switch_active` (+validity), `clutch_pedal_actual_pos`
  (+validity), `trans_engaged_state` (+validity),
  `trans_estimated_gear_validity`, `trans_torque_conv_clutch_cmd_mode`.
  Added VAL_ tables for all of them.
- **v1.9** - added diagnostic channels for the DPID logger: `ecm_diag_request`
  ($7E0), `ecm_diag_response` ($7E8), `ecm_uudt_periodic` ($5E8). Populated
  `BU_` node list. The logger has since moved to `gmlan_dpid_logger`. Its v1.10
  (adds $101/$7DF) lives in that project only.

## Scripts (`src/pyCANdash/examples/`)

- **`ac_compressor_cycle.py`** - WORKING on hardware. Impersonates the Platform
  to make the ECM engage the A/C compressor; cycles 15 s on / 15 s off.
  Requires $1F1 (`ac_comp_mode_request` = Engage) and $4E9
  (`ac_compressor_type` = Fixed Displacement Clutched).
- **`clutch_state_monitor.py`** - diagnostic for the clutch fuel cutoff / rev
  hang investigation. Decodes $1F5 clutch signals alongside RPM, pedal,
  throttle and DFCO state; writes CSV for post-drive review. `--tx-platform`
  also impersonates the Gateway ($1F1 Run + Run/Crank active, $4E9) to A/B test
  whether platform presence matters. Note that $4E9 then declares no cruise
  control and no ABS/TC, and A/C is forced off.
- The ECM DPID/RAM logger (`dpid_logger.py`) moved out in Nov 2026 to the sibling project
  `C:\git-personal\gmlan-dpid-logger\` (Pi: `/git/gmlan-dpid-logger`; folder with a hyphen, Python package `gmlan_dpid_logger`) (configs, PID library, generators and tests too).
  See its `CLAUDE.md`. pyCANdash only controls it (next section).

## DPID logger control (`dpid_logger_control.py`, `http_routes.py`)

The HTTP server (`httpServer`, port 8000) controls the separate `gmlan_dpid_logger` project at
`http://<pi>:8000/logger`. Contract: `gmlan-dpid-logger/docs/interfaces.md`. Config: the
`dpidLogger` block in `config_files/config_default.py` (`enable` False by default). How to use
it in the car: "In the car" in `gmlan-dpid-logger/CLAUDE.md`.
- `DpidLoggerController` (no Qt) runs the logger as a **subprocess** in its own venv
  (`python -I -m gmlan_dpid_logger --config NAME --out-dir PATH --run-name STEM [--debug]`,
  cwd = PATH, stdout (the 5 Hz table) to DEVNULL, stderr to `<STEM>_stderr.txt`). Never import
  the logger into the Qt process. One run at a time; STEM = local start time. Stop = SIGTERM to
  its session (Linux) / CTRL_BREAK_EVENT to its process group (Windows), killed after
  `STOP_TIMEOUT_S`. Never restarts a run (autoStart starts once at server start). Status trusts
  the process exit code over `<STEM>_status.json`. pyCANdash shutdown calls `controller.shutdown()`
  (clean stop; blocks the GUI thread about 1 s, at most ~30 s if the logger hangs).
- Linux: a PATH on the root fs (`/`) is refused unless `allowRootFs` (Pi: stick not mounted, the
  run would land on the RAM overlay).
- Orphan (Linux): at start the controller looks in `/proc` for a logger with exactly its command
  line and PATH (left by a pyCANdash that died hard), adopts it (page banner, Stop = SIGTERM after
  re-checking the cmdline, start refused while it runs). Not on Windows (no `/proc`).
- Windows: under `pythonw` (no console) CTRL_BREAK_EVENT can't be delivered, so Stop ends in the
  kill after `STOP_TIMEOUT_S` (no stopSending). Run pyCANdash with `python` on a PC.
- `http_routes.DataDirRequestHandler`: `/logger` page, `/logger/status.json`, POST-only
  `/logger/start` (form field `config`, one of `config/dpid_config*.py`) and `/logger/stop`
  (both 303). Every other path is the old data dir file serving. The TCPServer is
  single-threaded: no route may block.
- `debugArgs` (e.g. `['--debug-foreign-tester', '6']`) is passed only when `debug` is True.
- Tests: `pdm run python -I -m pytest` (dummy logger in a throwaway venv, plus the real logger in
  `--debug` if `C:/git-personal/gmlan-dpid-logger/.venv` exists, env `GMLAN_DPID_LOGGER_DIR`
  overrides). Full app headless on a PC: `pdm run python -I tests/e2e/run_app_pc_debug.py
  --data-dir C:/tmp/x/data --quit-after 120` (config_default + `tests/e2e/pc_debug_overrides.py`,
  port 8765, virtual CAN).

## E39 PID Library and Broadcast DBC

- The PID library (`e39_12648907_pid_library.py`) and its generators
  (`build_pid_library.py`, `build_broadcast_dbc.py`) now live in `gmlan_dpid_logger`
  (`config/`, `tools/`).
- `dbc/e39_12648907_broadcast.dbc` (generated, HPT signals prefixed `e39_`) stays here
  too. Use it on its own; don't merge it with gmlan_v*.dbc (same IDs).
- No unencrypted OS/flash image exists locally. HPT `.hpt` tunes are
  AES-encrypted. A plain `.bin` would allow targeted analysis of the CFCO
  code; the CFCO enable cals are at 0x7970C/0x7974E/0x79750.

## Raspberry Pi

- `victorzaccardo@raspberrypi.local` (DHCP, has been 192.168.0.181). Powered by
  the key. Wi-Fi link can be weak/laggy.
- Root is **overlayroot**: everything written outside `/mnt/usb_drive` lives in
  RAM and is lost at key-off, including `~/.ssh/authorized_keys` and `/tmp`.
  Do not change the overlay.
- pyCANdash autostarts and logs one `.blf` per key cycle to `/mnt/usb_drive`
  (persistent USB).
- System python has no python-can; use `~/git/pyCANdash/.venv`, or stdlib
  `socket.AF_CAN` for quick listen-only checks.

## Established Conventions

- Never hardcode arbitration IDs in scripts. Resolve them from the DBC by
  message name (`db.get_message_by_name(...).frame_id`).
- All tunable values (bitrate, channel, periods, thresholds) as named constants
  at the top of the script.
- Every script gets a `--debug` mode that runs without CAN hardware.
- Dual logging: console plus logfile using the 40-char name format.
- Cite the governing GMW standard and section number in comments for anything
  protocol-related.

## Findings Log

- **The ECM gates subsystems behind platform communication.** It does not read
  the A/C high-side pressure analog input at all until it starts receiving $1F1 /
  $4E9. Expect this pattern for other subsystems. (No such gate exists for CPP
  validity or CFCO.)
- **`ac_comp_normalized_load` should stay 0** for a fixed displacement clutched
  compressor. It only matters for electronically controlled variable
  displacement (ECVD).
- **System Power Mode is a red herring for engine run state.** GMW8762
  Sec 4.2.3.249.1: a Run -> Off/Accessory transition "shall not be used by
  powertrain to shut down the engine. Powertrain shall use the Run/Crank
  hardwire input for this purpose."
- **The ECM has three separate hardwired clutch inputs**, no CAN input on a
  manual: Top of Travel Clutch switch (early travel), Clutch Start Switch
  (bottom of travel, starter enable only), and the analog CPP potentiometer.
  GMW8769 Sec 3.3.4: TOT is used for cruise disable, idle speed control and gear
  estimation.
- **TOT switch has inverted sense** (GMW8769 Sec 3.5.2.1: normally closed,
  opens when depressed), so an unwired input reads "depressed, Valid".
- **Clutch / rev hang: full detail, addresses and history are in
  `GM_standards/clutch_investigation.md`.** Summary (2026-11-04):
  - **CPP Valid is fixed.** The ECM only trusts CPP if P0807/P0808 are "MIL on
    First/Second Error" and P0806 is not "No MIL Light" (DTC type = low 2 bits
    of the attribute byte). All three set to MIL on Second Error. CPP-valid flag
    RAM 0x4000674D; $1F5 bit 55 is its inverse. The sensor must also stay off
    both rails (pedal-up stop fitted; floor stop still needed).
  - **CFCO is a ≤0.4 s shift-flare suppressor, not a rev-hang fix.** Enable RPM
    set to 4500 so heel-toe blips aren't cut. Sets the $3D1 coast fuel cutoff
    bit.
  - **Rev hang = minimum-run torque in idle-follower mode:** airmass pinned at
    min airmass (0x489F8, ~80 mg/cyl) and spark at min spark (0x78B2A,
    22-30° at 80 mg), with the immediate request floored at that torque.
    Neither table is in VCM Editor (HPT definition request pending). Validated:
    hang ≈ −11.5 N·m, MAP ≈ 23 kPa, model within ±3 N·m.
  - **Exposed lever: Exhaust Cam Angle Minimum during Spark Reduction**
    (0x6C55C). 0° → 15° (≤100 mg rows, 1400-4400 rpm) cut the worst hangs in 5
    of 7 rpm bands on one drive; 20° is next.
  - Tried, no effect: Idle Torque Limit offset (cap never binds), follower
    overspeed spark tables (floor erases them), Neutral source = Clutch (worse).
  - RAM logger config for the hang: `gmlan-dpid-logger/config/dpid_config_follower.py`.
- **The wideband is in the Bank 1 pre-cat (B1S1) bung**, so P0030/P0131/P0135
  are expected and the DFCO re-entry lean tail (0.3-2 s after fuel resumes,
  MAP 23-50 kPa, 900-2000 rpm) is real mixture.
- **VCM Scanner raw CPP = PID $201B**, 1 byte, N x 100/255. Found by sniffing its
  $2C request. HP Tuners' `Scanner.HPTdb` is encrypted, so sniffing is the way
  to get PIDs.

## Missing Standards (would help; not in GM_standards yet)

- GMW8766 (Engine Power Management) is now in GM_standards, with a text extract
  in `.claude/pdftext/`. It only covers the platform interface; DFCO, idle and
  throttle follower are internal ECM calibration.
- **GMW8777 - Transmission** - CPP sensor electrical spec (Sec 3.5.2.2) and
  clutch switch thresholds.
- GMW8767 (Starter System), GMW8773 (Brakes and Traction Control).
