from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import liquid_gas_transient.hem_gate9_three_cfl_integration as d5
from liquid_gas_transient.hem_gate9_three_cfl_integration import (
    D5_CFL_SEQUENCE,
    D5_SCHEMA_VERSION,
    D5_THRESHOLD,
    run_gate9_d5_three_cfl_integration,
    write_gate9_d5_artifacts,
)


def test_d5_contract_is_fixed_and_non_approving() -> None:
    assert D5_CFL_SEQUENCE == (0.10, 0.05, 0.025)
    assert D5_THRESHOLD == 1.0e-6
    source = inspect.getsource(d5)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert '"Gate_9_execution_complete": True' not in source
    assert '"crossing_depth_root_cause_approved": True' not in source
    assert '"threshold_change_authorized": True' not in source
    assert '"production_hem_activation_approved": True' not in source


def test_d5_sequence_status_is_neutral_and_explicit() -> None:
    assert d5._sequence_status((1.0, 1.0, 1.0)) == "CONSTANT"
    assert d5._sequence_status((3.0, 2.0, 1.0)) == "MONOTONE_NONINCREASING"
    assert d5._sequence_status((1.0, 2.0, 3.0)) == "MONOTONE_NONDECREASING"
    assert d5._sequence_status((3.0, 1.0, 2.0)) == "NON_MONOTONE"
    assert d5._sequence_status((1.0, float("nan"), 2.0)) == "INCOMPLETE"


@pytest.fixture(scope="module")
def installed_d5():
    pytest.importorskip("CoolProp")
    return run_gate9_d5_three_cfl_integration()


@pytest.mark.coolprop_installed
def test_d5_executes_and_integrates_all_three_locked_columns(installed_d5) -> None:
    result = installed_d5
    assert tuple(column.cfl for column in result.columns) == D5_CFL_SEQUENCE
    by_cfl = {column.cfl: column for column in result.columns}

    assert by_cfl[0.10].formal_outcome == "ACCEPTED_FIRST_CROSSING"
    assert by_cfl[0.10].candidate_step == 125
    assert by_cfl[0.05].formal_outcome == "GUARD_FAILURE"
    assert by_cfl[0.05].candidate_step == 249
    assert by_cfl[0.025].formal_outcome == "ACCEPTED_FIRST_CROSSING"
    assert by_cfl[0.025].candidate_step == 499

    summary = result.summary()
    assert summary["schema_version"] == D5_SCHEMA_VERSION
    assert summary["locked_cfl_sequence"] == [0.10, 0.05, 0.025]
    assert summary["focused_cell_stage_record_count"] == 540
    assert summary["focused_interface_flux_record_count"] == 135
    assert summary["cfl_decision_record_count"] == 27
    assert summary["projection_record_count"] == 108
    assert summary["budget_record_count"] == 27
    assert summary["candidate_metric_count"] == 3
    assert summary["candidate_comparison_count"] == 3
    assert summary["acoustic_attempt_record_count"] > 0
    assert summary["timeline_record_count"] > 0
    assert summary["all_gate8_formal_identities_reproduced"] is True
    assert summary["all_rusanov_reconstruction_guards_passed"] is True
    assert summary["all_cfl_decisions_match_production_dt"] is True
    assert summary["all_timeline_records_have_source_time"] is True
    assert summary["all_second_projections_exact_noop"] is True
    assert summary["budgets_traceable"] is True
    assert summary["D5_three_cfl_integration_complete"] is True
    assert summary["D6_temporal_correlation_classification_complete"] is False
    assert summary["Gate_9_execution_complete"] is False
    assert summary["candidate_depth_sequence_status"] == "NON_MONOTONE"

    metrics = {row.cfl: row for row in result.candidate_metrics}
    assert metrics[0.10].maximum_candidate_q_eq == 3.773646403587342e-6
    assert metrics[0.05].maximum_candidate_q_eq == 1.1006096906989802e-7
    assert metrics[0.025].maximum_candidate_q_eq == 1.3949366092287805e-6
    assert all(row.second_projection_exact_noop for row in result.candidate_metrics)
    assert all(row.final_sound_speed_m_s is not None for row in result.candidate_metrics)
    assert all(
        row.q_internal_energy_coordinate is not None
        and row.q_specific_volume_coordinate is not None
        for row in result.candidate_metrics
    )
    assert np.isfinite(
        [row.delta_rho_E_pre_to_raw for row in result.candidate_metrics]
    ).all()


@pytest.mark.coolprop_installed
def test_d5_writer_emits_complete_same_schema_bundle(
    installed_d5,
    tmp_path: Path,
) -> None:
    paths = write_gate9_d5_artifacts(tmp_path, installed_d5)
    expected = {
        "summary.json",
        "per_cfl_candidate_metrics.csv",
        "focused_cell_stage_history.csv",
        "focused_interface_flux_decomposition.csv",
        "candidate_event_comparison.csv",
        "saturation_margin_history.csv",
        "projection_history.csv",
        "budget_history.csv",
        "acoustic_attempt_history.csv",
        "cfl_decision_history.csv",
        "candidate_event_timeline.csv",
        "report.md",
        "candidate_quality_vs_physical_time.png",
        "saturation_margins_vs_physical_time.png",
        "candidate_step_flux_decomposition.png",
        "acoustic_branch_vs_margin.png",
        "cross_cfl_depth_comparison.png",
        "artifact_sha256.txt",
    }
    assert expected == {path.name for path in tmp_path.iterdir()}
    assert all(path.stat().st_size > 0 for path in tmp_path.iterdir())

    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["D5_three_cfl_integration_complete"] is True
    assert summary["D6_temporal_correlation_classification_complete"] is False
    assert summary["Gate_9_execution_complete"] is False

    def count_rows(name: str) -> int:
        with (tmp_path / name).open(newline="", encoding="utf-8") as handle:
            return sum(1 for _ in csv.DictReader(handle))

    assert count_rows("per_cfl_candidate_metrics.csv") == 3
    assert count_rows("focused_cell_stage_history.csv") == 540
    assert count_rows("focused_interface_flux_decomposition.csv") == 135
    assert count_rows("candidate_event_comparison.csv") == 3
    assert count_rows("saturation_margin_history.csv") == 540
    assert count_rows("projection_history.csv") == 108
    assert count_rows("budget_history.csv") == 27
    assert count_rows("cfl_decision_history.csv") == 27
    assert count_rows("candidate_event_timeline.csv") == summary[
        "timeline_record_count"
    ]
    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 17
