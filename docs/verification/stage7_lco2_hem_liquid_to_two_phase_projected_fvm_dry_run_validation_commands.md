# Stage 7 Projected Liquid-to-Two-Phase FVM Dry Run — Validation Commands

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
git switch agent/stage7-projected-liquid-crossing-step
git status --short --branch
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected permanent files after temporary-workflow removal:

```text
src/liquid_gas_transient/
  hem_liquid_to_two_phase_projected_fvm_dry_run.py

tests/
  test_stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run.py

docs/verification/
  stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run_plan.md
  stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run_validation_commands.md
  stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run_evidence.md
```

## Syntax check

```bash
python -m compileall -q src/liquid_gas_transient
```

## Focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run.py \
  --strict-markers
```

The installed-CoolProp test must not skip.

## Fixed projected matrix

```bash
rm -rf verification/stage7_lco2_hem_projected_fvm_dry_run

python -m \
  liquid_gas_transient.hem_liquid_to_two_phase_projected_fvm_dry_run \
  --output-dir verification/stage7_lco2_hem_projected_fvm_dry_run
```

Required artifacts:

```text
stage7_lco2_hem_projected_fvm_dry_run.json
stage7_lco2_hem_projected_fvm_dry_run_cases.csv
stage7_lco2_hem_projected_fvm_dry_run_cells.csv
stage7_lco2_hem_projected_fvm_dry_run.md
stage7_lco2_hem_projected_fvm_dry_run.npz
```

## Required matrix assertions

```text
accepted crossing cases:
    strong_p5m5_to_p2m5
    moderate_p5m5_to_p3m5

accepted liquid no-op case:
    control_p5m5_to_p4m5

strong crossing cells:
    3, 4

moderate crossing cells:
    4

control crossing cells:
    none

first projection cells:
    exactly equal crossing cells

second projection cells:
    none for every case
```

## Required projection assertions

```text
rho unchanged bitwise
rho*u unchanged bitwise
rho*E unchanged bitwise
q_after = q_eq within 1e-12
post regions = raw thermodynamic regions
post pressure finite and positive
post temperature finite and positive
post sound speed finite and positive
post mixed accepted-state EOS succeeds
```

## Required vapor-budget assertions

For each case:

```text
PhaseChangeBudgetTracker source
=
sum(delta rho*q) * dx * area

post vapor inventory
=
raw vapor inventory + projection source

post vapor inventory
=
initial vapor + raw boundary vapor net + projection source
```

Required residuals:

```text
abs(phase_vapor_mass_balance_residual_kg) <= 1e-12
abs(projection_source_consistency_residual_kg) <= 1e-12
abs(combined_post_vapor_balance_residual_kg) <= 1e-12
```

The control projection source must be zero.

## Related Stage 7 HEM tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_phase_classification.py \
  tests/test_stage7_lco2_hem_equilibrium_sound_speed.py \
  tests/test_stage7_lco2_hem_uniform_state_preservation.py \
  tests/test_stage7_lco2_hem_equilibrium_quality_sync.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py \
  tests/test_stage7_lco2_hem_mixed_liquid_open_two_phase_eos.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_state_pair_survey.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run.py \
  --strict-markers
```

## Full repository

```bash
pytest -q --strict-markers
```

Record the actual test counts. Do not reuse PR #70's `616 passed` count without running the
current suite.

## Evidence flags

The generated JSON must retain:

```text
scope = verification_only
raw_first_order_fvm_crossing_observed = true
equilibrium_quality_projection_exercised = true
post_projection_accepted_eos_exercised = true
second_projection_noop_exercised = true
phase_vapor_budget_exercised = true
complete_one_step_crossing_path_observed = true
actual_first_order_fvm_crossing_verified = false
case_a_frozen = false
case_b_frozen = false
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Final workflow confirmation

After temporary validation evidence is captured and the temporary workflow is removed,
confirm all permanent pull-request workflows succeed on the final PR head. Record the run
identifiers and conclusions in the PR body before review.
