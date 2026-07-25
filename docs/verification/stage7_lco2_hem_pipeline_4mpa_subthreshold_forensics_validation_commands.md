# Stage 7 — Fixed 4 MPa Forensic Validation Commands

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

## Dependency-free tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics.py \
  tests/test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_contract.py \
  -m 'not coolprop_installed' \
  --strict-markers
```

Final authoritative result:

```text
8 passed, 0 skipped, 0 failed, 0 errors
```

These tests fix the observation window, perturbation grid, PR #77 baseline guard,
sensitivity-classification control flow, machine-readable contract scope, and approval
boundary without substituting for CoolProp evidence.

## Installed-CoolProp forensic tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics.py \
  tests/test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_contract.py \
  -m coolprop_installed \
  --strict-markers
```

Final authoritative result:

```text
9 passed, 0 skipped, 0 failed, 0 errors
```

The installed set requires:

```text
exact PR #77 baseline identity
complete step 300–313 / cell 23–27 evidence
positive independent crossing margins at step 313 / cell 25
explicit isentropic reference
exact Rusanov central+dissipative reconstruction
complete 9x9 rho/e perturbation grid
exact repeated forensic execution
exact machine-readable contract agreement
complete JSON/CSV/NPZ/Markdown/PNG artifact bundle
frozen PR #72 Case A/B signatures
```

## Generate the artifact bundle

```bash
python -m liquid_gas_transient.hem_pipeline_4mpa_subthreshold_forensics \
  --output-dir artifacts/stage7-4mpa-forensics
```

Expected files:

```text
4mpa_forensic_summary.json
4mpa_local_cell_history.csv
4mpa_saturation_margin.csv
4mpa_isentropic_reference.json
4mpa_flux_decomposition.csv
4mpa_property_perturbation.csv
4mpa_property_perturbation.npz
4mpa_forensic_evidence.md
rho_e_saturation_zoom.png
saturation_margin_vs_time.png
central_vs_dissipative_update.png
perturbation_classification_map.png
```

The authoritative summary must retain:

```text
baseline_reproduced_exactly = true
perturbation_sensitivity = WEAKLY_RESOLVED
diagnostic_categories = [
  THERMODYNAMIC_TWO_PHASE_SUPPORTED,
  NEAR_SATURATION_PROPERTY_SENSITIVE,
  MULTI_FACTOR_EVIDENCE
]
Gate_P2_passed = false
```

## Related Stage 7 regressions

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_increment2.py \
  tests/test_stage7_lco2_hem_pipeline_depressurization_boundary_increment1.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab.py \
  --strict-markers
```

Final authoritative result:

```text
69 passed, 0 skipped, 0 failed, 0 errors
```

## Full repository

```bash
python -m pytest -q --strict-markers
```

Final authoritative result:

```text
723 passed, 0 skipped, 0 failed, 0 errors
```

## Final authoritative GitHub Actions evidence

```text
validated implementation head:   719301dd64c9ee2571cf3296605466a2ee9de27f
workflow run:                     30162194409
artifact ID:                      8620823392
artifact SHA256:                  1b2c14790c3c66be47386f60ddb9c8b21ee5d253dcc0ab1d78e9deaa7b5184d7
CoolProp:                         8.0.0
forensic source Git blob:         af02452313fd942004f6b8d6ce1662e30c16ac1f
focused test Git blob:            9671974b63ee6d97839a53ff55cac7a5df1ecf98
contract test Git blob:           409f97edda208885de6eabc9d67dbf674f8a3a5f
```

Permanent workflows on the validated implementation head:

```text
CoolProp Wave Regression:                 success, run 556 / 30162194483
CoolProp Controlled Pressure Ramp:        success, run 500 / 30162194405
CoolProp Boundary Reflection Regression:  success, run 521 / 30162194415
CoolProp Internal Valve Regression:       success, run 376 / 30162194406
```

The final workflow also parsed all four JUnit reports and explicitly required zero skipped,
failed, or errored tests.

## Required interpretation

Successful execution means the fixed forensic diagnostic is internally reproducible and
its artifacts agree with the machine-readable contract. It does not mean:

```text
Gate P2 passed
physical nucleation was demonstrated
the 4 MPa result is mesh independent
the two-phase acoustic closure is validated
the prescribed outlet is a physical valve/tank model
design or production use is approved
```
