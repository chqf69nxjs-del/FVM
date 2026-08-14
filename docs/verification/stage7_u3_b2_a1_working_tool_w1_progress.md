# Stage 7 U3 B2 A1 Working Tool W1 progress

## Status

```text
IN PROGRESS
PUBLIC EXECUTION FACADE IMPLEMENTED
CANONICAL A2 LIVE BACKEND IMPLEMENTED
SHORT-RUN TESTS AND EIGHT-STEP HARNESS IMPLEMENTED
DEDICATED CI WORKFLOW IMPLEMENTED

NOT AUTHORITATIVE CI TESTED
NOT FULL 2L/c0 REGRESSION TESTED
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Branch and baseline

```text
branch:
agent/u3-b2-a1-working-tool-w1

W0 closeout head:
b8eefcc046a09da9cca2e9065c9963c3c9a81630
```

## Implemented path

```text
WorkingToolCase
    -> execute_case(case, backend)
    -> A2LiveWorkingToolBackend.run_case(case)
    -> one FvmSolver
    -> ModelManagedLiveFvmHook
    -> PhysicsBoundaryModelManager
    -> A1 transactional composer
    -> existing Increment 9L delegates
    -> WorkingToolResult
    -> standard five-file output
```

The public `execute_case` facade depends only on the W0 backend protocol and public result contracts. The A2 integration adapter remains on the verification/integration side, so the public package does not import the A2 verification runner or authority metadata.

## W1 scope

W1 is deliberately limited to the exact canonical locked A2 liquid case expressed through normal `WorkingToolCase` fields. Noncanonical geometry, mesh, CFL, initial state, outlet settings, or horizon inputs fail closed before solver construction.

The authoritative smoke target is eight accepted steps. Full 2L/c0 execution and exact A2 behavioral regression remain W2 scope.

## Implemented evidence paths

```text
tests/test_working_tool_w1_a2_live_backend.py

tools/verification/
    u3_b2_a1_working_tool_w1_a2_live_backend.py
    u3_b2_a1_working_tool_w1_smoke.py

.github/workflows/
    agent-u3-b2-a1-working-tool-w1.yml
```

The CI workflow retains W0 tests, runs W1 tests, executes the eight-step live smoke, inspects public/verification separation, records source metadata, and uploads an evidence artifact.

## Claim boundary

No protected FvmSolver, EOS, B1/B2, manager, A1 composer, Increment 9L delegate, or A2 implementation source is changed by W1.

W1 currently claims implementation only. Completion requires authoritative GitHub Actions run/job/artifact evidence.
