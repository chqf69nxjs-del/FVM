# Stage 7 — Fixed Pipeline CFL-Sensitivity Execution Plan

`ACTIVE GATE 4; GATE 3 COMPLETE; EXECUTION AUTHORIZED; RESULT ACCEPTANCE PENDING REVIEW; VERIFICATION ONLY`

## Objective

Execute the immutable PR #84 contract without result-dependent tuning:

```text
n_cells:          128
final pressures:  2 / 3 / 4 MPa
CFL values:       0.10 / 0.05 / 0.025
step caps:        8000 / 16000 / 32000
spatial flux:     existing first-order Rusanov
matrix size:      9 runs
```

The CFL 0.10 rows must reproduce PR #82 exactly before any lower-CFL row is retained.
Only CFL and its predeclared step cap may vary.

## Gate boundary

Gate 3 completed as `NUMERICALLY_EQUIVALENT` in merged PR #91, Issue #85 is closed, and
PR #92 synchronized the disposition into the Stage 7 central records. Issue #86 is now the
active Gate 4 execution tracker.

Gate 4 may:

```text
execute the immutable nine-run matrix in the authoritative CI environment
retain traceable Gate 4 execution observations
exercise contract and regression tests
prepare evidence for dedicated review
```

Gate 4 may not yet:

```text
promote a CFL-sensitivity conclusion to the central record
set low_cfl_result_accepted = true before review
set CFL_independent_crossing_verified = true before review
close Issue #86 as an accepted numerical result
approve physical Validation, design use, or production HEM
```

Any pre-Gate-3-clearance artifact remains quarantined and is not accepted as Gate 4 evidence.

## Mandatory evidence

```text
pipeline_cfl_sensitivity_summary.json
pipeline_cfl_sensitivity_cases.csv
pipeline_cfl_sensitivity_steps.csv
pipeline_cfl_sensitivity_cells.csv
pipeline_cfl_sensitivity_4mpa_metrics.csv
pipeline_cfl_sensitivity.npz
pipeline_cfl_sensitivity.md
cfl_qeq_vs_cfl.png
cfl_saturation_margin_vs_cfl.png
cfl_crossing_time_position.png
cfl_sound_speed_jump.png
JUnit evidence
artifact SHA256
```

Every standalone CSV row includes model, backend, backend version, source/checkout Git
identity, checkout cleanliness, and all unapproved acceptance fields.

## Classification rules

Only the reviewed PR #84 vocabulary is permitted:

```text
CROSSING_VANISHES_WITH_SMALLER_CFL
CROSSING_DEPTH_DECAYS_WITH_SMALLER_CFL
FINITE_CROSSING_PERSISTS_ACROSS_CFL
CROSSING_TIME_POSITION_TREND_STABLE
CROSSING_TIME_POSITION_NOT_STABLE
CFL_SEQUENCE_NON_MONOTONE
CFL_SENSITIVITY_INCONCLUSIVE
```

Endpoint, forbidden-transition, reverse-flow, backend, and non-threshold guard outcomes
return only `CFL_SENSITIVITY_INCONCLUSIVE`.

## Approval boundary

```text
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
local_pc_checkpoint_completed = true
low_cfl_result_accepted = false
central_record_promotion_allowed = false
near_saturation_acoustic_continuity_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
