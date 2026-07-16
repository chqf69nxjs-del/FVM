# Stage 6 V-012C Controlled Opening-Ramp Observation Notes

## Status

`IMPLEMENTED; LOCAL WINDOWS EXECUTION AND VISUAL REVIEW PENDING`

Work branch:

```text
agent/stage6-v012c-opening-ramp
```

This increment follows the merged V-012B constant-opening driven-flow baseline
(PR #36, merge commit `8cb3deee003b141c0cb8e8d56ccc3eaa77c01d8f`).

## Purpose

V-012C verifies the existing `LinearRampOpening` and `InternalValveInterface`
software paths for a small, controlled single-phase opening operation.

The primary schedule is fixed by the V-012 specification:

```text
opening:       0.0 -> 1.0
initial hold:  0.005 s
ramp duration: 0.010 s
```

The pipe, thermodynamic state, Kv calibration, external fixed-pressure numerical
boundaries, and baseline mesh/CFL remain the same as V-012B.

## Expected qualitative response

For initial `p_left > p_right`:

- opening is monotonic non-decreasing;
- through-flow begins at zero and becomes positive;
- upstream probes see a left-going decompression tendency;
- downstream probes see a right-going compression tendency;
- raw Kv, applied, and flux-derived flow remain consistent while the Mach cap is
  inactive;
- two-sided mass, energy, and vapor-mass flux mismatches remain at roundoff scale;
- the momentum-flux difference remains equal to the local valve pressure
  difference;
- the accepted window ends before a valve-generated wave reaches an external
  fixed-pressure boundary.

This prescribed schedule is not an actuator-dynamics, hysteresis, ESD, flashing,
cavitation, choked-flow, or two-phase model.

## Artifacts

The runner writes:

```text
*_config.json
*_metrics.json
*_valve_schedule.csv
*_valve_history.csv
*_interface_flux_history.csv
*_probe_history.csv
*_probe_characteristic_summary.csv
*_boundary_history.csv
*_final_profile.csv
*_field_history.npz
*_observation_report.md
```

The human-review plotter writes nine PNGs:

```text
*_valve_command_and_flow.png
*_probe_pressure_velocity.png
*_probe_characteristics.png
*_pressure_xt_map.png
*_velocity_xt_map.png
*_interface_flux_consistency.png
*_budget_and_health.png
*_profile_snapshots.png
*_valve_dp_q_path.png
```

The x-t figures include theoretical start- and end-of-ramp acoustic fronts. The
profile figure shows the initial state, ramp start, ramp midpoint, ramp end, and
final observation. Plotting reads saved artifacts only and does not rerun or
change the numerical calculation.

## Implementation constraints retained

- no governing-equation change;
- no Kv-law change;
- no Mach-cap change;
- no conserved-energy treatment change;
- the hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`;
- fixed-pressure ends remain zero-impedance numerical idealizations;
- no regression band is introduced before observation evidence exists;
- `property_backend_design_status = not_approved_for_design_use`.

## Pending evidence

Before this increment can be reviewed for merge:

1. run focused pure/installed-CoolProp tests on Windows;
2. generate the baseline artifacts and all nine PNGs;
3. inspect wave direction, acoustic timing, pressure/velocity fields, interface
   consistency, and `delta-p` / Q path;
4. run the full repository suite;
5. record exact metrics and any limitations in this document and the PR.

Any non-finite state, phase appearance, schedule mismatch, untracked Mach
clipping, finite-opening flux mismatch, boundary contamination, or required
physics change is a stop condition.
