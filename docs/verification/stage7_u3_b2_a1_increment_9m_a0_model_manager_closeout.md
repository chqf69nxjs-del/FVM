# Stage 7 U3 B2 A1 Increment 9M A0 model-manager closeout

## Status

```text
IMPLEMENTED
CONTROL-LAYER SEMANTICS TESTED
NOT END-TO-END
NOT VERIFIED
NOT ACCEPTED
NOT VALIDATED
NOT APPROVED
```

## Objective completed

Increment 9M A0 extracted the model-selection decision state from the Increment 9L verification runner into a solver-independent package module.

```text
src/liquid_gas_transient/physics_model_manager.py
```

The module imports neither CoolProp nor `FvmSolver` and does not modify `src/liquid_gas_transient/__init__.py`.

## Activated freedom

A0 contains only the model freedom already demonstrated by Increment 9L.

```text
thermodynamic regime:
LIQUID fixed

bulk model:
SINGLE_PHASE_FVM fixed

outward-flow model:
THREE_BRANCH_WAVE_MODEL
  -> GENERAL_EOS_FINITE_COMPRESSION
trigger: FINITE_COMPRESSION_MODEL_REQUIRED

public boundary:
OUTWARD_FLOW
  -> ZERO_TRANSFER_CLOSED
trigger: NO_ADMISSIBLE_ISLAND
```

Closure requires the finite-compression model to be active. Re-entry, repeated transitions, wrong triggers, invalid observation metadata, and unsupported ordering are rejected without changing manager state or history.

Solver step and time are retained only as event evidence. Every accepted event records:

```text
absolute_step_number_trigger_used = false
```

## Tests

The focused test set covers:

```text
deterministic initial selection
expected two-transition sequence
step-number-independent authorization
ordered and JSON-serializable history
wrong-trigger atomic rejection
closure-order precondition
repeated-transition rejection
re-entry rejection
invalid time/step observation rejection
immutable selection snapshots
no solver/property import dependency
```

Final result:

```text
17 passed in 0.17 s
```

## Authoritative CI

```text
source Git SHA:
9c0642e68eaece2cec3e8e8a6cc8c0141842b327

workflow:
Agent U3 B2 A1 Increment 9M A0 Model Manager Rerun

run:
31712019865

job:
94487133725

conclusion:
SUCCESS
```

All workflow steps passed:

```text
checkout with full history
Python 3.12.13 setup
source compile and diff checks
focused unit semantics
sample transition record
```

## Superseded failed workflow

The first workflow attempt is retained as historical evidence.

```text
run / job:
31711795047 / 94486359950

classification:
WORKFLOW_HISTORY_CHECKOUT_DEFECT
```

It stopped before compile or tests because shallow checkout did not contain the fixed Model Review parent commit. No implementation, numerical, or physical failure occurred. The correction added full-history checkout in a new workflow; model-manager source and tests were unchanged.

## Claim boundary

A0 establishes only reusable control-layer semantics. It does not connect to a physics delegate or execute a pipe trajectory.

The following remain false:

```text
finite_compression_branch_approved = false
multi_step_finite_compression_continuation_authorized = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Next controlled work

Increment 9M A1 shall compose this manager with the existing Increment 9L verification-side physics delegates.

```text
manager selection
  -> select existing outward-flow or closed delegate

delegate classification
  -> request registered manager transition

unsupported delegate outcome
  -> explicit stop without manager mutation
```

A1 must not duplicate root-search equations, change B1, modify `FvmSolver`, loosen a tolerance, or use absolute step/time transition rules.
