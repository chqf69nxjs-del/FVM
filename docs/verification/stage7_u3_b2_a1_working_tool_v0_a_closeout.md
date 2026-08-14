# Stage 7 U3 B2 A1 Working Tool v0-A closeout

## Status

```text
WORKING TOOL v0-A: COMPLETE

IMPLEMENTED
STRICT JSON CASE LOADING TESTED
REPOSITORY CLI APPLICATION PATH TESTED
CREATE-ONLY ATOMIC OUTPUT POLICY TESTED
CANONICAL 2L/c0 CLI EXECUTION PASSED
EXACT A2 BEHAVIORAL REGRESSION PASSED
AUTHORITATIVE CI PASSED

NOT ARBITRARY-INPUT CAPABLE
NOT AN INSTALLED DISTRIBUTION ENTRY POINT
NOT VERIFIED
NOT ACCEPTED
NOT PHYSICALLY VALIDATED
NOT DESIGN-USE ACCEPTED
NOT PRODUCTION APPROVED
```

## Purpose and completed path

Working Tool v0-A provides the first repository-local case-file operation path
around the protected W2 canonical calculation.

```text
UTF-8 JSON case file
    -> strict load_case_file()
    -> backend-independent run_case_file()
    -> repository-local CLI application
    -> retained A2FullHorizonWorkingToolBackend
    -> public Working Tool execute_case()
    -> one FvmSolver
    -> ModelManagedLiveFvmHook
    -> PhysicsBoundaryModelManager
    -> A1 transactional composer
    -> existing Increment 9L delegates
    -> 640 accepted steps / 2L/c0
    -> standard five-file public result directory
```

The exact A2 comparison remains outside the normal public result package:

```text
CLI/application result
+ integration-side runtime evidence
+ immutable Increment 9M A2 authority
    -> separate v0-A regression harness
    -> exact behavioral-regression evidence
```

v0-A adds no physical model and does not widen the locked input envelope.

## Baseline and source identity

```text
branch:
agent/u3-b2-a1-working-tool-v0-a

W2 closeout head:
d9f196d1a4843351b538a17af929f14246d84abf

W2 authoritative execution source:
59684d2f7e70204ab7d2db74619c17c70b1b279c

v0-A authoritative execution source:
898be97aaab9d96af2136b7908defcecb8e744b0
```

The authoritative source-scope gate passed against the W2 closeout head. The
recorded changed paths are exactly:

```text
.github/workflows/agent-u3-b2-a1-working-tool-v0-a.yml
docs/verification/stage7_u3_b2_a1_working_tool_v0_a_case_file_cli_spec.md
examples/working_tool/canonical_a2_case_v0.json
src/liquid_gas_transient/working_tool/__init__.py
src/liquid_gas_transient/working_tool/application.py
src/liquid_gas_transient/working_tool/case_io.py
tests/test_working_tool_v0_a_case_file_cli.py
tools/verification/u3_b2_a1_working_tool_v0_a_regression.py
tools/working_tool/run_working_tool_v0_a.py
```

`pyproject.toml` was checked unchanged. Protected FvmSolver, EOS, B1/B2,
Physics Model Manager, A1 composer, Increment 9L delegates, Increment 9M A2,
W1 backend, and W2 backend sources were not modified.

## Public JSON case-file loader

v0-A adds:

```text
src/liquid_gas_transient/working_tool/case_io.py
```

Public API:

```text
load_case_file(path) -> WorkingToolCase
```

The loader supports UTF-8 JSON only and requires the exact retained
`WorkingToolCase.as_dict()` schema. It fails closed for:

- missing or non-regular paths;
- invalid UTF-8;
- malformed JSON;
- duplicate object keys;
- `NaN`, `Infinity`, and `-Infinity`;
- non-object root or nested sections;
- missing or unknown keys;
- booleans in numeric fields;
- non-integer `n_cells`, `n_ghost`, or `max_steps`;
- string-to-number substitution;
- unsupported schema or model profile;
- unsupported fluid or values rejected by retained configuration contracts.

The loader does not ignore fields, insert case defaults, rename keys, choose a
physical model, or silently coerce strings to numbers.

## Public case-file application layer

v0-A adds:

```text
src/liquid_gas_transient/working_tool/application.py
```

Public API:

```text
run_case_file(case_path, output_dir, backend) -> CompletedCaseRun
```

The public application layer is backend-independent. It imports no Increment
9L/9M/W1/W2 verification runner, GitHub authority metadata, or artifact logic.

The requested output path is create-only:

- any existing file, directory, or symbolic-link path is rejected;
- no overwrite flag exists;
- execution writes to a hidden sibling temporary directory;
- the exact public file contract is checked before publication;
- successful output is atomically renamed into place;
- failed execution removes the temporary result and leaves no partial public
  output directory;
- an earlier result cannot be silently overwritten.

## Canonical example case

v0-A adds:

```text
examples/working_tool/canonical_a2_case_v0.json
```

The deterministic example has:

```text
case_id:
WORKING-TOOL-V0-A-CANONICAL-A2

fluid:
CO2

model profile:
STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0

pipe length:
1.0 m

pipe diameter:
0.011283791670955126 m

cells / ghost cells / CFL:
32 / 2 / 0.1

initial pressure:
5000000.0 Pa

initial temperature:
282.43392381063524 K

back pressure:
4950000.0 Pa

opening fraction / Cd:
0.5 / 0.8

target time:
0.004285834855172021 s
```

The example file was compared with the loaded case's deterministic
`as_dict()` serialization and matched exactly.

A structurally valid JSON file is not automatically a supported physical case.
The retained W2 backend still fail-closes every geometry, initial-state,
outlet, numerical, and horizon value outside the locked canonical scope before
solver construction.

## Repository-local CLI

v0-A adds:

```text
tools/working_tool/run_working_tool_v0_a.py
```

Normal repository command:

```text
python tools/working_tool/run_working_tool_v0_a.py \
  --case examples/working_tool/canonical_a2_case_v0.json \
  --output-dir <new-output-directory>
```

The CLI bootstraps the repository `src` and integration-tool paths itself. Its
`--help` path was executed in CI with `PYTHONPATH` removed, confirming that no
manual `PYTHONPATH` setup is required to start the command.

The authoritative full-horizon regression invoked the same CLI `main()`
application path with the real retained W2 backend and captured its stdout and
stderr. The CLI returned:

```text
return code:
0

case ID:
WORKING-TOOL-V0-A-CANONICAL-A2

accepted steps:
640

final time:
0.004285834855172021 s

target reached:
true
```

The CLI printed the explicit provisional-model notice before and after
execution:

```text
PROVISIONAL ENGINEERING MODEL
not VERIFIED
not ACCEPTED
not PHYSICALLY VALIDATED
not DESIGN-USE APPROVED
not PRODUCTION APPROVED
```

v0-A is a repository-local CLI application, not yet a packaged or installed
console-script distribution entry point.

## Public result package

The CLI/application path produces exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

The public package contains no workflow run/job IDs, artifact IDs or digests,
parent-authority metadata, or exact-regression authority fields.

The public warnings remain:

```text
PROVISIONAL_ENGINEERING_MODEL
WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_SCOPE
```

The public result intentionally retains:

```text
verified = false
accepted = false
validated = false
design_use_approved = false
a2_behavioral_regression_tested = false
```

The A2 comparison belongs to the separate verification harness, not the
normal-user output contract.

## Authoritative GitHub Actions evidence

```text
workflow:
Agent U3 B2 A1 Working Tool v0-A JSON CLI

workflow file:
.github/workflows/agent-u3-b2-a1-working-tool-v0-a.yml

run:
31769317033

job:
94671756741

source SHA:
898be97aaab9d96af2136b7908defcecb8e744b0

run conclusion:
SUCCESS

job conclusion:
SUCCESS
```

All retained steps completed successfully:

- Checkout exact source
- Install fixed dependencies
- Verify v0-A source scope
- Compile v0-A sources
- Verify repository CLI bootstrap without PYTHONPATH
- Run retained W0, W1, W2, and v0-A focused tests
- Verify and download immutable A2 authority
- Run authoritative v0-A JSON CLI full-horizon regression
- Inspect v0-A regression and public-result separation
- Record source metadata and workflow evidence manifest
- Upload v0-A evidence

The fresh full-horizon calculation ran for approximately 21 minutes. It did not
reuse an A2 checkpoint or final state.

An earlier candidate run was superseded by the final workflow-trigger hygiene
commit before authority was assigned. No physical, numerical, or public-output
correction was required.

## Focused tests

```text
48 passed in 3.97s
```

The suite retains all W0, W1, and W2 focused tests and adds v0-A coverage for:

- deterministic canonical JSON round-trip;
- duplicate-key, malformed-JSON, non-finite, invalid-UTF-8, and path rejection;
- exact root and nested key sets;
- strict numeric/integer typing;
- unsupported schema/profile/fluid rejection;
- create-only output policy;
- atomic public-package publication;
- partial-output cleanup on runtime failure;
- invalid-case rejection before backend construction;
- CLI completion summary and visible provisional disclosure;
- absence of verification dependencies from the public application layer.

## Immutable A2 authority verification

Before regression, the workflow verified and downloaded the immutable A2
authority:

```text
A2 source SHA:
947b0f0bf006e8015c3c109e57a8aeb7460cca02

A2 run:
31719604102

A2 job:
94512927800

A2 artifact ID:
9189445884

A2 artifact name:
u3-b2-a1-increment-9m-a2-31719604102

A2 artifact SHA256:
4678ecd9f919ea513bed16652a1fe5b484d6c664b74209bf7dbaffa2dc0a2b64

A2 artifact expired:
false
```

The run, job, source SHA, artifact identity, artifact name, live digest,
downloaded ZIP SHA256, nonexpired state, and A2 internal manifest all passed
before the v0-A trajectory comparison.

## Authoritative v0-A full-horizon execution

```text
accepted steps:
640

final solver step:
640

target 2L/c0:
0.004285834855172021 s

final solver time:
0.004285834855172021 s

horizon error:
0.0 s

starting state SHA256:
deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21

final state SHA256:
8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014
```

The normal JSON file reproduced the locked initial WorkingToolCase and exact
initial conserved state. One FvmSolver instance executed the full trajectory.

## Manager, model, and transition history

The manager sequence remained exactly:

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

Observed counts:

```text
manager transitions:
2

manager selections:
3

successful context restorations:
640 / 640

OUTWARD_FLOW:
637 accepted steps

ZERO_TRANSFER_CLOSED:
3 accepted steps

THREE_BRANCH_WAVE_MODEL:
483 accepted steps

GENERAL_EOS_FINITE_COMPRESSION:
154 accepted steps

CONNECTED_RAREFACTION:
336 accepted steps

NEUTRAL_ENDPOINT:
1 accepted step

WEAK_COMPRESSION:
146 accepted steps

FINITE_COMPRESSION_HUGONIOT:
154 accepted steps
```

All manager events retained:

```text
context restored without root reconstruction = true
physics flux modified by manager = false
absolute step-number transition condition used = false
checkpoint state used = false
```

Observed transition step/time values remain evidence only.

## Exact A2 behavioral regression

The separate v0-A harness produced:

```text
outcome:
WORKING_TOOL_V0_A_EXACT_A2_BEHAVIORAL_REGRESSION_PASS

CLI application gate:
PASS

parent authority gate:
PASS

full-horizon execution gate:
PASS

manager and restoration gate:
PASS

public-result separation gate:
PASS

exact A2 behavioral regression:
PASS
```

Comparison result:

```text
exact summary-field mismatches:
0

exact selected-CSV mismatches:
0

initial/final NPZ array mismatches:
0
```

Selected CSV comparison included:

```text
step_metrics.csv
boundary_state_history.csv
outward_model_transition_events.csv
boundary_transition_events.csv
three_branch_algorithm_transition_events.csv
finite_compression_bounded_window_fallback_events.csv
guard_front_root_topology_correction_events.csv
model_manager_transition_events.csv
model_manager_selection_history.csv
model_manager_context_restoration.csv
```

NPZ comparison used contained-array presence, dtype, shape, and exact value;
the NPZ container-file hash was not used as the array-equivalence criterion.

## Conservation and state-scope results

The CLI/application trajectory reproduced the A2 cumulative residuals exactly:

```text
mass:
2.6461309272224343e-17 kg

momentum:
1.214306433183765e-17 kg m/s

energy:
9.457323812966933e-12 J
```

It also retained:

```text
all conserved values finite
positive density
positive internal energy
liquid phase scope
rho*xv exact zero
closed mass transfer exact zero
closed energy transfer exact zero
closed vapor transfer exact zero
closed wall-momentum identity exact
```

These are software-trajectory, conservative-ledger, and engineering-scope
checks. They do not constitute physical validation or design approval.

## Authoritative artifact

```text
artifact ID:
9207899903

artifact name:
u3-b2-a1-working-tool-v0-a-31769317033

artifact digest:
sha256:444aa99619a79e5c35f754df50a045094e8405e066b21588662641549e7e0fea

artifact size:
1679247 bytes

expired at closeout:
false
```

The downloaded artifact ZIP SHA256 was independently recomputed at closeout and
exactly matched the live GitHub artifact digest.

Artifact contents include:

```text
changed_paths.txt
cli-help.txt
pytest.log
pytest.xml
regression-console.log
source_git_sha.txt
workflow_artifact_sha256.txt
regression/
    artifact_sha256.txt
    case.json
    cli_stdout.json
    cli_stderr.txt
    parent_authority_verification.json
    report.md
    v0_a_behavioral_regression.json
    public-result/
        summary.json
        history.csv
        transitions.csv
        warnings.csv
        state_history.npz
    runtime-evidence/
        accepted_state_history.npz
        boundary_state_history.csv
        boundary_transition_events.csv
        finite_compression_bounded_window_fallback_events.csv
        guard_front_root_topology_correction_events.csv
        initial_and_final_states.npz
        model_manager_context_restoration.csv
        model_manager_selection_history.csv
        model_manager_transition_events.csv
        outward_model_transition_events.csv
        runtime_summary.json
        step_metrics.csv
        three_branch_algorithm_transition_events.csv
```

Both manifests were recomputed from their extracted roots and passed exactly:

```text
workflow_artifact_sha256.txt: PASS
regression/artifact_sha256.txt: PASS
```

## Formal-state boundary

v0-A establishes that:

> A strict canonical JSON case can be passed through a repository-local CLI
> application path, executed to 2L/c0, published as the standard five-file
> result package, and reproduced exactly against the immutable A2 authority.

It does not establish:

```text
arbitrary user-input support
installed application packaging
YAML or batch-case support
sampling/storage optimization
general near-zero-flow closure validity
controlled re-entry
reverse flow
two-phase activation
physical/reference validation
design-use acceptance
production activation
```

The strongest inherited physical-model status remains:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

## Next development increment

The recommended next bounded increment is **Working Tool v0-B — output and
storage operation policy**, without new physics:

```text
sampling interval contract
full-state versus sampled-state storage modes
estimated output-size disclosure
run-directory naming policy
concise user run manifest
safe repeat-run naming
retained canonical CLI regression
```

Installed packaging, broader user documentation, and arbitrary-input
generalization should remain later and separately predeclared increments.
