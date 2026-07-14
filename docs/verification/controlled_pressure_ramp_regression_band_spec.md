# V-011 controlled pressure ramp CI-light regression-band specification

## Purpose

This document defines broad software / numerical regression sentinels for the
single-phase CoolProp controlled-pressure-ramp path.

These limits are not:

- physical Validation criteria
- design-use acceptance criteria
- operating limits
- evidence that the CI-light mesh is a design mesh
- evidence that lower CFL is truth

The limits are deliberately wider than the observed PR #31 results so that they
catch major code regressions without pretending to be accuracy acceptance bands.

## CI-light profile

```text
n_cells = 50
CFL = 0.5
initial pressure = 8 MPa
initial temperature = 280 K
pressure ramp = +1 kPa
ramp duration = 0.01 s
left boundary = transmissive
right boundary = PressureTankBoundary
```

The profile was selected because it is the least expensive observed case while
still exercising:

- real-fluid boundary-state closure
- time-dependent pressure scheduling
- conservative FVM propagation
- probe telemetry
- characteristic direction diagnostics
- conservation budgets
- p10 / p50 / p90 timing
- p50 propagation fit

The profile is a regression sentinel only.

## Observed PR #31 reference values

For `n=50`, `CFL=0.5`:

| metric | observed value |
|---|---:|
| wave-speed relative error | `1.284e-3` |
| absolute common launch / phase offset | `4.212 ms` |
| mean p10 arrival relative error | `0.0812` |
| mean p50 arrival relative error | `0.0503` |
| max p50 arrival relative error | `0.0777` |
| mean p90 arrival relative error | `0.2334` |
| primary peak-amplitude error | `2.117e-7` |
| primary opposite-direction leakage | `5.169e-6` |
| primary linear-velocity relative error | `1.034e-5` |
| p50 fit RMS residual | `9.05e-6 s` |
| p50 fit R-squared | `0.99999994` |
| mass relative residual | approximately `1e-16` |
| energy relative residual | approximately `1e-16` |
| vapor-mass relative residual | `0` |

## Formal CI-light limits

| check | limit |
|---|---:|
| absolute mass relative residual | `1e-12` |
| absolute energy relative residual | `1e-12` |
| absolute vapor-mass relative residual | `1e-12` |
| wave-speed relative error | `<= 5e-3` |
| absolute common launch / phase offset | `<= 8e-3 s` |
| mean p10 arrival relative error | `<= 0.15` |
| mean p50 arrival relative error | `<= 0.08` |
| max p50 arrival relative error | `<= 0.12` |
| mean p90 arrival relative error | `<= 0.35` |
| primary peak-amplitude error | `<= 5e-3` |
| primary opposite-direction leakage | `<= 1e-3` |
| primary linear-velocity relative error | `<= 1e-2` |
| p50 fit RMS residual | `<= 1e-4 s` |
| p50 fit R-squared | `>= 0.999` |

Required health checks:

- target time reached
- maximum step count not exceeded
- all histories finite
- pressure, temperature, density, and sound speed remain positive
- single-phase state retained
- requested schedule remains within the existing 8-ULP roundoff tolerance
- no budget fields missing
- primary probe exists
- left-going characteristic remains dominant
- `property_backend_design_status = not_approved_for_design_use`

## Rationale

The timing and phase limits are approximately 1.5 to 2 times the observed coarse
case values. The amplitude, leakage, velocity, and fit-residual limits are much
wider because their observed values are already near numerical or diagnostic
floors.

The budget limits remain `1e-12`, consistent with earlier Stage 4 and Stage 5
software-regression protection.

The limits must not be weakened merely to make a future test pass. Any failure
should first be investigated as a possible change in:

- boundary thermodynamic closure
- pressure scheduling
- numerical flux
- timestep logic
- probe timing analysis
- characteristic decomposition
- conservation accounting
- property backend behaviour

## Deferred work

This specification does not define:

- a production or design mesh
- a physical accuracy requirement
- a valve-operation regression profile
- flashing, cavitation, choked-flow, or two-phase criteria
- experimental Validation criteria
