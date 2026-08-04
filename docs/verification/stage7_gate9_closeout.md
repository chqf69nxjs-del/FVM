# Stage 7 Gate 9 Closeout

## Status

```text
Stage 7:                                      IN_PROGRESS
Gate 9 D0-D6 execution:                      COMPLETE
Gate_9_execution_complete:                   true
crossing_depth_CFL_sensitivity_characterized:true
crossing_depth_root_cause_approved:           false
```

Gate 9 completed the fixed, verification-only diagnosis of CFL-dependent first-crossing depth for the 32-cell `pipeline_crossing_candidate_p5m5_to_p2m5` case. The production solver, first-order FVM, Rusanov flux, phase classifier, equilibrium sound-speed closure, quality projection, prescribed outlet, crossing threshold, and formal stop behavior were not changed.

## Authoritative records

```text
D5 integration PR:                  #121
D5 source head:                     45894a3fbe8c176c8435517c6204d94359dccccc
D5 workflow run:                    30805641241
D5 artifact ID:                     8855725551
D5 artifact ZIP SHA256:             6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850

D6 classification PR:               #122
D6 validated source head:           b90aa04ca3e1d8f2958f6a700c4ae73917ce39c8
D6 main merge SHA:                  5f0099101cbc9e9694297394a4c424904260ba94
D6 workflow run:                    30860513453
D6 artifact ID:                     8875962770
D6 artifact ZIP SHA256:             b0c4b490eedeb7332659051d13cc1e108ef08dfd381eec9fbf63773c4e4aa088

D6 dedicated / related / full:      6 / 52 / 903 passed
skips / failures / errors:          0 / 0 / 0
Issue #110:                         CLOSED / completed
```

## Immutable three-CFL candidate identities

| CFL | formal outcome | candidate step | candidate time [s] | cell | maximum `q_eq` |
|---:|---|---:|---:|---:|---:|
| 0.10 | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `3.773646403587342e-6` |
| 0.05 | `GUARD_FAILURE` | 249 | `7.967173062790038e-4` | 29 | `1.1006096906989802e-7` |
| 0.025 | `ACCEPTED_FIRST_CROSSING` | 499 | `7.981201399992095e-4` | 29 | `1.3949366092287805e-6` |

All candidates occurred at cell 29, 0.078125 m from the outlet. Candidate time spread was approximately `0.534` times the largest candidate-step `dt`, supporting comparison of the same boundary-adjacent physical event.

## Reviewed D6 evidence labels

Assigned:

```text
CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL
CROSSING_DEPTH_CFL_SENSITIVE
CROSSING_DEPTH_SEQUENCE_NON_MONOTONE
SATURATION_MARGIN_DISPLACEMENT_CORRELATED
PROJECTION_ACTIVITY_POSTDATES_RAW_CROSSING
THRESHOLD_CLASSIFICATION_DISCONTINUITY_OBSERVED
CROSSING_DEPTH_REVIEW_INCONCLUSIVE
```

Not assigned:

```text
CANDIDATE_STEP_OVERSHOOT_CORRELATED
RUSANOV_DISSIPATION_CORRELATED
BOUNDARY_FLUX_IMBALANCE_CORRELATED
ACOUSTIC_BRANCH_SELECTION_CORRELATED
MULTI_FACTOR_CROSSING_DEPTH
```

Primary denominators:

```text
candidate dt ordering:                  2 / 3
Rusanov dissipative ordering:          12 / 18
boundary-flux ordering:                 6 / 9
saturation-margin ordering:            12 / 12
acoustic branch differences:            0 / 3
projection temporal ordering:           3 / 3
threshold / outcome consistency:        3 / 3
```

## Technical disposition

The Gate 9 evidence supports the following conclusions:

1. The three CFL columns reach the same candidate cell at closely aligned physical times.
2. Continuous crossing depth is strongly CFL-sensitive and non-monotone; the maximum-to-minimum depth ratio is approximately 34.29.
3. Saturation coordinates `q_u`, `q_v`, `Delta e`, and `Delta v` preserve the crossing-depth ordering, but they describe the same raw thermodynamic state and are not an independent causal mechanism.
4. Raw thermodynamic crossing exists at `RAW_POST_FVM` before first quality projection. Projection synchronizes transported `rho*q`; it does not create the raw crossing. Second projection remains an exact no-op.
5. The fixed `1e-6` threshold converts continuous `q_eq` differences into discrete accepted / guard outcomes. This observation does not authorize threshold changes.
6. Candidate-step `dt`, Rusanov dissipative contribution, boundary-adjacent net flux, and accepted acoustic branch do not individually reproduce the complete non-monotone depth ordering.
7. Gate 9 therefore characterizes the sensitivity and temporal ordering but does not approve a root cause or mitigation.

## Approval boundary

```text
D6_temporal_correlation_classification_complete = true
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true

crossing_depth_root_cause_approved = false
threshold_change_authorized = false
flux_change_authorized = false
sound_speed_change_authorized = false
projection_change_authorized = false
post_crossing_propagation_approved = false
CFL_independent_crossing_verified = false
mesh_independent_crossing_verified = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Active next controlled work

The next primary implementation track is Issue #109, U3 B0 single-phase discharge-boundary component benchmark. Gate 9 numerical diagnosis is closed rather than extended into result-driven changes. The prescribed-subcooled outlet remains a verification analogue, not a physical blowdown closure.

The technical-report track, Issue #114, should incorporate Gate 9 execution and this closeout record while retaining the distinction between software verification, numerical characterization, model characterization, and physical validation / design use.
