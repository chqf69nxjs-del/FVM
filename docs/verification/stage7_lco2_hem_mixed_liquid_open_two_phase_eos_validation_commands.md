# Stage 7 Mixed Liquid/Open-Two-Phase EOS — Validation Commands

## Environment

```bash
cd /home/o6046/FVM
source .venv/bin/activate
python --version
python -c "import CoolProp; print(CoolProp.__version__)"
```

Expected:

```text
Python:   3.11.15
CoolProp: 8.0.0
backend:  coolprop_co2
```

## Branch and diff

```bash
git fetch origin
git switch agent/stage7-mixed-liquid-open-two-phase-eos
git status --short --branch
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected permanent file set:

```text
src/liquid_gas_transient/hem_mixed_liquid_open_two_phase_eos.py
tests/test_stage7_lco2_hem_mixed_liquid_open_two_phase_eos.py
docs/verification/stage7_lco2_hem_mixed_liquid_open_two_phase_eos_plan.md
docs/verification/stage7_lco2_hem_mixed_liquid_open_two_phase_eos_validation_commands.md
```

No temporary workflow file may remain in the final diff.

## Syntax check

```bash
python -m compileall -q src/liquid_gas_transient
```

## Dependency-free focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_mixed_liquid_open_two_phase_eos.py \
  -m "not coolprop_installed" \
  --strict-markers
```

## Installed-CoolProp focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_mixed_liquid_open_two_phase_eos.py \
  --strict-markers
```

Installed tests must execute without skips and verify:

```text
5 MPa / 280 K liquid
+
2 MPa / Q=0.50 open two phase
```

in one accepted array.

They must also verify:

```text
2 MPa / Q=0 saturated liquid
-> endpoint_acoustic_closure_not_established
```

## Related Stage 7 HEM tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_phase_classification.py \
  tests/test_stage7_lco2_hem_equilibrium_sound_speed.py \
  tests/test_stage7_lco2_hem_uniform_state_preservation.py \
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py \
  tests/test_stage7_lco2_hem_mixed_liquid_open_two_phase_eos.py \
  --strict-markers
```

## Full repository

```bash
pytest -q --strict-markers
```

Record the actual test counts. Do not reuse the earlier `546 passed`
baseline without executing the current suite.

## Required review assertions

```text
accepted per-cell regions:
    LIQUID_CANDIDATE
    OPEN_TWO_PHASE

rejected:
    saturation endpoints
    vapor
    guarded/unknown/invalid states

phase evaluation:
    canonical rho/e
    supplied HEMPhaseClassificationConfig

quality:
    strict bounds [0, 1]
    accepted-state mismatch tolerance = 1e-10
    tolerance not tighter than projection activation tolerance
    no clipping

acoustics:
    same existing equilibrium sound-speed estimator for liquid and two phase
    no runtime CoolProp A branch
    finite positive result required
    center phase must agree

solver:
    primitive/CFL compatibility only
    no FVM step
    no crossing case
    no state-pair exploration

approval:
    verification only
    production HEM false
    physical Validation false
    design use false
    acoustic accuracy band false
```

## Final workflow confirmation

After temporary validation evidence is captured and the temporary workflow is
removed, confirm all permanent pull-request workflows succeed on the final PR
head. Record run identifiers and conclusions in the PR body before merge.
