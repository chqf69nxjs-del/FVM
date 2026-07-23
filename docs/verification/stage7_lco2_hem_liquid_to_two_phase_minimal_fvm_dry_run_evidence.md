# Stage 7 — Minimal Liquid-to-Two-Phase Raw FVM Dry-Run Evidence

## Status

`VALIDATED DRAFT; RAW FIRST-ORDER FVM CROSSING OBSERVED; NO PROJECTION; NOT FORMAL COMPLETE CROSSING VERIFICATION`

This record captures the first fixed one-step dry-run matrix using the actual existing
`FvmSolver.step()`, Rusanov flux, CFL path, transmissive boundaries, `NoSource`, and
`NoPhaseChange` paths.

## Validation environment

```text
validated head:            a870d313bd821bc05ba5e3fdd2ab155edadb8de9
workflow run:              30015273238
artifact ID:               8566944015
artifact SHA256:           15569960f65261d16f79d8341ab2706fb61309a5bfd044e1cc0a846bf099f34c
CoolProp:                  8.0.0
compileall:                 success
git diff --check:           success
focused dry-run tests:     15 passed, 0 skipped
related Stage 7 HEM:      174 passed, 0 skipped
full repository:          616 passed, 0 skipped
failures / errors:          0 / 0
```

## Fixed numerical setup

```text
cells:              8
pipe length:        1.0 m
pipe diameter:      0.10 m
interface:          between cells 3 and 4
initial velocity:   0 m/s
initial q:          0 exactly
CFL:                0.20
boundaries:         transmissive
physical source:    none
phase projection:   none
steps:              exactly 1
```

All three cases completed one actual FVM step. Only cells 3 and 4, adjacent to the
initial discontinuity, changed. Initial and raw transported quality remained exactly zero
in every cell.

## Matrix summary

```text
case count:          3
OPEN_TWO_PHASE:      2
ALL_LIQUID:          1
ENDPOINT_LANDING:    0
FORBIDDEN_REGION:    0
GUARD_FAILURE:       0
BACKEND_FAILURE:     0
```

## Strong candidate

```text
case ID:                       strong_p5m5_to_p2m5
left / right:                  5 MPa / 5 K -> 2 MPa / 5 K subcooling
outcome:                       OPEN_TWO_PHASE
dt:                            3.356317173211922e-5 s
measured CFL:                  0.20
changed cells:                 3, 4
crossing cells:                3, 4
raw liquid / open cells:       6 / 2
maximum raw q_eq:              5.911503500507591e-4
maximum raw quality mismatch:  5.911503500507591e-4
endpoint / forbidden count:    0 / 0
```

Cellwise crossing evidence:

| cell | raw pressure | raw temperature | raw q_eq | raw alpha | event |
|---:|---:|---:|---:|---:|---|
| 3 | `3.9680896849 MPa` | `278.1364573 K` | `5.9115035005e-4` | `4.6051306477e-3` | `LIQUID_TO_TWO_PHASE_CROSSING` |
| 4 | `1.8716583570 MPa` | `251.5064170 K` | `1.8439049901e-4` | `3.8956065955e-3` | `LIQUID_TO_TWO_PHASE_CROSSING` |

Boundary-budget residuals closed to numerical precision. The largest absolute residual was
energy `2.3283064365386963e-10`, with relative residual
`1.742733258599977e-16`; mass, momentum, and vapor residuals were zero.

## Moderate candidate

```text
case ID:                       moderate_p5m5_to_p3m5
left / right:                  5 MPa / 5 K -> 3 MPa / 5 K subcooling
outcome:                       OPEN_TWO_PHASE
dt:                            3.9278457537062076e-5 s
measured CFL:                  0.20
changed cells:                 3, 4
crossing cells:                4
raw liquid / open cells:       7 / 1
maximum raw q_eq:              6.844477600333753e-5
maximum raw quality mismatch:  6.844477600333753e-5
endpoint / forbidden count:    0 / 0
```

Cell 4 reached approximately `2.7261385459 MPa`, `264.1662617 K`,
`q_eq=6.8444776003e-5`, and was classified as one direct
`LIQUID_TO_TWO_PHASE_CROSSING`. Cell 3 remained a liquid candidate. All boundary-budget
residuals were zero in the recorded precision.

## Liquid negative control

```text
case ID:                       control_p5m5_to_p4m5
left / right:                  5 MPa / 5 K -> 4 MPa / 5 K subcooling
outcome:                       ALL_LIQUID
dt:                            4.589645677266401e-5 s
measured CFL:                  0.20
changed cells:                 3, 4
crossing cells:                none
raw liquid / open cells:       8 / 0
maximum raw q_eq:              0
maximum raw quality mismatch:  0
endpoint / forbidden count:    0 / 0
```

The control retained all eight cells as `LIQUID_CANDIDATE`. Mass, energy, and vapor
residuals were zero; the momentum residual was `1.6653345369377348e-16`, consistent with
roundoff.

## Technical interpretation

The fixed matrix demonstrates that the actual first-order Rusanov/CFL update, not merely
the PR #68 conservative-blend screening proxy, produces raw liquid-to-open-two-phase
transitions for the strong and moderate pressure-span candidates while the nearest-span
control remains liquid.

The raw two-phase cells retain transported `q=0` while `rho/e` implies positive
`q_eq`. This is the intended mismatch for the next equilibrium-quality projection
increment.

The evidence does **not** yet establish a complete accepted crossing step. The following
remain outside this increment:

```text
equilibrium-quality projection
post-projection mixed accepted-state EOS recovery
second-projection no-op
complete projection vapor accounting
multi-step behavior
formal Case A and matched Case B freeze
```

## Approval boundary

```text
verification_only = true
raw_first_order_fvm_crossing_observed = true
actual_first_order_fvm_crossing_verified = false
phase_projection_exercised = false
post_projection_accepted_eos_exercised = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment

Connect `HEMEquilibriumQualityProjection` to the observed raw crossing state, verify
post-projection recovery through the mixed liquid/open-two-phase accepted-state EOS,
confirm the second projection is a no-op, and close phase-vapor accounting without
changing the fixed numerical or thermodynamic algorithms.
