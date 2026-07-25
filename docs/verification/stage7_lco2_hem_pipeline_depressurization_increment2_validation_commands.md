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
12 passed, 0 skipped, 0 failed, 0 errors
```

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

## Installed-CoolProp Increment 2 tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_increment2.py \
  -m coolprop_installed \
  --strict-markers
```

Authoritative result:

```text
3 passed, 0 skipped, 0 failed, 0 errors
```

These tests fix the observed outcome matrix:

```text
5→2 MPa: ACCEPTED_FIRST_CROSSING
5→3 MPa: ACCEPTED_FIRST_CROSSING
5→4 MPa: GUARD_FAILURE with retained subthreshold raw crossing
```

They also verify all 195 boundary-path samples, zero reverse-flow fallback, artifact bundle
completeness, and exact frozen PR #72 Case A/B regression signatures.

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
690 passed, 0 skipped, 0 failed, 0 errors
```

## Authoritative GitHub Actions evidence

```text
validated head:                  2d09fd98af32f77969be49f5c1394c05e6314ea5
workflow run:                    30146579752
artifact ID:                     8616354622
artifact SHA256:                 3e5dce108b433ffc3caa288487fb461e461a2fb7bc5b47bd724546ae730acd6a
runner source Git blob:          414f6019710091cd51ed8732859f71b695783d18
focused test Git blob:           e9823c6c66d6f664e095f986066aa9213863736b
```

Permanent workflow results on the validated head:

```text
CoolProp Wave Regression:                 success, run 501 / 30146579780
CoolProp Controlled Pressure Ramp:        success, run 445 / 30146579751
CoolProp Boundary Reflection Regression:  success, run 466 / 30146579786
CoolProp Internal Valve Regression:       success, run 321 / 30146579741
```

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
