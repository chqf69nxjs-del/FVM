# Stage 7 — HEM Contact / Projection Contrast Validation Commands

## Environment

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -c "import CoolProp, matplotlib, numpy; print(CoolProp.__version__); print(matplotlib.__version__); print(numpy.__version__)"
```

Validated environment:

```text
Python 3.11.15
CoolProp 8.0.0
matplotlib 3.11.1
numpy 2.4.6
```

## Focused tests

```powershell
python -m pytest -q `
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py `
  tests/test_stage7_lco2_hem_nonuniform_quality_sync.py `
  tests/test_stage7_lco2_hem_quality_sync_contact_comparison.py `
  tests/test_stage7_lco2_hem_uniform_state_preservation.py
```

Validated result:

```text
67 passed in 5.04 s
```

## Fixed comparison runner

```powershell
python -m liquid_gas_transient.hem_quality_sync_contact_comparison `
  --output-dir artifacts/stage7_lco2_hem_quality_sync_contact_comparison
```

Required files:

```text
stage7_lco2_hem_quality_sync_contact_comparison.json
stage7_lco2_hem_quality_sync_contact_comparison_history.csv
stage7_lco2_hem_quality_sync_contact_comparison_final_profile.csv
stage7_lco2_hem_quality_sync_contact_comparison.md
stage7_lco2_hem_quality_sync_contact_comparison.npz
quality_contact_comparison.png
projection_activity_comparison.png
contact_comparison_budgets.png
```

## Required numerical checks

The JSON summary must show:

```text
no_op_projection_total_cell_updates = 0
activated_projection_total_cell_updates > 0
delta_q_contrast_satisfied = true
projection_activity_contrast_satisfied = true
vapor_source_contrast_satisfied = true
comparison_acceptance_satisfied = true
```

The nested no-op summary must show:

```text
contact_transport_exercised = true
quality_max_jump_reduced = true
mixed_quality_cell_count >= 2
quality_no_op_tolerance_satisfied = true
equal_pressure_span_tolerance_satisfied = true
phase_vapor_source_max_abs_kg = 0
```

Validated observations:

```text
no-op projected cells by step:            0, 0, 0, 0
activated projected cells by step:        2, 4, 6, 8
no-op maximum |delta q|:                  4.440892098500626e-16
activated maximum |delta q|:              2.4143668471476865e-5
activated/no-op |delta q| ratio:          5.436670816575e10
no-op pressure span:                      1.6298145055770874e-9 Pa
no-op mixed-quality cells:                8
no-op cumulative projection vapor source: 0.0 kg
activated cumulative vapor source:        3.501570117236952e-5 kg
```

## Full repository

```powershell
python -m pytest -q
```

Validated result:

```text
514 passed in 127.91 s
```

## Static checks

```powershell
git diff --check origin/main...HEAD
git status -sb
git diff --stat origin/main...HEAD
```

Expected permanent diff:

```text
src/liquid_gas_transient/hem_quality_sync_contact_comparison.py
tests/test_stage7_lco2_hem_quality_sync_contact_comparison.py
docs/verification/stage7_lco2_hem_quality_sync_contact_comparison_plan.md
docs/verification/stage7_lco2_hem_quality_sync_contact_comparison_validation_commands.md
```

## Validation closeout

```text
validation head:       7a6dd47b7c72eb87f3415b66bdc4d034ff7c19b5
workflow run:          29812617503
artifact ID:           8488096499
artifact SHA256:       db0a5e997bd3fc07cba2d5a7470724778f2a3ac831ea1c62804e26a97c37b19b
focused tests:         67 passed
full repository:       514 passed
fixed runner:          success
static diff checks:    success
artifact upload:       success
```

The validation artifact also contains:

```text
focused_pytest.txt
full_pytest.txt
numerical_summary.txt
validation_environment.txt
SHA256SUMS.txt
```

## Approval boundary

```text
verification_only = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```
