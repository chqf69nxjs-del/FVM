# Stage 7 — LCO2 HEM Pipeline Depressurization Increment 2 Validation Commands

## Environment

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[plotting]'
python -m pip install pytest 'CoolProp==8.0.0'
export PYTHONPATH=src
export MPLBACKEND=Agg
```

## Compile and diff checks

```bash
python -m compileall -q src tests
git diff --check
```

## Dependency-free Increment 2 tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_increment2.py \
  -m 'not coolprop_installed' \
  --strict-markers
```

Authoritative result:

```text
26 passed, 0 skipped, 0 failed, 0 errors
```

These tests enforce the complete fixed configuration, including the phase and projection
configs, crossing-evidence threshold, accepted-state tolerance, and every mass, momentum,
energy, and vapor-budget tolerance. They also require the reviewed Gate P2 rule that the
4 MPa control must finish as `NO_CROSSING_WITHIN_HORIZON` with no raw crossing.

## Generate the fixed-matrix evidence bundle

```bash
python -m liquid_gas_transient.hem_pipeline_depressurization_first_crossing \
  --output-dir artifacts/stage7-pipeline-increment2
```

Expected artifact names:

```text
stage7_lco2_hem_pipeline_depressurization_increment2.json
stage7_lco2_hem_pipeline_depressurization_increment2_cases.csv
stage7_lco2_hem_pipeline_depressurization_increment2_steps.csv
stage7_lco2_hem_pipeline_depressurization_increment2_cells.csv
stage7_lco2_hem_pipeline_depressurization_increment2_boundary_path.csv
stage7_lco2_hem_pipeline_depressurization_increment2.md
stage7_lco2_hem_pipeline_depressurization_increment2.npz
```

The JSON artifact records the entire effective fixed configuration, fixed case matrix,
reviewed Gate P2 rule, and the explicit 4 MPa control outcome.

## Installed-CoolProp Increment 2 tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_increment2.py \
  -m coolprop_installed \
  --strict-markers
```

Authoritative result:

```text
5 passed, 0 skipped, 0 failed, 0 errors
```

These tests fix the observed outcome matrix:

```text
5→2 MPa: ACCEPTED_FIRST_CROSSING
5→3 MPa: ACCEPTED_FIRST_CROSSING
5→4 MPa: GUARD_FAILURE with retained subthreshold raw crossing
```

They verify all 195 boundary-path samples, zero reverse-flow fallback, exact
machine-readable observation-contract fields, complete effective configuration output,
artifact bundle completeness, exact frozen PR #72 Case A/B signatures, and a second full
fixed-matrix execution with exact repeatability.

The repeatability comparison requires exact equality of:

```text
matrix summary
outcome and failure reason
step count and final time
crossing step, time, cells, and distance
maximum crossing quality
final-state SHA256
run signature SHA256
```

## Related pre-existing Stage 7 HEM tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_spec.py \
  tests/test_stage7_lco2_hem_pipeline_depressurization_boundary_increment1.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab.py \
  --strict-markers
```

Authoritative result:

```text
74 passed, 0 skipped, 0 failed, 0 errors
```

## Full repository

```bash
python -m pytest -q --strict-markers
```

Authoritative result:

```text
706 passed, 0 skipped, 0 failed, 0 errors
```

## Authoritative GitHub Actions evidence

```text
validated implementation head:  2bbe2ad210d45c6403aa0b9a6a097dff56b44685
workflow run:                    30154880687
artifact ID:                     8618870653
artifact SHA256:                 7d254126a741e7d92e5ed1a2b6da94c703bbc2da91f1769d58c11deaa22b89b9
runner source Git blob:          87df463996ea68789764e11f4ce9799ec214440e
focused test Git blob:           817cb1c8c42658481ab0babcdddc34ab7966c4a2
```

Permanent workflow results on the validated implementation head:

```text
CoolProp Wave Regression:                 success, run 513 / 30154880697
CoolProp Controlled Pressure Ramp:        success, run 457 / 30154880677
CoolProp Boundary Reflection Regression:  success, run 478 / 30154880664
CoolProp Internal Valve Regression:       success, run 333 / 30154880684
```

Subsequent commits only update documentation and remove temporary validation machinery.
The source and focused-test Git blobs above remain unchanged.

## Required interpretation

Successful test execution does not imply Gate P2 passed. The authoritative fixed matrix is
validly executed and retained, but the 4 MPa intended liquid control produced a subthreshold
raw crossing. Therefore:

```text
fixed_matrix_explicit_outcomes_retained = true
gate_p2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
