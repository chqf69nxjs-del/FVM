# Stage 7 LCO2 HEM Equilibrium Sound-Speed — Validation Commands

The acoustic scaffold is verification-only and is not connected to `FvmSolver`, Rusanov
flux, or CFL.

## Windows PowerShell

```powershell
$env:PYTHONPATH = "src"

python -m pytest -q `
  tests/test_stage7_lco2_hem_thermodynamic_scaffold.py `
  tests/test_stage7_lco2_hem_phase_classification.py `
  tests/test_stage7_lco2_hem_equilibrium_sound_speed.py `
  tests/test_coolprop_backend_installed.py

python -m liquid_gas_transient.hem_equilibrium_sound_speed `
  --output-dir verification/stage7_lco2_hem_equilibrium_sound_speed

python -m pytest -q

git diff --check origin/agent/stage7-lco2-hem-phase-classification...HEAD
git diff --check origin/main...HEAD
git status -sb
```

## Expected artifact inventory

```text
stage7_lco2_hem_equilibrium_sound_speed.json
stage7_lco2_hem_equilibrium_sound_speed.csv
stage7_lco2_hem_equilibrium_sound_speed.md
```

## Required evidence flags

```text
scope = verification_only
production_solver_connected = false
production_cfl_connected = false
production_flux_connected = false
equilibrium_two_phase_sound_speed_closure_approved = false
coolprop_two_phase_sound_speed_requested = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

A green result demonstrates a guarded numerical implementation of an equilibrium acoustic
closure candidate and its single-phase consistency check. It does not approve the two-phase
closure for production or establish design accuracy.
