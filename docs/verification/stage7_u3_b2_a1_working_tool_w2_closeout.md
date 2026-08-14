# Stage 7 U3 B2 A1 Working Tool W2 closeout

## Status

```text
WORKING TOOL W2: COMPLETE

IMPLEMENTED
PUBLIC FULL-HORIZON PATH TESTED
CANONICAL 2L/c0 EXECUTION PASSED
EXACT A2 BEHAVIORAL REGRESSION PASSED
STANDARD RESULT PACKAGE PRODUCED
AUTHORITATIVE CI PASSED

NOT VERIFIED
NOT ACCEPTED
NOT PHYSICALLY VALIDATED
NOT DESIGN-USE ACCEPTED
NOT PRODUCTION APPROVED
```

## Scope

Working Tool W2 runs the exact canonical A2 liquid case through the completed
public Working Tool path from the locked initial state to the nominal `2L/c0`
horizon.

The established normal execution path is:

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

The exact A2 comparison remains outside the public result path:

```text
public Working Tool result
+ backend runtime evidence
+ immutable A2 authority artifact
    -> separate W2 regression harness
    -> exact behavioral regression evidence
```

W2 adds no new physical model and does not generalize the accepted input scope
beyond the locked canonical case.

## Baseline and authoritative source

```text
branch:
agent/u3-b2-a1-working-tool-w2

W1 closeout head:
a9ca38a18634dae8006379997403b6d6dc0f1230

A2 authoritative execution source:
947b0f0bf006e8015c3c109e57a8aeb7460cca02

W2 authoritative execution source SHA:
59684d2f7e70204ab7d2db74619c17c70b1b279c
```

The W2 source-scope gate passed against the W1 closeout head. The authoritative
source differs only in:

- W2 specification and closeout-support documentation;
- W2 integration backend;
- W2 external regression harness;
- W2 focused tests;
- W2 GitHub Actions workflow.

Protected FvmSolver, EOS, B1/B2, Physics Model Manager, A1 composer, Increment
9L delegate, and Increment 9M A2 implementation sources were not modified.

## Authoritative GitHub Actions evidence

```text
workflow:
Agent U3 B2 A1 Working Tool W2 Full Horizon Regression

workflow file:
.github/workflows/agent-u3-b2-a1-working-tool-w2.yml

run:
31765277696

job:
94659759551

run conclusion:
SUCCESS

job conclusion:
SUCCESS
```

All retained job steps completed successfully, including:

- Verify W2 source scope
- Compile W2 sources
- Run retained W0, W1, and W2 focused tests
- Verify and download immutable A2 authority
- Run authoritative W2 full-horizon regression
- Inspect W2 regression and public-result separation
- Record source metadata and workflow evidence manifest
- Upload W2 evidence

The full-horizon regression step ran for approximately 23 minutes. It performed
a fresh live FVM execution; it did not reuse an A2 checkpoint or final state.

## Authoritative artifact

```text
artifact ID:
9206506605

artifact name:
u3-b2-a1-working-tool-w2-31765277696

artifact digest:
sha256:80830a0e2cb324840c7534bea69380e5435f665fb0333a14468a11365f77d557

expired at closeout:
false
```

The downloaded artifact ZIP SHA256 was recomputed at closeout and exactly
matched the live GitHub artifact digest.

The artifact contains:

```text
changed_paths.txt
pytest.log
pytest.xml
regression-console.log
source_git_sha.txt
workflow_artifact_sha256.txt
regression/
    artifact_sha256.txt
    case.json
    parent_authority_verification.json
    report.md
    w2_behavioral_regression.json
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

Both evidence manifests were recomputed from their extracted roots and passed:

```text
workflow_artifact_sha256.txt: PASS
regression/artifact_sha256.txt: PASS
```

## Focused tests

```text
26 passed in 4.49s
```

The focused suite retains the W0 and W1 tests and adds W2 checks for:

- fail-closed noncanonical case handling before solver construction;
- exact trajectory neutrality of the accepted-state recording wrapper;
- direct NPZ array/dtype/shape comparison semantics;
- reuse of the retained A2 path rather than physics duplication;
- mandatory canonical full-horizon warning semantics.

## Immutable A2 authority verification

Before the W2 comparison, the workflow verified and downloaded the immutable A2
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

The live run, job, source SHA, artifact identity, artifact name, artifact digest,
nonexpired state, downloaded ZIP digest, and A2 internal artifact manifest all
passed before the W2 runtime was compared.

## Authoritative W2 execution

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

The normal `WorkingToolCase` input reproduced the runtime initial conserved
state exactly. The run used one FvmSolver instance and recorded 641 states:
the initial state plus all 640 accepted states.

## Manager and transition history

The exact manager sequence was retained:

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

Resulting counts:

```text
manager transitions:
2

manager selections:
3

successful context restorations:
640 / 640

public boundary states:
OUTWARD_FLOW = 637
ZERO_TRANSFER_CLOSED = 3

outward models:
THREE_BRANCH_WAVE_MODEL = 483
GENERAL_EOS_FINITE_COMPRESSION = 154

outward branches:
CONNECTED_RAREFACTION = 336
NEUTRAL_ENDPOINT = 1
WEAK_COMPRESSION = 146
FINITE_COMPRESSION_HUGONIOT = 154
```

All 640 accepted evaluations retained:

```text
context restored without root reconstruction = true
physics flux modified by manager = false
absolute step-number transition condition used = false
checkpoint state used = false
```

## Exact A2 behavioral comparison

The separate W2 regression harness produced:

```text
outcome:
WORKING_TOOL_W2_EXACT_A2_BEHAVIORAL_REGRESSION_PASS

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

The selected exact CSV comparison covered:

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

The initial/final NPZ comparison checked contained array presence, dtype, shape,
and values directly. It did not use the NPZ container hash as the equivalence
criterion.

## Conservation and state-scope results

The full Working Tool trajectory reproduced the A2 cumulative residuals exactly:

```text
mass:
2.6461309272224343e-17 kg

momentum:
1.214306433183765e-17 kg m/s

energy:
9.457323812966933e-12 J
```

The retained trajectory also preserved:

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

These are engineering trajectory and conservation checks. They are not physical
validation or design-use approval.

## Public result package

The normal-user package remains exactly:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

The public state-history package contains:

```text
641 time samples
32 spatial cells
conserved state
pressure
temperature
density
velocity
internal energy
vapor mass fraction
```

The public warnings are:

```text
PROVISIONAL_ENGINEERING_MODEL
WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_SCOPE
```

The public result intentionally reports:

```text
a2_behavioral_regression_tested = false
```

because the A2 authority comparison is performed by the separate verification
harness, not by the normal-user execution path.

The public package contains no workflow run/job IDs, artifact IDs or digests,
parent authority metadata, or exact-equivalence authority fields.

## Formal-state boundary

The public result retains:

```text
verified = false
accepted = false
validated = false
design_use_approved = false
```

W2 completion establishes that:

> The canonical normal Working Tool path reaches 2L/c0 and reproduces the
> immutable Increment 9M A2 trajectory exactly.

It does **not** establish:

```text
arbitrary user-input support
general near-zero-flow closure validity
controlled re-entry
reverse flow
two-phase activation
single-phase finite-pipe coupling verification
physical/reference validation
design-use acceptance
production activation
```

The strongest inherited physical-model status remains:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

## Next development phase

W0 established the public contracts, W1 connected the live backend, and W2
established the exact full-horizon A2 regression.

The next phase may now assemble **Working Tool v0** around this protected
canonical path, focusing on user operation rather than new physics:

```text
case-file loading
CLI or reusable application entry point
output-directory policy
sampling/storage controls
concise user documentation
example canonical case
explicit provisional-scope disclosure
repeatable v0 regression package
```

Input-envelope generalization and new physics shall remain separate increments
with their own predeclared scope and evidence.
