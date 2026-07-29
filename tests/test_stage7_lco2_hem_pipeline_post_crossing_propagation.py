from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_pipeline_post_crossing_propagation import (
    APPROVAL_BOUNDARY,
    BASELINE_CASE_ID,
    CONTINUATION_OFFSETS,
    EXPECTED_BASELINE,
    HEMPostCrossingPropagationConfig,
    _classify_raw_state,
    _review_classifications,
    run_post_crossing_propagation_review,
    write_post_crossing_propagation_artifacts,
)


def test_gate6_contract_is_locked_before_results() -> None:
    config = HEMPostCrossingPropagationConfig()

    assert BASELINE_CASE_ID == "pipeline_crossing_candidate_p5m5_to_p2m5"
    assert CONTINUATION_OFFSETS == (1, 4, 16, 64)
    assert config.continuation_offsets == CONTINUATION_OFFSETS
    assert config.maximum_post_crossing_steps == 64
    assert config.pipeline.n_cells == 32
    assert config.pipeline.cfl == 0.10
    assert config.pipeline.initial_pressure_pa == 5.0e6
    assert config.pipeline.subcooling_K == 5.0
    assert config.pipeline.crossing_evidence_min_quality == 1.0e-6
    assert all(value is False for value in APPROVAL_BOUNDARY.values())
    assert EXPECTED_BASELINE["step_count"] == 125
    assert EXPECTED_BASELINE["crossing_cell_indices"] == (29,)


def test_gate6_rejects_result_dependent_configuration_changes() -> None:
    with pytest.raises(ValueError):
        HEMPostCrossingPropagationConfig(
            continuation_offsets=(1, 2, 4, 8)
        )
    with pytest.raises(ValueError):
        HEMPostCrossingPropagationConfig(
            pipeline=replace(
                HEMPostCrossingPropagationConfig().pipeline,
                cfl=0.05,
            )
        )


def test_post_crossing_raw_classifier_allows_persistence_and_reverse_transition() -> None:
    def detection(regions, events):
        return SimpleNamespace(
            raw=SimpleNamespace(region=np.asarray(regions)),
            transitions=SimpleNamespace(event=np.asarray(events)),
        )

    assert _classify_raw_state(
        detection(
            ["LIQUID_CANDIDATE", "OPEN_TWO_PHASE"],
            ["NO_TRANSITION", "NO_TRANSITION"],
        )
    ) == "OPEN_TWO_PHASE"
    assert _classify_raw_state(
        detection(
            ["LIQUID_CANDIDATE", "LIQUID_CANDIDATE"],
            ["NO_TRANSITION", "REVERSE_TRANSITION"],
        )
    ) == "ALL_LIQUID"
    assert _classify_raw_state(
        detection(
            ["LIQUID_CANDIDATE", "SATURATED_LIQUID_ENDPOINT"],
            ["NO_TRANSITION", "BOUNDARY_TOUCH"],
        )
    ) == "ENDPOINT_LANDING"


def test_gate6_classification_retains_guard_limit_without_approving_propagation() -> None:
    step = SimpleNamespace(
        open_two_phase_cell_count=1,
        furthest_upstream_two_phase_cell=29,
        second_projection_noop=True,
    )
    labels, rationale = _review_classifications(
        outcome="FAIL_SAFE_STOP",
        steps=[step],
        baseline_open_cells=(29,),
        region_toggle_counts=[0] * 32,
    )
    assert "POST_CROSSING_REGION_PERSISTS" in labels
    assert "PROJECTION_RECOVERY_STABLE" in labels
    assert "CONSERVATION_BUDGET_STABLE" in labels
    assert "POST_CROSSING_GUARD_LIMIT_REACHED" in labels
    assert "PROPAGATION_REVIEW_INCONCLUSIVE" in labels
    assert rationale


def test_gate6_module_is_verification_orchestration_only() -> None:
    import liquid_gas_transient.hem_pipeline_post_crossing_propagation as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "class VerificationHEMLiquidOpenTwoPhaseEOS" not in source
    assert "class HEMEquilibriumQualityProjection" not in source
    assert "MUSCL" not in source
    assert "quality projection" in source
    assert "production_default_changed" in source


@pytest.fixture(scope="module")
def installed_gate6_result():
    pytest.importorskip("CoolProp")
    return run_post_crossing_propagation_review()


@pytest.mark.coolprop_installed
def test_gate6_replays_pr77_baseline_exactly(installed_gate6_result) -> None:
    result = installed_gate6_result
    summary = result.summary()
    baseline = summary["baseline"]

    assert summary["case_id"] == BASELINE_CASE_ID
    assert summary["baseline_reproduced_exactly"] is True
    assert baseline["outcome"] == EXPECTED_BASELINE["outcome"]
    assert baseline["step_count"] == EXPECTED_BASELINE["step_count"]
    assert baseline["final_time_s"] == EXPECTED_BASELINE["final_time_s"]
    assert baseline["crossing_step"] == EXPECTED_BASELINE["crossing_step"]
    assert baseline["crossing_time_s"] == EXPECTED_BASELINE["crossing_time_s"]
    assert baseline["crossing_cell_indices"] == [29]
    assert baseline["crossing_distances_from_outlet_m"] == [0.078125]
    assert (
        baseline["maximum_crossing_quality"]
        == EXPECTED_BASELINE["maximum_crossing_quality"]
    )
    assert baseline["final_state_sha256"] == EXPECTED_BASELINE[
        "final_state_sha256"
    ]
    assert baseline["run_signature_sha256"] == EXPECTED_BASELINE[
        "run_signature_sha256"
    ]


@pytest.mark.coolprop_installed
def test_gate6_continuation_is_complete_or_explicit_fail_safe(
    installed_gate6_result,
) -> None:
    result = installed_gate6_result
    summary = result.summary()

    assert summary["fixed_continuation_offsets"] == [1, 4, 16, 64]
    assert len(result.checkpoints) == 4
    assert summary["outcome"] in {
        "COMPLETED_FIXED_CHECKPOINTS",
        "FAIL_SAFE_STOP",
    }
    assert summary["successful_post_crossing_step_count"] <= 64
    assert summary["checkpoint_record_count"] == 4
    assert summary["classifications"]

    if result.outcome == "COMPLETED_FIXED_CHECKPOINTS":
        assert summary["reached_continuation_offsets"] == [1, 4, 16, 64]
        assert len(result.steps) == 64
        assert result.failure_category == ""
        assert result.failure_reason == ""
    else:
        assert result.failure_category
        assert result.failure_reason
        assert result.failure_post_crossing_step is not None
        assert "POST_CROSSING_GUARD_LIMIT_REACHED" in result.classifications
        assert "PROPAGATION_REVIEW_INCONCLUSIVE" in result.classifications

    assert all(summary[key] is False for key in APPROVAL_BOUNDARY)


@pytest.mark.coolprop_installed
def test_gate6_successful_steps_retain_projection_and_budget_evidence(
    installed_gate6_result,
) -> None:
    result = installed_gate6_result
    assert len(result.cells) == len(result.steps) * 32

    for step in result.steps:
        assert step.absolute_step == 125 + step.post_crossing_step
        assert step.dt_s > 0.0
        assert step.time_after_s > step.time_before_s
        assert step.second_projection_noop is True
        assert step.second_projection_cell_count == 0
        assert np.isfinite(step.mass_total_kg)
        assert np.isfinite(step.energy_total_J)
        assert (
            abs(step.phase_vapor_residual_kg)
            <= result.config.pipeline.vapor_budget_absolute_tolerance_kg
        )

    for cell in result.cells:
        assert np.isfinite(cell.rho_kg_m3)
        assert np.isfinite(cell.pressure_pa)
        assert np.isfinite(cell.temperature_K)
        assert 0.0 <= cell.q_equilibrium <= 1.0
        assert 0.0 <= cell.q_post <= 1.0
        assert 0.0 <= cell.void_fraction <= 1.0
        assert cell.sound_speed_status == "SUCCESS"
        assert cell.sound_speed_m_s is not None
        assert cell.sound_speed_m_s > 0.0


@pytest.mark.coolprop_installed
def test_gate6_artifact_bundle_is_complete(
    installed_gate6_result,
    tmp_path: Path,
) -> None:
    paths = write_post_crossing_propagation_artifacts(
        tmp_path,
        installed_gate6_result,
    )
    assert set(paths) == {
        "summary_json",
        "checkpoints_csv",
        "cell_history_csv",
        "transition_events_csv",
        "inventory_csv",
        "markdown",
        "digest",
    }
    expected_files = {
        "summary.json",
        "checkpoints.csv",
        "cell_history.csv",
        "transition_events.csv",
        "inventory_vapor_budget.csv",
        "report.md",
        "artifact_sha256.txt",
        "phase_region_space_time.png",
        "quality_void_fraction_space_time.png",
        "pressure_sound_speed_space_time.png",
        "inventory_residual.png",
    }
    assert expected_files <= {path.name for path in tmp_path.iterdir()}

    payload = json.loads(
        paths["summary_json"].read_text(encoding="utf-8")
    )
    assert payload["baseline_reproduced_exactly"] is True
    assert payload["fixed_continuation_offsets"] == [1, 4, 16, 64]
    assert payload["config"]["production_solver_changed"] is False
    assert payload["config"]["sound_speed_formula_changed"] is False
    assert payload["config"]["rusanov_flux_changed"] is False
    assert payload["config"]["boundary_changed"] is False
    assert payload["config"]["quality_projection_changed"] is False
    assert payload["config"]["threshold_or_tolerance_tuned"] is False
    assert all(payload[key] is False for key in APPROVAL_BOUNDARY)
    assert len(payload["checkpoints"]) == 4
    assert len(payload["cells"]) == len(installed_gate6_result.cells)
    assert paths["digest"].read_text(encoding="utf-8").strip()
