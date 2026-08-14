# Stage 7 U3 B2 A1 Working Tool W1 closeout

## Status

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

## Scope

Working Tool W1 connects the completed W0 public shell to the retained Increment 9M A2 model-managed live FVM path.

The established execution path is:

```text
WorkingToolCase
    -> execute_case(case, backend)
    -> A2LiveWorkingToolBackend.run_case(case)
    -> one FvmSolver
    -> ModelManagedLiveFvmHook
    -> PhysicsBoundaryModelManager
    -> A1 transactional composer
    -> existing Increment 9L delegates
    -> BackendRunData
    -> WorkingToolResult
    -> standard five-file result package
```

W1 is intentionally a short canonical live-connection increment. The full initial-state-to-2L/c0 execution and exact A2 behavioral regression remain W2 scope.

## Baseline and authoritative source

```text
branch:
agent/u3-b2-a1-working-tool-w1

W0 closeout head:
b8eefcc046a09da9cca2e9065c9963c3c9a81630

A2 parent head:
a7e362d72b8fef627803bd7b9e8cf3595b0e5282

authoritative W1 execution source SHA:
c61b178c256980db900b4d6fc45398ad52e775d4
```

The W1 source-scope gate passed against the W0 closeout head. The authoritative source differs only in:

- W1 documentation;
- the public `execute_case` facade and export;
- W1 integration backend, tests, and smoke harness;
- the W1 GitHub Actions workflow.

Protected FvmSolver, EOS, B1/B2, Physics Model Manager, A1 composer, Increment 9L delegate, and Increment 9M A2 implementation sources were not modified.

## Public execution facade

W1 adds the backend-independent public entry point:

```text
execute_case(case, backend) -> WorkingToolResult
```

The public facade depends only on the W0 public contracts. It does not import the A2 verification runner, workflow metadata, authority artifacts, or parent evidence.

It:

- invokes only `WorkingToolBackend.run_case(case)`;
- converts `BackendRunData` to `WorkingToolResult`;
- inserts `PROVISIONAL_ENGINEERING_MODEL` exactly once;
- preserves additional backend warnings;
- copies backend mappings and arrays across the public result boundary.

## Canonical W1 backend scope

The W1 backend accepts only the exact locked A2 liquid case expressed through normal `WorkingToolCase` fields.

Before constructing a solver it fail-closes noncanonical values for:

- fluid and model profile;
- pipe geometry and area;
- cells, ghost cells, and CFL;
- initial pressure, temperature, and velocity;
- back pressure, opening fraction, and discharge coefficient;
- target horizon and operational step allowance.

This narrow gate prevents W1 from implying support for arbitrary user cases before W2 and later generalization increments.

## Authoritative GitHub Actions evidence

```text
workflow:
Agent U3 B2 A1 Working Tool W1 Live Backend

workflow file:
.github/workflows/agent-u3-b2-a1-working-tool-w1.yml

run:
31762074867

job:
94650363932

run conclusion:
SUCCESS

job conclusion:
SUCCESS
```

All retained job steps completed successfully, including:

- Verify W1 source scope
- Compile W1 sources
- Run W0 and W1 focused tests
- Run authoritative W1 eight-step smoke
- Inspect W1 result and separation gates
- Record source metadata and evidence manifest
- Upload W1 evidence

## Authoritative artifact

```text
artifact ID:
9204978491

artifact name:
u3-b2-a1-working-tool-w1-31762074867

artifact digest:
sha256:2487d40b1f9f2c2b2830528dbd1b85d67f20ddffaf569e4885da2f41dc25c5e8

expired at closeout:
false
```

The artifact-recorded source SHA is exactly:

```text
c61b178c256980db900b4d6fc45398ad52e775d4
```

Artifact contents include:

```text
changed_paths.txt
pytest.log
pytest.xml
smoke-console.log
source_git_sha.txt
workflow_artifact_sha256.txt
smoke/
    artifact_sha256.txt
    case.json
    w1_smoke_evidence.json
    public-result/
        summary.json
        history.csv
        transitions.csv
        warnings.csv
        state_history.npz
```

Both artifact manifests were recomputed from their extracted roots and passed exactly:

```text
workflow_artifact_sha256.txt: PASS
smoke/artifact_sha256.txt: PASS
```

The initial successful W1 run exposed only a workflow-level manifest path-prefix bookkeeping issue. It was classified explicitly as implementation/bookkeeping, corrected without changing physics, numerics, trajectory, or public output, and followed by this clean authoritative rerun.

## Focused tests

```text
22 passed in 4.48s
```

The focused suite contains the retained W0 contract tests plus W1 tests covering:

- backend-independent public execution;
- provisional-warning injection and deduplication;
- copied public state arrays;
- fail-closed noncanonical case handling before solver construction;
- actual short A2 live-backend execution;
- standard five-file result generation;
- absence of verification imports from the public runtime facade.

## Authoritative eight-step smoke result

```text
outcome:
WORKING_TOOL_W1_A2_LIVE_BACKEND_SMOKE_PASS

accepted steps:
8

final solver step:
8

final solver time:
5.357293568955425e-05 s

starting state SHA256:
deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21

final state SHA256:
e6c037310182e6b8b4fa43962facdf7f56354a35e31c2e6ff780cf32ee840ba4
```

The normal `WorkingToolCase` input reproduced the retained A2 starting state exactly.

The smoke execution used:

```text
one FvmSolver instance
ModelManagedLiveFvmHook
PhysicsBoundaryModelManager profile U3_B2_A1_INCREMENT_9M_A0
A1 transactional composition
existing Increment 9L delegates
```

## Manager and restoration evidence

The eight-step trajectory remains in the early A2 regime:

```text
public boundary regime:
OUTWARD_FLOW

outward-flow model:
THREE_BRANCH_WAVE_MODEL

manager transition count:
0

manager selection-history count:
1

successful context restorations:
8 / 8
```

All eight live evaluations confirmed:

```text
context restored without root reconstruction = true
physics flux modified by manager = false
absolute step number transition condition used = false
checkpoint state used = false
```

No later finite-compression or closed-boundary transition is expected or claimed in this short W1 smoke.

## Short-run physical and numerical safety gates

At the end of the eight-step smoke:

```text
all conserved values finite = true
minimum density = 874.5377317519599 kg/m3
minimum internal energy = 216874.08853965366 J/kg
normalized phase set = [liquid]
rho*xv exact zero = true
```

These are short-run engineering safety gates. They are not physical validation or design approval.

## Public result package

The normal-user output remains exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

The W1 public package contains no workflow run/job IDs, artifact IDs or digests, parent-artifact metadata, or A2/9L exact-equivalence authority fields.

The public warnings are:

```text
PROVISIONAL_ENGINEERING_MODEL
WORKING_TOOL_W1_SMOKE_SCOPE
```

The second warning states explicitly that W1 exercises only the short live connection and is not a full 2L/c0 regression, physical validation, or design-use approval.

## Formal-state boundary

The public result and W1 evidence retain:

```text
verified = false
accepted = false
validated = false
design_use_approved = false
full_two_l_over_c0_regression_tested = false
target_horizon_reached = false
```

W1 completion establishes that the W0 shell can drive the actual retained A2 model-managed FVM path and produce the standard public result package.

It does **not** establish:

```text
full 640-step / 2L/c0 public-path execution
exact W1-to-A2 full-trajectory equivalence
single-phase finite-pipe coupling verification
physical validation
design-use acceptance
production activation
```

The strongest inherited physics status remains:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

## Next increment

Working Tool W2 may now run the canonical public Working Tool path from the exact initial state to 2L/c0 and compare its trajectory externally against the immutable Increment 9M A2 authority.

W2 shall retain the W0/W1 separation:

```text
normal case input
    -> public Working Tool path
    -> standard result package

standard result package + runtime evidence
    -> separate verification harness
    -> exact A2 behavioral regression evidence
```
