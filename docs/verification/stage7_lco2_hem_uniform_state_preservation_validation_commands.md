# Stage 7 LCO2 HEM Uniform-State Preservation — Validation Commands

This increment is verification-only and is stacked on PR #56.

## Windows PowerShell

```powershell
$env:PYTHONPATH = "src"

python -m pytest -q `
  tests/test_stage7_lco2_hem_phase_classification.py `
  tests/test_stage7_lco2_hem_equilibrium_sound_speed.py `
  tests/test_stage7_lco2_hem_uniform_state_preservation.py

python -m liquid_gas_transient.hem_uniform_state_preservation `
  --output-dir verification/stage7_lco2_hem_uniform_state_preservation `
  --cells 8 `
  --steps 8

python -m pytest -q

git diff --check origin/agent/stage7-lco2-hem-equilibrium-sound-speed...HEAD
git diff --check origin/main...HEAD
git status -sb
```

CoolProp is required. In an installed-CoolProp CI job, focused tests must run with zero skips.

## Required artifact inventory

```text
stage7_lco2_hem_uniform_state_preservation.json
stage7_lco2_hem_uniform_state_preservation.csv
stage7_lco2_hem_uniform_state_preservation.md
stage7_lco2_hem_uniform_state_preservation.npz
```

## Required evidence flags

```text
scope = verification_only
fvm_solver_exercised = true
rusanov_flux_exercised = true
cfl_exercised = true
transmissive_boundaries = true
source_term_enabled = false
phase_change_operator_enabled = false
internal_interfaces_enabled = false
verification_only_hem_eos_adapter = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
uniform_state_preserved = true
```

## Required numerical observations

```text
conserved maximum absolute drift <= 1e-10
conserved maximum relative drift <= 1e-12
pressure drift = 0 within verification tolerance
quality drift = 0 within verification tolerance
void-fraction drift = 0 within verification tolerance
mass, momentum, energy and vapor-mass inventories unchanged
CFL maximum equals the configured value for the stationary uniform state
```

These are uniform-state software invariants. They are not an accuracy band for a nonuniform
two-phase flow, an acoustic Validation result, or design-use acceptance.
