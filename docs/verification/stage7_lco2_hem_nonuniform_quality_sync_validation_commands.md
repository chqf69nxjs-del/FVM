# Stage 7 — Nonuniform HEM Quality-Sync Validation Commands

## Environment

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -c "import CoolProp, matplotlib, numpy; print(CoolProp.__version__); print(matplotlib.__version__); print(numpy.__version__)"
```

## Focused test

```powershell
python -m pytest -q `
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py `
  tests/test_stage7_lco2_hem_nonuniform_quality_sync.py `
  tests/test_stage7_lco2_hem_uniform_state_preservation.py
```

## Fixed runner

```powershell
python -m liquid_gas_transient.hem_nonuniform_quality_sync `
  --output-dir artifacts/stage7_lco2_hem_nonuniform_quality_sync
```

Required files:

```text
stage7_lco2_hem_nonuniform_quality_sync.json
stage7_lco2_hem_nonuniform_quality_sync_history.csv
stage7_lco2_hem_nonuniform_quality_sync_final_profile.csv
stage7_lco2_hem_nonuniform_quality_sync.md
stage7_lco2_hem_nonuniform_quality_sync.npz
quality_sync_snapshot.png
hem_state_profiles.png
conservation_and_projection_history.png
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
src/liquid_gas_transient/hem_nonuniform_quality_sync.py
tests/test_stage7_lco2_hem_nonuniform_quality_sync.py
docs/verification/stage7_lco2_hem_nonuniform_quality_sync_plan.md
docs/verification/stage7_lco2_hem_nonuniform_quality_sync_validation_commands.md
```

## Human-review checklist

Confirm from the saved artifacts and PNGs:

```text
projection is active at one or more cells
q_after and q_equilibrium overlap
all phase_class entries are liquid_vapor_two_phase
pressure and velocity contain no non-finite values or isolated numerical spikes
sound speed remains finite and positive
mass / momentum / energy budget residuals remain within tolerance
vapor inventory change closes with boundary flux plus projection source
conservative phase-energy delta remains exactly zero
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
