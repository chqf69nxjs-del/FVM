# Stage 7 U3 B2 A1 Working Tool W0 implementation freeze

## Status

```text
IMPLEMENTED
DEVELOPMENT-TESTED
NOT AUTHORITATIVE CI TESTED
W0 NOT YET COMPLETE
```

Implementation head:

`f85a875ea9ecdfd6e168ce3554f563f05f6f8fee`

A2 parent:

`a7e362d72b8fef627803bd7b9e8cf3595b0e5282`

## Implemented contracts

- case schema using existing `PipeGeometry`, `NumericsConfig`, `TimeConfig`;
- backend-independent `WorkingToolBackend.run_case(case)` protocol;
- structured result, warning, and transition contracts;
- mandatory `PROVISIONAL_ENGINEERING_MODEL` disclosure;
- five-file normal-user output package;
- fail-closed reserved authority/verification metadata handling;
- self-contained W0 contract verification harness.

## Development evidence

```text
focused isolated pytest: 18 passed
contract harness: WORKING_TOOL_W0_CONTRACT_CHECK_PASS
```

## Source-scope gate

Comparison with the A2 parent contains only W0 documentation, the new `working_tool` package, W0 tests, and the W0 contract harness. Protected solver, EOS, B1/B2, model-manager, A1, and A2 live-composition sources are unchanged.

## Remaining completion gate

W0 is not promoted to COMPLETE until an authoritative GitHub CI run/job/artifact executes the retained W0 tests and contract harness.

No live FVM connection or A2 behavioral regression is claimed in W0.
