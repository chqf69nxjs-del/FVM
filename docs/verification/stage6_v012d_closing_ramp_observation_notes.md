# Stage 6 V-012D Controlled Closing-Ramp Observation Notes

## Status

`OBSERVED; READY FOR REVIEW`

Work branch:

```text
agent/stage6-v012d-closing-ramp
```

Pull request:

```text
#38 Add V-012D controlled internal-valve closing ramp
```

This increment follows the merged V-012C opening ramp (PR #37, merge commit
`f933479658d61b30d2214a2ceb9cd64d0efa671a`).

## Purpose and schedule

V-012D verifies the existing `LinearRampOpening` and `InternalValveInterface`
software paths for a complete single-phase closing operation.

```text
opening:           1.0 -> 0.0
initial hold:      0.005 s
ramp duration:     0.010 s
ramp end:          0.015 s
post-closure hold: 0.005 s minimum
```

The complete-closure state is part of V-012D rather than a separate V-012E. At
zero opening, the existing interface changes to two independent reflective-wall
fluxes. V-012D therefore separates finite-opening checks from post-closure checks.

This prescribed schedule is not an actuator-dynamics, hysteresis, ESD-event,
flashing, cavitation, choked-flow, or two-phase model.

## GitHub Actions execution evidence

Focused tests:

```text
7 passed in 7.53s
```

Full repository suite:

```text
252 passed in 106.74s
```

The verification run also completed:

```text
static checks = success
baseline artifact generation = success
baseline metrics gate = success
plot count = 9
overall_observation_execution_pass = true
CoolProp version = 8.0.0
```

The generated diagnostics artifact was associated with observed head
`9683f9751fc0875c1d96de21093fe33e262a9fe4` and recorded digest:

```text
sha256:16db7283d620565e54c8918a48d7b38753c127a78a2e677f8a20522ac53336ef
```

All three existing installed-CoolProp workflows also completed successfully on
the observed head:

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
- target time: `0.06971437311556053 s`
- first initial-state boundary arrival: `0.08969295335583746 s`

The accepted observation window includes the configured post-closure hold and
ends before the first initial full-open disturbance reaches an external
fixed-pressure boundary.

## Key numerical results

### Schedule and finite-opening flow

- opening monotonic non-increasing: `true`
- maximum opening error: `0`
- initial applied Q: `7.068583469428279e-05 m3/s`
- maximum applied Q: `7.068583469428279e-05 m3/s`
- final applied Q: `0 m3/s`
- finite-opening raw/applied relative difference: `0`
- finite-opening applied/flux relative difference: `1.8702192872045635e-16`
- flow-sign consistency: `1.0`
- finite-opening hydraulic-separation count: `0`
- Mach-cap activation count: `0`
- maximum applied face Mach: `1.7939138723497895e-06`

The relative flow-consistency comparison is intentionally scoped to finite-opening
rows. At complete closure, the reference quantities are numerical zero and a
relative ratio is ill-conditioned. Closure is protected by the absolute gates
listed below; no tolerance was relaxed.

### Complete closure

- post-closure sample count: `61`
- post-closure hydraulic-separation fraction: `1.0`
- post-closure no-flow-direction fraction: `1.0`
- maximum post-closure raw target Q: `0 m3/s`
- maximum post-closure applied Q: `0 m3/s`
- maximum post-closure flux-derived Q: `4.151910405935732e-24 m3/s`
- maximum post-closure mass through-flux: `5.421010862427522e-20 kg/m2/s`
- maximum post-closure energy through-flux: `0 W/m2`
- maximum post-closure vapor-mass through-flux: `0 kg/m2/s`
- mass-flux roundoff tolerance: `2.842170943040401e-14 kg/m2/s`
- energy-flux roundoff tolerance: `5.570537671148064e-09 W/m2`
- vapor-mass-flux roundoff tolerance: `2.842170943040401e-14 kg/m2/s`
- finite-opening momentum relation applied to closed rows: `false`

The closed interface retained side-specific momentum reactions. The two sides
remained hydraulically separated and were not required to equalize in pressure.

### Interface, budgets, and state

- maximum mass-flux mismatch: `5.421010862427522e-20 kg/m2/s`
- maximum energy-flux mismatch: `0 W/m2`
- maximum vapor-mass-flux mismatch: `0 kg/m2/s`
- maximum finite-opening momentum-difference residual: within roundoff
- maximum flux-Q minus applied-Q: `6.776263578034403e-21 m3/s`
- mass budget relative residual: `0`
- energy budget relative residual: `0`
- vapor-mass budget relative residual: `0`
- required budget fields missing: none
- remained single phase: `true`
- maximum vapor mass fraction: `0`
- maximum void fraction: `0`
- pressure, temperature, density, and sound speed remained positive

### Wave direction

- upstream compression observed: `true`
- downstream decompression observed: `true`
- primary characteristic-direction pass: `true`
- maximum opposite-direction characteristic ratio: `1.2305912228546978e-06`

The characteristic increment at each probe is rebased to its pre-arrival state.
This separates the closure-generated wave from the initial full-open startup wave.

## Human review of the nine figures

### Valve command and flow

Requested and actual opening coincide. The valve remains fully open during the
initial hold, closes monotonically, reaches zero, and stays closed. Raw Kv,
applied, and flux-derived Q coincide during finite opening and decay smoothly to
zero. The Mach cap remains inactive.

### Probe pressure, velocity, and characteristics

The closure-generated response is an upstream left-going compression and a
downstream right-going decompression. Near probes respond before far probes. The
pre-arrival-rebased dominant characteristics have the expected signs, while the
opposite-direction component remains approximately `1.23e-06` of the dominant
component.

### x-t maps and field profiles

The pressure and velocity fronts follow the expected acoustic lines. The accepted
window ends before external-boundary contamination. Representative profiles are
smooth at the resolved scale. No growing oscillation, checkerboard pattern,
isolated non-valve spike, or premature boundary-return signature was observed.

### Interface consistency, budgets, and delta-p/Q path

Finite-opening mass, energy, and vapor-mass two-sided consistency remains at
roundoff. After complete closure, through quantities collapse to numerical zero
while independent left/right wall momentum reactions remain. Budget ratios stay
below their observation limits.

The delta-p/Q event marker uses the nearest stored sample, so its displayed opening
can differ slightly from the exact event value. This is presentation-only and does
not change the schedule, solver state, metrics, or observation result.

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

The plotter reads saved artifacts only and does not rerun or alter the solver
result.

## Constraints retained

- software / numerical verification only;
- physical Validation is not performed;
- design-use acceptance is not performed;
- no governing-equation, Kv-law, Mach-cap, or fixed-pressure-boundary change;
- Kv remains a single-phase liquid relation;
- complete closure uses the existing independent reflective-wall branch;
- hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`;
- fixed-pressure ends remain zero-impedance numerical idealizations;
- no regression band is introduced before mesh/CFL observation;
- the baseline mesh is not a design mesh or exact solution;
- `property_backend_design_status = not_approved_for_design_use`.

## Review decision

No solver-physics, conservation, sign, timing, phase-state, reproducibility, or
data-integrity blocker was found. V-012D is ready for PR review. V-012 overall
remains `IN_PROGRESS`; mesh/CFL observation, CI-light, formal report, and SHA256
manifest remain before completion.
