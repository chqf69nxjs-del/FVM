# Stage 6 V-012C Controlled Opening-Ramp Observation Notes

## Status

`OBSERVED; READY FOR REVIEW`

Work branch:

```text
agent/stage6-v012c-opening-ramp
```

Pull request:

```text
#37 Add V-012C controlled internal-valve opening ramp
```

This increment follows the merged V-012B constant-opening driven-flow baseline
(PR #36, merge commit `8cb3deee003b141c0cb8e8d56ccc3eaa77c01d8f`).

## Purpose and schedule

V-012C verifies the existing `LinearRampOpening` and `InternalValveInterface`
software paths for a small, controlled single-phase opening operation.

```text
opening:       0.0 -> 1.0
initial hold:  0.005 s
ramp duration: 0.010 s
ramp end:      0.015 s
```

The pipe, thermodynamic state, Kv calibration, external fixed-pressure numerical
boundaries, and baseline mesh/CFL remain the same as V-012B.

This prescribed schedule is not an actuator-dynamics, hysteresis, ESD, flashing,
cavitation, choked-flow, or two-phase model.

## Windows execution evidence

Focused tests:

```text
6 passed in 4.27s
```

Full repository suite on the final numerical head:

```text
245 passed in 72.53s
```

No output followed `git status --short`, so the supplied working tree was clean.

One-command artifact execution completed with:

```text
overall_observation_execution_pass = true
plot_count = 9
CoolProp version = 8.0.0
```

The plotter reads saved artifacts only:

```text
solver_rerun = false
numerical_results_changed = false
```

All three existing installed-CoolProp GitHub workflows completed successfully on
the observed branch head:

- CoolProp Wave Regression
- CoolProp Boundary Reflection Regression
- CoolProp Controlled Pressure Ramp Regression

## Configuration and timing

- pipe length: `100 m`
- diameter: `0.30 m`
- valve location: `x/L = 0.50`
- left/right requested pressure: `8,000,500 / 7,999,500 Pa`
- initial temperature: `280 K`
- initial pressure difference: `1,000 Pa`
- baseline mesh: `n = 100`, `dx = 1 m`
- baseline CFL: `0.5`
- target time: `0.0697143731 s`
- first valve-generated boundary arrival: `0.0946929534 s`
- safe-window end: `0.0812390104 s`

The accepted observation ends before the first valve-generated wave reaches an
external fixed-pressure boundary.

## Key numerical results

### Schedule and flow

- opening monotonic non-decreasing: `true`
- maximum opening error: `0`
- pre-hold maximum opening: `0`
- post-ramp minimum opening: `1`
- zero-opening hydraulic-separation fraction: `1.0`
- finite-opening hydraulic-separation count: `0`
- initial applied Q: `0 m3/s`
- final applied Q: `4.3125747224746e-05 m3/s`
- maximum applied Q: `4.312685061599612e-05 m3/s`
- maximum raw/applied relative difference: `0`
- maximum applied/flux relative difference: `1.9174770433785486e-16`
- flow-sign consistency: `78 / 78 = 1.0`
- Mach-cap activation count: `0`
- maximum applied face Mach: `1.0944969604068111e-06`

### Interface and budgets

- mass-flux mismatch: `0`
- energy-flux mismatch: `0`
- vapor-mass-flux mismatch: `0`
- momentum-difference residual: `0`
- maximum flux-Q minus applied-Q: `6.776263578034403e-21 m3/s`
- mass budget relative residual: `-1.394135662426362e-16`
- energy budget relative residual: `0`
- vapor-mass budget relative residual: `0`
- required budget fields missing: none

### State and wave direction

- remained single phase: `true`
- maximum vapor mass fraction: `0`
- maximum void fraction: `0`
- pressure, temperature, density, and sound speed remain positive
- upstream decompression observed: `true`
- downstream compression observed: `true`
- primary characteristic-direction pass: `true`
- maximum opposite-direction characteristic ratio: `1.6229101813567113e-06`
- maximum pressure perturbation: `313.8912506327033 Pa`
- maximum velocity: `6.101059874685836e-04 m/s`

## Human review of the nine figures

### Valve command and flow

Requested and actual opening coincide. The valve stays closed during the initial
hold, ramps monotonically to full opening, and remains at `1.0`. Through-flow
starts from zero and rises to approximately `4.31e-05 m3/s`. Raw Kv, applied,
and flux-derived Q remain visually coincident. The Mach cap remains inactive.

The valve pressure difference falls from `1,000 Pa` to roughly `0.37 kPa` as the
opening-generated acoustic response develops. The final flow and remaining
pressure difference are mutually consistent with the implemented Kv relation.

### Probe pressure, velocity, and characteristics

The two upstream probes develop negative pressure perturbations while the two
downstream probes develop positive pressure perturbations. All observed
velocities are positive, consistent with left-to-right flow.

The nearer probes respond first and the farther probes later. Upstream `A_minus`
is dominant and negative, while downstream `A_plus` is dominant and positive.
The opposite-direction components remain visually negligible, consistent with
the recorded `1.623e-06` maximum leakage ratio.

The acoustic-scale relation is internally consistent: the observed `rho*c*u` is
approximately the recorded `314 Pa` pressure perturbation.

### x-t maps and field profiles

The pressure x-t map shows a left-going decompression region and a right-going
compression region launched at the valve. The velocity map shows positive flow
behind both propagating fronts. The numerical fronts follow the theoretical
ramp-start and ramp-end acoustic lines without an early boundary-return pattern.

Representative field profiles are smooth at the resolved scale. Pressure,
velocity, density, and temperature changes have the expected signs. No
checkerboard pattern, isolated one-cell spike away from the valve, growing
oscillation, or premature end-boundary reflection was observed.

The discontinuity retained at the valve is expected: the remaining local pressure
difference supplies the Kv through-flow and the documented valve-body momentum
reaction.

### Interface consistency, budgets, and delta-p/Q path

Mass, energy, and vapor-mass two-sided mismatches remain on the zero line.
Momentum-flux difference follows the local valve pressure difference exactly.
The flux-derived-Q minus applied-Q signal remains at floating-point roundoff.

The delta-p/Q path is smooth. It contains a small transient loop after the ramp
because pressure difference and pipe acoustic state continue adjusting after the
prescribed opening has reached `1.0`; no unstable or growing loop was observed.

A presentation-only limitation is retained and accepted for this observation:
the point labelled `ramp start` is the nearest stored numerical sample, so its
legend shows opening `0.038` rather than the exact prescribed value `0.0` at
`t = 0.005 s`. The prescribed schedule, solver state, metrics, and acceptance
result are unaffected. A later plot-only cleanup may make the label more explicit.

## Artifacts

Numerical artifacts:

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

Human-review figures:

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

## Constraints retained

- no governing-equation change;
- no Kv-law change;
- no Mach-cap change;
- no fixed-pressure-boundary meaning change;
- no conserved-energy treatment change;
- hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`;
- fixed-pressure ends remain zero-impedance numerical idealizations;
- no regression band is introduced before mesh/CFL observations;
- `property_backend_design_status = not_approved_for_design_use`.

## Review decision

No solver-physics, conservation, sign, timing, phase-state, reproducibility, or
data-integrity blocker was found. The V-012C increment is ready for PR review.
V-012 overall remains `IN_PROGRESS`; the next case is the controlled closing ramp
(V-012D), followed by mesh/CFL observation and formalization.
