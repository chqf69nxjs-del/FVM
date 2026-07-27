# Stage 7 Gate 3 Numeric-Equivalence Capture

`DIAGNOSTIC ONLY; EXACT BASELINES UNCHANGED; NO GATE ACCEPTANCE`

## Purpose

The first Windows Gate 3 replay preserved formal outcomes, step counts, crossing
steps, crossing cells, and crossing positions, but differed from the
authoritative Ubuntu evidence in least-significant floating-point digits and
therefore in SHA256 values.

A second Windows replay using Python 3.12.10, NumPy 2.5.1, and CoolProp 8.0.0
reproduced the same Windows values. The Python and NumPy alignment did not
remove the difference. This capture therefore records complete histories on
both platforms so the remaining runtime/backend difference can be measured
without weakening any exact regression.

## Fixed execution

```text
source revision:     Gate 3 reviewed main/branch revision
mesh:                128 cells
CFL:                 0.10
maximum steps:       8000
final pressures:     2 / 3 / 4 MPa
spatial flux:        existing first-order Rusanov
property backend:    CoolProp 8.0.0
```

The capture calls the existing case runner directly and writes:

```text
scalar MeshCaseMetrics
time_history_s.npy
pressure_history_pa.npy
accepted_state_history.npy
runtime and Git provenance
exact comparison against the retained PR #82 scalar/hash contract
```

The exact PR #82 baseline assertion is not called by this diagnostic. It remains
unchanged in the existing baseline and forensic paths.

## Interpretation boundary

This artifact is not itself a `NUMERICALLY_EQUIVALENT` decision. Compare the
Ubuntu reference and Windows candidate for:

```text
formal outcome and failure category
step count and crossing event identity
crossing time, cell, and position
quality, void fraction, saturation margins, and sound-speed evidence
mass, momentum, energy, and vapor residuals
array shape and maximum absolute/relative differences
```

Until that comparison is reviewed:

```text
Gate_3_disposition = INVESTIGATION_REQUIRED
Gate_4_execution_paused = true
low_cfl_result_accepted = false
central_record_promotion_allowed = false
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
