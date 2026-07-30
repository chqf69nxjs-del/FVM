# Stage 7 Current Gate Snapshot

## Status — 2026-07-30

```text
Stage 1–6:                              COMPLETE
Stage 7:                                IN_PROGRESS
recorded substantive main:              9a943cf93fbcd6c637d16f6f81957d7452c84b16
Gate 3 cross-runtime checkpoint:        NUMERICALLY_EQUIVALENT; PR #91
Gate 4 low-CFL execution:               CFL_SENSITIVITY_OBSERVED; PR #90
Gate 5 acoustic execution:              COMPLETE; PR #96
Gate 5 acoustic approval:               NOT APPROVED
Gate 6 propagation execution:           COMPLETE; PR #99
Gate 6 propagation approval:            NOT APPROVED
Gate 7 chatter diagnosis:               COMPLETE; PR #102
Gate 7 root-cause approval:             NOT APPROVED
Gate 8 CFL execution:                   COMPLETE; PR #107 / #108; Issue #105
Gate 8 post-crossing comparability:      NOT ESTABLISHED
Application Track A1:                   COMPLETE; PR #106; Issue #104 CLOSED
selected first pilot:                   U3 pipeline depressurization / blowdown
next numerical gate:                    Issue #110 crossing-depth forensic diagnosis
active U3 component track:              Issue #109 B0 discharge-boundary benchmark
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
- [`stage7_gate8_closeout.md`](stage7_gate8_closeout.md)
- [`stage7_real_problem_application_strategy.md`](stage7_real_problem_application_strategy.md)
- [`stage7_gate8_post_crossing_cfl_sensitivity_plan.md`](stage7_gate8_post_crossing_cfl_sensitivity_plan.md)
- [`stage7_u3_physical_discharge_boundary_benchmark_spec.md`](stage7_u3_physical_discharge_boundary_benchmark_spec.md)
- [`stage7_u3_b0_discharge_boundary_contract_v1.json`](stage7_u3_b0_discharge_boundary_contract_v1.json)
- [`stage7_u3_b0_discharge_boundary_implementation_plan.md`](stage7_u3_b0_discharge_boundary_implementation_plan.md)

## Project-level current conclusion

The first-order pure-CO2 HEM verification path now supports:

- direct liquid-to-open-two-phase crossing from an all-liquid initial state;
- equilibrium-quality projection and accepted mixed-state recovery;
- exact second-projection no-op behavior;
- fixed first-crossing mesh and CFL sensitivity evidence;
- an independent near-saturation acoustic map;
- one complete CFL `0.10` continuation through the fixed T1–T4 horizon;
- a persistent open-two-phase region moving upstream in that fixed column;
- conservative and vapor-budget closure throughout retained successful states;
- event-aligned diagnosis of boundary-adjacent cell-30 chatter;
- one completed 32-cell Gate 8 formal-outcome matrix at CFL `0.10 / 0.05 / 0.025`.

The evidence also establishes important limitations:

- crossing depth and accepted/guard classification are non-monotone across CFL;
- CFL `0.05` reaches cell 29 with subthreshold quality and cannot start continuation;
- CFL `0.025` accepts crossing but encounters an unchanged acoustic refusal before T3;
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

Track N identifies numerical sensitivity, guards, and model limitations. Track A defines engineering decisions, required inputs and outputs, component benchmarks, and physical validation steps. Neither track may bypass the approval boundary of the other.

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

Every cell-30 region change crossed both fixed saturated-liquid margin coordinates, switched between non-overlapping acoustic branches, and activated quality synchronization. Projection changes only transported `rho*q`; it does not alter the raw `rho/e` crossing state.

```text
Gate_7_execution_complete = true
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
```

## Gate 8 — completed post-crossing CFL execution

```text
implementation PRs:                    #107 / #108
PR #108 merge SHA:                      9a943cf93fbcd6c637d16f6f81957d7452c84b16
workflow / artifact:                    30544667388 / 8761925785
artifact digest:                        6efd929562d30538fd517a71894f4e71ea2753f80a0b9ccb015937489c092ded
Gate 8 / related / full JUnit:          10 / 70 / 850
skips / failures / errors:              0 / 0 / 0
```

Formal outcome matrix:

| CFL | first-crossing outcome | maximum q_eq | continuation | checkpoints |
|---:|---|---:|---|---|
| 0.10 | accepted | `3.773646403587342e-6` | complete | T1 / T2 / T3 / T4 |
| 0.05 | threshold guard | `1.1006096906989802e-7` | not started | none |
| 0.025 | accepted | `1.3949366092287805e-6` | acoustic fail-safe after 64 valid steps | T1 / T2 |

CFL `0.025` stopped at last valid elapsed time `9.542346840227527e-5 s`, just short of T3, because the unchanged equilibrium sound-speed evaluator could not find a valid central density stencil after 12 halvings.

Reviewed labels:

```text
FIXED_HORIZON_OUTCOME_DIVERGENCE
CFL_SEQUENCE_NON_MONOTONE
POST_CROSSING_CFL_REVIEW_INCONCLUSIVE
```

```text
Gate_8_execution_complete = true
post_crossing_CFL_sensitivity_characterized = false
CFL_independent_post_crossing_verified = false
```

## Application Track A1 — real-problem application strategy

The selected first pilot is U3 pipeline depressurization / blowdown. Every future engineering result must present:

```text
representative result
+ numerical / model sensitivity envelope
+ applicability warnings / guard outcomes
+ unapproved or unvalidated model elements
```

The existing prescribed-subcooled outlet remains a verification analogue, not a physical blowdown closure.

## Active next work

### Track N — Issue #110

The next numerical gate is a specification-first event-aligned diagnosis of CFL-dependent crossing depth and the CFL `0.025` acoustic refusal.

```text
threshold changes:                 prohibited
flux / stencil changes:            prohibited
one-sided acoustic substitution:   prohibited
root-cause approval:               false
```

The planned evidence separates raw saturation-margin displacement, Rusanov central and dissipative contributions, boundary-adjacent flux imbalance, acoustic-branch selection, and post-raw projection activity.

### Track A — Issue #109

The U3 physical-discharge track begins with the B0 subcooled-liquid component benchmark.

```text
p0:                                5.0 MPa
upstream definition:               5 K subcooled
Aref:                              1.0e-4 m2
base opening / Cd:                 0.5 / 0.8
base back pressure:                4.95 MPa
B1 choking:                        out of scope
pipe coupling:                     out of scope
```

The B0 numerical states, sign convention, cases, and tolerances are locked before results. Static pressure-force mapping remains deferred to a later FVM adapter.

## Forward roadmap

### Track N

```text
Issue #110 crossing-depth / acoustic-refusal forensic diagnosis
→ post-crossing mesh sensitivity
→ local flux / acoustic causal discrimination
→ longer-duration continuation
→ HEM / non-equilibrium comparison
```

### Track A

```text
Issue #109 B0 single-phase discharge-component benchmark
→ B1 equilibrium nozzle / critical-state reference
→ physical discharge-boundary adapter
→ friction / thermal / elevation extensions
→ integrated blowdown case
→ validation-data comparison
→ sensitivity-bounded engineering-screening review
```

## Approval boundary

```text
application_specification_complete = true
real_problem_pilot_selected = true
Gate_8_execution_complete = true
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
