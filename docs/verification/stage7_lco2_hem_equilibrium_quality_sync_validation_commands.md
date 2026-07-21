# Stage 7 — HEM Equilibrium-Quality Synchronization Validation Commands

## Scope

These commands validate the verification-only equilibrium-quality projection and
its compatibility with the existing post-source phase-change slot.

They do not approve production HEM activation, physical Validation, design use,
or a real-fluid accuracy band.

## Environment

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -c "import sys, numpy; print(sys.version); print('numpy', numpy.__version__)"
```

For installed-CoolProp gates:

```powershell
python -c "import CoolProp; print('CoolProp', CoolProp.__version__)"
```

## Pure and FVM-slot tests

```powershell
python -m pytest -q `
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py `
  -m "not coolprop_installed"
```

These tests cover:

- bitwise no-op;
- intentional mismatch correction;
- idempotence;
- input immutability;
- fail-fast phase/quality guards;
- no clipping of out-of-range transported quality;
- time argument validation;
- analytic strict-EOS FVM phase-change-slot integration;
- phase-vapor and conservative-energy budget behavior.

## Installed-CoolProp focused tests

```powershell
python -m pytest -q `
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py `
  tests/test_stage7_lco2_hem_phase_classification.py `
  tests/test_stage7_lco2_hem_equilibrium_sound_speed.py `
  tests/test_stage7_lco2_hem_uniform_state_preservation.py
```

Required CoolProp observations:

```text
dense-liquid candidate projects to q_eq = 0
open two-phase state projects to the backend equilibrium quality
single-phase vapor candidate projects to q_eq = 1
strict PR #57 EOS rejects mismatch before projection
strict PR #57 EOS accepts the repaired state after projection
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

Expected implementation diff:

```text
src/liquid_gas_transient/hem_equilibrium_quality_sync.py
tests/test_stage7_lco2_hem_equilibrium_quality_sync.py
docs/verification/stage7_lco2_hem_equilibrium_quality_sync_plan.md
docs/verification/stage7_lco2_hem_equilibrium_quality_sync_validation_commands.md
```

The governing specification is already merged separately and should not appear
as a new file in this implementation diff.

## Acceptance checks

The focused run must confirm:

```text
mass column bitwise unchanged
momentum column bitwise unchanged
total-energy column bitwise unchanged
post-projection quality equals equilibrium quality within configured tolerance
second projection is a no-op
unsupported states fail without partial output
phase-vapor source matches integrated delta_rho_q
conservative phase-energy delta is exactly zero
strict EOS handoff succeeds after projection
```

## Deliberately deferred

The following are not acceptance criteria for this implementation-only increment:

- weak pressure-offset real-CO2 multi-step run;
- equal-pressure nonuniform contact case;
- saved JSON/CSV/NPZ numerical artifacts;
- human-review PNG figures;
- liquid-to-two-phase boundary crossing;
- wall heat transfer, friction or discharge boundaries;
- HNE, impurities or higher-order transport.
