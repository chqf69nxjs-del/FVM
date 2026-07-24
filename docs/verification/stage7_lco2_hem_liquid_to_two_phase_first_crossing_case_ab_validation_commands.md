# Stage 7 First-Crossing Case A/B Freeze — Validation Commands

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
git switch agent/stage7-first-crossing-case-ab-freeze
git status --short --branch
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected permanent files after removal of the temporary workflow:

```text
src/liquid_gas_transient/hem_liquid_to_two_phase_first_crossing_case_ab.py
tests/test_stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab.py
docs/verification/stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab_plan.md
docs/verification/stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab_validation_commands.md
docs/verification/stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab_evidence.md
```

## Static checks

```bash
python -m compileall -q src/liquid_gas_transient
git diff --check origin/main...HEAD
```

## Focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab.py \
  --strict-markers
```

Requirements:

```text
installed CoolProp test is executed
skipped = 0
failures = 0
errors = 0
```

## Run the fixed repeated Case A/B matrix

```bash
rm -rf verification/stage7_lco2_hem_first_crossing_case_ab

python -m \
  liquid_gas_transient.hem_liquid_to_two_phase_first_crossing_case_ab \
  --output-dir verification/stage7_lco2_hem_first_crossing_case_ab
```

Required artifacts:

```text
stage7_lco2_hem_first_crossing_case_ab.json
stage7_lco2_hem_first_crossing_case_ab_runs.csv
stage7_lco2_hem_first_crossing_case_ab_steps.csv
stage7_lco2_hem_first_crossing_case_ab_cells.csv
stage7_lco2_hem_first_crossing_case_ab.md
stage7_lco2_hem_first_crossing_case_ab.npz
```

## Required evidence checks

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path(
    "verification/stage7_lco2_hem_first_crossing_case_ab/"
    "stage7_lco2_hem_first_crossing_case_ab.json"
)
payload = json.loads(path.read_text(encoding="utf-8"))

assert payload["scope"] == "verification_only"
assert payload["repeat_count"] == 3
assert payload["case_a_case_id"] == "strong_p5m5_to_p2m5"
assert payload["case_b_case_id"] == "control_p5m5_to_p4m5"

assert payload["case_a_repeatable"] is True
assert payload["case_b_repeatable"] is True
assert payload["case_b_matched_physical_time"] is True
assert payload["case_a_frozen"] is True
assert payload["case_b_frozen"] is True
assert payload["actual_first_order_fvm_crossing_verified"] is True

assert payload["case_a_crossing_step"] == 1
assert payload["case_a_crossing_cell_indices"] == [3, 4]
assert payload["algorithms_or_tolerances_tuned"] is False
assert payload["production_default_changed"] is False
assert payload["production_hem_activation_approved"] is False
assert payload["physical_validation"] is False
assert payload["design_use_acceptance"] is False
assert payload["two_phase_acoustic_accuracy_band_approved"] is False

a_runs = [run for run in payload["runs"] if run["role"] == "Case A"]
b_runs = [run for run in payload["runs"] if run["role"] == "Case B"]

assert len(a_runs) == 3
assert len(b_runs) == 3
assert len({run["repeatability_signature"] for run in a_runs}) == 1
assert len({run["repeatability_signature"] for run in b_runs}) == 1

target = payload["case_a_crossing_time_s"]
for run in a_runs:
    assert run["outcome"] == "ACCEPTED_CROSSING"
    assert run["crossing_step"] == 1
    assert run["crossing_cell_indices"] == [3, 4]
    assert run["projection_cell_indices"] == [3, 4]
    assert abs(
        run["phase_budget_diagnostics"][
            "phase_vapor_mass_balance_residual_kg"
        ]
    ) <= 1.0e-12

for run in b_runs:
    assert run["outcome"] == "MATCHED_ALL_LIQUID"
    assert run["crossing_cell_indices"] == []
    assert run["projection_cell_indices"] == []
    assert run["cumulative_projection_vapor_source_kg"] == 0.0
    assert abs(run["final_time_s"] - target) <= 1.0e-15

print(json.dumps({
    "case_a_crossing_time_s": target,
    "case_a_signature": payload["case_a_repeatability_signature"],
    "case_b_signature": payload["case_b_repeatability_signature"],
}, indent=2))
PY
```

## Related Stage 7 tests

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
  tests/test_stage7_lco2_hem_liquid_to_two_phase_first_crossing_case_ab.py \
  --strict-markers
```

## Full repository

```bash
pytest -q --strict-markers
```

Record the actual counts. Do not copy the previous `628 passed` total without
executing the current suite.

## Review assertions

```text
Case A:
    strong 5 MPa -> 2 MPa pair
    stop at first accepted crossing
    repeat count = 3
    crossing step/time/cells identical
    projection cells identical to crossing cells
    post state accepted
    budgets close

Case B:
    5 MPa -> 4 MPa liquid control
    same geometry, flux, CFL limit, boundaries, and algorithms
    exact matched Case A physical time
    repeat count = 3
    all cells remain liquid
    projection source = 0
    budgets close

Freeze:
    Case A signatures identical
    Case B signatures identical
    case_a_frozen = true
    case_b_frozen = true
    software crossing verified = true

Approval:
    verification only
    physical Validation = false
    production HEM = false
    design use = false
    acoustic accuracy band = false
```

## Final workflow confirmation

After temporary validation evidence is captured and the temporary workflow is
removed, confirm all permanent pull-request workflows succeed on the final head.
Record run IDs and conclusions in the PR body before marking the PR ready for
review.
