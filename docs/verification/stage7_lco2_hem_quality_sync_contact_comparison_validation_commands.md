# Stage 7 — HEM Contact / Projection Contrast Validation Commands

## Environment

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -c "import CoolProp, matplotlib, numpy; print(CoolProp.__version__); print(matplotlib.__version__); print(numpy.__version__)"
```

## Focused tests

```powershell
python -m pytest -q `
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py `
  tests/test_stage7_lco2_hem_nonuniform_quality_sync.py `
  tests/test_stage7_lco2_hem_quality_sync_contact_comparison.py `
  tests/test_stage7_lco2_hem_uniform_state_preservation.py
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

## Full repository

```powershell
python -m pytest -q
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

## Closeout record

Record the following in the PR after validation:

```text
validation head
workflow run
artifact ID and SHA256
focused test count
full repository test count
fixed runner result
projection counts by step for both cases
maximum |delta q| for both cases
contrast ratio
maximum budget residuals
final approval-boundary flags
```
