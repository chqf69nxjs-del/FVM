# Stage 7 Liquid-to-Two-Phase State-Pair Survey — Validation Commands

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
git switch agent/stage7-liquid-state-pair-survey
git status --short --branch
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected permanent files after temporary-workflow removal:

```text
src/liquid_gas_transient/hem_liquid_to_two_phase_state_pair_survey.py
tests/test_stage7_lco2_hem_liquid_to_two_phase_state_pair_survey.py
docs/verification/stage7_lco2_hem_liquid_to_two_phase_state_pair_survey_plan.md
docs/verification/stage7_lco2_hem_liquid_to_two_phase_state_pair_survey_validation_commands.md
```

## Syntax check

```bash
python -m compileall -q src/liquid_gas_transient
```

## Dependency-free focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_state_pair_survey.py \
  -m "not coolprop_installed" \
  --strict-markers
```

## Installed-CoolProp focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_state_pair_survey.py \
  --strict-markers
```

The installed test must not skip.

## Fixed survey runner

```bash
rm -rf verification/stage7_lco2_hem_liquid_state_pair_survey

python -m liquid_gas_transient.hem_liquid_to_two_phase_state_pair_survey \
  --output-dir verification/stage7_lco2_hem_liquid_state_pair_survey
```

Required artifacts:

```text
stage7_lco2_hem_liquid_state_pair_survey.json
stage7_lco2_hem_liquid_state_pair_survey_candidates.csv
stage7_lco2_hem_liquid_state_pair_survey_pairs.csv
stage7_lco2_hem_liquid_state_pair_survey_blend_points.csv
stage7_lco2_hem_liquid_state_pair_survey.md
stage7_lco2_hem_liquid_state_pair_survey.npz
```

Inspect the summary without assuming that a promising pair must exist:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path(
    "verification/stage7_lco2_hem_liquid_state_pair_survey/"
    "stage7_lco2_hem_liquid_state_pair_survey.json"
)
payload = json.loads(path.read_text(encoding="utf-8"))

assert payload["scope"] == "verification_only"
assert payload["screening_is_fvm_solution"] is False
assert payload["fvm_step_exercised"] is False
assert payload["case_a_frozen"] is False
assert payload["case_b_frozen"] is False
assert payload["algorithms_or_tolerances_tuned"] is False
assert payload["production_hem_activation_approved"] is False
assert payload["physical_validation"] is False
assert payload["design_use_acceptance"] is False

print(json.dumps({
    "candidate_count": payload["candidate_count"],
    "accepted_liquid_candidate_count": payload[
        "accepted_liquid_candidate_count"
    ],
    "pair_outcome_counts": payload["pair_outcome_counts"],
    "promising_pair_ids": payload["promising_pair_ids"],
    "highest_quality_pair_id": payload["highest_quality_pair_id"],
    "highest_screened_equilibrium_quality": payload[
        "highest_screened_equilibrium_quality"
    ],
}, indent=2))
PY
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
  tests/test_stage7_lco2_hem_liquid_to_two_phase_state_pair_survey.py \
  --strict-markers
```

## Full repository

```bash
pytest -q --strict-markers
```

Record the actual counts; do not reuse the previous `583 passed` count.

## Required review assertions

```text
candidate PT construction is re-evaluated through canonical rho/e
every attempt is retained with a reason
current e >= 0 guard is retained
same equilibrium sound-speed estimator is used on liquid and open two phase
endpoint sound speed is not invented
conservative blend is labeled as screening proxy, not FVM evidence
crossing evidence threshold is not used as a solver switch
no FvmSolver.step call exists in this increment
no algorithm or tolerance is tuned from the observed result
production, Validation, acoustic-band, and design-use flags remain false
```

## Final-head checks

After deleting the temporary validation workflow:

```bash
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
```

Confirm all permanent workflows pass on the final head.
