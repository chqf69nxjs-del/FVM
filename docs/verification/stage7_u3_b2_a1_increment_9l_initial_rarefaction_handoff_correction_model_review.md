# Stage 7 U3 B2 A1 Increment 9L initial rarefaction handoff correction

## Status

`MODEL_REVIEW_ONLY / IMPLEMENTATION_CLASSIFICATION_CORRECTION / NO PHYSICS OR TOLERANCE CHANGE`

## Failed precursor

The first Increment 9L end-to-end workflow was:

```text
source Git SHA:
74d636bf43d2eb4b47d6759a626ccd2ad79783a9

workflow run:
31686007487

job:
94402114920

artifact:
9175422808

artifact SHA256:
57e9d1900936195bb05ae426dc6efaa8881335890d137dcc6d27770b4c350f35
```

It stopped before accepting step 1 with:

```text
classification:
POSITIVE_SCAN_EVALUATION_FAILURE

message:
positive-pressure scan evaluation failed at node 1:
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
Adjacent-cell velocity is negative beyond the locked tolerance.
```

The initial state itself remained finite, positive, single-phase liquid, and unchanged.

## Classification

This is an implementation/classification-integration defect, not a physical or model failure.

At the uniform initial state:

```text
interior velocity = 0
interior pressure > back pressure
```

The established connected-rarefaction path supplies the physical outward root. Positive-pressure compression candidates imply a negative characteristic velocity and are therefore correctly rejected by B1. The first Increment 9L controller incorrectly invoked the later three-branch positive-side classification before exhausting the connected-rarefaction path, and treated an expected excluded compression candidate as a fatal initial-state error.

No evidence supports changing B1, its reverse-velocity guard, any tolerance, the locked B2 contract, or the physical scope.

## Correction

The public boundary state remains:

```text
OUTWARD_FLOW
```

The internal `THREE_BRANCH_WAVE_MODEL` gains an explicit algorithmic handoff:

```text
CONNECTED_RAREFACTION
    |
    | exact existing connected-root classification:
    | sign_changes = 0
    v
GENERAL_THREE_BRANCH_CLASSIFICATION
    rarefaction / neutral endpoint / weak compression
```

This is not a public boundary-state transition and is not a switch to finite compression or closure.

The connected-rarefaction stage shall use the unchanged existing function:

```text
u3_b2_characteristic_port_two_l_over_c0._solve_two_l_over_c0_root
```

It shall continue until that exact path raises the established no-root message family:

```text
connected subsonic scan did not retain exactly one root branch
sign_changes=0
```

Only that exact classification authorizes the internal handoff to the existing three-branch classifier for the same requested step. The failed connected solve supplies no flux and causes no solver-state mutation.

All other connected-rarefaction failures remain fail-closed.

## Invariants

The correction shall preserve:

```text
public state machine:
OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED

finite-compression switch trigger:
FINITE_COMPRESSION_MODEL_REQUIRED

closure trigger:
NO_ADMISSIBLE_ISLAND

re-entry:
disabled

reverse mass transfer:
disabled
```

The correction shall not change:

```text
B1 equations or guards
production adapter
FvmSolver core
locked B2 contract
root tolerance
velocity tolerance
chi cap
scan node counts
Hugoniot equations
zero-transfer flux identity
```

## Evidence requirement

The corrected artifact shall record an internal handoff event with:

```text
from_algorithm = CONNECTED_RAREFACTION
to_algorithm = GENERAL_THREE_BRANCH_CLASSIFICATION
trigger = CONNECTED_ROOT_SIGN_CHANGES_ZERO
absolute_step_number_trigger_used = false
failed_candidate_used_as_flux = false
solver_state_mutated_before_handoff = false
```

The end-to-end state-machine success conditions from the original Increment 9L model review remain unchanged.

## Formal-state boundary

All formal verification, acceptance, validation, approval, design-use, and production-activation states remain false.
