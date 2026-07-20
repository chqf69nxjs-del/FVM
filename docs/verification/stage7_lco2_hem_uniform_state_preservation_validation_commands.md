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

## GitHub validation evidence

```text
validation head:          068bd1d9d1a57c30687cf217273d9f87eb04f424
workflow run:             29751190749
artifact ID:              8464712262
artifact SHA256:          71f7934f6f0061191f8af09b9cdf802a5b797f628878cd045a13a94273f5e999
focused HEM tests:        76 passed, 0 skipped
full repository:          460 passed, 0 skipped
uniform-state history:    9 records including step zero
uniform cells / steps:    8 / 8
```

Observed fixed-case results:

```text
rho:                              99.97757528102285 kg/m3
internal energy:                  276181.4404260976 J/kg
temperature:                      253.64735829812284 K
quality:                          0.5
void fraction:                    0.951436972434191
equilibrium sound speed:          135.76568112572576 m/s
dt:                               0.002301759895496782 s
final time:                       0.018414079163974254 s
maximum CFL:                      0.25
conserved maximum absolute drift: 0.0
conserved maximum relative drift: 0.0
all primitive drifts:             0.0
all inventory drifts:             0.0
```

The temporary validation workflow extension is removed before review-ready state. These are
uniform-state software invariants. They are not an accuracy band for a nonuniform two-phase
flow, an acoustic Validation result, or design-use acceptance.
