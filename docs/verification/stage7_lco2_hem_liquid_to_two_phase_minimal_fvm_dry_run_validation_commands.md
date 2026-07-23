# Stage 7 Minimal Liquid-to-Two-Phase Raw FVM Dry Run — Validation Commands

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
git switch agent/stage7-minimal-liquid-crossing-dry-run
git status --short --branch
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected permanent files after temporary-workflow removal:

```text
src/liquid_gas_transient/hem_liquid_to_two_phase_minimal_fvm_dry_run.py
tests/test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py
docs/verification/stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run_plan.md
docs/verification/stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run_validation_commands.md
```

## Syntax and diff checks

```bash
python -m compileall -q src/liquid_gas_transient
git diff --check origin/main...HEAD
```

## Dependency-free focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py \
  -m "not coolprop_installed" \
  --strict-markers
```

## Installed-CoolProp focused tests

```bash
pytest -q \
  tests/test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py \
  --strict-markers
```

The installed test must execute with zero skips. It must run all three fixed cases through
one real `FvmSolver.step()` and must not report `GUARD_FAILURE` or `BACKEND_FAILURE`.

## Fixed dry-run runner

```bash
rm -rf verification/stage7_lco2_hem_minimal_raw_fvm_dry_run

python -m \
  liquid_gas_transient.hem_liquid_to_two_phase_minimal_fvm_dry_run \
  --output-dir verification/stage7_lco2_hem_minimal_raw_fvm_dry_run \
  --n-cells 8 \
  --cfl 0.20 \
  --length-m 1.0 \
  --diameter-m 0.10
```

Required artifacts:

```text
stage7_lco2_hem_minimal_raw_fvm_dry_run.json
stage7_lco2_hem_minimal_raw_fvm_dry_run_cases.csv
stage7_lco2_hem_minimal_raw_fvm_dry_run_cells.csv
stage7_lco2_hem_minimal_raw_fvm_dry_run.md
stage7_lco2_hem_minimal_raw_fvm_dry_run.npz
```

## Evidence checks

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path(
    "verification/stage7_lco2_hem_minimal_raw_fvm_dry_run/"
    "stage7_lco2_hem_minimal_raw_fvm_dry_run.json"
)
payload = json.loads(path.read_text(encoding="utf-8"))

assert payload["scope"] == "verification_only"
assert payload["case_count"] == 3
assert payload["all_cases_exercised_one_fvm_step"] is True
assert payload["fvm_solver_step_exercised"] is True
assert payload["rusanov_flux_exercised"] is True
assert payload["cfl_path_exercised"] is True
assert payload["phase_projection_exercised"] is False
assert payload["accepted_state_eos_after_raw_exercised"] is False
assert payload["actual_first_order_fvm_crossing_verified"] is False
assert payload["case_a_frozen"] is False
assert payload["case_b_frozen"] is False
assert payload["production_hem_activation_approved"] is False
assert payload["physical_validation"] is False
assert payload["design_use_acceptance"] is False

for case in payload["cases"]:
    assert case["outcome"] not in {"GUARD_FAILURE", "BACKEND_FAILURE"}
    assert case["fvm_step_exercised"] is True
    assert case["initial_transport_quality_exactly_zero"] is True
    assert case["raw_transport_quality_exactly_zero"] is True
    assert case["changed_cell_indices"] == [3, 4]

print(json.dumps({
    "outcome_counts": payload["outcome_counts"],
    "raw_crossing_case_ids": payload["raw_crossing_case_ids"],
    "cases": [
        {
            "case_id": case["case_id"],
            "outcome": case["outcome"],
            "changed_cell_indices": case["changed_cell_indices"],
            "max_raw_equilibrium_quality": case[
                "max_raw_equilibrium_quality"
            ],
            "max_raw_quality_mismatch": case["max_raw_quality_mismatch"],
            "event_counts": case["event_counts"],
            "raw_region_counts": case["raw_region_counts"],
        }
        for case in payload["cases"]
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
  tests/test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py \
  --strict-markers
```

## Full repository

```bash
pytest -q --strict-markers
```

Record actual test counts. Do not reuse the prior `601 passed` total without running the
current suite.

## Review assertions

```text
initial states:
    all liquid
    q_transport = 0 exactly
    q_eq = 0

numerics:
    existing FvmSolver.step
    existing Rusanov flux
    existing CFL formula
    8 cells
    CFL 0.20
    transmissive boundaries
    no source
    one step

raw evaluation:
    direct rho/e phase path
    transported q not used as phase classifier
    endpoint and forbidden states recorded explicitly

scope:
    no quality projection
    no post-raw accepted EOS
    no Case A/B freeze
    no algorithm or tolerance tuning
    no production, Validation, acoustic-band, or design-use approval
```

## Final workflow confirmation

After temporary validation evidence is captured and the temporary workflow is removed,
confirm the permanent CoolProp wave, controlled-pressure-ramp, boundary-reflection, and
internal-valve workflows all succeed on the final PR head. Record run identifiers and
conclusions in the PR body before merge.
