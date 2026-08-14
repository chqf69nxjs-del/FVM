# Stage 7 / U3 B2 A1 Working Tool v0-B — Output / Storage Operation Policy Contract

## 1. Status and authority

Status: **A0 CONTRACT FREEZE**

This document freezes the implementation contract for Working Tool v0-B before any Python source, test, workflow, or example-file change is made.

- Repository: `chqf69nxjs-del/FVM`
- Baseline commit: `ec700d91d136469161be6dc1d1e1f1b6513798bb`
- Working branch: `agent/u3-b2-a1-working-tool-v0-b`
- v0-A closeout status: `COMPLETE`
- v0-B implementation status at this contract freeze: `NOT STARTED`
- Pull request status: `NOT CREATED`

The strongest physical status remains:

> **PROVISIONAL ENGINEERING END-TO-END WORKING SLICE**

This contract does not promote the tool to any of the following states:

- `VERIFIED`
- `ACCEPTED`
- `PHYSICALLY VALIDATED`
- `DESIGN-USE ACCEPTED`
- `PRODUCTION APPROVED`

The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative in this document.

---

## 2. Purpose

Working Tool v0-B adds an operational policy layer around the existing v0-A/A2 full-horizon execution path. Its purpose is to make result storage, run-directory publication, repeat-run naming, and file-integrity disclosure practical without changing the physical calculation.

The governing development order remains:

> Working vertical slice first  
> → Physics refinement / Verification second

v0-B is not a physics increment. It is an output and storage operation-policy increment.

---

## 3. Architectural invariant

The authoritative data flow is:

```text
strict case JSON
    ↓
WorkingToolCase
    ↓
A2FullHorizonWorkingToolBackend
    ↓
execute_case()
    ↓
FULL WorkingToolResult
    ├─ verification branch
    │     full result + runtime evidence + A2 authority
    │
    └─ normal-user branch
          ↓
       storage projection
          ↓
       public output package
```

The following invariants are mandatory:

1. Storage and sampling policy MUST NOT enter the solver, EOS, boundary model, manager, backend, or `execute_case()`.
2. The backend MUST complete the same full calculation and return the same full `WorkingToolResult` that the v0-A path receives.
3. Sampling MUST be applied only after the full solver calculation has completed successfully.
4. The verification branch MUST retain access to the unprojected full result and runtime evidence.
5. The normal-user branch MAY project only the public state-history storage described by this contract.
6. v0-B sampled mode is a disk-output reduction feature only. Runtime state capture remains `FULL`.
7. v0-B MUST NOT claim runtime-memory optimization, streaming, checkpointing, or state discard.

---

## 4. In scope

v0-B implements only the following capabilities:

1. A separate immutable operation-policy contract.
2. Full-state and sampled-state public storage.
3. Fixed accepted-solver-step sampling.
4. A truthful pre-run raw sample-dependent state payload estimate.
5. Post-run actual core-file byte sizes and SHA-256 digests.
6. Explicit output-directory operation.
7. Automatic run-directory operation under a user-selected root.
8. Collision-resistant repeat-run naming.
9. A public `run_manifest.json`.
10. Retained canonical full-mode and sampled-storage regression.
11. Authoritative CI and closeout evidence kept outside the public package.

---

## 5. Explicitly out of scope

v0-B MUST NOT implement or change any of the following:

- solver, EOS, B1, B2, Hugoniot, root-search, χ, manager, Increment 9L, Increment 9M A2, or W2 backend physics;
- expansion of the arbitrary input envelope;
- reverse flow;
- re-entry;
- closure reflection;
- two-phase capability;
- time-based sampling;
- adaptive sampling;
- event-aligned sampling;
- sampling of `history.csv`, `transitions.csv`, or `warnings.csv`;
- runtime state discard;
- streaming output;
- runtime-memory optimization;
- checkpoint, restart, or resume;
- NPZ compression changes;
- batch execution;
- YAML input;
- installed console-script packaging;
- retention or automatic deletion;
- cloud, database, or distributed-locking operation;
- physical validation;
- design acceptance.

An unresolved extreme-state issue MAY remain technical debt only when its applicability limit, guard, restriction, and fail-closed behavior are explicit.

---

## 6. Operation-policy contract

The physical case JSON schema remains exact-key and unchanged. Output and storage settings MUST NOT be inserted into the physical case JSON.

The v0-B operation policy is conceptually:

```python
WorkingToolOperationPolicy(
    state_sample_interval_accepted_steps=1,
    destination_mode="EXPLICIT",
    output_dir=Path("results/run001"),
    output_root=None,
)
```

The implementation MAY use equivalent field organization, but the public semantics below are fixed.

### 6.1 State-sample interval

`state_sample_interval_accepted_steps`:

- MUST be a built-in integer with `type(value) is int`;
- MUST therefore reject `bool` even though `bool` is an `int` subclass in Python;
- MUST be greater than or equal to `1`;
- defaults to `1` at the v0-B CLI boundary.

The following values MUST fail closed:

- `True` or `False`;
- float values, including integral-looking values such as `1.0`;
- strings, including `"1"` at the Python policy boundary;
- `0`;
- negative integers.

CLI parsing MAY convert valid command-line text to an integer before policy construction. Invalid CLI text MUST still fail before execution.

### 6.2 Derived storage mode

Storage mode MUST be derived from the interval and MUST NOT be independently configurable:

```text
interval == 1  → FULL_STATE
interval > 1   → SAMPLED_STATE
```

A second user-controlled mode field that permits contradictory combinations such as `FULL_STATE + interval=10` is prohibited.

### 6.3 Destination modes

Exactly two destination modes are permitted:

| Destination mode | Required path | Forbidden path | Publication behavior |
|---|---|---|---|
| `EXPLICIT` | `output_dir` | `output_root` | Publish to the exact requested create-only directory |
| `AUTO_RUN_DIRECTORY` | `output_root` | `output_dir` | Generate and publish one create-only child run directory |

The policy MUST fail closed on:

- an unknown destination mode;
- both `output_dir` and `output_root` being supplied;
- neither path being supplied;
- an explicit mode without `output_dir`;
- an automatic mode without `output_root`;
- any other mode/path contradiction.

The policy object MUST be immutable after construction.

---

## 7. Accepted-step state sampling

Only `state_history.npz` is subject to sampling.

The following files remain complete and unsampled:

- `summary.json`
- `history.csv`
- `transitions.csv`
- `warnings.csv`

For `n` accepted steps and interval `k`, the retained solver-state indices are:

```text
S(n, k)
=
{0}
∪
{j | 1 <= j <= n and j mod k = 0}
∪
{n}
```

The implementation MUST guarantee:

- the initial state at index `0` is retained;
- every accepted step divisible by `k` is retained;
- the final accepted state at index `n` is retained;
- indices are unique;
- indices are strictly ascending;
- no solver state is synthesized or interpolated.

For the canonical `n = 640` result:

| Interval | Stored samples |
|---:|---:|
| `1` | `641` |
| `10` | `65` |
| `64` | `11` |
| `100` | `8` |
| `> 640` | `2` |

For interval `100`, the retained indices are exactly:

```text
0, 100, 200, 300, 400, 500, 600, 640
```

The maximum pre-run sample count for a positive `max_steps = n_max` is:

```text
1 + floor(n_max / k) + indicator(n_max mod k != 0)
```

This is an upper-bound count based on the configured step limit, not a prediction of the accepted-step count of a particular run.

---

## 8. Versioned public state-layout contract

Projection MUST use a versioned explicit allowlist. Array classification MUST NOT be inferred from shape alone.

### `WORKING_TOOL_PUBLIC_STATE_LAYOUT_V1`

Sample-axis arrays:

- `time_s`
- `conserved`
- `rho_kg_m3`
- `velocity_m_s`
- `pressure_pa`
- `temperature_k`
- `internal_energy_j_kg`
- `vapor_mass_fraction`

Static arrays:

- `x_m`

Every sample-axis array is projected with the same retained-index sequence. `x_m` is copied without sampling.

An unknown, missing, duplicated, or reclassified public array MUST fail closed until the allowlist version is deliberately revised.

---

## 9. Pre-projection fail-closed consistency gates

Before any projection, all of the following MUST pass:

1. `summary.accepted_steps == len(history)`.
2. The full state sample count equals `accepted_steps + 1`.
3. History step numbers equal the exact integer sequence `1..accepted_steps`.
4. History times equal `state_history["time_s"][1:]` element by element.
5. Every required sample-axis array exists.
6. Every required static array exists.
7. All sample-axis arrays have the same leading dimension.
8. All required numerical values, including `x_m`, are finite.
9. The requested retained indices are valid for every sample-axis array.

The projection MUST NOT mutate the source `WorkingToolResult`, any source mapping, or any source array.

Every projected array, including the copied static `x_m`, MUST own storage independent of the original for the purposes of the public projection. Tests MUST establish that projected and original arrays do not share memory, including interval `1` full-mode projection.

A failed consistency gate MUST prevent publication of a completed run directory.

---

## 10. Pre-run storage estimate

The pre-run disclosure is a **raw sample-dependent state-array payload estimate**. It is not an exact NPZ size, file size, directory size, or runtime-memory estimate.

For the current float64 public state layout:

```text
bytes per stored sample
=
8 × [1 + (4 + 6) × N_cells]
```

The terms are:

- one `time_s` value;
- four conserved values per cell;
- six primitive/public state values per cell.

For `N_cells = 32`:

```text
2568 bytes per stored sample
```

Using canonical `max_steps = 32000` as an upper-bound basis:

```text
interval 1:
32001 samples
≈ 78.37 MiB raw sample-dependent state payload

interval 10:
3201 samples
≈ 7.84 MiB raw sample-dependent state payload
```

The estimate MUST explicitly state that it excludes:

- static `x_m` payload;
- CSV payload;
- JSON payload;
- NPZ/ZIP container metadata and other overhead;
- filesystem allocation overhead;
- temporary publication storage;
- Python and NumPy runtime memory;
- backend full-history memory.

The estimate MUST use binary MiB (`1 MiB = 1,048,576 bytes`). It MUST NOT be presented as an exact final package size.

Post-run reporting uses actual file byte sizes from the published core files.

---

## 11. Public output contracts

The existing v0-A five-file contract remains unchanged:

```python
RESULT_FILENAMES = (
    "summary.json",
    "history.csv",
    "transitions.csv",
    "warnings.csv",
    "state_history.npz",
)
```

v0-B defines a separate exact six-file contract equivalent to:

```python
V0_B_RUN_FILENAMES = RESULT_FILENAMES + ("run_manifest.json",)
```

A completed v0-B public directory MUST contain exactly those six regular files and no subdirectories.

The existing v0-A writer, application, CLI, and exact five-file package MUST remain available and behaviorally unchanged.

---

## 12. Resolved-case SHA-256

`resolved_case_sha256` MUST describe the validated `WorkingToolCase`, not the raw source-file bytes.

The digest input is the UTF-8 encoding of this deterministic serialization:

```python
json.dumps(
    working_tool_case.as_dict(),
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
)
```

No trailing newline is included. The manifest stores the lowercase hexadecimal SHA-256 digest.

This makes semantically identical validated cases produce the same resolved-case digest even when the source JSON has different whitespace or key ordering.

---

## 13. `run_manifest.json` schema

The manifest is public operational metadata. It is not verification evidence.

The v0-B schema is logically fixed as follows; implementation may use typed internal objects but the emitted JSON field names and meanings MUST remain stable for schema version `1`:

```text
schema                              = "liquid_gas_transient.working_tool.run_manifest"
schema_version                      = 1
output_contract                     = "WORKING_TOOL_V0_B_SIX_FILE_V1"
local_run_id                        = opaque local identifier
case.case_id                        = validated case identifier
case.resolved_case_sha256           = digest defined in Section 12
case.model_profile                  = resolved model profile
case.fluid                          = resolved fluid
storage.mode                        = FULL_STATE | SAMPLED_STATE
storage.state_sample_interval_accepted_steps
storage.sampling_basis              = ACCEPTED_SOLVER_STEP
storage.sampling_applied_after_solver = true
storage.runtime_state_capture_mode  = FULL
storage.full_state_samples
storage.stored_state_samples
storage.raw_state_payload_reduction_ratio
destination.mode                    = EXPLICIT | AUTO_RUN_DIRECTORY
destination.published_directory_name
started_at_utc                      = RFC 3339 UTC timestamp ending in Z
completed_at_utc                    = RFC 3339 UTC timestamp ending in Z
result.accepted_steps
result.final_time_s
result.target_reached
core_files.<core filename>.size_bytes
core_files.<core filename>.sha256
core_total_bytes
formal_status.provisional_engineering_end_to_end_working_slice = true
formal_status.verified              = false
formal_status.accepted              = false
formal_status.physically_validated  = false
formal_status.design_use_accepted   = false
formal_status.production_approved   = false
```

`local_run_id` MUST be locally generated, non-authoritative, and contain at least 128 bits of cryptographic randomness. A lowercase 32-hex-character token is the reference representation.

`raw_state_payload_reduction_ratio` is defined exactly as:

```text
1 - stored_state_samples / full_state_samples
```

It describes reduction of the sample-dependent raw payload count basis only. It MUST NOT be described as measured NPZ, core-package, directory, or runtime-memory reduction.

`core_files` contains exactly the existing five core filenames. For each core file:

- `size_bytes` is the actual regular-file size after writing;
- `sha256` is the lowercase SHA-256 digest of the actual file bytes.

`core_total_bytes` is the exact sum of those five `size_bytes` values.

The manifest MUST be generated after all five core files have been completed and hashed. `run_manifest.json` MUST NOT contain its own size or digest because that would create a self-reference.

A Git commit SHA MAY be included only in an explicitly informational field and MUST be labelled non-authoritative. It MUST NOT substitute for CI or verification evidence.

---

## 14. Public result / verification evidence separation

The separation below is mandatory:

| Information | Normal public package | Verification/CI branch |
|---|---:|---:|
| Physical case identity and resolved-case digest | Yes | Yes |
| Storage policy and retained sample counts | Yes | Yes |
| Actual core-file size and SHA-256 | Yes | Yes |
| Solver summary, histories, warnings, and stored states | Yes | Yes |
| Full unprojected runtime result | No | Yes |
| Workflow run or job ID | No | Yes |
| Artifact ID or digest | No | Yes |
| Parent or A2 authority | No | Yes |
| Exact behavioral-equivalence authority | No | Yes |
| Mismatch counts | No | Yes |
| Context-restoration evidence | No | Yes |
| pytest result | No | Yes |
| CI success claim | No | Yes |
| Verification or approval claim | No | Yes |

The normal public manifest MUST NOT contain:

- workflow ID;
- job ID;
- artifact ID or artifact digest;
- A2 authority;
- parent authority;
- exact-regression PASS;
- mismatch count;
- context-restoration evidence;
- pytest result;
- CI success;
- verification approval.

Any existing normal-run field such as `a2_behavioral_regression_tested` remains `false`. A normal execution MUST NOT turn test evidence into a public physical claim.

---

## 15. Run-directory policy

### 15.1 `EXPLICIT`

Example:

```text
--output-dir results/run001
```

Rules:

- the requested output path is exact;
- the path is create-only;
- an existing file, directory, or symlink at that path is rejected;
- no suffix is silently added;
- no overwrite is permitted;
- missing parent directories MAY be created recursively, matching v0-A behavior;
- a path that appears during execution is treated as a race and fails closed.

### 15.2 `AUTO_RUN_DIRECTORY`

Example:

```text
--output-root results
```

The generated child name has this contract:

```text
working-tool-v0-b-<sanitized-case-slug>__<UTC timestamp>__<random suffix>
```

Reference example:

```text
working-tool-v0-b-canonical-a2__20260814T061530Z__8f42a9c731bd
```

The timestamp format is exactly `YYYYMMDDTHHMMSSZ` in UTC. The random suffix is 12 lowercase hexadecimal characters derived from cryptographic randomness.

The case slug is produced as follows:

1. normalize the validated `case_id` using Unicode NFKD;
2. retain an ASCII transliteration where available and lowercase it;
3. replace each maximal sequence outside `[a-z0-9]` with `-`;
4. strip leading and trailing `-`;
5. use `case` when the result is empty;
6. truncate to at most 64 characters and strip a trailing `-` again.

The raw `case_id` MUST never be used directly as a path component. `/`, `\\`, `..`, control characters, and excessive length therefore cannot create path traversal or uncontrolled names.

Automatic naming MUST:

- create the user-selected root recursively when necessary;
- reject a root that resolves operationally to a non-directory;
- generate another cryptographic identifier when a candidate collides;
- use at most 16 candidate attempts;
- fail closed after the bounded attempts;
- never overwrite an existing path.

### 15.3 Atomic publication

Both modes retain the v0-A publication model:

1. validate that the completed destination does not already exist;
2. create a hidden temporary sibling under the same parent/root;
3. execute the full calculation;
4. create the projected five core files;
5. measure and hash the core files;
6. create `run_manifest.json` last;
7. enforce the exact six-file/no-subdirectory contract;
8. atomically rename the hidden sibling into the completed destination;
9. remove the hidden temporary directory on any failure.

A completed run directory MUST never expose a partial package. Distributed locking is out of scope; any detected publication race MUST fail closed or select a new bounded automatic candidate without overwriting.

---

## 16. Backward compatibility and CLI boundary

The existing v0-A CLI remains unchanged:

```text
tools/working_tool/run_working_tool_v0_a.py
```

v0-B adds a separate repository-local CLI:

```text
tools/working_tool/run_working_tool_v0_b.py
```

Reference invocations:

```bash
python tools/working_tool/run_working_tool_v0_b.py \
  --case examples/working_tool/canonical_a2_case_v0.json \
  --output-root results \
  --state-sample-every 10
```

```bash
python tools/working_tool/run_working_tool_v0_b.py \
  --case examples/working_tool/canonical_a2_case_v0.json \
  --output-dir results/my_run \
  --state-sample-every 1
```

The CLI contract is:

- exactly one of `--output-dir` and `--output-root` is required;
- `--state-sample-every` defaults to `1`;
- interval `1` means `FULL_STATE`;
- manual `PYTHONPATH` configuration is not required;
- the pre-run display labels the estimate truthfully;
- the CLI states that runtime capture remains `FULL`;
- the completion display includes the published directory, accepted steps, stored samples, actual core bytes, and unchanged false formal-status claims.

---

## 17. Full-mode and sampled-mode regression contracts

For `state_sample_interval_accepted_steps = 1`, the v0-B core five files MUST be semantically exact with v0-A output from the same full `WorkingToolResult`:

- parsed `summary.json` dictionary exact;
- CSV headers and rows exact;
- NPZ array names exact;
- NPZ dtypes exact;
- NPZ shapes exact;
- NPZ values exact.

Only `run_manifest.json` is additional.

Cross-run NPZ container SHA-256 MUST NOT be used as semantic-equivalence evidence. NPZ comparison uses array name, dtype, shape, and values.

Canonical A6 verification performs one fresh A2/W2 physical solve and fans out from that one full result:

```text
one fresh A2/W2 solve
        ↓
full WorkingToolResult
        ├─ exact A2 regression
        ├─ v0-B FULL output
        └─ v0-B sampled outputs
```

Sampling intervals MUST NOT trigger repeated 20-minute-class physical solves when the same full result can be projected repeatedly.

Canonical gates retain:

- accepted steps `640`;
- exact final time `0.004285834855172021 s`;
- exact starting and final state hashes;
- exact manager-transition sequence;
- exact context-restoration count;
- full core mismatch count `0`;
- sampled solver-summary mismatch count `0`;
- sampled final-state mismatch count `0`;
- public/evidence separation PASS;
- legacy v0-A CLI exact five-file output.

These are verification-path gates, not normal public manifest claims.

---

## 18. Protected baseline sources

The following existing v0-A public and execution-path files are protected against modification during v0-B unless a separately documented contract amendment is made first:

- `src/liquid_gas_transient/working_tool/__init__.py`
- `src/liquid_gas_transient/working_tool/application.py`
- `src/liquid_gas_transient/working_tool/backend.py`
- `src/liquid_gas_transient/working_tool/case_io.py`
- `src/liquid_gas_transient/working_tool/case_schema.py`
- `src/liquid_gas_transient/working_tool/output.py`
- `src/liquid_gas_transient/working_tool/results.py`
- `src/liquid_gas_transient/working_tool/runtime.py`
- `tools/working_tool/run_working_tool_v0_a.py`
- existing v0-A canonical case files, tests, and authoritative evidence documents.

All baseline solver, EOS, B1, B2, Hugoniot, root-search, χ, manager, Increment 9L, Increment 9M A2, and W2 physical source paths are protected. A6 MUST demonstrate zero physics diff from baseline commit `ec700d91d136469161be6dc1d1e1f1b6513798bb`.

New implementation SHOULD be isolated in new v0-B modules, with candidates including:

- `src/liquid_gas_transient/working_tool/operation_policy.py`
- `src/liquid_gas_transient/working_tool/output_size.py`
- `src/liquid_gas_transient/working_tool/storage_projection.py`
- `src/liquid_gas_transient/working_tool/run_manifest.py`
- `src/liquid_gas_transient/working_tool/output_v0_b.py`
- `src/liquid_gas_transient/working_tool/application_v0_b.py`
- `tools/working_tool/run_working_tool_v0_b.py`

New tests, a new v0-B workflow, and v0-B-specific evidence documents MAY be added in their normal repository locations.

---

## 19. Planned increments

### A0 — Contract freeze

- This document only.
- No implementation.
- Read-back, commit SHA, and baseline diff confirmation required before A1.

### A1 — Operation policy and estimator

- immutable strict policy;
- destination validation;
- maximum retained-sample count;
- truthful raw payload estimate;
- no physics/backend imports.

### A2 — State storage projection

- full-result layout validation;
- deterministic retained-index selection;
- versioned allowlist projection;
- static-array preservation;
- no source mutation or memory sharing;
- canonical interval tests for `1`, `10`, `64`, `100`, and `>640`.

### A3 — Manifest and v0-B writer

- reuse the existing five-file writer without altering it;
- write and hash the core five files;
- generate manifest last;
- enforce the exact six-file package.

### A4 — Run-directory operation

- explicit output;
- automatic output-root naming;
- safe slug;
- UTC timestamp;
- cryptographic suffix;
- bounded collision handling;
- hidden sibling temporary directory;
- atomic publication and cleanup.

### A5 — Repository-local CLI

- strict flags and mutual exclusion;
- truthful pre-run disclosure;
- clear full-runtime-capture statement;
- operational completion receipt;
- no manual `PYTHONPATH` requirement.

### A6 — Canonical regression and authoritative CI

- one fresh live A2/W2 solve;
- exact A2 regression;
- full and sampled projections from the same full result;
- public/evidence separation checks;
- v0-A legacy regression;
- authoritative source, workflow, run, job, artifact, and digest evidence.

### A7 — Closeout

- documentation-only commit after the authoritative implementation commit;
- authoritative source SHA and separate closeout HEAD;
- workflow/run/job and artifact/digest;
- limitations and unchanged formal status.

---

## 20. Completion gates

### G1 — Physics protection

Solver/EOS/B1/B2/Hugoniot/root/χ/manager/9L/9M/W2 backend physics diff is zero.

### G2 — v0-A backward compatibility

The legacy application and CLI path remain behaviorally unchanged.

### G3 — `FULL_STATE` compatibility

The five core files are semantically exact with v0-A; only the manifest is extra.

### G4 — Sampling correctness

Initial/final retention, no duplicates, exact alignment, unchanged copied `x_m`, and full scalar logs are demonstrated.

### G5 — Solver invariance

Operation policy never enters the backend, projection occurs after the full result, and A2 trajectory mismatch is zero.

### G6 — Truthful storage disclosure

The pre-run estimate is correctly labelled, post-run sizes/hashes are exact, and no memory-saving claim is made.

### G7 — Safe publication

Create-only, no overwrite, bounded collision-resistant naming, cleanup, and no partial completed run are demonstrated.

### G8 — Public/evidence separation

Normal public output contains no verification authority.

### G9 — Canonical authoritative regression

The 640-step final time, hashes, transitions, restoration evidence, and exact comparisons pass in the verification branch.

### G10 — Evidence hygiene

Authoritative source, workflow/job, artifact/digest, and closeout commit remain distinctly recorded.

### G11 — Formal status unchanged

The tool is not promoted to Verification, Acceptance, Validation, design-use acceptance, or production approval.

---

## 21. Expected v0-B closeout wording

```text
WORKING TOOL v0-B: COMPLETE

IMPLEMENTED
OUTPUT / STORAGE OPERATION POLICY TESTED
FULL-STATE STORAGE TESTED
SAMPLED-STATE STORAGE TESTED
PRE-RUN STORAGE DISCLOSURE TESTED
POST-RUN FILE INTEGRITY MANIFEST TESTED
CREATE-ONLY EXPLICIT OUTPUT TESTED
SAFE REPEAT-RUN NAMING TESTED
CANONICAL FULL-MODE REGRESSION PASSED
CANONICAL SAMPLED-STORAGE INVARIANCE PASSED
PUBLIC / VERIFICATION EVIDENCE SEPARATION PASSED
AUTHORITATIVE CI PASSED

NOT ARBITRARY-INPUT CAPABLE
NOT RUNTIME-MEMORY OPTIMIZED
NOT STREAMING-CAPABLE
NOT AN INSTALLED DISTRIBUTION ENTRY POINT
NOT VERIFIED
NOT ACCEPTED
NOT PHYSICALLY VALIDATED
NOT DESIGN-USE ACCEPTED
NOT PRODUCTION APPROVED
```

This wording is a future closeout target only. It is not asserted by A0.

---

## 22. A0 exit condition

A0 is complete only when:

1. this document is committed as the sole change from baseline;
2. the committed document is read back from the branch;
3. its content is confirmed readable and intact;
4. the branch commit SHA is recorded;
5. the baseline-to-branch diff shows exactly one added documentation file and no implementation change.

A1 MUST NOT begin before those checks pass.
