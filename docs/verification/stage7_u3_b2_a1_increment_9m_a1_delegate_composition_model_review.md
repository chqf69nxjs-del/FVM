# Stage 7 U3 B2 A1 Increment 9M A1 delegate composition

## Status

`MODEL_REVIEW_ONLY / VERIFICATION-SIDE INTEGRATION / NO NEW PHYSICS / NOT END-TO-END`

## Objective

Increment 9M A0 separated model-selection state and transition authorization from the Increment 9L verification runner.

Increment 9M A1 shall connect that pure manager to the existing Increment 9L verification-side physics preparation methods without copying or modifying their equations, root searches, fluxes, or gates.

The target structure is:

```text
PhysicsBoundaryModelManager
        |
        | current selection
        v
Increment 9L existing delegate adapter
        |
        +-- _prepare_three_branch
        +-- _prepare_finite
        +-- _prepare_closed
        |
        | classification request
        v
registered manager transition
        |
        `-- retry the same evaluation request with the selected delegate
```

A1 is an integration-semantics increment. It does not execute the full pipe trajectory and does not increase the physical authority established by Increment 9L.

## Authoritative parents

### Increment 9L behavioral parent

```text
source Git SHA:
512723f35addb63fd55f86468c69feb6d24fd457

workflow run / job:
31700264132 / 94447447243

artifact ID:
9181655488

artifact SHA256:
36b8276998871e2939fc7755644d5910689838d78f967e025d2e5ce08f0b89f3

outcome:
INCREMENT_9L_PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE_PASS
```

### Increment 9M A0 control parent

```text
A0 authoritative source Git SHA:
9c0642e68eaece2cec3e8e8a6cc8c0141842b327

workflow run / job:
31712019865 / 94487133725

result:
17 passed

status:
IMPLEMENTED / CONTROL-LAYER SEMANTICS TESTED / NOT END-TO-END
```

## Existing delegate boundary

A1 shall invoke the existing Increment 9L preparation methods as bound delegates:

```text
_prepare_three_branch(U, t)
_prepare_finite(U, t)
_prepare_closed(U, t)
```

The adapter may read the context installed by those methods and may attach manager/evidence metadata to a copied context dictionary.

It may not alter:

```text
flux values
root values
B1 state
Hugoniot equations
candidate admissibility
root topology
fallback classifications
closed-state pressure traction
trial-state validation
accepted-step bookkeeping
```

A1 shall not duplicate detailed weak-compression, finite-compression, or closed-flux equations in the manager or composer.

## Selection routing

The manager selection exclusively determines which delegate is requested:

```text
boundary = OUTWARD_FLOW
outward model = THREE_BRANCH_WAVE_MODEL
    -> _prepare_three_branch

boundary = OUTWARD_FLOW
outward model = GENERAL_EOS_FINITE_COMPRESSION
    -> _prepare_finite

boundary = ZERO_TRANSFER_CLOSED
    -> _prepare_closed
```

Observed solver time and step are passed to the delegate and recorded in transition evidence, but do not select a delegate or authorize a transition.

## Transition interception

The legacy Increment 9L preparation methods currently request transitions through their internal transition callbacks.

A1 shall intercept only those callbacks and convert them into explicit integration requests:

```text
_switch_outward_model(...)
    -> OUTWARD_FLOW_MODEL transition request

_transition_to_closed(...)
    -> BOUNDARY_REGIME transition request
```

The intercepted callback shall not mutate the legacy hook state or construct a target-model flux.

Exactly the A0-registered classifications remain supported:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
NO_ADMISSIBLE_ISLAND
```

All other classifications remain explicit failures.

## Transactional composition

A1 shall stage delegate-requested transitions in a shadow manager before mutating the authoritative manager.

```text
real manager snapshot
        |
        v
shadow manager replay
        |
        v
source delegate evaluation
        |
        +-- supported transition request
        |       -> apply to shadow
        |       -> retry same U / t / observed step
        |
        +-- target delegate success
        |       -> validate context identity
        |       -> commit staged transitions to real manager
        |
        `-- any failure
                -> restore adapter to real selection
                -> real manager unchanged
```

This gives the integration layer atomic behavior for one evaluation request:

```text
unsupported source outcome         -> no manager mutation
wrong transition trigger           -> no manager mutation
target delegate failure            -> no manager mutation
context/selection identity mismatch -> no manager mutation
successful transition chain        -> ordered commit exactly once
```

The solver conserved state is outside A1 and is never mutated by this composer.

## Context identity gate

Before transition commit, the returned copied context shall agree with the staged manager selection.

```text
context public_boundary_state
    == staged boundary regime

when OUTWARD_FLOW:
context outward_internal_model
    == staged outward-flow model

when ZERO_TRANSFER_CLOSED:
context outward_internal_model
    is None or absent
```

A mismatch is an integration/bookkeeping failure, not an accepted approximate equivalence.

## Evidence metadata

A successful composed result may add only control/evidence fields to the copied context:

```text
model_manager_profile
model_manager_selection
model_manager_transition_events_for_request
model_manager_transition_count_for_request
absolute_step_number_trigger_used = false
physics_flux_modified_by_manager = false
delegate_source = INCREMENT_9L_EXISTING_PREPARE_METHODS
```

The original delegate context and flux object shall not be modified in place.

## Required A1 tests

A1 shall demonstrate at least:

```text
initial selection routes to three-branch delegate
preselected finite state routes to finite delegate
preselected closed state routes to closed delegate
finite transition retries the same request with finite delegate
finite + closure transition chain retries the same request with closed delegate
transition order is preserved
arbitrary observed step numbers do not change authorization
unsupported delegate outcome leaves manager unchanged
wrong trigger leaves manager unchanged
target delegate failure rolls back staged transition
context identity mismatch rolls back staged transition
re-entry and repeated transitions remain rejected
result metadata is serializable
adapter does not import/copy detailed physics equations
```

Test doubles may emulate the bound method contract to isolate composition semantics. Actual numerical equivalence with the real Increment 9L trajectory is deferred to A2.

## A1 success status

A successful A1 may be recorded as:

```text
IMPLEMENTED
DELEGATE COMPOSITION SEMANTICS TESTED
TRANSACTIONAL TRANSITION ROUTING TESTED
NOT END-TO-END
NOT VERIFIED
NOT ACCEPTED
```

## Source-scope boundary

A1 may add a verification-side composer, tests, CI, and closeout records.

It shall not modify:

```text
src/liquid_gas_transient/physics_model_manager.py
FvmSolver core
B1 component
locked B2 contract
Increment 9L physics delegate source
EOS equations
Hugoniot equations
root tolerances
chi scope
production adapter
src/liquid_gas_transient/__init__.py
```

## Deferred A2 work

A2 shall instantiate the real Increment 9L delegate/hook composition and run from the locked initial state to nominal `2L/c0`.

A2 must compare against the Increment 9L authority for:

```text
accepted step count
transition sequence and classifications
branch/model sequence
final time
final state SHA or separately reviewed exact-equivalence failure
conservation residuals
closed-flux identities
```

A1 does not claim these results.

## Formal-state boundary

All formal verification, acceptance, validation, design-use, and production-activation fields remain false.