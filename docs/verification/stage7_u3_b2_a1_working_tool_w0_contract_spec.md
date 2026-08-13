# Stage 7 U3 B2 A1 Working Tool W0 contract spec

## Status

```text
PREDECLARED CONTRACT / IMPLEMENTATION TARGET
NOT LIVE-FVM CONNECTED
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Purpose

Working Tool W0 defines the public case, run, warning, transition, and result contracts that will wrap the Increment 9M A2 model-managed single-phase path in later increments.

W0 adds no new physics and does not change the Increment 9M A2 trajectory. It deliberately separates normal-user output from verification-only evidence generation.

## Baseline authority

```text
parent branch: agent/u3-b2-a1-9m-a2
parent head: a7e362d72b8fef627803bd7b9e8cf3595b0e5282
strongest inherited claim: PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

The following remain protected and are not changed by W0:

```text
FvmSolver core
B1
locked B2 contract
EOS equations
Hugoniot equations
root tolerances
chi scope
Increment 9M A2 live-composition physics path
```

## Public architecture target

```text
case input
    -> WorkingToolCase validation
    -> run_case(case, backend=...)
    -> runtime backend
    -> WorkingToolResult
    -> normal user output package
```

W0 uses a fake/test backend only. The A2 live backend is deferred to W1.

## Case contract

The W0 public case schema shall:

- reuse `PipeGeometry`, `NumericsConfig`, and `TimeConfig` rather than define a second numerical configuration system;
- carry a stable `schema_version` and `case_id`;
- explicitly select the only supported W0 model profile: `STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0`;
- reject unsupported model profiles fail-closed;
- contain only normal run inputs and no GitHub workflow, artifact, parent-authority, or verification-comparison identifiers.

## Run contract

The public API shall expose a reusable `run_case(...)` entry point whose backend is injected through a small protocol/interface.

W0 shall not import or invoke the Increment 9M A2 verification runner. W1 will provide the live adapter.

## Result contract

A successful result shall be representable as:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

W0 defines the in-memory contract and deterministic writers. Large state arrays belong in NPZ; scalar and event records belong in JSON/CSV.

Verification-only files such as parent-authority checks, exact A2/9L comparisons, workflow metadata, and artifact manifests are outside this public result contract.

## Mandatory provisional warning

Every successful result produced under `STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0` shall contain a non-optional warning with code:

```text
PROVISIONAL_ENGINEERING_MODEL
```

The result shall state explicitly:

```text
verified = false
accepted = false
validated = false
design_use_approved = false
```

The warning shall not be suppressible through the W0 public case schema.

## Transition contract

Transition records may contain observed solver step and solver time as evidence fields, together with axis, from/to states, and trigger classification.

The W0 contract shall contain no field that makes an absolute solver step or elapsed time a transition criterion.

## Unsupported scope

W0 does not add or authorize:

```text
two-phase activation
re-entry
reverse flow
new near-zero-flow physics
new closure criterion
new hysteresis physics
design approval
production activation
```

Inputs requesting unsupported model profiles shall fail closed.

## Verification separation gate

Normal-user execution shall not require or emit:

```text
parent workflow run/job
parent artifact ID/SHA
Increment 9L authority bundle
Increment 9M A2 exact-equivalence comparison
verification report.md
artifact manifest
```

A later verification harness may consume ordinary Working Tool outputs and compare them externally against A2 authority.

## W0 completion gates

W0 is complete only when focused tests establish:

1. canonical case validation;
2. reuse of existing geometry/numerics/time configuration classes;
3. fail-closed unsupported profile handling;
4. reusable backend-independent `run_case` API;
5. deterministic public result serialization contract;
6. mandatory provisional warning and false formal-status flags;
7. transition records treat step/time as evidence only;
8. public modules do not depend on verification-runner authority/artifact inputs;
9. protected physics sources are unchanged.

## Permitted closeout wording

```text
IMPLEMENTED
PUBLIC CASE CONTRACT TESTED
PUBLIC RUN CONTRACT TESTED
PUBLIC RESULT CONTRACT TESTED
PROVISIONAL-MODEL DISCLOSURE TESTED

NOT LIVE-FVM CONNECTED
NOT A2 REGRESSION TESTED
NOT VERIFIED
NOT ACCEPTED
NOT VALIDATED
NOT APPROVED
```
