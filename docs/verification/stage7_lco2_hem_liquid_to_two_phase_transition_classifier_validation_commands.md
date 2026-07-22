# Stage 7 — Liquid-to-Two-Phase Transition Classifier Validation Commands

## Environment

```bash
cd /home/o6046/FVM
source .venv/bin/activate
python --version
python -c "import CoolProp; print(CoolProp.__version__)"
```

Expected environment:

```text
Python:   3.11.15
CoolProp: 8.0.0
backend:  coolprop_co2
```

## Branch and diff

```bash
git fetch origin
git switch agent/stage7-liquid-two-phase-transition-classifier
git status --short --branch
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected permanent file set:

```text
src/liquid_gas_transient/hem_liquid_to_two_phase_crossing.py
tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py
docs/verification/stage7_lco2_hem_liquid_to_two_phase_transition_classifier_plan.md
docs/verification/stage7_lco2_hem_liquid_to_two_phase_transition_classifier_validation_commands.md
```

## Syntax check

```bash
python -m compileall -q src/liquid_gas_transient
```

## Dependency-free focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py \
  -m "not coolprop_installed"
```

## Installed-CoolProp focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py
```

The installed test must not skip in the intended WSL environment. It must confirm the
actual `rho/e` endpoint mapping:

```text
2 MPa / Q=0 -> SATURATED_LIQUID_ENDPOINT
2 MPa / Q=1 -> SATURATED_VAPOR_ENDPOINT
```

## Related Stage 7 regression tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_phase_classification.py \
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py
```

## Full repository

```bash
pytest -q
```

The full-suite count must be recorded rather than assumed from the earlier `514 passed`
baseline.

## Required review assertions

```text
classifier uses direct rho/e evaluation
transported q is not a phase classifier
endpoint tolerance comes from HEMPhaseClassificationConfig
no quality clipping is added
guarded/unknown/invalid states fail atomically
current e >= 0 solver constraint is retained
no FvmSolver, flux, CFL, projection, EOS, or sound-speed behavior changes
production HEM activation remains false
physical Validation remains false
design-use acceptance remains false
```

## Permanent GitHub workflows

Confirm all permanent workflows complete successfully for the final PR head. Record the
run identifiers and conclusions in the PR before merge.
