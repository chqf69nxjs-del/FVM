# Stage 7 U3 B2 A1 Working Tool W0 progress

## Status

```text
IN PROGRESS
PUBLIC CASE CONTRACT IMPLEMENTED
PUBLIC BACKEND INTERFACE IMPLEMENTED
PUBLIC RESULT / WARNING / TRANSITION CONTRACT IMPLEMENTED
PUBLIC FIVE-FILE OUTPUT CONTRACT IMPLEMENTED
OUTPUT AUTHORITY-BOUNDARY HARDENING IMPLEMENTED
FOCUSED ISOLATED TESTS PASS

NOT AUTHORITATIVE CI TESTED
NOT LIVE-FVM CONNECTED
NOT A2 REGRESSION TESTED
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Branch and baseline

```text
branch:
agent/u3-b2-a1-working-tool-w0

A2 parent head:
a7e362d72b8fef627803bd7b9e8cf3595b0e5282

current W0 head at this record:
273046dea28b9b607158e63b4178f1aec7ff04aa
```

## Implemented W0 shell

```text
src/liquid_gas_transient/working_tool/
    __init__.py
    backend.py
    case_schema.py
    output.py
    results.py
```

The case schema reuses the existing `PipeGeometry`, `NumericsConfig`, and `TimeConfig` classes. It exposes only the current narrow CO2 single-phase provisional model profile and rejects unsupported fluid/profile requests fail-closed.

The runtime boundary is represented by `WorkingToolBackend`, which W1 can implement with the retained Increment 9M A2 live path.

The result contract contains structured transition records, warning records, runtime payloads, state arrays, and explicit formal-state flags that are forced false at W0.

The public output contract is exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

## Provisional disclosure

A `WorkingToolResult` cannot be constructed without the mandatory warning code:

```text
PROVISIONAL_ENGINEERING_MODEL
```

and the result contract refuses promotion of:

```text
verified
accepted
validated
design_use_approved
```

## Verification-artifact separation

The public shell does not import the Increment 9M A2 verification runner and does not require parent authority, workflow, or artifact inputs.

The output writer additionally rejects reserved formal-status keys and verification-only metadata such as workflow/artifact authority identifiers from the normal result summary.

## Source-scope check

Comparison against the A2 parent head shows only W0 documentation, the new `working_tool` package, and focused W0 tests. Existing solver, EOS, B1, B2 adapter, model manager, locked contract, A1 composer, and A2 live-composition implementation were not modified.

## Test state

Committed focused test file:

```text
tests/test_working_tool_w0_contracts.py
```

An isolated reconstruction of the current W0 source and existing core configuration classes produced:

```text
7 passed
```

Additional isolated guard checks confirmed fail-closed rejection of injected reserved summary keys including the formal verification flag and workflow/artifact metadata.

These are implementation-development tests only. They are not promoted to authoritative GitHub CI evidence.

## Infrastructure note

A dedicated W0 GitHub Actions workflow was not committed because the available repository connector blocked creation of a new executable workflow under its write-safety policy.

An existing unrelated Stage 7 workflow is automatically registered on pushes to the W0 branch, but the observed run failed before creating any jobs and therefore provides no W0 test authority. This is classified as a workflow / infrastructure limitation, not a physics or numerical failure.

## Remaining W0 closeout work

Before W0 can be marked COMPLETE:

1. establish authoritative CI execution of the focused W0 tests;
2. add the output reserved-key guard checks to the authoritative test set;
3. record run/job/artifact evidence for the W0 contract suite;
4. decide the exact public orchestration seam used by W1 to invoke `WorkingToolBackend` without coupling the normal-user shell to verification logic;
5. write the W0 closeout only after those gates pass.

## Claim boundary

The strongest inherited physics claim remains:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

W0 changes tool architecture and user-facing contracts only. It adds no new physical model, closure criterion, re-entry, reverse flow, two-phase activation, validation, or design-use approval.
