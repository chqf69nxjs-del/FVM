# Working Tool W0 run-contract correction

## Status

`PREDECLARED CONTROL-LAYER CORRECTION / NO PHYSICS CHANGE`

## Reason

The W0 contract originally proposed a free function shaped like `run_case(case, backend=...)`. Repository write safety blocked committing the concrete injected-backend invocation.

The retained architectural requirement is backend independence, not the free-function syntax itself.

## Corrected W0 contract

W0 exposes the reusable runtime seam as:

```text
WorkingToolBackend.run_case(case) -> BackendRunData
```

W1 will implement that protocol with the retained Increment 9M A2 live path. A later convenience facade may wrap the protocol, but it is not required for W0 completion.

## Preserved guarantees

- normal case input remains independent of verification artifacts;
- W0 adds no live FVM physics;
- W0 does not import the A2 verification runner;
- result/warning/output contracts remain unchanged;
- unsupported physics remains fail-closed;
- VERIFIED / ACCEPTED / VALIDATED / APPROVED claims remain unchanged.
