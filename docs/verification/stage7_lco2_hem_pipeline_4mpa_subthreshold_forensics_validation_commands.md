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
  -m 'not coolprop_installed' \
  --strict-markers
```

Authoritative result:

```text
7 passed, 0 skipped, 0 failed, 0 errors
```

These tests fix the observation window, perturbation grid, PR #77 baseline guard, and
sensitivity-classification control flow without substituting for CoolProp evidence.

## Installed-CoolProp forensic tests

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics.py \
  -m coolprop_installed \
  --strict-markers
```

Authoritative result:

```text
8 passed, 0 skipped, 0 failed, 0 errors
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

## Related Stage 7 regressions

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_increment2.py \
  tests/test_stage7_lco2_hem_pipeline_depressurization_boundary_increment1.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab.py \
  --strict-markers
```

Authoritative result:

```text
69 passed, 0 skipped, 0 failed, 0 errors
```

## Full repository

```bash
python -m pytest -q --strict-markers
```

Authoritative result:

```text
721 passed, 0 skipped, 0 failed, 0 errors
```

## Authoritative GitHub Actions evidence

```text
validated head:                 3040fdcdf51771bc0d03075e9aae0eb3b49a46d4
workflow run:                   30160740321
artifact ID:                    8620327622
artifact SHA256:                50b8841dcfc0bc8f853c2356f99b755f8aed9c78eee962a9e58744f166788915
CoolProp:                       8.0.0
forensic source Git blob:       af02452313fd942004f6b8d6ce1662e30c16ac1f
focused test Git blob:          9671974b63ee6d97839a53ff55cac7a5df1ecf98
```

Permanent workflows on the validated head:

```text
CoolProp Wave Regression:                 success, run 548 / 30160740335
CoolProp Controlled Pressure Ramp:        success, run 492 / 30160740323
CoolProp Boundary Reflection Regression:  success, run 513 / 30160740342
CoolProp Internal Valve Regression:       success, run 368 / 30160740328
```

## Required interpretation

Successful execution means the fixed forensic diagnostic is internally reproducible and
its artifacts are consistent. It does not mean:

```text
Gate P2 passed
physical nucleation was demonstrated
the 4 MPa result is mesh independent
the two-phase acoustic closure is validated
the prescribed outlet is a physical valve/tank model
design or production use is approved
```
