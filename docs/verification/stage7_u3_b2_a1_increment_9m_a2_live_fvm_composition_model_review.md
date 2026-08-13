# Stage 7 U3 B2 A1 Increment 9M A2 live FVM composition

## Status

`MODEL_REVIEW_ONLY / END-TO-END TOOL INTEGRATION / NO NEW PHYSICS / NOT VERIFICATION`

## Objective

Increment 9M A0 established a solver-independent `PhysicsBoundaryModelManager`.

Increment 9M A1 established transactional selection and transition routing to the existing Increment 9L preparation delegates.

Increment 9M A2 shall place that manager/composer in the actual `FvmSolver` external-face-flux path and reproduce the authoritative Increment 9L trajectory from the locked initial state to nominal `2L/c0`.

The target structure is:

```text
locked initial state
        |
        v
one unchanged FvmSolver instance
        |
        v
model-managed boundary hook
        |
        +-- A0 PhysicsBoundaryModelManager
        +-- A1 transactional delegate composer
        +-- existing Increment 9L delegates
        |
        v
actual accepted FVM steps to 2L/c0
```

A2 is an integration-equivalence increment. It does not add physical freedom or increase the physical authority of Increment 9L.

## Authoritative parents

### Increment 9L behavioral authority

```text
source Git SHA:
512723f35addb63fd55f86468c69feb6d24fd457

workflow run / job:
31700264132 / 94447447243

artifact ID:
9181655488

artifact name:
u3-b2-a1-increment-9l-state-based-clean-31700264132

artifact SHA256:
36b8276998871e2939fc7755644d5910689838d78f967e025d2e5ce08f0b89f3

starting state SHA256:
deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21

final state SHA256:
8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014

accepted steps:
640

final time:
0.004285834855172021 s

outcome:
INCREMENT_9L_PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE_PASS
```

The parent artifact is comparison authority only. A2 may not load its conserved state as an initial condition or checkpoint.

### Increment 9M A0 control authority

```text
source Git SHA:
9c0642e68eaece2cec3e8e8a6cc8c0141842b327

workflow run / job:
31712019865 / 94487133725

result:
17 passed
```

### Increment 9M A1 composition authority

```text
source Git SHA:
f75c0674829253aff319fa0b6cc3c3354650d83e

workflow run / job:
31716110925 / 94501160218

result:
32 passed
```

## Reused physics boundary

A2 shall reuse the existing Increment 9L hook lineage, including:

```text
connected rarefaction handoff
general three-branch classification
weak-compression model
general-EOS finite-compression Hugoniot model
Guard-front topology correction
bounded B1-success-window fallback
zero-transfer closed boundary model
trial-state and conservation gates
```

A2 shall not duplicate or alter those equations, root searches, flux formulae, tolerances, scan counts, or admissibility rules.

## Live hook composition

A2 shall provide a subclass of the retained Increment 9L bounded-window hook.

The live hook shall own:

```text
one PhysicsBoundaryModelManager
one Increment9LHookDelegateAdapter
one ModelManagedIncrement9LDelegateComposer
```

Its `_ensure_root(U, t)` path shall:

1. honor the existing cache identity check;
2. submit the same `U`, `t`, and observed requested step to the A1 composer;
3. allow only the A0-registered transition classifications;
4. receive a successful copied delegate context;
5. commit the manager transition transactionally;
6. restore the exact successful context and flux to the live hook cache;
7. return control to the unchanged `FvmSolver` path.

No absolute step number, hard-coded time, or parent checkpoint may select a model.

## Exact successful-context restoration

A1 intentionally invalidates the wrapped legacy cache when synchronizing the committed manager selection. That behavior is harmless for isolated A1 results but would discard the successful flux before a live FVM step.

A2 therefore selects the predeclared restoration approach:

```text
successful delegate context
        |
        | shallow copy returned by A1 composer
        v
manager transition commit
        |
        | legacy cache invalidated by selection sync
        v
restore the exact successful context through
existing hook._install_context(context, U, t)
```

The restoration shall:

```text
reuse the exact successful context values
copy the exact successful flux values
restore cache time and outlet-state identity
perform no root reconstruction
perform no EOS reconstruction
perform no flux modification
```

The A2 manager/composer may add evidence metadata to the copied context. It may not change physical fields.

## Legacy evidence compatibility

The retained Increment 9L runner and postprocessors audit legacy event lists.

For each manager transition committed during a live evaluation, A2 shall append one compatibility event to the corresponding legacy evidence list:

```text
OUTWARD_FLOW_MODEL transition
    -> outward_model_transition_events

BOUNDARY_REGIME transition
    -> boundary_transition_events
```

The event shall preserve:

```text
observed requested step
solver time
from/to state
trigger classification
original delegate trigger message
absolute_step_number_trigger_used = false
```

For public closure it shall also record:

```text
failed_candidate_used_as_root = false
failed_candidate_used_as_flux = false
solver_state_mutated_before_transition = false
reentry_allowed = false
```

These compatibility records are evidence only; the authoritative control state remains the A0 manager.

## Transition sequence

The expected manager sequence remains exactly:

```text
initial:
LIQUID / SINGLE_PHASE_FVM /
OUTWARD_FLOW / THREE_BRANCH_WAVE_MODEL

transition 1:
axis = OUTWARD_FLOW_MODEL
trigger = FINITE_COMPRESSION_MODEL_REQUIRED
THREE_BRANCH_WAVE_MODEL
    -> GENERAL_EOS_FINITE_COMPRESSION

transition 2:
axis = BOUNDARY_REGIME
trigger = NO_ADMISSIBLE_ISLAND
OUTWARD_FLOW
    -> ZERO_TRANSFER_CLOSED
```

Observed step and time shall be compared to the parent as behavioral evidence, but shall not authorize either transition.

## End-to-end execution

A2 shall build the locked `LIQUID_SMALL_DROP` initial state from the locked B2 contract and start at:

```text
t = 0
solver step = 0
```

It shall use one `FvmSolver` instance and run by actual accepted steps to:

```text
2L/c0 = 0.004285834855172021 s
```

The final accepted step shall use the unchanged target clipping policy.

## Exact behavioral-equivalence gate

A2 shall download and verify the immutable Increment 9L parent artifact, then compare at least:

```text
starting state SHA256
final state SHA256
accepted step count
final solver step
final solver time
horizon error
public boundary-state counts
outward internal-model counts
accepted branch counts
transition count
transition axes
transition from/to states
transition classifications
observed transition steps and times
closed mass-flux identity
closed energy-flux identity
closed vapor-flux identity
closed wall-momentum identity
maximum halving count
step and cumulative conservation gates
positivity gates
liquid-phase gate
rho*xv exact-zero gate
```

The required final-state comparison is exact SHA256 identity.

```text
A2 final state SHA256
    == Increment 9L final state SHA256
```

Approximate numerical equivalence is not authorized in A2. Any mismatch shall stop for review.

## Required A2 evidence

The immutable A2 artifact shall contain the retained Increment 9L evidence plus at least:

```text
model_manager_transition_events.csv
model_manager_selection_history.csv
increment_9m_a2_behavioral_comparison.json
increment_9m_a2_live_composition.json
parent_authority_verification.json
summary.json
report.md
artifact_sha256.txt
```

The A2 summary shall identify the result as:

```text
INCREMENT_9M_A2_EXACT_INCREMENT_9L_BEHAVIORAL_EQUIVALENCE_PASS
```

only when every exact-equivalence and engineering gate passes.

## Fail-closed boundary

A2 shall stop without manager or solver-state disguise for:

```text
unsupported delegate classification
wrong transition trigger
transition ordering failure
manager/context identity mismatch
successful-context restoration mismatch
missing or nonfinite flux
parent artifact authority mismatch
starting-state SHA mismatch
final-state SHA mismatch
accepted-step or transition-sequence mismatch
conservation failure
positivity loss
phase/EOS scope departure
multiple roots or multiple admissible islands
unknown exception
```

## Source-scope boundary

A2 may add a verification-side live hook wrapper, runner, workflow, tests, and closeout records.

It shall not modify:

```text
src/liquid_gas_transient/physics_model_manager.py
A1 delegate-composition source
Increment 9L physics delegate sources
FvmSolver core
B1 component
locked B2 contract
production B2 adapter
EOS equations
Hugoniot equations
root tolerances
chi scope
src/liquid_gas_transient/__init__.py
```

## A2 success status

A successful result may be recorded as:

```text
IMPLEMENTED
MODEL-MANAGED LIVE FVM COMPOSITION EXECUTED
EXACT INCREMENT 9L BEHAVIORAL EQUIVALENCE PASS
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
NOT VERIFIED
NOT ACCEPTED
NOT VALIDATED
NOT APPROVED
```

## Formal-state boundary

Regardless of exact behavioral equivalence, retain:

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

A2 changes architecture and integration evidence only. It does not independently verify or validate the physical model.