# Stage 7 U3 B2 A1 Working Tool v0-A — JSON case-file and repository CLI specification

## Status

```text
PREDECLARED IMPLEMENTATION CONTRACT
W2 COMPLETE BASELINE
NO NEW PHYSICS
NO INPUT-ENVELOPE GENERALIZATION
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Baseline

```text
branch:
agent/u3-b2-a1-working-tool-v0-a

W2 closeout head:
d9f196d1a4843351b538a17af929f14246d84abf

W2 authoritative execution source:
59684d2f7e70204ab7d2db74619c17c70b1b279c

W2 authoritative run:
31765277696

W2 authoritative job:
94659759551

W2 authoritative artifact:
9206506605

W2 authoritative artifact digest:
sha256:80830a0e2cb324840c7534bea69380e5435f665fb0333a14468a11365f77d557
```

v0-A starts from the completed W2 public full-horizon path. It shall not modify
FvmSolver, EOS, B1/B2, Physics Model Manager, A1 composer, Increment 9L
delegates, Increment 9M A2 implementation, W1 backend behavior, or W2 backend
behavior.

## Purpose

v0-A provides the first repository-local user operation path:

```text
JSON case file
    -> strict case-file loader
    -> backend-independent application runner
    -> canonical W2 backend
    -> public Working Tool execution
    -> standard five-file output directory
```

The initial v0-A command shall be:

```text
python tools/working_tool/run_working_tool_v0_a.py \
  --case examples/working_tool/canonical_a2_case_v0.json \
  --output-dir <new-directory>
```

This is a repository-local CLI, not yet an installed console-script entry point.
Packaging, distribution, GUI support, YAML support, batch execution, and
arbitrary backend selection remain later scope.

## Public and integration dependency boundary

The reusable public application layer shall remain backend-independent:

```text
load_case_file(path) -> WorkingToolCase
run_case_file(case_path, output_dir, backend) -> completed public result path
```

Public source under `src/liquid_gas_transient/working_tool/` shall not import:

- `tools.verification`;
- Increment 9L, 9M, W1, or W2 runner modules;
- GitHub workflow, run, job, or artifact metadata;
- A2 authority evidence.

The repository-local CLI may compose the public application layer with the
existing integration-side `A2FullHorizonWorkingToolBackend`. That composition
shall remain outside the public Working Tool package.

## JSON case-file contract

v0-A supports UTF-8 JSON only. The file content shall correspond exactly to
`WorkingToolCase.as_dict()` for schema:

```text
stage7_u3_b2_a1_working_tool_case_v0
```

Required root keys:

```text
schema_version
case_id
fluid
model_profile
geometry
numerics
time
initial
outlet
```

Required nested keys:

```text
geometry:
  length_m
  diameter_m
  roughness_m

numerics:
  n_cells
  n_ghost
  cfl

time:
  t_end_s
  max_steps

initial:
  pressure_pa
  temperature_k
  velocity_m_s

outlet:
  back_pressure_pa
  opening_fraction
  discharge_coefficient
```

The loader shall fail closed for:

- missing files or non-regular file paths;
- invalid UTF-8;
- malformed JSON;
- duplicate object keys;
- `NaN`, `Infinity`, or `-Infinity` constants;
- non-object root or nested sections;
- missing keys;
- unknown root or nested keys;
- booleans used as numeric or integer values;
- non-integral `n_cells`, `n_ghost`, or `max_steps`;
- unsupported schema, fluid, or model profile;
- values rejected by retained `PipeGeometry`, `NumericsConfig`, `TimeConfig`,
  `InitialCondition`, `OutletCondition`, or `WorkingToolCase` validation.

The loader shall not silently insert defaults, rename fields, ignore unknown
keys, select a physical model, or coerce strings to numbers.

## Canonical example case

v0-A shall add one canonical example file:

```text
examples/working_tool/canonical_a2_case_v0.json
```

It shall be deterministic UTF-8 JSON generated from the exact canonical W2
case and shall contain:

```text
case_id:
WORKING-TOOL-V0-A-CANONICAL-A2

fluid:
CO2

model_profile:
STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0

cells:
32

CFL:
0.1

target time:
0.004285834855172021 s
```

The retained canonical backend shall still verify every locked geometry,
initial-state, outlet, numerical, and horizon value before solver construction.
The existence of a JSON schema does not authorize values outside the locked W2
case.

## Output-directory policy

v0-A shall use a fail-closed create-only output policy:

- the requested output directory must not already exist;
- its parent directory may be created as needed;
- no `--overwrite` or implicit deletion is permitted;
- a failed run shall not overwrite an earlier result package;
- a successful run shall contain exactly the existing public files:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
```

No workflow, authority, regression, or artifact metadata may be added to the
normal output directory.

## CLI behavior

The repository-local CLI shall:

1. resolve and strictly load the JSON case;
2. construct the retained canonical W2 backend;
3. run the case through the public `run_case_file` / `execute_case` path;
4. write the standard five-file public package;
5. print a concise completion summary containing case ID, output directory,
   accepted steps, final time, and warning codes;
6. print an explicit provisional-model notice;
7. return nonzero for case-file, output-policy, or runtime failure.

The CLI shall not print or write a VERIFIED, ACCEPTED, VALIDATED,
DESIGN-USE APPROVED, or PRODUCTION APPROVED claim.

## Warning boundary

Every successful canonical v0-A run shall retain exactly the inherited public
warnings:

```text
PROVISIONAL_ENGINEERING_MODEL
WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_SCOPE
```

The CLI shall visibly state that the result is limited to the canonical
provisional single-phase model and is not physically validated or approved for
design use.

## Regression architecture

The authoritative v0-A verification shall exercise the same application path as
the CLI:

```text
example JSON
    -> load_case_file
    -> run_case_file
    -> canonical W2 backend
    -> 640 accepted steps / 2L/c0
    -> public result package
```

A separate verification harness may inspect the injected backend's retained W2
runtime evidence and compare it against the immutable A2 authority. The normal
public result shall remain unaware of that comparison.

The authoritative regression shall retain the W2 criteria:

- exact starting and final state SHA256;
- 640 accepted steps and zero horizon error;
- exact manager transitions and selection history;
- 640/640 successful context restorations;
- exact selected summary fields and evidence CSV content;
- exact initial/final NPZ arrays by presence, dtype, shape, and value;
- exact public five-file contract and warning boundary;
- all formal-authority flags false.

## Permitted source scope

v0-A changes are limited to:

```text
src/liquid_gas_transient/working_tool/case_io.py
src/liquid_gas_transient/working_tool/application.py
src/liquid_gas_transient/working_tool/__init__.py
tools/working_tool/run_working_tool_v0_a.py
tools/verification/u3_b2_a1_working_tool_v0_a_*.py
examples/working_tool/canonical_a2_case_v0.json
tests/test_working_tool_v0_a_case_file_cli.py
docs/verification/stage7_u3_b2_a1_working_tool_v0_a_*.md
.github/workflows/agent-u3-b2-a1-working-tool-v0-a.yml
```

`pyproject.toml` shall not be changed in v0-A. An installed console entry point
is deferred until the canonical integration backend has an approved packaging
boundary.

## Completion gates

v0-A is complete only when authoritative CI establishes all of the following:

1. W0, W1, and W2 focused tests remain passing.
2. Strict valid JSON loading reproduces the exact canonical
   `WorkingToolCase.as_dict()` value.
3. Duplicate keys, non-finite JSON constants, unknown/missing keys, wrong types,
   and unsupported scope fail closed.
4. The output directory must be new and is never implicitly overwritten.
5. The public application layer has no verification-runner or authority import.
6. The repository-local CLI runs the canonical example without manual
   `PYTHONPATH` setup.
7. The CLI path creates exactly the standard five-file public result package.
8. The CLI path completes 640 accepted steps and reaches the exact `2L/c0`
   horizon with zero error.
9. The CLI/application trajectory passes the exact immutable A2 behavioral
   regression retained from W2.
10. Public warnings and false formal-authority flags remain exact.
11. Protected physics and solver sources are unchanged from W2 closeout.
12. A clean run, job, artifact ID, artifact digest, and internally verifiable
   SHA256 manifests are recorded.

## Permitted closeout wording

```text
WORKING TOOL v0-A: COMPLETE

IMPLEMENTED
STRICT JSON CASE LOADING TESTED
REPOSITORY CLI TESTED
CREATE-ONLY OUTPUT POLICY TESTED
CANONICAL 2L/c0 CLI EXECUTION PASSED
EXACT A2 BEHAVIORAL REGRESSION PASSED
AUTHORITATIVE CI PASSED

NOT ARBITRARY-INPUT CAPABLE
NOT VERIFIED
NOT ACCEPTED
NOT PHYSICALLY VALIDATED
NOT DESIGN-USE ACCEPTED
NOT PRODUCTION APPROVED
```

## Deferred after v0-A

```text
installed console-script packaging
YAML or other case formats
controlled overwrite/resume policy
sampling and storage reduction policy
batch case execution
arbitrary supported-input envelope
user-facing plots and reports
broader user documentation
general near-zero-flow physics
re-entry / reverse flow / two-phase activation
physical/reference validation
design-use acceptance
```
