# Tip-in lean spike: investigation plan

Status: **planned, not started.** Started 2026-11-03.

## Symptom
- The wideband (Spartan 3, CAN 0x400) shows a lean spike **when the throttle opens**: blips at idle and light tip-ins at low or no load while driving.
- The engine hesitates on a blip, so the lean is real and not a wideband artifact. Possible knock (not yet confirmed).
- It has always done this.
- The engine (LFX 3.6, E39 ECM, OS 12648907) is 100% stock. The intake tract, exhaust and radiator are custom for the Miata swap.
- The throttle body is the **stock** unit, modified by welding an elbow directly to its inlet.
- Open question: MAF sensor and housing (stock?), and its position relative to the bends and the elbow.

## What the calibration says (decoded from the v15 flash, hpt_re `tools/decode_cal.py`)
- **No transient-fuel tables.** The engine is direct-injected, so there is no wall-wetting or accel enrichment. Tip-in fueling depends only on (a) the airmass estimate and (b) rail pressure.
- **Airmass during transients** comes from the Dynamic Airflow blend of MAF, speed density and throttle-predictive terms, zoned by RPM × pressure ratio. Idle is RPM zone 0 (< 1000 rpm), where the TPS predictive gains are large (730–807).
- **Desired rail pressure** is a flat 4 MPa in the 800 rpm column at every load. A blip makes it step to 8–11 MPa.

## Hypotheses (most likely first)
1. **Airmass prediction lags real cylinder air.** Slight favourite, not certain. The throttle blade is stock, but the inlet isn't, and the Dynamic Airflow terms were calibrated for the stock intake:
   - The elbow welded right at the throttle inlet disturbs the incoming flow, which changes the throttle's effective area. Probably modest.
   - On tip-in the throttle first draws down the air already in the tube, so the MAF lags. A longer or larger tube than stock makes this worse, and upstream bends distort the MAF reading.
   - Steady state hides all of this because the MAF and trims correct it; transients don't.
2. **Rail pressure undershoots** desired rail pressure during the step up from 4 MPa.
3. *(Ruled out by the symptom timing)*: DFCO on throttle close making the wideband read pure air.

## Logging: pyCANdash only, one file, no alignment needed
Use the DPID logger, now its own project `C:\git-personal\gmlan-dpid-logger\` (Pi: `/git/gmlan-dpid-logger`) (GMW3110 `$2C`/`$AA`, fast rate = 25 ms). In the car, pyCANdash starts it from its "DPID Logger" tab. The Spartan broadcasts at 50 Hz (measured from the 2026-11-02 log).

**VCM Scanner must NOT be connected at the same time.** Two tools defining DPIDs on the same ECM will conflict.

### Channels (15 DIDs, within the 10-DPID / 400 frames/s budget)
| Purpose | Library field (DID) |
|---|---|
| Airmass (#1) | `dynamic_airflow` (0x12E0), `mass_airflow_sensor` (0x12DA), `manifold_absolute_pressure_hi_res` (0x208A), `volumetric_efficiency_airflow` (0x11AC) |
| Rail pressure (#2) | `desired_fuel_pressure` (0x308A), `fuel_pressure_sensor` (0x309C), `injector_pulse_width_avg_bank_1` (0x12C3), `injector_pulse_width_avg_bank_2` (0x12C4) |
| Throttle | `accelerator_pedal_position`, actual TPS DID, `throttle_desired_position` (0x131E), `throttle_desired_area` (0xFD04) |
| Context | `dfco_active` (DID 0x1131), `total_knock_retard` (0x12D9) |
| Broadcast (DBC) | `lambda`, `spartan_stat`, `commanded_air_fuel_ratio`, `eng_speed` |

Not available without HPT: `cylinder_airmass_mem` and per-cylinder knock retard. These are HPT-style `$23` RAM reads and are untested.

### Decisions still open
- [x] Config location: option (b) exists now. The logger has `--config`, and every `gmlan-dpid-logger/config/dpid_config*.py` shows up in the config dropdown of the pyCANdash "DPID Logger" tab.
- [ ] Write this selection as `gmlan-dpid-logger/config/dpid_config_tip_in.py`. Leave `dpid_config.py` (the clutch selection) and `dpid_config_follower.py` as they are.

### Test procedure
1. Fully warm engine, closed loop.
2. About 10 idle blips, from gentle to sharp.
3. A few light tip-ins while driving in 2nd and 3rd.
4. Note roughly where the hesitation happens.

## How to read the log
- `fuel_pressure_sensor` lags `desired_fuel_pressure` by MPa during the blip → **#2: fuel system** (desired-pressure shaping at idle, HPFP).
- Rail pressure tracks, but lambda goes lean while commanded AFR stays flat, and `dynamic_airflow` rises behind `mass_airflow_sensor` / MAP → **#1: airmass estimate** (Dynamic Airflow gains, throttle flow model).
- The fix is iterative: change in HPT, flash, re-log.

## Related finding: no torque limit at WOT (2026-11-03)
- Checked whether any torque limits cut performance. None do.
- Driver Demand tops out at 275, but logged engine torque reaches ~355 N·m. At ≥ 95% pedal, MAP is within 1–3 kPa of baro at every RPM (2026-11-02 log).
- The throttle stays at ~65–75% below 4500 rpm. That is normal GM torque-based behaviour: the ECM opens the throttle only as far as needed, and with MAP already near baro, opening it further wouldn't add air.
