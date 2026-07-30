from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import liquid_gas_transient.hem_pipeline_post_crossing_cfl_sensitivity as gate8
from liquid_gas_transient.hem_pipeline_post_crossing_cfl_sensitivity import (
    APPROVAL_BOUNDARY,
    EXPECTED_GATE6_CELL30_REGION_CHANGES,
    EXPECTED_GATE6_FINAL_STATE_SHA256,
    EXPECTED_GATE6_FINAL_TIME_S,
    GATE6_REFERENCE_POST_STEPS,
    GATE8_CFL_SEQUENCE,
    IMPLEMENTED_CFL_COLUMNS,
    PENDING_CFL_COLUMNS,
    PHYSICAL_CHECKPOINTS_S,
    HEMGate8CflSensitivityError,
    HEMGate8PipelineConfig,
    run_gate8_cfl_0p10_0p05_increment,
    write_gate8_cfl_0p10_0p05_artifacts,
)


def test_gate8_increment_contract_is_locked_before_results() -> None:
    assert GATE8_CFL_SEQUENCE == (0.10, 0.05, 0.025)
    assert IMPLEMENTED_CFL_COLUMNS == (0.10, 0.05)
    assert PENDING_CFL_COLUMNS == (0.025,)
    assert dict(PHYSICAL_CHECKPOINTS_S) == {
        "T1": 6.016940923599307e-6,
        "T2": 2.402911232474538e-5,
        "T3": 9.544429181626145e-5,
        "T4": 3.696527559334590e-4,
    }
    assert GATE6_REFERENCE_POST_STEPS == {"T1": 1, "T2": 4, "T3": 16, "T4": 64}
    assert HEMGate8PipelineConfig.for_cfl(0.10).max_steps == 2000
    assert HEMGate8PipelineConfig.for_cfl(0.05).max_steps == 4000
    assert HEMGate8PipelineConfig.for_cfl(0.025).max_steps == 8000
    assert all(value is False for value in APPROVAL_BOUNDARY.values())


def test_gate8_config_rejects_unreviewed_changes() -> None:
    with pytest.raises(ValueError):
        HEMGate8PipelineConfig.for_cfl(0.075)
    with pytest.raises(ValueError):
        HEMGate8PipelineConfig(cfl=0.05, max_steps=2000)
    with pytest.raises(ValueError):
        HEMGate8PipelineConfig(cfl=0.05, max_steps=4000, n_cells=64)
    with pytest.raises(ValueError):
        HEMGate8PipelineConfig(cfl=0.05, max_steps=4000, subcooling_K=4.0)


def test_gate8_module_is_verification_orchestration_only() -> None:
    source = inspect.getsource(gate8)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "class VerificationHEMLiquidOpenTwoPhaseEOS" not in source
    assert "class HEMEquilibriumQualityProjection" not in source
    assert "MUSCL" not in source
    assert "production_solver_changed" in source
    assert "sound_speed_formula_changed" in source
    assert "quality_projection_changed" in source
    assert "threshold_or_tolerance_tuned" in source


def test_gate8_stops_before_0p05_when_0p10_identity_fails(monkeypatch) -> None:
    refined_called = False

    def fail_gate6():
        raise HEMGate8CflSensitivityError("synthetic Gate 6 identity mismatch")

    def refined(_cfl: float):
        nonlocal refined_called
        refined_called = True
        raise AssertionError("CFL 0.05 must not start")

    monkeypatch.setattr(gate8, "_run_gate6_column", fail_gate6)
    monkeypatch.setattr(gate8, "_run_refined_column", refined)
    with pytest.raises(HEMGate8CflSensitivityError):
        run_gate8_cfl_0p10_0p05_increment()
    assert refined_called is False


@pytest.fixture(scope="module")
def installed_gate8_increment():
    pytest.importorskip("CoolProp")
    return run_gate8_cfl_0p10_0p05_increment()


@pytest.mark.coolprop_installed
def test_gate8_cfl_0p10_reproduces_complete_gate6_identity(
    installed_gate8_increment,
) -> None:
    by_cfl = {column.cfl: column for column in installed_gate8_increment.columns}
    column = by_cfl[0.10]
    assert installed_gate8_increment.summary()["gate6_identity_reproduced_exactly"] is True
    assert column.baseline.outcome == "ACCEPTED_FIRST_CROSSING"
    assert column.baseline.crossing_step == 125
    assert column.baseline.crossing_time_s == 7.999325695335248e-4
    assert column.baseline.crossing_cell_indices == (29,)
    assert column.baseline.crossing_distances_from_outlet_m == (0.078125,)
    assert column.baseline.maximum_crossing_quality == 3.773646403587342e-6
    assert column.continuation_outcome == "COMPLETED_FIXED_CHECKPOINTS"
    assert len(column.steps) == 64
    assert column.steps[-1].time_after_s == EXPECTED_GATE6_FINAL_TIME_S
    assert column.last_valid_state_sha256 == EXPECTED_GATE6_FINAL_STATE_SHA256
    assert column.region_toggle_counts[30] == EXPECTED_GATE6_CELL30_REGION_CHANGES
    assert {
        row.checkpoint: row.post_crossing_step
        for row in column.checkpoints
        if row.reached
    } == GATE6_REFERENCE_POST_STEPS


@pytest.mark.coolprop_installed
def test_gate8_cfl_0p05_retains_its_formal_outcome(installed_gate8_increment) -> None:
    by_cfl = {column.cfl: column for column in installed_gate8_increment.columns}
    column = by_cfl[0.05]
    assert column.config.n_cells == 32
    assert column.config.cfl == 0.05
    assert column.baseline.outcome in {
        "ACCEPTED_FIRST_CROSSING",
        "NO_CROSSING_WITHIN_HORIZON",
        "ENDPOINT_LANDING",
        "FORBIDDEN_TRANSITION",
        "REVERSE_FLOW_GUARD",
        "GUARD_FAILURE",
        "BACKEND_FAILURE",
    }
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
def test_gate8_checkpoint_sampling_uses_physical_time(installed_gate8_increment) -> None:
    targets = dict(PHYSICAL_CHECKPOINTS_S)
    for column in installed_gate8_increment.columns:
        assert len(column.checkpoints) == 4
        for row in column.checkpoints:
            assert row.target_elapsed_s == targets[row.checkpoint]
            if not row.reached:
                continue
            assert row.actual_elapsed_s is not None
            assert row.overshoot_s is not None
            assert row.local_dt_s is not None
            assert row.actual_elapsed_s >= row.target_elapsed_s
            assert row.overshoot_s >= 0.0
            assert row.overshoot_s <= row.local_dt_s
            assert row.accepted_state_sha256


@pytest.mark.coolprop_installed
def test_gate8_successful_steps_retain_projection_and_budgets(
    installed_gate8_increment,
) -> None:
    for column in installed_gate8_increment.columns:
        for step in column.steps:
            assert step.dt_s > 0.0
            assert step.time_after_s > step.time_before_s
            assert step.second_projection_noop is True
            assert step.second_projection_cell_count == 0
            assert np.isfinite(step.mass_total_kg)
            assert np.isfinite(step.energy_total_J)
            assert abs(step.phase_vapor_residual_kg) <= column.config.vapor_budget_absolute_tolerance_kg
        if column.steps:
            assert len(column.focused_cells) == len(column.steps) * 3
            assert all(row.cell_index in {29, 30, 31} for row in column.focused_cells)
            assert all(np.isfinite(row.pressure_pa) for row in column.focused_cells)
            assert all(np.isfinite(row.sound_speed_m_s) for row in column.focused_cells)


@pytest.mark.coolprop_installed
def test_gate8_increment_withholds_full_sequence_interpretation(
    installed_gate8_increment,
) -> None:
    summary = installed_gate8_increment.summary()
    assert summary["locked_full_cfl_sequence"] == [0.10, 0.05, 0.025]
    assert summary["implemented_cfl_columns"] == [0.10, 0.05]
    assert summary["pending_cfl_columns"] == [0.025]
    assert summary["full_gate8_sequence_executed"] is False
    assert summary["cross_cfl_interpretation_authorized"] is False
    assert summary["cross_cfl_classifications"] == []
    assert all(summary[key] is False for key in APPROVAL_BOUNDARY)


@pytest.mark.coolprop_installed
def test_gate8_increment_artifact_bundle_is_complete(
    installed_gate8_increment,
    tmp_path: Path,
) -> None:
    result, paths = write_gate8_cfl_0p10_0p05_artifacts(
        tmp_path, installed_gate8_increment
    )
    assert result is installed_gate8_increment
    assert set(paths) == {
        "summary",
        "cases",
        "checkpoints",
        "focus",
        "transitions",
        "inventory",
        "report",
        "digest",
    }
    expected = {
        "summary.json",
        "cfl_cases.csv",
        "physical_checkpoints.csv",
        "cell_29_30_31_history.csv",
        "transition_events.csv",
        "inventory_budget.csv",
        "report.md",
        "artifact_sha256.txt",
    }
    assert expected == {path.name for path in tmp_path.iterdir()}
    payload = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert payload["gate6_identity_reproduced_exactly"] is True
    assert payload["full_gate8_sequence_executed"] is False
    assert payload["pending_cfl_columns"] == [0.025]
    assert payload["production_solver_changed"] is False
    assert payload["sound_speed_formula_changed"] is False
    assert payload["quality_projection_changed"] is False
    assert payload["threshold_or_tolerance_tuned"] is False
    assert all(payload[key] is False for key in APPROVAL_BOUNDARY)
    digest = paths["digest"].read_text(encoding="utf-8")
    assert "summary.json" in digest
    assert "inventory_budget.csv" in digest
