# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4F authority inspection correction

## Status

`MODEL_REVIEW_ONLY / AUTHORITY_INSPECTION_CORRECTION / FIXED_BEFORE_RERUN`

This note corrects an authority-inspection mismatch in the first root-topology rerun workflow. It does not change the physical model, B1, the characteristic relation, the Weak Compression scope, any tolerance, the root algorithm, the production Adapter, `FvmSolver`, or any formal project state.

## Audited workflow

```text
workflow:
Agent U3 B2 A1 Weak Compression Bridge Increment 4F Root Topology Rerun

workflow run:
31620635130

job:
94194311714

source Git SHA:
b2294d17118ad28d64c82c54a4bc28bb29c1140d

conclusion:
failure
```

The workflow completed checkout, dependency installation, source-scope inspection, and all four parent-artifact downloads. It stopped in the read-only step:

```text
Inspect failed Increment 4F authority
```

The corrected full-horizon solver step was never executed in that run.

## Cause

The downloaded failed Increment 4F artifact is:

```text
workflow run:
31619671593

artifact ID:
9150769457

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-31619671593

GitHub artifact digest:
sha256:64ce6c2ee282163a841c3df518f27bd45eac6bf2e3c91a061ff3007bbab09034
```

Its `summary.json` records:

```text
solver_step_after:
451

pre_guard_front_reproduction_passed:
true

stop_classification:
GuardFrontContinuationStop

stop_reason:
GuardFrontContinuationStop: successful-domain compatibility residual is not monotone
```

The rerun workflow incorrectly required:

```text
stop_classification == GUARD_FRONT_SCAN_FAILURE
```

and also carried a non-authoritative archive digest value in its environment. The read-only assertion therefore failed before the corrected solver could run.

## Fixed inspection

The rerun must require the exact retained evidence:

```text
source_git_sha == 618f49c0a75620751cb517d669a4da868e82f41e
solver_step_after == 451
pre_guard_front_reproduction_passed == true
stop_classification == GuardFrontContinuationStop
stop_reason contains successful-domain compatibility residual is not monotone
GitHub artifact digest == sha256:64ce6c2ee282163a841c3df518f27bd45eac6bf2e3c91a061ff3007bbab09034
internal artifact SHA256 manifest passes
```

This correction changes authority inspection only. The same root-topology correction source must then be executed from the same authoritative Increment 3, corrected Increment 4E, and failed Increment 4D parents.

## Claim boundary

Until a workflow actually executes the corrected solver and produces a successful inspected artifact, the previously written full-horizon baseline record is not authoritative evidence of a completed run.

All formal states remain false:

```text
finite_compression_branch_approved = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
