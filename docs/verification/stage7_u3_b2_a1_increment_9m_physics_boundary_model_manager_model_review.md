# Stage 7 U3 B2 A1 Increment 9M Physics / Boundary Model Manager

## Status

`MODEL_REVIEW_ONLY / TOOL_INTEGRATION / NO NEW PHYSICS / NOT VERIFICATION`

## Objective

Increment 9L established an authoritative provisional engineering end-to-end working slice from the locked liquid initial state to nominal `2L/c0` using one actual `FvmSolver` trajectory and classification-driven model transitions.

Increment 9M shall convert that demonstrated path from a verification-script chain into a reusable tool architecture without adding physical freedom.

The goal is:

```text
current proven working delegates
    -> reusable model-selection / transition controller
    -> reusable boundary hook composition
    -> normal initial-state runner
    -> transition and warning event log
```

This increment is an integration/refactoring track. It does not claim stronger physical authority than Increment 9L.

## Authoritative behavioral parent

```text
Increment 9L source SHA:
512723f35addb63fd55f86468c69feb6d24fd457

workflow run:
31700264132

job:
94447447243

artifact ID:
9181655488

artifact name:
u3-b2-a1-increment-9l-state-based-clean-31700264132

artifact SHA256:
36b8276998871e2939fc7755644d5910689838d78f967e025d2e5ce08f0b89f3

outcome:
INCREMENT_9L_PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE_PASS
```

Increment 9M must preserve the Increment 9L physical/model assumptions and formal-state limits.

## Architecture rule

The model manager is a **control and evidence layer**, not a new physics layer.

It may:

```text
hold current model/regime state
validate explicitly supported transition triggers
record transition events
reject unsupported transitions
expose current selection to the boundary hook / runner
```

It may not:

```text
invent a root
modify a flux supplied by the selected model
change the EOS
change B1 behavior
change Hugoniot equations
change tolerances or chi scope
silently convert unknown errors into model transitions
```

## Controlled degrees of freedom

Increment 9M activates only the degrees of freedom already demonstrated by Increment 9L.

### Thermodynamic regime

```text
LIQUID
```

No liquid/two-phase or liquid/vapor transition is implemented in Increment 9M.

### Bulk solver model

```text
SINGLE_PHASE_FVM
```

No HEM, drift-flux, slip, or two-fluid bulk model is activated in Increment 9M.

### Public boundary regime

```text
OUTWARD_FLOW
    -> ZERO_TRANSFER_CLOSED
```

The transition is one-way.

### Internal outward-flow model

```text
THREE_BRANCH_WAVE_MODEL
    -> GENERAL_EOS_FINITE_COMPRESSION
```

This is an internal model transition while the public boundary remains `OUTWARD_FLOW`.

## Supported transition triggers

Exactly the following control transitions are supported in the first 9M profile:

```text
THREE_BRANCH_WAVE_MODEL
    -> GENERAL_EOS_FINITE_COMPRESSION
trigger = FINITE_COMPRESSION_MODEL_REQUIRED

OUTWARD_FLOW
    -> ZERO_TRANSFER_CLOSED
trigger = NO_ADMISSIBLE_ISLAND
```

Observed solver step and time are evidence fields only. An absolute solver step or hard-coded time may not authorize either transition.

Any unknown trigger, reverse transition, repeated transition, or unsupported target shall raise an explicit control-layer error and shall not mutate the manager state.

## Transition event contract

Each accepted model transition shall record at least:

```text
axis
from_state
to_state
trigger_classification
solver_time_s
observed_solver_step
absolute_step_number_trigger_used = false
```

Later integration layers may add physics-specific pre/post state identities and conservation-map residuals. A0 shall not fabricate fields it cannot establish.

## Increment 9M staged plan

### 9M A0 — pure model-manager semantics

Add an isolated reusable package module implementing only:

```text
current regime/model selection
allowed transition validation
one-way state mutation
transition history
event serialization
fail-closed unsupported transition behavior
```

A0 shall have no CoolProp dependency and shall not instantiate or modify `FvmSolver`.

Required unit semantics:

```text
initial selection is deterministic
arbitrary observed step numbers do not affect transition authorization
expected outward-model trigger succeeds exactly once
expected public closure trigger succeeds exactly once
wrong trigger fails without state mutation
re-entry fails
repeated transition fails
transition order is preserved
all recorded events mark absolute-step trigger false
```

A0 status on success:

```text
IMPLEMENTED / CONTROL-LAYER SEMANTICS TESTED / NOT END-TO-END
```

### 9M A1 — compose existing Increment 9L physics delegates

Connect the A0 manager to the existing verification-side outward-flow and zero-transfer delegates without changing their equations or gates.

A1 shall remain verification/integration-side until behavioral equivalence is demonstrated.

Required behavior:

```text
manager selection determines which existing delegate is queried
existing delegate classification requests a manager transition
failed/unsupported delegate outcomes remain fail-closed
no absolute step or checkpoint transition logic
```

A1 shall not duplicate the detailed root-search physics in the manager module.

### 9M A2 — reusable initial-state runner

Build one normal runner around the composed manager/hook and run from the locked initial state to nominal `2L/c0`.

A2 must reproduce the 9L working trajectory semantics:

```text
one FvmSolver instance
initial state, no checkpoint continuation
classification-driven internal model transition
classification-driven public boundary transition
no re-entry
no reverse mass-transfer model
same conservation / positivity / phase gates
same final target-time policy
```

Behavioral comparison shall include:

```text
accepted step count
transition count and trigger classes
branch/model sequence
final solver time
final state identity or explicitly reviewed numerical equivalence
conservation residuals
closed-flux identities
```

If exact final-state identity is lost solely because of integration/refactoring, the run shall stop for review. Approximate equivalence shall not be silently accepted.

## Source-scope boundary

Increment 9M may add new modules/tests/runners, but shall not modify without a separate predeclared review:

```text
FvmSolver core
B1 component
locked B2 contract
EOS equations
existing Hugoniot equations
existing root tolerances
chi scope
existing verified/reference artifacts
```

The first A0 implementation shall not modify `src/liquid_gas_transient/__init__.py`; direct module import is sufficient until the interface is stable.

## Fail-closed boundary

The model manager shall never turn the following into a supported transition merely because another model exists:

```text
nonfinite state
positivity loss
phase/EOS scope departure
multiple roots / multiple admissible islands
unknown exception
conservation gate failure
unregistered trigger
unregistered transition
```

A physical/model transition requires an explicitly registered classification in the active profile.

## Relationship to two-phase development

Increment 9M is intentionally single-phase. It creates an architecture into which a future thermodynamic-regime transition can be added, but it does not pre-authorize one.

A later liquid-to-two-phase increment should add only the minimum required new regime/model freedom and define its own:

```text
entry/exit criteria
conservative transition map
EOS consistency gate
continuity diagnostics
hysteresis/chatter policy
verification/validation scope
```

## Evidence requirements

A0 shall produce normal unit-test/CI evidence.

A1/A2 shall later produce immutable evidence including at least:

```text
model_selection_history.csv
model_transition_events.csv
boundary_state_history.csv
step_metrics.csv
summary.json
report.md
artifact_sha256.txt
```

Observed step numbers shall remain evidence, not acceptance criteria.

## Formal-state boundary

Regardless of A0/A1/A2 implementation success, Increment 9M does not independently promote B2 physical authority.

Retain:

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

## Increment 9M success interpretation

A2 success may be described as:

```text
PROVISIONAL ENGINEERING REUSABLE TOOL-INTEGRATION WORKING SLICE
```

It may not be described as `VERIFIED`, `ACCEPTED`, `VALIDATED`, or `APPROVED` without separate evidence and project decisions.
