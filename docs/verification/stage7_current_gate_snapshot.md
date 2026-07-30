# Stage 7 Current Gate Snapshot

## Status — 2026-07-30

```text
Stage 1–6:                              COMPLETE
Stage 7:                                IN_PROGRESS
recorded substantive main:              6c661029c01653d56b45629bcc7db6c37551531e
Gate 3 cross-runtime checkpoint:        NUMERICALLY_EQUIVALENT; PR #91
Gate 4 low-CFL execution:               CFL_SENSITIVITY_OBSERVED; PR #90
Gate 5 acoustic execution:              COMPLETE; PR #96
Gate 5 acoustic approval:               NOT APPROVED
Gate 6 propagation execution:           COMPLETE; PR #99
Gate 6 propagation approval:            NOT APPROVED
Gate 7 chatter diagnosis:               COMPLETE; PR #102
Gate 7 root-cause approval:             NOT APPROVED
Application Track A1:                   SPECIFICATION COMPLETE; Issue #104
selected first pilot:                   U3 pipeline depressurization / blowdown
active next numerical gate:             Issue #105 post-crossing CFL sensitivity
Gate P2:                                FALSE
physical Validation:                    NOT ESTABLISHED
design-use acceptance:                  NOT ESTABLISHED
production HEM activation:              NOT APPROVED
```

Detailed historical evidence remains in:

- [`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md)
- [`stage7_execution_log.md`](stage7_execution_log.md)
- [`stage7_gate5_closeout.md`](stage7_gate5_closeout.md)
- [`stage7_gate6_closeout.md`](stage7_gate6_closeout.md)
- [`stage7_gate7_closeout.md`](stage7_gate7_closeout.md)
- [`stage7_real_problem_application_strategy.md`](stage7_real_problem_application_strategy.md)
- [`stage7_gate8_post_crossing_cfl_sensitivity_plan.md`](stage7_gate8_post_crossing_cfl_sensitivity_plan.md)

## Project-level current conclusion

The first-order pure-CO2 HEM verification path now supports:

- direct liquid-to-open-two-phase crossing from an all-liquid initial state;
- equilibrium-quality projection and accepted mixed-state recovery;
- exact second-projection no-op behavior;
- fixed first-crossing mesh and CFL sensitivity evidence;
- an independent near-saturation acoustic map;
- continuation for 64 accepted steps after the first 5→2 MPa crossing;
- an open-two-phase region that persists and moves upstream;
- conservative and vapor-budget closure throughout the fixed continuation;
- event-aligned diagnosis of the boundary-adjacent cell-30 chatter.

The evidence also retains important limitations:

- crossing depth is non-monotone across reviewed mesh and CFL sequences;
- accepted / guard classification is CFL-dependent at 2 MPa in the reviewed first-crossing study;
- strict `q -> 0+` acoustic continuity is unresolved;
- liquid and open-two-phase acoustic branches differ substantially;
- cell 30 repeatedly crosses the selected saturation boundary and switches acoustic branches;
- first-order flux, boundary-adjacent coupling, acoustic switching, and equilibrium modeling remain causally entangled;
- post-crossing CFL / mesh independence, propagation speed, physical accuracy, and design use are unapproved.

## Development model — two controlled tracks

```text
Track N — numerical / model characterization
Track A — real-problem application definition and validation planning
```

Track N identifies sensitivity, numerical behavior, and model limitations. Track A defines engineering decisions, required inputs / outputs, validation steps, and application boundaries. Neither track may bypass the approval boundary of the other.

## Gate 3 — cross-runtime software reproduction

```text
PR:                                  #91
formal disposition:                  NUMERICALLY_EQUIVALENT
all reviewed discrete events exact:  true
maximum normalized array difference: 5.519112370006797e-12
comparison guard:                    1.0e-10
```

Ubuntu remains authoritative for exact scalar and SHA256 references. The reviewed Windows result preserves outcomes and decisions without replacing Ubuntu hashes.

## Gate 4 — low-CFL first-crossing execution

```text
PR:                                  #90
workflow / artifact:                 30313389184 / 8675117973
formal disposition:                  CFL_SENSITIVITY_OBSERVED
low_cfl_result_accepted:             true
CFL_independent_crossing_verified:   false
```

Crossing time and position show a stable trend, but crossing depth is non-monotone and the fixed accepted / guard decision changes with CFL at 2 MPa.

## Gate 5 — near-saturation acoustic review

```text
PR:                                  #96
workflow / artifact:                 30451125151 / 8723959176
state / perturbation records:        33 / 588
successful / failed-or-refused:      24 / 9
```

Reviewed labels:

```text
FINITE_JUMP_MODEL_CONSISTENT
PHASE_CLASSIFIER_SENSITIVE
NEAR_SATURATION_PROPERTY_SENSITIVE
ACOUSTIC_REVIEW_INCONCLUSIVE
```

The nearest sampled liquid and acoustically evaluable open-two-phase branches have a large finite sound-speed difference. The unchanged central stencil cannot evaluate `q=0`, `q=1e-12`, or `q=1e-10`.

```text
Gate_5_execution_complete = true
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
```

## Gate 6 — post-crossing propagation review

```text
implementation PR:                  #99
workflow / artifact:                30466063542 / 8730632937
Gate 6 / related / full JUnit:      9 / 54 / 820
skips / failures / errors:          0 / 0 / 0
```

The fixed CFL 0.10 continuation reached all predeclared checkpoints:

| offset | open-two-phase cells | indices | furthest upstream distance [m] | maximum q_eq | maximum alpha |
|---:|---:|---|---:|---:|---:|
| +1 | 1 | `[29]` | 0.078125 | `9.9651e-6` | `7.3594e-5` |
| +4 | 2 | `[28, 29]` | 0.109375 | `2.7667e-5` | `2.0583e-4` |
| +16 | 4 | `[27, 28, 29, 30]` | 0.140625 | `1.3211e-4` | `9.3335e-4` |
| +64 | 7 | `[24, 25, 26, 27, 28, 29, 30]` | 0.234375 | `1.2605e-3` | `9.0086e-3` |

Reviewed labels:

```text
POST_CROSSING_REGION_PERSISTS
POST_CROSSING_REGION_PROPAGATES
PHASE_CLASSIFIER_CHATTER_OBSERVED
PROJECTION_RECOVERY_STABLE
CONSERVATION_BUDGET_STABLE
```

```text
Gate_6_execution_complete = true
post_crossing_propagation_approved = false
```

## Gate 7 — boundary-adjacent phase-chatter diagnosis

```text
implementation PR:                  #102
workflow / artifact:                30501363884 / 8744210262
Gate 7 / related / full JUnit:      10 / 52 / 830
skips / failures / errors:          0 / 0 / 0
focused cell / interface / events:  576 / 192 / 49
```

```text
cell 29: 0 toggles; stable OPEN_TWO_PHASE
cell 30: 49 toggles; localized chatter
cell 31: 0 toggles; stable LIQUID_CANDIDATE
```

Reviewed labels:

```text
STABLE_FRONT_SEPARATED_FROM_CHATTER
PHASE_MARGIN_OSCILLATION_CORRELATED
ACOUSTIC_BRANCH_SWITCH_CORRELATED
PROJECTION_ACTIVITY_CORRELATED
MULTI_FACTOR_CHATTER
CHATTER_REVIEW_INCONCLUSIVE
```

Every cell-30 region change crossed both fixed saturated-liquid margin coordinates, switched between non-overlapping acoustic branches, and activated quality synchronization. Projection changes only transported `rho*q`; it does not alter the `rho/e` crossing state. Boundary pressure remained monotonic and the predeclared interface-flux screen was not met.

```text
Gate_7_execution_complete = true
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
```

## Application Track A1 — real-problem application strategy

Issue #104 fixes three initial use cases:

```text
U1 — ESD valve operation / rapid isolation
U2 — pump trip / rotating-inertia rundown
U3 — pipeline depressurization / blowdown
```

The common engineering-result contract requires:

```text
representative result
+ numerical / model sensitivity envelope
+ applicability warnings / guard outcomes
+ unapproved or unvalidated model elements
```

The selected first pilot is U3 because it is closest to the existing 5→2 MPa verification analogue and creates a direct development path toward a physical discharge boundary, thermal inventory, longer-duration propagation, and validation data.

```text
application_specification_complete = true
real_problem_pilot_selected = true
selected pilot = U3 pipeline depressurization / blowdown

ESD_design_use_approved = false
pump_trip_design_use_approved = false
blowdown_design_use_approved = false
```

## Active numerical gate — Issue #105 / Gate 8

Gate 8 is a fixed 32-cell post-crossing CFL sensitivity review.

```text
CFL sequence:                 0.10 / 0.05 / 0.025
comparison basis:             physical elapsed time after each accepted crossing
reference horizon:            3.696527559334590e-4 s
CFL 0.10 replay:              exact Gate 6 identity required
production changes:           prohibited
```

Fixed elapsed-time targets:

```text
T1 = 6.016940923599307e-6 s
T2 = 2.402911232474538e-5 s
T3 = 9.544429181626145e-5 s
T4 = 3.696527559334590e-4 s
```

Primary decisions:

- whether phase-front position and inferred speed are stable or CFL-sensitive;
- whether cell-30 chatter persists and how its frequency changes per unit physical time;
- whether quality, void fraction, vapor inventory, projection behavior, and budgets retain a stable trend;
- whether lower-CFL columns retain comparable first-crossing and post-crossing outcomes.

## Forward roadmap

### Track N

```text
Gate 8 post-crossing CFL sensitivity
→ post-crossing mesh sensitivity
→ local flux / acoustic contribution discrimination
→ longer-duration continuation
→ HEM / non-equilibrium comparison
```

### Track A

```text
U3 pilot specification
→ physical discharge-boundary benchmark
→ friction / thermal / elevation extensions
→ integrated blowdown case
→ validation-data comparison
→ sensitivity-bounded engineering-screening review
```

U1 and U2 requirements remain active planning inputs but do not bypass the common numerical and validation ladder.

## Approval boundary

```text
application_specification_complete = true
real_problem_pilot_selected = true
Gate_8_execution_complete = false
post_crossing_CFL_sensitivity_characterized = false
CFL_independent_post_crossing_verified = false
mesh_independent_post_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```