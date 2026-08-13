# Stage 7 U3 B2 A1 Increment 9M A1 delegate-composition closeout

## Status

```text
IMPLEMENTED
DELEGATE COMPOSITION SEMANTICS TESTED
TRANSACTIONAL TRANSITION ROUTING TESTED
NOT END-TO-END
NOT VERIFIED
NOT ACCEPTED
NOT VALIDATED
NOT APPROVED
```

## Objective completed

Increment 9M A1 connected the Increment 9M A0 `PhysicsBoundaryModelManager` to the existing Increment 9L verification-side preparation methods without copying their physical equations, root searches, flux construction, or admissibility gates.

The implementation is:

```text
tools/verification/
u3_b2_a1_increment_9m_a1_delegate_composition.py
```

The existing Increment 9L delegates remain authoritative for their own calculations:

```text
_prepare_three_branch(U, t)
_prepare_finite(U, t)
_prepare_closed(U, t)
```

A1 selects and invokes those bound methods; it does not reimplement them.

## Manager/delegate composition

The implemented routing is:

```text
manager selection
    |
    +-- OUTWARD_FLOW / THREE_BRANCH_WAVE_MODEL
    |       -> existing _prepare_three_branch
    |
    +-- OUTWARD_FLOW / GENERAL_EOS_FINITE_COMPRESSION
    |       -> existing _prepare_finite
    |
    `-- ZERO_TRANSFER_CLOSED
            -> existing _prepare_closed
```

Legacy transition callbacks are intercepted only on the wrapped hook instance:

```text
_switch_outward_model(...)
    -> manager transition request

_transition_to_closed(...)
    -> manager transition request
```

The supported classifications remain exactly:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
NO_ADMISSIBLE_ISLAND
```

No observed solver step or time authorizes a transition. They are recorded as evidence only.

## Transactional behavior

A1 replays the authoritative manager history into a shadow manager and evaluates the selected delegate against that staged selection.

```text
real manager snapshot
        |
        v
shadow manager
        |
        v
selected existing delegate
        |
        +-- supported transition request
        |       -> apply only to shadow
        |       -> retry same U / t / observed step
        |
        +-- target delegate succeeds
        |       -> validate returned context identity
        |       -> commit staged transitions to real manager
        |
        `-- any failure
                -> real manager remains unchanged
```

The following were demonstrated as atomic fail-closed outcomes:

```text
unsupported delegate classification
wrong registered trigger
failure of the target delegate after a staged transition
returned context inconsistent with staged selection
invalid observation metadata
```

In each case, the real manager selection and transition history remain unchanged.

## Evidence metadata

A successful composed result adds only copied control/evidence fields:

```text
model_manager_profile
model_manager_selection
model_manager_transition_events_for_request
model_manager_transition_count_for_request
absolute_step_number_trigger_used = false
physics_flux_modified_by_manager = false
delegate_source = INCREMENT_9L_EXISTING_PREPARE_METHODS
```

The delegate-installed source context is not modified in place.

## Tests

The focused test inventory combines the 17 A0 tests with 15 A1 composition tests.

A1 coverage includes:

```text
initial three-branch routing
preselected finite routing
preselected closed routing
three-branch -> finite retry of the same request
three-branch -> finite -> closed chain
ordered transition commit
arbitrary observed-step independence
unsupported outcome rollback
wrong-trigger rollback
target-delegate-failure rollback
context-selection-mismatch rollback
invalid observation rollback
serializable evidence metadata
source-context immutability
missing legacy-method rejection
```

Final result:

```text
32 passed in 0.22 s
```

## Authoritative CI

```text
source Git SHA:
f75c0674829253aff319fa0b6cc3c3354650d83e

branch:
agent/u3-b2-a1-9m-a1

workflow:
Agent U3 B2 A1 Increment 9M A1 Delegate Composition

run:
31716110925

job:
94501160218

conclusion:
SUCCESS
```

All workflow stages passed:

```text
full-history checkout
Python 3.12.13 setup
existing-source protection and compile
verification that A1 calls but does not redefine 9L delegates
absence of CoolProp / FvmSolver / absolute-step transition logic in A1
A0 and A1 focused tests
```

## Superseded failed CI attempt

The first A1 CI attempt is retained as immutable historical evidence:

```text
source Git SHA:
fa3bf91c1a1f89c722e643e6bd533158a479210f

run / job:
31715828549 / 94500175123

classification:
TEST_BOOKKEEPING_DEFECT
```

The test module used an invalid pytest parameter-name expression:

```text
@pytest.mark.parametrize((plan, expected), ...)
```

instead of a supported parameter-name declaration. Collection stopped before the A1 tests executed.

The following checks had already passed in that run:

```text
source compilation
protected-source diff checks
delegate-only structure checks
```

The correction changed only the test declaration. It did not change the manager, delegate composer, transition logic, physics, root search, or flux behavior.

## Protected-source confirmation

Relative to the completed A0 head, A1 did not modify:

```text
src/liquid_gas_transient/physics_model_manager.py
src/liquid_gas_transient/__init__.py
tools/verification/u3_b2_a1_increment_9l_two_state_boundary_state_machine.py
FvmSolver core
B1 component
locked B2 contract
production B2 adapter
EOS or Hugoniot equations
root tolerances
chi scope
```

## Important A2 integration boundary

A1 validates composition semantics using copied delegate contexts. It does not yet place the composer in the live `FvmSolver` boundary-flux path.

The current adapter synchronizes the wrapped legacy hook after a successful manager commit by invalidating its cache. In A1 this is harmless because the successful copied context is the result authority.

Before A2 connects the composer directly to `FvmSolver`, the integration must explicitly review how the successful delegate context and flux remain installed after manager commit. A2 shall not silently discard or reconstruct that flux.

Permitted A2 approaches include, after predeclared review:

```text
commit manager selection without invalidating the successful delegate context
or
restore the exact successful delegate context / flux after commit
```

Whichever approach is selected must reproduce Increment 9L exactly or stop for review.

## Claim boundary

A1 establishes only reusable delegate-selection and transactional transition semantics.

It does not demonstrate:

```text
a live FvmSolver step through the new composer
initial-state to 2L/c0 execution
final-state identity with Increment 9L
conservation equivalence in the composed runner
closed-flux identity in the composed runner
physical verification or validation
```

All formal state fields remain false:

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

Increment 9M A2 shall compose the real Increment 9L hook with the A0 manager and A1 composer, then run one actual `FvmSolver` trajectory from the locked initial state to nominal `2L/c0`.

A2 must compare against the authoritative Increment 9L result for:

```text
accepted step count = 640
transition classifications and order
public-state history
outward-model history
final solver time
final state SHA256
step and cumulative conservation residuals
closed mass / energy / vapor flux exact-zero identities
wall momentum identity
positivity and liquid-phase gates
```

Any integration-induced difference in final state or transition history shall stop for explicit review rather than being accepted approximately.
