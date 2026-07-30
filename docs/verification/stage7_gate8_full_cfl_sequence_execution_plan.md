# Stage 7 Gate 8 — Full CFL Sequence Execution Plan

## Status

```text
Issue:                              #105
scope:                              verification only
mesh:                               32 cells
locked sequence:                    0.10 / 0.05 / 0.025
PR #107 increment:                  merged
active implementation:              full three-column execution
production changes:                 prohibited
```

## 1. Objective

Complete the exact Gate 8 contract by executing CFL `0.025` after the already
reviewed CFL `0.10` identity replay and CFL `0.05` formal guard result, then
retain one complete formal-outcome matrix for all three locked columns.

This work characterizes the fixed numerical path. It does not alter or approve
the physical model.

## 2. Fixed execution order

```text
1. replay CFL 0.10 through the authoritative Gate 6 path
2. require the complete Gate 6 identity
3. execute CFL 0.05 independently from the all-liquid initial state
4. retain its formal outcome without tuning
5. execute CFL 0.025 independently from the same all-liquid initial state
6. retain its formal outcome without tuning
7. continue only an accepted first crossing to T1 / T2 / T3 / T4
8. classify the complete formal-outcome sequence
```

A CFL `0.05` guard does not cancel CFL `0.025`; the locked sequence must be
completed. A Gate 6 identity failure stops both lower-CFL columns.

## 3. Immutable numerical contract

```text
fluid / backend:                   pure CO2 / CoolProp 8.0.0
case:                              pipeline_crossing_candidate_p5m5_to_p2m5
pipe length / diameter:            1.0 m / 0.10 m
cells:                             32
initial state:                     5 MPa / 5 K subcooling / u=0 / q=0
left boundary:                     reflective
right boundary:                    prescribed 2 MPa / 5 K subcooling
spatial method:                    existing first-order FVM
numerical flux:                    existing Rusanov flux
phase classifier:                  unchanged
sound-speed formula:               unchanged
quality projection:                unchanged
crossing evidence threshold:       1e-6, unchanged
friction / heat / gravity:         disabled
```

Prohibited:

```text
threshold or tolerance tuning
quality clipping
one-sided acoustic substitution
boundary retuning
hysteresis or chatter suppression
formula, stencil, flux, or production-solver changes
forcing a lower-CFL candidate into accepted continuation
```

## 4. Fixed physical checkpoints

| checkpoint | elapsed time after each accepted crossing [s] |
|---|---:|
| T1 | `6.016940923599307e-6` |
| T2 | `2.402911232474538e-5` |
| T3 | `9.544429181626145e-5` |
| T4 | `3.696527559334590e-4` |

The first accepted state at or after each target is retained. Overshoot must not
exceed one accepted local time step. Interpolation and target adjustment remain
prohibited.

## 5. Formal outcomes

Each column retains one of the existing formal outcomes:

```text
ACCEPTED_FIRST_CROSSING
NO_CROSSING_WITHIN_HORIZON
ENDPOINT_LANDING
FORBIDDEN_TRANSITION
REVERSE_FLOW_GUARD
GUARD_FAILURE
BACKEND_FAILURE
```

Only `ACCEPTED_FIRST_CROSSING` may enter post-crossing continuation.

## 6. Full-matrix interpretation

The primary matrix records:

```text
CFL
first-crossing formal outcome
candidate / accepted step, time, cell, distance, and q_eq
continuation outcome
T1-T4 reach status
cell-30 region-change count and frequency
last valid accepted-state SHA256
failure category and reason
```

The first-crossing time, position, and maximum candidate quality are also
reported as absolute differences and ratios relative to CFL `0.10`.

The following labels remain the only permitted initial classifications:

```text
POST_CROSSING_FRONT_TREND_STABLE_ACROSS_CFL
POST_CROSSING_FRONT_CFL_SENSITIVE
CHATTER_PERSISTS_ACROSS_CFL
CHATTER_FREQUENCY_CFL_SENSITIVE
CFL_REFINEMENT_REDUCES_CHATTER
CFL_REFINEMENT_AMPLIFIES_CHATTER
CFL_SEQUENCE_NON_MONOTONE
FIXED_HORIZON_OUTCOME_DIVERGENCE
PROJECTION_BUDGET_STABLE_ACROSS_CFL
POST_CROSSING_CFL_REVIEW_INCONCLUSIVE
```

No convergence order is assigned unless all three columns provide comparable,
monotone post-crossing histories and the assumptions are documented.

## 7. Required artifact bundle

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
runtime / Git provenance
```

The cell-30 phase/acoustic/saturation-margin figure uses the already reviewed
Gate 7 focused diagnostic as the unchanged CFL `0.10` reference. Lower-CFL
columns without accepted continuation are shown as formal non-comparability,
not reconstructed histories.

## 8. Completion and approval boundary

After all three columns execute to formal outcomes with clean evidence:

```text
Gate_8_execution_complete = true
post_crossing_CFL_sensitivity_characterized = false unless comparable evidence supports it
CFL_independent_post_crossing_verified = false
mesh_independent_post_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

`Gate_8_execution_complete = true` means the locked experiment was completed
and its outcome divergence was recorded. It does not mean that the post-crossing
solution is CFL independent or physically validated.
