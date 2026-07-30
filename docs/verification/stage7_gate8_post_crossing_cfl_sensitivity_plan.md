# Stage 7 Gate 8 — Post-Crossing CFL Sensitivity Plan

## Status — contract locked before results

```text
Issue:                              #105
scope:                              verification only
mesh:                               32 cells
CFL sequence:                       0.10 / 0.05 / 0.025
case:                               pipeline_crossing_candidate_p5m5_to_p2m5
post-crossing physical horizon:     3.696527559334590e-4 s
production changes:                 prohibited
```

Application driver: Issue #104 and [`stage7_real_problem_application_strategy.md`](stage7_real_problem_application_strategy.md).

## 1. Why this gate is next

Engineering outputs for ESD valve operation, pump trip, and pipeline depressurization depend strongly on time:

- pressure-wave arrival;
- first crossing;
- phase-front propagation;
- chatter onset and frequency;
- duration above or below engineering limits.

Gate 6 demonstrated one CFL 0.10 continuation. Gate 7 showed localized phase-boundary and acoustic-branch oscillation. Before those timings can support even sensitivity-bounded screening, the project must establish how they change under explicit time-step refinement at fixed mesh.

## 2. Fixed problem

```text
fluid / backend:                   pure CO2 / CoolProp 8.0.0
pipe length / diameter:            1.0 m / 0.10 m
cells / dx:                        32 / 0.03125 m
initial state:                     5 MPa / 5 K subcooling / u=0 / q=0
left boundary:                     reflective
right boundary:                    prescribed 2 MPa / 5 K subcooling
friction / wall heat / gravity:    disabled
spatial method:                    existing first-order FVM
flux:                              existing Rusanov
phase classifier:                  unchanged
sound-speed closure:               unchanged
quality projection:                unchanged
crossing evidence threshold:       1e-6, unchanged
```

Prohibited:

```text
threshold or tolerance tuning
quality clipping
one-sided acoustic substitute
hysteresis or chatter suppression
boundary retuning
formula or stencil changes
production solver changes
result-dependent case changes
```

## 3. CFL columns

```text
CFL 0.10 — authoritative Gate 6 replay column
CFL 0.05 — first time-step refinement
CFL 0.025 — second time-step refinement
```

Each column starts from the same all-liquid initial state and independently executes the unchanged first-crossing logic.

The accepted-crossing outcome is not assumed for the two lower-CFL columns. Any guard, no-crossing, backend, phase, or acoustic outcome is retained explicitly.

## 4. Gate 6 replay requirement

Before sensitivity interpretation, the CFL 0.10 column must match:

```text
first crossing outcome:             ACCEPTED_FIRST_CROSSING
crossing step:                       125
crossing time:                       7.999325695335248e-4 s
crossing cell / distance:            29 / 0.078125 m
maximum crossing q_eq:              3.773646403587342e-6
final post-crossing absolute time:   1.1695853254669838e-3 s
final accepted-state SHA256:         62bbaf5d7014af258180fe29622324a2228a0c5eec507ef10eb6b9f3e411d440
cell-30 region changes:              49
```

A mismatch invalidates Gate 8 interpretation.

## 5. Physical-time checkpoints

Raw step count cannot be used as the primary cross-CFL comparison because changing CFL changes the number of steps per unit physical time.

The fixed elapsed-time targets, measured from each column's own accepted crossing, are:

| checkpoint | elapsed time [s] | Gate 6 reference |
|---|---:|---:|
| T1 | `6.016940923599307e-6` | +1 step |
| T2 | `2.402911232474538e-5` | +4 steps |
| T3 | `9.544429181626145e-5` | +16 steps |
| T4 | `3.696527559334590e-4` | +64 steps |

The solver continues with ordinary CFL time steps. At each target, retain the first accepted state at or after the target.

Required sampling evidence:

```text
target elapsed time
actual elapsed time
overshoot
local accepted dt
absolute step
post-crossing step count
```

No interpolation, reconstructed phase label, result-dependent step cap, or target adjustment is allowed. Overshoot must be no more than one local accepted time step.

## 6. Primary comparison quantities

### First crossing

```text
formal outcome
crossing time / step / cell / distance
maximum q_eq
accepted-state hash
```

### Phase front

```text
OPEN_TWO_PHASE cell count and indices
furthest upstream two-phase position
front displacement from first crossing
average front speed using actual elapsed time
first and last transition time per cell
```

### Thermodynamic growth

```text
maximum and integrated q_eq
maximum alpha
vapor mass
minimum / maximum pressure
liquid / two-phase sound-speed ranges
acoustic refusals and categories
```

### Projection and budgets

```text
first-projection activation count
second-projection activation count / exact no-op status
projection vapor source
mass / momentum / energy / vapor residuals
```

### Chatter

```text
cell-30 liquid→two-phase events
cell-30 reverse events
total toggles
first and last chatter time
toggles per 1e-4 s
fraction of accepted steps with a toggle
longest consecutive one-step alternation
onset of persistent one-step alternation
saturation-margin sign changes
acoustic-branch switches
projection activity at chatter events
cell-29 and cell-31 toggle counts
```

## 7. Comparison rules

Primary results are plotted and tabulated against physical elapsed time.

For each metric report:

```text
absolute value
absolute difference from CFL 0.10
ratio to CFL 0.10
monotonic / non-monotonic sequence status
```

No convergence order is assigned unless:

- all columns retain comparable formal outcomes;
- the metric sequence is monotone;
- the assumptions for the estimate are documented;
- no threshold or discrete-event discontinuity invalidates the estimate.

Otherwise the evidence is classified as sensitivity or non-monotonicity, not convergence.

## 8. Required artifacts

```text
summary.json
cfl_cases.csv
physical_checkpoints.csv
focused_phase_history.csv
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

## 9. Permitted evidence labels

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

Labels describe the fixed numerical evidence only.

## 10. Completion and approval boundary

```text
Gate_8_execution_complete = false
post_crossing_CFL_sensitivity_characterized = false
CFL_independent_post_crossing_verified = false
mesh_independent_post_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

Gate 8 execution may close after all three formal columns and their fixed physical-time evidence are retained with clean tests and provenance. Execution closeout does not itself approve propagation physics, chatter cause, or design use.