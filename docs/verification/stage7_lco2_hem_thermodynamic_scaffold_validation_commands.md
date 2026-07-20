# Stage 7 LCO2 HEM Thermodynamic Scaffold — Validation Commands

The scaffold is verification-only and is not connected to `FvmSolver`.

## Windows PowerShell

```powershell
$env:PYTHONPATH = "src"

python -m pytest -q `
  tests/test_property_backend_pt_energy.py `
  tests/test_coolprop_backend_installed.py `
  tests/test_stage7_lco2_hem_thermodynamic_scaffold.py

python -m pytest -q

python -m liquid_gas_transient.hem_thermodynamics `
  --output-dir verification/stage7_lco2_hem_zero_d_flash

git diff --check origin/main...HEAD
git status -sb
```

CoolProp-specific tests are installed-only. They must skip explicitly when CoolProp is not
available; a CI job that installs CoolProp must require them to run without skips.

## Expected scaffold artifact inventory

```text
stage7_lco2_hem_zero_d_flash.json
stage7_lco2_hem_zero_d_flash.csv
stage7_lco2_hem_zero_d_flash.md
stage7_lco2_hem_zero_d_flash.npz
```

## Required evidence flags

```text
scope = verification_only
backend_name = surrogate_lco2
production_solver_connected = false
production_solver_behavior_changed = false
pure_co2_hem_thermodynamic_core_complete = false
equilibrium_two_phase_sound_speed_closure_approved = false
backend_reported_sound_speed_is_diagnostic_only = true
solid_phase_supported = false
critical_region_validated = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Review note

A green scaffold demonstrates only that the existing property-backend contract can be
wrapped with explicit HEM-oriented validation and exercised along a deterministic
surrogate liquid/two-phase/vapor path. It does not establish the final CoolProp HEM closure
or authorize use of backend-reported two-phase sound speed in the production CFL/flux path.
