# Stage 7 U3 B2 A1 Working Tool W2 — full-horizon A2 regression specification

## Status

```text
PREDECLARED IMPLEMENTATION CONTRACT
W1 COMPLETE BASELINE
NO NEW PHYSICS
NO INPUT-SCOPE GENERALIZATION
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Baseline

```text
W1 closeout branch:
agent/u3-b2-a1-working-tool-w1

W1 closeout head:
a9ca38a18634dae8006379997403b6d6dc0f1230

A2 authoritative execution source:
947b0f0bf006e8015c3c109e57a8aeb7460cca02

A2 authoritative run:
31719604102

A2 authoritative job:
94512927800

A2 authoritative artifact ID:
9189445884

A2 authoritative artifact name:
u3-b2-a1-increment-9m-a2-31719604102

A2 authoritative artifact digest:
sha256:4678ecd9f919ea513bed16652a1fe5b484d6c664b74209bf7dbaffa2dc0a2b64
```

W2 starts from the completed W1 Working Tool path. It shall not modify the
protected FVM, EOS, B1/B2, Physics Model Manager, A1 composer, Increment 9L
delegates, or Increment 9M A2 implementation.

## Purpose

W2 establishes that the normal public Working Tool path can run the exact
canonical A2 liquid case from the locked initial state to the nominal `2L/c0`
horizon and reproduce the immutable Increment 9M A2 authority exactly.

The normal execution path is:

```text
WorkingToolCase
    -> execute_case(case, backend)
    -> A2FullHorizonWorkingToolBackend.run_case(case)
    -> one FvmSolver
    -> ModelManagedLiveFvmHook
    -> PhysicsBoundaryModelManager
    -> A1 transactional composer
    -> existing Increment 9L delegates
    -> BackendRunData
    -> WorkingToolResult
    -> standard five-file public result package
```

The verification path remains separate:

```text
public Working Tool result
+ backend runtime evidence
+ immutable A2 authority artifact
    -> W2 external regression harness
    -> exact behavioral comparison evidence
```

The public Working Tool result shall not receive A2 workflow, job, artifact,
parent-authority, or exact-equivalence metadata.

## Canonical case scope

W2 accepts only the exact locked A2 liquid case expressed through the normal
`WorkingToolCase` contract.

Before constructing a solver, the backend shall fail closed unless the input
matches the retained locked scope for:

- fluid and model profile;
- pipe length, diameter, area, and roughness;
- cell count, ghost-cell count, and CFL;
- initial pressure, temperature, and velocity;
- outlet back pressure, opening fraction, and discharge coefficient;
- target time equal to the canonical `2L/c0` horizon;
- operational step allowance sufficient for the full run.

W2 does not authorize arbitrary case input, reverse flow, re-entry, two-phase
activation, a new near-zero-flow criterion, new closure physics, or new
hysteresis physics.

## Reuse boundary

W2 shall reuse, not duplicate:

```text
Working Tool public execute_case facade
W1 canonical case construction and fail-closed scope validation
ModelManagedLiveFvmHook
PhysicsBoundaryModelManager
ModelManagedIncrement9LDelegateComposer
existing Increment 9L preparation delegates
existing Increment 9L conservative run ledger
CoolPropSinglePhaseEOS
FvmSolver right external-face override seam
```

W2 may wrap the retained solver only to record accepted-state snapshots after
`FvmSolver.step()` returns. Such recording shall not alter a time step,
conserved state, flux, root, transition, or acceptance decision.

No root search, B1 law, Hugoniot relation, admissibility rule, flux formula,
transition trigger, closure rule, tolerance, or scope cap may be reimplemented
or changed.

## Full-horizon execution target

The authoritative W2 run shall start from the exact canonical initial state and
reach the exact A2 target:

```text
accepted steps:
640

final solver step:
640

target 2L/c0:
0.004285834855172021 s

final time:
0.004285834855172021 s

horizon error:
0.0 s
```

Expected manager transition sequence:

```text
1. outward_flow_model
   THREE_BRANCH_WAVE_MODEL
   -> GENERAL_EOS_FINITE_COMPRESSION
   trigger: FINITE_COMPRESSION_MODEL_REQUIRED

2. boundary_regime
   OUTWARD_FLOW
   -> ZERO_TRANSFER_CLOSED
   trigger: NO_ADMISSIBLE_ISLAND
```

Observed step/time values remain evidence only. Absolute step-number transition
conditions are forbidden.

## Public W2 result

The public package remains exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

The public result may report that the canonical full horizon was executed and
reached. It shall not report or imply that physical validation, design-use
acceptance, or formal verification was achieved.

Every W2 public result shall contain:

```text
PROVISIONAL_ENGINEERING_MODEL
WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_SCOPE
```

The W2 warning shall state that the execution is limited to the canonical
provisional single-phase case and remains not VERIFIED, ACCEPTED, VALIDATED, or
DESIGN-USE APPROVED.

## Runtime evidence retained outside the public package

The backend/harness may retain separate evidence for:

- exact initial and final conserved arrays;
- full per-step conservative ledger;
- public boundary-state history;
- legacy outward-model and boundary-transition events;
- manager transition and selection histories;
- successful context-restoration history;
- sampled or full accepted-state arrays;
- source and evidence SHA256 manifests.

This evidence is for regression authority only and shall not be inserted into
the normal user-facing `summary.json`.

## Immutable A2 authority comparison

The W2 harness shall verify live A2 artifact metadata before comparison:

```text
source SHA = 947b0f0bf006e8015c3c109e57a8aeb7460cca02
run = 31719604102
job = 94512927800
artifact ID = 9189445884
artifact name = u3-b2-a1-increment-9m-a2-31719604102
artifact digest = sha256:4678ecd9f919ea513bed16652a1fe5b484d6c664b74209bf7dbaffa2dc0a2b64
expired = false
```

The comparison shall include exact equality of at least:

```text
starting state SHA256
final state SHA256
accepted-step count
final solver step and time
target time and horizon error
public state counts
outward-model counts
outward branch counts
transition sequence and classifications
manager selection history
successful context-restoration count
closed-flux identities
positivity and liquid-phase scope
rho*xv exact zero
selected conservation-residual fields
selected evidence CSV content
initial and final NPZ arrays, dtypes, and shapes
```

CSV comparisons may use exact SHA256 equality after deterministic serialization.
NPZ container-file hashes shall not be used as the array-equivalence criterion;
contained arrays shall be compared directly.

## W2 completion gates

W2 is complete only when authoritative CI establishes all of the following:

1. Retained W0 and W1 focused tests remain passing.
2. Noncanonical W2 input fails closed before solver construction.
3. The normal public Working Tool path constructs exactly one FvmSolver.
4. The initial state SHA256 exactly matches the A2 authority.
5. The public path completes exactly 640 accepted steps and reaches `2L/c0`
   with zero horizon error.
6. The final state SHA256 and initial/final conserved arrays exactly match A2.
7. The two manager transitions and three manager selections exactly match A2.
8. Successful delegate-context restoration passes for all 640 accepted steps,
   with no root reconstruction or manager flux modification.
9. Public state, outward-model, and branch histories exactly match A2.
10. Selected conservation residuals and closed-boundary identities exactly
    match A2.
11. Selected deterministic evidence CSV files have exact SHA256 equality.
12. The public package contains exactly five standard result files, both
    mandatory warnings, and no verification-only authority metadata.
13. All public formal-authority flags remain false.
14. Source scope contains only W2 documentation, W2 integration backend,
    regression harness/tests, and W2 workflow changes.
15. A clean run, job, artifact ID, artifact digest, and internally verifiable
    evidence manifests are recorded.

## Permitted W2 closeout wording

```text
WORKING TOOL W2: COMPLETE

IMPLEMENTED
PUBLIC FULL-HORIZON PATH TESTED
CANONICAL 2L/c0 EXECUTION PASSED
EXACT A2 BEHAVIORAL REGRESSION PASSED
STANDARD RESULT PACKAGE PRODUCED
AUTHORITATIVE CI PASSED

NOT PHYSICALLY VALIDATED
NOT DESIGN-USE ACCEPTED
NOT PRODUCTION APPROVED
```

The W2 exact A2 regression is a software/trajectory regression result. It does
not promote the underlying provisional physical model to VERIFIED, ACCEPTED,
VALIDATED, APPROVED, or design-use status.

## Deferred after W2

W2 does not itself provide arbitrary-input tool generalization or productization.
Later increments may address, under separate predeclared scope:

```text
case-file loading and CLI ergonomics
output sampling and storage policy
broader supported input envelopes
additional boundary/equipment models
near-zero-flow technical debt
controlled re-entry and reverse flow
two-phase activation
physical/reference validation
design-use acceptance
Working Tool v0 packaging and user documentation
```
