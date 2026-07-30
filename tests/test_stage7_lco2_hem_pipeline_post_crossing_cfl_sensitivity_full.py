from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import liquid_gas_transient.hem_pipeline_post_crossing_cfl_sensitivity_full as full
from liquid_gas_transient.hem_pipeline_post_crossing_cfl_sensitivity import (
    EXPECTED_GATE6_CELL30_REGION_CHANGES,
    EXPECTED_GATE6_FINAL_STATE_SHA256,
    EXPECTED_GATE6_FINAL_TIME_S,
    GATE8_CFL_SEQUENCE,
)
from liquid_gas_transient.hem_pipeline_post_crossing_cfl_sensitivity_full import (
    FULL_APPROVAL_BOUNDARY,
    PERMITTED_CLASSIFICATIONS,
    HEMGate8CflSensitivityError,
    run_gate8_full_cfl_sequence,
    write_gate8_full_artifacts,
)


def test_gate8_full_contract_is_locked_before_results() -> None:
    assert GATE8_CFL_SEQUENCE == (0.10, 0.05, 0.025)
    assert FULL_APPROVAL_BOUNDARY["Gate_8_execution_complete"] is True
    assert all(
        value is False
        for key, value in FULL_APPROVAL_BOUNDARY.items()
        if key != "Gate_8_execution_complete"
    )
    assert "FIXED_HORIZON_OUTCOME_DIVERGENCE" in PERMITTED_CLASSIFICATIONS
    assert "POST_CROSSING_CFL_REVIEW_INCONCLUSIVE" in PERMITTED_CLASSIFICATIONS


def test_gate8_full_module_is_verification_orchestration_only() -> None:
    source = inspect.getsource(full)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "class VerificationHEMLiquidOpenTwoPhaseEOS" not in source
    assert "class HEMEquilibriumQualityProjection" not in source
    assert "MUSCL" not in source
    assert "production_solver_changed" in source
    assert "sound_speed_formula_changed" in source
    assert "quality_projection_changed" in source
    assert "threshold_or_tolerance_tuned" in source


def test_gate8_full_stops_before_lower_cfl_when_gate6_identity_fails(
    monkeypatch,
) -> None:
    refined_calls: list[float] = []
    monkeypatch.setattr(full, "_run_gate6_column", lambda: object())
    monkeypatch.setattr(full, "_gate6_identity_matches", lambda _column: False)
    monkeypatch.setattr(
        full,
        "_run_refined_column",
        lambda cfl: refined_calls.append(cfl),
    )
    with pytest.raises(HEMGate8CflSensitivityError):
        run_gate8_full_cfl_sequence()
    assert refined_calls == []


def test_gate8_full_executes_both_refined_columns_in_fixed_order(monkeypatch) -> None:
    gate6 = object()
    lower = {0.05: object(), 0.025: object()}
    calls: list[float] = []
    monkeypatch.setattr(full, "_run_gate6_column", lambda: gate6)
    monkeypatch.setattr(full, "_gate6_identity_matches", lambda _column: True)

    def refined(cfl: float):
        calls.append(cfl)
        return lower[cfl]

    monkeypatch.setattr(full, "_run_refined_column", refined)
    monkeypatch.setattr(
        full,
        "_classify",
        lambda _columns: (
            ("POST_CROSSING_CFL_REVIEW_INCONCLUSIVE",),
            {"POST_CROSSING_CFL_REVIEW_INCONCLUSIVE": "synthetic"},
        ),
    )
    monkeypatch.setattr(
        full,
        "run_phase_chatter_diagnosis",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(full, "_git_provenance", lambda: {})
    result = run_gate8_full_cfl_sequence()
    assert calls == [0.05, 0.025]
    assert result.columns == (gate6, lower[0.05], lower[0.025])


@pytest.fixture(scope="module")
def installed_gate8_full():
    pytest.importorskip("CoolProp")
    return run_gate8_full_cfl_sequence()


@pytest.mark.coolprop_installed
def test_gate8_full_reproduces_gate6_and_executes_all_columns(
    installed_gate8_full,
) -> None:
    assert tuple(column.cfl for column in installed_gate8_full.columns) == (
        0.10,
        0.05,
        0.025,
    )
    by_cfl = {column.cfl: column for column in installed_gate8_full.columns}
    gate6 = by_cfl[0.10]
    assert gate6.baseline.outcome == "ACCEPTED_FIRST_CROSSING"
    assert gate6.baseline.crossing_step == 125
    assert gate6.baseline.crossing_time_s == 7.999325695335248e-4
    assert gate6.baseline.crossing_cell_indices == (29,)
    assert gate6.baseline.maximum_crossing_quality == 3.773646403587342e-6
    assert gate6.continuation_outcome == "COMPLETED_FIXED_CHECKPOINTS"
    assert len(gate6.steps) == 64
    assert gate6.steps[-1].time_after_s == EXPECTED_GATE6_FINAL_TIME_S
    assert gate6.last_valid_state_sha256 == EXPECTED_GATE6_FINAL_STATE_SHA256
    assert gate6.region_toggle_counts[30] == EXPECTED_GATE6_CELL30_REGION_CHANGES


@pytest.mark.coolprop_installed
def test_gate8_full_retains_exact_cfl_0p05_guard_result(installed_gate8_full) -> None:
    column = {column.cfl: column for column in installed_gate8_full.columns}[0.05]
    assert column.baseline.outcome == "GUARD_FAILURE"
    assert column.baseline.crossing_step == 249
    assert column.baseline.crossing_time_s == 7.967173062790038e-4
    assert column.baseline.crossing_cell_indices == (29,)
    assert column.baseline.crossing_distances_from_outlet_m == (0.078125,)
    assert column.baseline.maximum_crossing_quality == 1.1006096906989802e-7
    assert (
        column.baseline.failure_reason
        == "HEMPipelineDepressurizationError: crossing quality evidence is below the fixed minimum"
    )
    assert column.continuation_outcome == "NOT_STARTED_NO_ACCEPTED_FIRST_CROSSING"
    assert not column.steps
    assert all(not row.reached for row in column.checkpoints)
    assert (
        column.last_valid_state_sha256
        == "d18e4bdf1477c29f1183b2f3276c84e086f6cfef80c336a7f6f13616769c5a29"
    )


@pytest.mark.coolprop_installed
def test_gate8_full_cfl_0p025_retains_formal_outcome(installed_gate8_full) -> None:
    column = {column.cfl: column for column in installed_gate8_full.columns}[0.025]
    assert column.config.n_cells == 32
    assert column.config.cfl == 0.025
    assert column.baseline.outcome in {
        "ACCEPTED_FIRST_CROSSING",
        "NO_CROSSING_WITHIN_HORIZON",
        "ENDPOINT_LANDING",
        "FORBIDDEN_TRANSITION",
        "REVERSE_FLOW_GUARD",
        "GUARD_FAILURE",
        "BACKEND_FAILURE",
    }
    assert column.baseline.step_count <= 8000
    if column.baseline.outcome == "ACCEPTED_FIRST_CROSSING":
        assert column.continuation_outcome in {
            "COMPLETED_FIXED_CHECKPOINTS",
            "FAIL_SAFE_STOP",
        }
        if column.continuation_outcome == "COMPLETED_FIXED_CHECKPOINTS":
            assert all(row.reached for row in column.checkpoints)
        else:
            assert column.failure_category
            assert column.failure_reason
    else:
        assert column.continuation_outcome == "NOT_STARTED_NO_ACCEPTED_FIRST_CROSSING"
        assert not column.steps
        assert not column.focused_cells
        assert all(not row.reached for row in column.checkpoints)


@pytest.mark.coolprop_installed
def test_gate8_full_classifies_outcome_divergence_without_approval(
    installed_gate8_full,
) -> None:
    summary = installed_gate8_full.summary()
    assert summary["locked_full_cfl_sequence"] == [0.10, 0.05, 0.025]
    assert summary["implemented_cfl_columns"] == [0.10, 0.05, 0.025]
    assert summary["pending_cfl_columns"] == []
    assert summary["gate6_identity_reproduced_exactly"] is True
    assert summary["full_gate8_sequence_executed"] is True
    assert summary["formal_outcome_comparison_complete"] is True
    assert "FIXED_HORIZON_OUTCOME_DIVERGENCE" in summary[
        "cross_cfl_classifications"
    ]
    assert "POST_CROSSING_CFL_REVIEW_INCONCLUSIVE" in summary[
        "cross_cfl_classifications"
    ]
    assert summary["Gate_8_execution_complete"] is True
    for key, value in FULL_APPROVAL_BOUNDARY.items():
        assert summary[key] is value


@pytest.mark.coolprop_installed
def test_gate8_full_checkpoint_and_budget_contract(installed_gate8_full) -> None:
    targets = dict(full.PHYSICAL_CHECKPOINTS_S)
    for column in installed_gate8_full.columns:
        assert len(column.checkpoints) == 4
        for row in column.checkpoints:
            assert row.target_elapsed_s == targets[row.checkpoint]
            if row.reached:
                assert row.actual_elapsed_s is not None
                assert row.overshoot_s is not None
                assert row.local_dt_s is not None
                assert row.actual_elapsed_s >= row.target_elapsed_s
                assert 0.0 <= row.overshoot_s <= row.local_dt_s
                assert row.accepted_state_sha256
        for step in column.steps:
            assert step.dt_s > 0.0
            assert step.time_after_s > step.time_before_s
            assert step.second_projection_noop is True
            assert step.second_projection_cell_count == 0
            assert np.isfinite(step.mass_total_kg)
            assert np.isfinite(step.energy_total_J)
            assert (
                abs(step.phase_vapor_residual_kg)
                <= column.config.vapor_budget_absolute_tolerance_kg
            )


@pytest.mark.coolprop_installed
def test_gate8_full_artifact_bundle_is_complete(
    installed_gate8_full,
    tmp_path: Path,
) -> None:
    result, paths = write_gate8_full_artifacts(tmp_path, installed_gate8_full)
    assert result is installed_gate8_full
    assert set(paths) == {
        "summary",
        "cases",
        "comparison",
        "checkpoints",
        "focus",
        "transitions",
        "inventory",
        "report",
        "digest",
        "front",
        "quality",
        "cell30",
        "chatter",
        "budget",
    }
    expected = {
        "summary.json",
        "cfl_cases.csv",
        "cross_cfl_comparison.csv",
        "physical_checkpoints.csv",
        "cell_29_30_31_history.csv",
        "transition_events.csv",
        "inventory_budget.csv",
        "report.md",
        "front_position_vs_time.png",
        "quality_void_fraction_vs_time.png",
        "cell30_phase_acoustic_margin.png",
        "chatter_frequency_comparison.png",
        "budget_residual_comparison.png",
        "artifact_sha256.txt",
    }
    assert expected == {path.name for path in tmp_path.iterdir()}
    assert all(path.stat().st_size > 0 for path in tmp_path.iterdir())
    payload = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert payload["full_gate8_sequence_executed"] is True
    assert payload["pending_cfl_columns"] == []
    assert payload["Gate_8_execution_complete"] is True
    assert payload["production_solver_changed"] is False
    assert payload["sound_speed_formula_changed"] is False
    assert payload["quality_projection_changed"] is False
    assert payload["threshold_or_tolerance_tuned"] is False
    digest = paths["digest"].read_text(encoding="utf-8")
    assert "summary.json" in digest
    assert "budget_residual_comparison.png" in digest
