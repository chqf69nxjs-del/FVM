# Stage 7 U3 B2 A1 Working Tool W1 — A2 live backend specification

## Status

```text
PREDECLARED IMPLEMENTATION CONTRACT
W0 COMPLETE BASELINE
NO NEW PHYSICS
NOT FULL-HORIZON REGRESSION
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Baseline

```text
W0 closeout branch:
agent/u3-b2-a1-working-tool-w0

W0 closeout head:
b8eefcc046a09da9cca2e9065c9963c3c9a81630

A2 parent head:
a7e362d72b8fef627803bd7b9e8cf3595b0e5282

A2 authoritative execution source:
947b0f0bf006e8015c3c109e57a8aeb7460cca02
```

W1 starts from the completed W0 shell. It shall not modify the protected FVM, EOS, B1/B2, Physics Model Manager, A1 composer, Increment 9L delegates, or Increment 9M A2 implementation.

## Purpose

W1 connects the W0 backend-independent run contract to the retained Increment 9M A2 live FVM composition path.

The target data path is:

```text
WorkingToolCase
    -> public execute_case facade
    -> WorkingToolBackend.run_case(case)
    -> one FvmSolver
    -> ModelManagedLiveFvmHook
    -> PhysicsBoundaryModelManager
    -> A1 transactional composer
    -> existing Increment 9L delegates
    -> BackendRunData
    -> WorkingToolResult
    -> standard five-file result package
```

W1 proves live connection and public-result construction with a short canonical smoke trajectory. Full initial-state-to-2L/c0 behavioral regression remains W2 scope.

## Scope boundary

W1 supports only the canonical locked A2 liquid case represented through `WorkingToolCase`.

The backend shall fail closed unless the normal case input matches the retained locked A2 scope for:

- fluid and model profile;
- pipe length, diameter/area, and roughness;
- cell count, ghost-cell count, and CFL;
- initial pressure, temperature, and velocity;
- outlet back pressure, opening fraction, and discharge coefficient;
- positive time horizon and a sufficient operational step allowance.

This exact-input gate prevents W1 from implying that arbitrary user inputs are already supported by the A2 physics path.

## Public orchestration facade

A backend-independent public helper shall be added under `src/liquid_gas_transient/working_tool/`:

```text
execute_case(case, backend) -> WorkingToolResult
```

The helper shall:

- call only the `WorkingToolBackend.run_case(case)` protocol;
- contain no import from `tools.verification` or the A2 runner;
- convert `BackendRunData` to `WorkingToolResult`;
- inject the canonical `PROVISIONAL_ENGINEERING_MODEL` warning exactly once;
- preserve additional backend warnings;
- copy backend arrays and mappings into the public result boundary.

## W1 backend

The W1 backend shall be implemented on the verification/integration side and shall implement:

```text
WorkingToolBackend.run_case(case) -> BackendRunData
```

It may import the retained A2 live hook because dependency direction remains:

```text
verification/integration adapter -> public Working Tool contracts
```

The public Working Tool package shall not import the verification runner or authority metadata.

The backend shall reuse, not reimplement:

```text
ModelManagedLiveFvmHook
PhysicsBoundaryModelManager
ModelManagedIncrement9LDelegateComposer
existing Increment 9L preparation delegates
CoolPropSinglePhaseEOS
FvmSolver right external-face override seam
```

No root search, B1 law, Hugoniot equation, admissibility rule, flux formula, transition rule, or closure physics may be duplicated in W1.

## Canonical smoke execution

The authoritative W1 smoke target is eight accepted FVM steps from the exact canonical A2 initial state.

The smoke run shall:

- use exactly one `FvmSolver` instance;
- construct its initial conserved state from the normal `WorkingToolCase` pressure, temperature, velocity, geometry, and mesh inputs;
- require the starting-state SHA256 to equal the retained A2 starting-state SHA256;
- execute through the actual model-managed right-face hook;
- call the retained accepted-step hook commit method after each accepted solver step;
- stop after eight accepted steps, before the known later model transitions;
- not use checkpoint state, absolute step triggers, or verification artifact state.

Expected early-path observations:

```text
accepted steps: 8
manager transition count: 0
manager selection history count: 1
successful context restoration count: 8
public boundary regime: OUTWARD_FLOW
outward-flow model: THREE_BRANCH_WAVE_MODEL
```

The observed solver step remains evidence only.

## Backend result contract

The backend shall return structured:

- summary values;
- per-step scalar history;
- manager transition records;
- sampled state-history arrays;
- explicit W1 smoke-scope warning.

The public result package remains exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

It shall not contain parent workflow, parent artifact, or A2/9L exact-equivalence authority metadata.

## Mandatory warnings

Every W1 public result shall contain:

```text
PROVISIONAL_ENGINEERING_MODEL
WORKING_TOOL_W1_SMOKE_SCOPE
```

The W1 smoke warning shall state that only the short live connection was exercised and that the run is not a 2L/c0 regression, physical validation, or design-use approval.

## W1 completion gates

W1 is complete only when authoritative CI establishes all of the following:

1. W0 focused contract tests remain passing.
2. The public `execute_case` facade is backend-independent and verification-import-free.
3. Unsupported or noncanonical W1 case inputs fail closed before solver construction.
4. The canonical case starting-state SHA256 exactly matches the retained A2 starting state.
5. Exactly one FvmSolver executes eight accepted steps.
6. All eight steps use the A2 model-managed live hook and successful context restoration.
7. The manager has zero transitions and one initial selection during the short smoke trajectory.
8. Conservative state values remain finite, density/internal energy remain positive, liquid phase scope is retained, and `rho*xv` remains exact zero.
9. The public result carries both mandatory warnings and all formal authority flags remain false.
10. The standard five-file output package is produced without verification-only authority metadata.
11. Source scope contains only W1 documentation, the public runtime facade/export, W1 integration backend/harness/tests, and the W1 workflow.
12. A run, job, artifact ID, artifact digest, and internal evidence manifest are recorded.

## Permitted W1 closeout wording

```text
WORKING TOOL W1: COMPLETE

IMPLEMENTED
PUBLIC EXECUTION FACADE TESTED
A2 LIVE BACKEND CONNECTED
SHORT LIVE FVM SMOKE PASSED
STANDARD RESULT PACKAGE PRODUCED
AUTHORITATIVE CI PASSED

NOT FULL 2L/c0 REGRESSION TESTED
NOT VERIFIED
NOT ACCEPTED
NOT VALIDATED
NOT APPROVED
```

## Explicitly deferred to W2

```text
full 640-step / 2L/c0 execution through the public Working Tool path
exact A2 behavioral comparison
exact final-state SHA comparison
full transition sequence comparison
full conservation-residual comparison
selected evidence CSV exact comparison
```
