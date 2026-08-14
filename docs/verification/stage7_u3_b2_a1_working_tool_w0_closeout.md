# Stage 7 U3 B2 A1 Working Tool W0 closeout

## Status

```text
WORKING TOOL W0: COMPLETE

IMPLEMENTED
PUBLIC CASE CONTRACT TESTED
PUBLIC RUN CONTRACT TESTED
PUBLIC RESULT CONTRACT TESTED
PROVISIONAL-MODEL DISCLOSURE TESTED
AUTHORITATIVE CI PASSED

NOT LIVE-FVM CONNECTED
NOT A2 REGRESSION TESTED
NOT VERIFIED
NOT ACCEPTED
NOT VALIDATED
NOT APPROVED
```

## Scope

Working Tool W0 defines the public case, run/backend, result, warning, transition, and normal-user output contracts for the current provisional single-phase Stage 7 U3 B2 path.

W0 adds no new physical model and does not connect the public shell to the Increment 9M A2 live FVM path. That connection is deferred to W1.

## Authoritative source

```text
branch:
agent/u3-b2-a1-working-tool-w0

A2 parent head:
a7e362d72b8fef627803bd7b9e8cf3595b0e5282

authoritative W0 execution source SHA:
fc9f026a426993db867ba4fb30d8aff58a032631
```

The source-scope gate passed against the A2 parent. The authoritative W0 source differs only in W0 documentation, the W0 public package, the focused W0 tests, the W0 contract harness, and the W0 workflow. Protected solver/EOS/B1/B2/model-manager/A1/A2 live-composition sources were not modified.

## Authoritative GitHub Actions evidence

```text
workflow:
Agent U3 B2 A1 Working Tool W0 Contracts

workflow file:
.github/workflows/agent-u3-b2-a1-working-tool-w0-contracts.yml

run:
31760898553

job:
94646810162

run conclusion:
SUCCESS

job conclusion:
SUCCESS
```

All retained job steps completed successfully, including:

- Verify W0 source scope
- Compile W0 sources
- Run focused W0 tests
- Run W0 contract harness
- Record source metadata
- Upload W0 evidence

## Authoritative artifact

```text
artifact ID:
9204537957

artifact name:
u3-b2-a1-working-tool-w0-31760898553

artifact digest:
sha256:2aa575a24f3155a298c94537ebb72cd80b660e9ef296dfbaaa964aa584a00751

expired at closeout:
false
```

Artifact contents inspected at closeout:

```text
changed_paths.txt
contract-check.json
pytest.log
pytest.xml
sha256.txt
source_git_sha.txt
```

The artifact-recorded source SHA is exactly:

```text
fc9f026a426993db867ba4fb30d8aff58a032631
```

Focused pytest result:

```text
18 passed in 0.16s
```

Contract harness outcome:

```text
WORKING_TOOL_W0_CONTRACT_CHECK_PASS
```

The contract harness passed all seven W0 gates:

```text
existing_config_types_reused = true
supported_profile_exact = true
public_file_contract_exact = true
provisional_warning_present = true
formal_authority_false = true
transition_step_is_evidence_only = true
reserved_authority_keys_fail_closed = true
```

The artifact internal SHA256 values for the retained evidence files were recomputed at closeout and matched the recorded manifest entries.

## Public W0 contracts established

### Case contract

- Reuses existing `PipeGeometry`, `NumericsConfig`, and `TimeConfig`.
- Supports the explicit provisional profile `STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0`.
- Unsupported fluid/profile requests fail closed.
- Public case input contains no GitHub workflow/artifact authority inputs.

### Run/backend contract

```text
WorkingToolBackend.run_case(case) -> BackendRunData
```

W0 proves backend substitution semantics with a fake backend. The A2 live backend remains W1 scope.

### Result contract

Normal-user result package is exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

### Authority boundary

Every provisional result requires:

```text
PROVISIONAL_ENGINEERING_MODEL
```

and W0 keeps the following false:

```text
verified
accepted
validated
design_use_approved
```

Reserved formal-authority and verification-only metadata are rejected from normal-user summary output.

### Transition semantics

Observed solver step and solver time are evidence fields only. W0 rejects absolute solver-step transition criteria.

## Claim boundary

W0 completion means the public shell contracts are implemented and authoritatively CI-tested.

It does **not** mean:

```text
live FVM connected
A2 behavioral regression passed
single-phase finite-pipe coupling verified
physical validation completed
design use approved
production activation approved
```

The strongest inherited physics status remains:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

## Next increment

Working Tool W1 may now connect the W0 backend contract to the retained Increment 9M A2 live path using the existing FvmSolver right-face integration seam, while preserving the W0 normal-user / verification-evidence separation.
