# Stage 7 Gate 8 — Post-Crossing CFL Sensitivity Closeout

## Status — execution complete, post-crossing comparability not established

```text
Issue:                                      #105
implementation increments:                  PR #107 / PR #108
PR #107 merge SHA:                          526e85f35b096d3372089a93498ccf41a4d67fe0
PR #108 merge SHA:                          9a943cf93fbcd6c637d16f6f81957d7452c84b16
mesh:                                       32 cells
fixed CFL sequence:                         0.10 / 0.05 / 0.025
workflow run:                               30544667388
artifact ID:                                8761925785
artifact digest:                            sha256:6efd929562d30538fd517a71894f4e71ea2753f80a0b9ccb015937489c092ded
Gate 8 execution:                           COMPLETE
post-crossing CFL characterization:         NOT ESTABLISHED
physical validation:                        NOT ESTABLISHED
design-use acceptance:                      NOT APPROVED
production HEM activation:                  NOT APPROVED
```

## 1. Purpose

Gate 8 executed the unchanged first-order HEM verification path at fixed mesh
and three explicit CFL values. Each column began from the same fixed all-liquid
initial state. An accepted first crossing was required before post-crossing
continuation to the fixed physical checkpoints T1–T4.

The gate was designed to retain formal outcome divergence without tuning. It did
not authorize changes to the production solver, Rusanov flux, prescribed
boundary, phase classifier, equilibrium sound-speed formula, quality projection,
crossing threshold, or any tolerance.

## 2. Locked problem

```text
fluid / backend:                   pure CO2 / CoolProp 8.0.0
case:                              pipeline_crossing_candidate_p5m5_to_p2m5
pipe length / diameter:            1.0 m / 0.10 m
cells:                             32
initial state:                     5 MPa / 5 K subcooling / u=0 / q=0
left boundary:                     reflective
right boundary:                    prescribed 2 MPa / 5 K subcooling
friction / heat / gravity:         disabled
spatial method:                    existing first-order FVM
numerical flux:                    existing Rusanov flux
phase classifier:                  unchanged
sound-speed closure:               unchanged
quality projection:                unchanged
accepted-crossing threshold:       1e-6, unchanged
```

Fixed post-crossing elapsed-time targets:

```text
T1 = 6.016940923599307e-6 s
T2 = 2.402911232474538e-5 s
T3 = 9.544429181626145e-5 s
T4 = 3.696527559334590e-4 s
```

## 3. Formal outcome matrix

| CFL | first-crossing outcome | crossing step | crossing time [s] | cell | maximum crossing q_eq | continuation | reached checkpoints |
|---:|---|---:|---:|---:|---:|---|---|
| 0.10 | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `3.773646403587342e-6` | `COMPLETED_FIXED_CHECKPOINTS` | T1 / T2 / T3 / T4 |
| 0.05 | `GUARD_FAILURE` | 249 | `7.967173062790038e-4` | 29 | `1.1006096906989802e-7` | `NOT_STARTED_NO_ACCEPTED_FIRST_CROSSING` | none |
| 0.025 | `ACCEPTED_FIRST_CROSSING` | 499 | `7.981201399992095e-4` | 29 | `1.3949366092287805e-6` | `FAIL_SAFE_STOP` / `ACOUSTIC_REFUSAL` | T1 / T2 |

All three candidate locations were `0.078125 m` from the outlet.

## 4. CFL 0.10 authoritative replay

The complete Gate 6 identity reproduced exactly before either refined column
was interpreted.

```text
first-crossing state SHA256:       170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361
run signature SHA256:              28a5f8b1fd43f6208807bd15d96eaf09a568349007a1994273717aa264505fea
successful post-crossing steps:    64
cell-30 region changes:            49
cell-30 changes per 1e-4 s:        13.255683668924267
final absolute time:               1.1695853254669838e-3 s
final accepted-state SHA256:       62bbaf5d7014af258180fe29622324a2228a0c5eec507ef10eb6b9f3e411d440
```

## 5. CFL 0.05 formal guard

CFL `0.05` reached cell 29 at nearly the same physical time but produced only
`1.1006096906989802e-7` maximum candidate equilibrium quality. This is below
the unchanged `1e-6` accepted-crossing threshold.

```text
formal outcome:                    GUARD_FAILURE
failure category:                  GUARD_FAILURE
failure reason:                    crossing quality evidence is below the fixed minimum
post-crossing continuation:        not started
last valid state SHA256:           d18e4bdf1477c29f1183b2f3276c84e086f6cfef80c336a7f6f13616769c5a29
run signature SHA256:              1292331d53eddd7ec700d8a76bc3900a501c40f4671c758b0ae4bd5c9487cfde
```

The candidate quality ratio relative to CFL `0.10` was
`0.029165681491851156`. The formal guard was retained without threshold change,
quality clipping, or forced continuation.

## 6. CFL 0.025 accepted crossing and acoustic fail-safe

CFL `0.025` produced an accepted first crossing, demonstrating that the fixed
CFL sequence is non-monotone in both candidate depth and formal outcome.

```text
first-crossing state SHA256:       cb2d5859775d1b1c736e936af798c36cd8d20c73d926de9ed47bcc0aadb1f688
run signature SHA256:              5af1d089f4139b209a7bfc192a4fc5d6afda9da4031a60a1d13f0ddf683e6dd7
successful post-crossing steps:    64
cell-30 region changes:            15
cell-30 changes per 1e-4 s:        15.719403466623879
last valid absolute step:          563
last valid elapsed time:           9.542346840227527e-5 s
last valid state SHA256:           8692bf59750a25ebf40c7c87577a11e479deb040f9a207ded118ed333a462653
continuation outcome:              FAIL_SAFE_STOP
failure category:                  ACOUSTIC_REFUSAL
failure reason:                    no valid central rho stencil found after 12 halvings
```

The last valid elapsed time was approximately `2.08234e-8 s` short of the fixed
T3 target. The next ordinary continuation attempt was refused by the unchanged
accepted-state equilibrium sound-speed evaluator. No one-sided stencil or
fallback acoustic model was substituted.

### Reached physical checkpoints at CFL 0.025

| checkpoint | actual elapsed [s] | overshoot [s] | post step | open two-phase cells | furthest distance [m] | max q_eq | max alpha | accepted-state SHA256 |
|---|---:|---:|---:|---|---:|---:|---:|---|
| T1 | `7.518979417634104e-6` | `1.5020384940347964e-6` | 5 | `[29]` | `0.078125` | `9.135094250249286e-6` | `6.748307171016593e-5` | `7be83f26d9029437ad4a4b49b46d2a75cd48139cb88f0e2ed5ad0135c7564acd` |
| T2 | `2.5523461928356845e-5` | `1.4943496036114645e-6` | 17 | `[28, 29]` | `0.109375` | `2.6915641450918947e-5` | `2.0036023818143455e-4` | `8b56f2c3bed6193624e307ea574dae05786c0ba66819451ebfa84b38bf5a0772` |

At the final valid post-crossing state, cells `[27, 28, 29, 30]` were open two
phase, maximum `q_eq` was `1.3179763670840693e-4`, and maximum void fraction was
`9.31475398308367e-4`.

## 7. Cross-CFL evidence classification

The reviewed result retains:

```text
FIXED_HORIZON_OUTCOME_DIVERGENCE
CFL_SEQUENCE_NON_MONOTONE
POST_CROSSING_CFL_REVIEW_INCONCLUSIVE
```

Rationale:

- the three columns do not retain the same formal first-crossing and
  continuation outcomes;
- maximum candidate crossing quality decreases sharply from CFL `0.10` to
  `0.05`, then increases again at `0.025`;
- fewer than three columns provide comparable accepted post-crossing histories
  through T1–T4.

Therefore no convergence order, CFL-independent front speed, CFL-independent
chatter frequency, or approved post-crossing sensitivity envelope is retained.

## 8. Software and evidence validation

```text
dedicated Gate 8 full-sequence tests:  10 passed
related Stage 7 regressions:           70 passed
full repository:                       850 passed
skips / failures / errors:             0 / 0 / 0
source Git SHA:                         61f8fb8c8ea5898bd215fca8f4b295b0d0ba5b3f
clean checkout:                         true
property backend:                       CoolProp 8.0.0
```

The artifact contains:

```text
summary.json
cfl_cases.csv
cross_cfl_comparison.csv
physical_checkpoints.csv
cell_29_30_31_history.csv
transition_events.csv
inventory_budget.csv
report.md
front_position_vs_time.png
quality_void_fraction_vs_time.png
cell30_phase_acoustic_margin.png
chatter_frequency_comparison.png
budget_residual_comparison.png
artifact_sha256.txt
Gate 8 dedicated JUnit
related Stage 7 JUnit
full-repository JUnit
```

## 9. Completion and approval disposition

```text
Gate_8_execution_complete = true
formal_outcome_comparison_complete = true
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

Gate 8 is closed as a completed fixed numerical experiment with divergent and
non-monotone formal outcomes. It is not closed as a successful demonstration of
post-crossing CFL independence.

## 10. Controlled next work

Two separate tracks follow this closeout:

```text
Track N — Issue #110
  event-aligned diagnosis of CFL-dependent crossing depth and the CFL 0.025
  acoustic refusal without changing thresholds, fluxes, or closures

Track A — Issue #109
  lock and implement the U3 B0 single-phase physical-discharge component
  benchmark independently from pipeline propagation
```

Neither track may reinterpret or overwrite the Gate 8 formal outcomes.
