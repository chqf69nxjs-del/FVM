from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"replacement anchor missing: {path}\n{old[:160]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_after_once(path: str, marker: str, addition: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if addition in text:
        return
    if marker not in text:
        raise RuntimeError(f"insertion anchor missing: {path}\n{marker[:160]!r}")
    target.write_text(text.replace(marker, marker + addition, 1), encoding="utf-8")


SOURCE = "src/liquid_gas_transient/hem_pipeline_depressurization_first_crossing.py"
TEST = "tests/test_stage7_lco2_hem_pipeline_depressurization_increment2.py"
PLAN = "docs/verification/stage7_lco2_hem_pipeline_depressurization_increment2_plan.md"
VALIDATION_PLAN = "docs/verification/stage7_lco2_hem_pipeline_depressurization_validation_plan.md"
EVIDENCE = "docs/verification/stage7_lco2_hem_pipeline_depressurization_increment2_evidence.md"
CONTRACT = "docs/verification/stage7_lco2_hem_pipeline_depressurization_increment2_observation_contract_v1.json"


insert_after_once(
    SOURCE,
    '''        if self.max_steps != 2000 or self.preflight_sample_count != 65:
            raise ValueError("Increment 2 limits are fixed at 2000 steps and 65 samples")
''',
    '''        fixed_scalars = (
            ("pressure_drop_evidence_relative", self.pressure_drop_evidence_relative, 1.0e-6),
            ("crossing_evidence_min_quality", self.crossing_evidence_min_quality, 1.0e-6),
            ("accepted_state_quality_tolerance", self.accepted_state_quality_tolerance, 1.0e-10),
            ("mass_budget_relative_tolerance", self.mass_budget_relative_tolerance, 1.0e-10),
            ("mass_budget_absolute_tolerance_kg", self.mass_budget_absolute_tolerance_kg, 1.0e-12),
            ("momentum_budget_relative_tolerance", self.momentum_budget_relative_tolerance, 1.0e-10),
            ("momentum_budget_absolute_tolerance_kg_m_s", self.momentum_budget_absolute_tolerance_kg_m_s, 1.0e-10),
            ("energy_budget_relative_tolerance", self.energy_budget_relative_tolerance, 1.0e-10),
            ("energy_budget_absolute_tolerance_J", self.energy_budget_absolute_tolerance_J, 1.0e-6),
            ("vapor_budget_absolute_tolerance_kg", self.vapor_budget_absolute_tolerance_kg, 1.0e-12),
        )
        for name, value, expected in fixed_scalars:
            if value != expected:
                raise ValueError(
                    f"Increment 2 {name} is fixed at {expected!r}; received {value!r}"
                )
        if self.phase_config != HEMPhaseClassificationConfig():
            raise ValueError("Increment 2 phase_config is fixed by the PR #74 contract")
        if self.projection_config != HEMEquilibriumQualitySyncConfig():
            raise ValueError("Increment 2 projection_config is fixed by the PR #74 contract")
''',
)

replace_once(
    SOURCE,
    '''@dataclass(frozen=True)
class HEMPipelineDepressurizationResult:
''',
    '''def _gate_p2_passes(cases: Sequence[PipelineCaseResult]) -> bool:
    """Return the reviewed Gate P2 decision for the fixed three-case matrix."""

    by_id = {case.case.case_id: case for case in cases}
    expected_ids = {case.case_id for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES}
    if set(by_id) != expected_ids:
        return False
    accepted_or_honest_no_crossing = {
        "ACCEPTED_FIRST_CROSSING",
        "NO_CROSSING_WITHIN_HORIZON",
    }
    strong = by_id["pipeline_crossing_candidate_p5m5_to_p2m5"]
    moderate = by_id["pipeline_moderate_diagnostic_p5m5_to_p3m5"]
    control = by_id["pipeline_liquid_control_p5m5_to_p4m5"]
    return bool(
        strong.outcome in accepted_or_honest_no_crossing
        and moderate.outcome in accepted_or_honest_no_crossing
        and control.outcome == "NO_CROSSING_WITHIN_HORIZON"
        and all(case.reverse_flow_fallback_count == 0 for case in cases)
    )


@dataclass(frozen=True)
class HEMPipelineDepressurizationResult:
''',
)

replace_once(
    SOURCE,
    '''        crossing_candidate = by_id.get(
            "pipeline_crossing_candidate_p5m5_to_p2m5"
        )
        return {
''',
    '''        crossing_candidate = by_id.get(
            "pipeline_crossing_candidate_p5m5_to_p2m5"
        )
        liquid_control = by_id.get("pipeline_liquid_control_p5m5_to_p4m5")
        return {
''',
)

replace_once(
    SOURCE,
    '''            "gate_p2_passed": bool(
                self.cases
                and all(case.completed_without_guard_failure for case in self.cases)
            ),
            "subthreshold_crossing_case_ids": [
''',
    '''            "gate_p2_passed": _gate_p2_passes(self.cases),
            "gate_p2_rule": "4_mpa_control_must_finish_no_crossing_within_horizon",
            "four_mpa_control_outcome": (
                liquid_control.outcome if liquid_control is not None else None
            ),
            "four_mpa_control_remained_all_liquid": bool(
                liquid_control is not None
                and liquid_control.outcome == "NO_CROSSING_WITHIN_HORIZON"
            ),
            "subthreshold_crossing_case_ids": [
''',
)

replace_once(
    SOURCE,
    '''            "max_steps": result.config.max_steps,
            "preflight_sample_count": result.config.preflight_sample_count,
            "phase_config": asdict(result.config.phase_config),
            "projection_config": asdict(result.config.projection_config),
''',
    '''            "max_steps": result.config.max_steps,
            "preflight_sample_count": result.config.preflight_sample_count,
            "pressure_drop_evidence_relative": (
                result.config.pressure_drop_evidence_relative
            ),
            "crossing_evidence_min_quality": (
                result.config.crossing_evidence_min_quality
            ),
            "accepted_state_quality_tolerance": (
                result.config.accepted_state_quality_tolerance
            ),
            "mass_budget_relative_tolerance": (
                result.config.mass_budget_relative_tolerance
            ),
            "mass_budget_absolute_tolerance_kg": (
                result.config.mass_budget_absolute_tolerance_kg
            ),
            "momentum_budget_relative_tolerance": (
                result.config.momentum_budget_relative_tolerance
            ),
            "momentum_budget_absolute_tolerance_kg_m_s": (
                result.config.momentum_budget_absolute_tolerance_kg_m_s
            ),
            "energy_budget_relative_tolerance": (
                result.config.energy_budget_relative_tolerance
            ),
            "energy_budget_absolute_tolerance_J": (
                result.config.energy_budget_absolute_tolerance_J
            ),
            "vapor_budget_absolute_tolerance_kg": (
                result.config.vapor_budget_absolute_tolerance_kg
            ),
            "phase_config": asdict(result.config.phase_config),
            "projection_config": asdict(result.config.projection_config),
            "fixed_case_matrix": [
                asdict(case) for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
            ],
''',
)

replace_once(
    TEST,
    '''import inspect
import json
from pathlib import Path
''',
    '''import inspect
import json
from dataclasses import replace
from pathlib import Path
''',
)

replace_once(
    TEST,
    '''from liquid_gas_transient.hem_liquid_to_two_phase_first_crossing_case_ab import (
    run_first_crossing_case_ab_freeze,
)
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
''',
    '''from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualitySyncConfig,
)
from liquid_gas_transient.hem_liquid_to_two_phase_first_crossing_case_ab import (
    run_first_crossing_case_ab_freeze,
)
from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
)
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
''',
)

replace_once(
    TEST,
    '''    HEMPipelineDepressurizationConfig,
    _budget_limit,
''',
    '''    HEMPipelineDepressurizationConfig,
    _budget_limit,
    _gate_p2_passes,
''',
)

replace_once(
    TEST,
    '''    write_pipeline_depressurization_artifacts,
)


def test_increment2_fixed_configuration_matches_reviewed_contract() -> None:
''',
    '''    write_pipeline_depressurization_artifacts,
)


OBSERVATION_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/verification/"
    "stage7_lco2_hem_pipeline_depressurization_increment2_observation_contract_v1.json"
)


def _load_observation_contract() -> dict[str, object]:
    return json.loads(OBSERVATION_CONTRACT_PATH.read_text(encoding="utf-8"))


def test_increment2_fixed_configuration_matches_reviewed_contract() -> None:
''',
)

replace_once(
    TEST,
    '''        ("max_steps", 1999),
        ("preflight_sample_count", 33),
''',
    '''        ("max_steps", 1999),
        ("preflight_sample_count", 33),
        ("pressure_drop_evidence_relative", 2.0e-6),
        ("crossing_evidence_min_quality", 1.0e-9),
        ("accepted_state_quality_tolerance", 2.0e-10),
        ("mass_budget_relative_tolerance", 2.0e-10),
        ("mass_budget_absolute_tolerance_kg", 2.0e-12),
        ("momentum_budget_relative_tolerance", 2.0e-10),
        ("momentum_budget_absolute_tolerance_kg_m_s", 2.0e-10),
        ("energy_budget_relative_tolerance", 2.0e-10),
        ("energy_budget_absolute_tolerance_J", 2.0e-6),
        ("vapor_budget_absolute_tolerance_kg", 2.0e-12),
        (
            "phase_config",
            replace(
                HEMPhaseClassificationConfig(),
                endpoint_tolerance=2.0e-10,
            ),
        ),
        (
            "projection_config",
            replace(
                HEMEquilibriumQualitySyncConfig(),
                activation_tolerance=2.0e-12,
            ),
        ),
''',
)

replace_once(
    TEST,
    '''@pytest.fixture(scope="module")
def installed_pipeline_result():
''',
    '''def test_observation_contract_matches_the_fixed_configuration() -> None:
    contract = _load_observation_contract()
    fixed = contract["fixed_problem"]
    config = HEMPipelineDepressurizationConfig()

    assert fixed["pressure_drop_evidence_relative"] == config.pressure_drop_evidence_relative
    assert fixed["crossing_evidence_min_quality"] == config.crossing_evidence_min_quality
    assert fixed["accepted_state_quality_tolerance"] == config.accepted_state_quality_tolerance
    assert fixed["mass_budget_relative_tolerance"] == config.mass_budget_relative_tolerance
    assert fixed["mass_budget_absolute_tolerance_kg"] == config.mass_budget_absolute_tolerance_kg
    assert fixed["momentum_budget_relative_tolerance"] == config.momentum_budget_relative_tolerance
    assert fixed["momentum_budget_absolute_tolerance_kg_m_s"] == config.momentum_budget_absolute_tolerance_kg_m_s
    assert fixed["energy_budget_relative_tolerance"] == config.energy_budget_relative_tolerance
    assert fixed["energy_budget_absolute_tolerance_J"] == config.energy_budget_absolute_tolerance_J
    assert fixed["vapor_budget_absolute_tolerance_kg"] == config.vapor_budget_absolute_tolerance_kg
    assert fixed["phase_config"] == {
        "critical_temperature_margin_K": config.phase_config.critical_temperature_margin_K,
        "critical_pressure_margin_Pa": config.phase_config.critical_pressure_margin_Pa,
        "endpoint_tolerance": config.phase_config.endpoint_tolerance,
    }
    assert fixed["projection_config"] == {
        "activation_tolerance": config.projection_config.activation_tolerance,
        "supported_phase_classes": list(config.projection_config.supported_phase_classes),
    }
    decision = contract["gate_decision"]
    assert decision["gate_rule"] == "4_mpa_control_must_finish_no_crossing_within_horizon"
    assert decision["four_mpa_all_liquid_control_observed"] is False
    assert decision["four_mpa_subthreshold_crossing_retained"] is True
    assert decision["gate_p2_passed"] is False


def test_gate_p2_requires_the_four_mpa_control_to_remain_liquid() -> None:
    def case(case_id: str, outcome: str, reverse_count: int = 0):
        return SimpleNamespace(
            case=SimpleNamespace(case_id=case_id),
            outcome=outcome,
            reverse_flow_fallback_count=reverse_count,
        )

    strong = case(
        "pipeline_crossing_candidate_p5m5_to_p2m5",
        "ACCEPTED_FIRST_CROSSING",
    )
    moderate = case(
        "pipeline_moderate_diagnostic_p5m5_to_p3m5",
        "ACCEPTED_FIRST_CROSSING",
    )
    liquid = case(
        "pipeline_liquid_control_p5m5_to_p4m5",
        "NO_CROSSING_WITHIN_HORIZON",
    )
    accepted_control = case(
        "pipeline_liquid_control_p5m5_to_p4m5",
        "ACCEPTED_FIRST_CROSSING",
    )
    guarded_control = case(
        "pipeline_liquid_control_p5m5_to_p4m5",
        "GUARD_FAILURE",
    )

    assert _gate_p2_passes((strong, moderate, liquid)) is True
    assert _gate_p2_passes((strong, moderate, accepted_control)) is False
    assert _gate_p2_passes((strong, moderate, guarded_control)) is False
    reverse_control = case(
        "pipeline_liquid_control_p5m5_to_p4m5",
        "NO_CROSSING_WITHIN_HORIZON",
        reverse_count=1,
    )
    assert _gate_p2_passes((strong, moderate, reverse_control)) is False


@pytest.fixture(scope="module")
def installed_pipeline_result():
''',
)

replace_once(
    TEST,
    '''@pytest.mark.coolprop_installed
def test_installed_pipeline_artifact_bundle_is_complete(
''',
    '''@pytest.mark.coolprop_installed
def test_installed_pipeline_result_matches_observation_contract_exactly(
    installed_pipeline_result,
) -> None:
    contract = _load_observation_contract()
    by_id = {case.case.case_id: case for case in installed_pipeline_result.cases}
    assert set(by_id) == {case["case_id"] for case in contract["cases"]}

    for expected in contract["cases"]:
        actual = by_id[expected["case_id"]]
        assert actual.outcome == expected["formal_outcome"]
        assert actual.failure_reason == expected["failure_reason"]
        assert actual.step_count == expected["step_count"]
        assert actual.final_time_s == expected["final_time_s"]
        assert actual.crossing_step == expected["crossing_step"]
        assert actual.crossing_time_s == expected["crossing_time_s"]
        assert list(actual.crossing_cell_indices) == expected["crossing_cell_indices"]
        assert list(actual.crossing_distances_from_outlet_m) == expected[
            "crossing_distances_from_outlet_m"
        ]
        assert actual.maximum_crossing_quality == expected["maximum_crossing_quality"]
        assert actual.final_state_sha256 == expected["final_state_sha256"]
        assert actual.run_signature_sha256 == expected["run_signature_sha256"]


@pytest.mark.coolprop_installed
def test_installed_pipeline_matrix_repeats_exactly(
    installed_pipeline_result,
) -> None:
    repeated = run_fixed_pipeline_depressurization_matrix()
    assert repeated.summary() == installed_pipeline_result.summary()
    for first, second in zip(installed_pipeline_result.cases, repeated.cases, strict=True):
        assert second.outcome == first.outcome
        assert second.failure_reason == first.failure_reason
        assert second.step_count == first.step_count
        assert second.final_time_s == first.final_time_s
        assert second.crossing_step == first.crossing_step
        assert second.crossing_time_s == first.crossing_time_s
        assert second.crossing_cell_indices == first.crossing_cell_indices
        assert second.crossing_distances_from_outlet_m == first.crossing_distances_from_outlet_m
        assert second.maximum_crossing_quality == first.maximum_crossing_quality
        assert second.final_state_sha256 == first.final_state_sha256
        assert second.run_signature_sha256 == first.run_signature_sha256


@pytest.mark.coolprop_installed
def test_installed_pipeline_artifact_bundle_is_complete(
''',
)

replace_once(
    TEST,
    '''    assert payload["gate_p2_passed"] is False
    assert payload["outcome_counts"]["ACCEPTED_FIRST_CROSSING"] == 2
''',
    '''    assert payload["gate_p2_passed"] is False
    assert payload["gate_p2_rule"] == "4_mpa_control_must_finish_no_crossing_within_horizon"
    assert payload["four_mpa_control_outcome"] == "GUARD_FAILURE"
    assert payload["four_mpa_control_remained_all_liquid"] is False
    assert payload["outcome_counts"]["ACCEPTED_FIRST_CROSSING"] == 2
''',
)

replace_once(
    TEST,
    '''    assert payload["algorithms_or_tolerances_tuned"] is False
    assert len(payload["boundary_path"]) == 195
''',
    '''    assert payload["algorithms_or_tolerances_tuned"] is False
    contract = _load_observation_contract()
    fixed = contract["fixed_problem"]
    artifact_config = payload["config"]
    for key in (
        "pressure_drop_evidence_relative",
        "crossing_evidence_min_quality",
        "accepted_state_quality_tolerance",
        "mass_budget_relative_tolerance",
        "mass_budget_absolute_tolerance_kg",
        "momentum_budget_relative_tolerance",
        "momentum_budget_absolute_tolerance_kg_m_s",
        "energy_budget_relative_tolerance",
        "energy_budget_absolute_tolerance_J",
        "vapor_budget_absolute_tolerance_kg",
    ):
        assert artifact_config[key] == fixed[key]
    assert artifact_config["phase_config"] == fixed["phase_config"]
    assert artifact_config["projection_config"] == fixed["projection_config"]
    assert len(payload["boundary_path"]) == 195
''',
)

replace_once(
    PLAN,
    '''Gate P2 may pass only when the fixed matrix is executed honestly, the 2 MPa candidate
produces an accepted crossing or an honest no-crossing result, the 3 MPa result is retained
diagnostically, the 4 MPa control observation is retained without tuning, budgets close,
and the frozen PR #72 Case A/B regressions remain exact.
''',
    '''Gate P2 may pass only when all of the following are true:

```text
the fixed matrix is executed without changing a case, algorithm, or tolerance
the 2 MPa candidate is ACCEPTED_FIRST_CROSSING or NO_CROSSING_WITHIN_HORIZON
the 3 MPa diagnostic is ACCEPTED_FIRST_CROSSING or NO_CROSSING_WITHIN_HORIZON
the 4 MPa control is exactly NO_CROSSING_WITHIN_HORIZON
the 4 MPa control has no raw liquid-to-two-phase crossing, including a subthreshold one
reverse-flow fallback remains zero
budgets close
frozen PR #72 Case A/B regressions remain exact
```

A 4 MPa raw crossing with `0 < q_eq < 1e-6` is retained as an explicit
`GUARD_FAILURE`, but it does not satisfy the all-liquid control and therefore keeps
Gate P2 false.
''',
)

replace_once(
    VALIDATION_PLAN,
    '''```text
fixed runner completes
2 MPa case produces accepted crossing or an honest no-crossing result
3 MPa result is retained diagnostically
4 MPa result is retained as a control observation
budgets close
frozen Case A/B regressions remain exact
```

Only a later gate may freeze a boundary-driven prototype pair or evaluate front propagation.
''',
    '''```text
fixed runner completes without changing a fixed case, algorithm, or tolerance
2 MPa case produces accepted crossing or an honest no-crossing result
3 MPa result is retained diagnostically as accepted crossing or honest no-crossing
4 MPa control completes as NO_CROSSING_WITHIN_HORIZON
4 MPa control contains no raw liquid-to-two-phase crossing, including subthreshold crossing
reverse-flow fallback remains zero
budgets close
frozen Case A/B regressions remain exact
```

A raw 4 MPa crossing below the `1e-6` accepted-crossing evidence threshold must be
retained as a guarded observation. It is neither an accepted crossing nor an all-liquid
control, and Gate P2 remains false.

Only a later gate may freeze a boundary-driven prototype pair or evaluate front propagation.
''',
)

replace_once(
    EVIDENCE,
    '''Gate P2 remains false because the intended 4 MPa liquid-control observation did not remain
all liquid and instead reached a subthreshold two-phase state. This is an outcome of the
fixed matrix, not an implementation result to be hidden or tuned away.
''',
    '''Gate P2 remains false because the reviewed rule requires the fixed 4 MPa control to
complete as `NO_CROSSING_WITHIN_HORIZON` with no raw liquid-to-two-phase crossing.
The observed subthreshold crossing therefore fails the all-liquid-control requirement.
This is an outcome of the fixed matrix, not an implementation result to be hidden or tuned away.

The runner now enforces every fixed phase, projection, crossing-evidence, and budget
tolerance from the PR #74 contract. The focused regression reads the machine-readable
observation contract and fixes each case outcome, step, time, crossing cell, maximum
quality, final-state SHA256, and run signature. A second full matrix execution is also
required to reproduce those values exactly.
''',
)

contract_path = Path(CONTRACT)
contract = json.loads(contract_path.read_text(encoding="utf-8"))
fixed = contract["fixed_problem"]
fixed.update(
    {
        "pressure_drop_evidence_relative": 1.0e-6,
        "accepted_state_quality_tolerance": 1.0e-10,
        "mass_budget_relative_tolerance": 1.0e-10,
        "mass_budget_absolute_tolerance_kg": 1.0e-12,
        "momentum_budget_relative_tolerance": 1.0e-10,
        "momentum_budget_absolute_tolerance_kg_m_s": 1.0e-10,
        "energy_budget_relative_tolerance": 1.0e-10,
        "energy_budget_absolute_tolerance_J": 1.0e-6,
        "vapor_budget_absolute_tolerance_kg": 1.0e-12,
        "phase_config": {
            "critical_temperature_margin_K": 0.5,
            "critical_pressure_margin_Pa": 50000.0,
            "endpoint_tolerance": 1.0e-10,
        },
        "projection_config": {
            "activation_tolerance": 1.0e-12,
            "supported_phase_classes": [
                "compressed_or_subcooled_liquid",
                "liquid_vapor_two_phase",
                "single_phase_vapor",
            ],
        },
    }
)
decision = contract["gate_decision"]
decision.update(
    {
        "gate_rule": "4_mpa_control_must_finish_no_crossing_within_horizon",
        "two_mpa_allowed_outcomes": [
            "ACCEPTED_FIRST_CROSSING",
            "NO_CROSSING_WITHIN_HORIZON",
        ],
        "three_mpa_allowed_outcomes": [
            "ACCEPTED_FIRST_CROSSING",
            "NO_CROSSING_WITHIN_HORIZON",
        ],
        "four_mpa_required_outcome": "NO_CROSSING_WITHIN_HORIZON",
        "four_mpa_raw_crossing_allowed": False,
    }
)
contract["review_resolution"] = {
    "fixed_configuration_enforced": True,
    "gate_p2_rule_made_explicit": True,
    "observation_contract_regression_required": True,
    "exact_repeatability_required": True,
}
contract_path.write_text(
    json.dumps(contract, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
