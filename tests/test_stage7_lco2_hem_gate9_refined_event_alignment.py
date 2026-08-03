from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import liquid_gas_transient.hem_gate9_refined_event_alignment as refined
from liquid_gas_transient.hem_gate9_event_alignment import (
    D4_CAPTURED_STAGES,
    D4_POST_STATUS_FORMAL_STOP,
)
from liquid_gas_transient.hem_gate9_refined_event_alignment import (
    REFINED_D4_CFL_SEQUENCE,
    REFINED_D4_CONTRACTS,
    REFINED_D4_SCHEMA_VERSION,
    run_gate9_d4_refined_columns,
    write_gate9_d4_refined_artifacts,
)


def test_refined_d4_contract_locks_retained_gate8_identities() -> None:
    assert REFINED_D4_CFL_SEQUENCE == (0.05, 0.025)
    by_cfl = {contract.cfl: contract for contract in REFINED_D4_CONTRACTS}

    lower = by_cfl[0.05]
    assert lower.expected_outcome == "GUARD_FAILURE"
    assert lower.expected_step_count == 249
    assert lower.expected_candidate_time_s == 7.967173062790038e-4
    assert lower.expected_candidate_cells == (29,)
    assert lower.expected_maximum_candidate_quality == 1.1006096906989802e-7
    assert lower.expected_final_state_sha256 == (
        "d18e4bdf1477c29f1183b2f3276c84e086f6cfef80c336a7f6f13616769c5a29"
    )
    assert lower.expected_run_signature_sha256 == (
        "1292331d53eddd7ec700d8a76bc3900a501c40f4671c758b0ae4bd5c9487cfde"
    )

    finest = by_cfl[0.025]
    assert finest.expected_outcome == "ACCEPTED_FIRST_CROSSING"
    assert finest.expected_step_count == 499
    assert finest.expected_candidate_time_s == 7.981201399992095e-4
    assert finest.expected_candidate_cells == (29,)
    assert finest.expected_maximum_candidate_quality == 1.3949366092287805e-6
    assert finest.expected_final_state_sha256 == (
        "cb2d5859775d1b1c736e936af798c36cd8d20c73d926de9ed47bcc0aadb1f688"
    )
    assert finest.expected_run_signature_sha256 == (
        "5af1d089f4139b209a7bfc192a4fc5d6afda9da4031a60a1d13f0ddf683e6dd7"
    )


def test_refined_d4_module_is_observation_orchestration_only() -> None:
    source = inspect.getsource(refined)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "class VerificationHEMLiquidOpenTwoPhaseEOS" not in source
    assert "crossing_threshold_changed\": True" not in source
    assert "production_hem_activation_approved\": True" not in source
    assert "forced_post_guard_continuation\": True" not in source


@pytest.fixture(scope="module")
def installed_refined_d4():
    pytest.importorskip("CoolProp")
    return run_gate9_d4_refined_columns()


@pytest.mark.coolprop_installed
def test_refined_d4_reproduces_both_formal_outcomes_without_solver_change(
    installed_refined_d4,
) -> None:
    result = installed_refined_d4
    assert tuple(column.contract.cfl for column in result.columns) == (
        0.05,
        0.025,
    )
    by_cfl = {column.contract.cfl: column for column in result.columns}

    lower = by_cfl[0.05]
    lower_summary = lower.summary()
    assert lower_summary["formal_outcome"] == "GUARD_FAILURE"
    assert lower_summary["candidate_step"] == 249
    assert lower_summary["candidate_time_s"] == 7.967173062790038e-4
    assert lower_summary["candidate_cells"] == [29]
    assert lower_summary["window_steps"] == list(range(241, 250))
    assert lower_summary["maximum_candidate_quality"] == 1.1006096906989802e-7

    finest = by_cfl[0.025]
    finest_summary = finest.summary()
    assert finest_summary["formal_outcome"] == "ACCEPTED_FIRST_CROSSING"
    assert finest_summary["candidate_step"] == 499
    assert finest_summary["candidate_time_s"] == 7.981201399992095e-4
    assert finest_summary["candidate_cells"] == [29]
    assert finest_summary["window_steps"] == list(range(491, 500))
    assert finest_summary["maximum_candidate_quality"] == 1.3949366092287805e-6

    for column in result.columns:
        summary = column.summary()
        assert summary["gate8_identity_reproduced_exactly"] is True
        assert summary["diagnostic_off_on_identity"] is True
        assert summary["available_pre_step_count"] == 8
        assert summary["available_post_step_count"] == 0
        assert summary["post_window_status"] == D4_POST_STATUS_FORMAL_STOP
        assert summary["captured_exact_stages"] == list(D4_CAPTURED_STAGES)
        assert summary["exact_cell_stage_record_count"] == 9 * 5 * 4
        assert summary["d1_cell_stage_record_count"] == 9 * 3 * 4
        assert summary["interface_flux_record_count"] == 9 * 5
        assert summary["cfl_decision_record_count"] == 9
        assert summary["aligned_acoustic_record_count"] > 0
        assert summary["all_acoustic_records_have_step_cell_stage_dt"] is True
        assert summary["all_cfl_decisions_match_production_dt"] is True
        assert summary["all_timeline_records_have_source_time"] is True
        assert summary["rusanov_reconstruction_guard_passed"] is True
        assert summary["forced_post_guard_continuation"] is False
        assert summary["Gate_9_execution_complete"] is False
        assert np.array_equal(
            column.solver_identity_off["crossing_cell_indices"],
            column.solver_identity_on["crossing_cell_indices"],
        )

    aggregate = result.summary()
    assert aggregate["schema_version"] == REFINED_D4_SCHEMA_VERSION
    assert aggregate["all_gate8_identities_reproduced_exactly"] is True
    assert aggregate["all_diagnostic_off_on_identities_passed"] is True
    assert aggregate["all_rusanov_reconstruction_guards_passed"] is True
    assert aggregate["all_cfl_decisions_match_production_dt"] is True
    assert aggregate["all_timeline_records_have_source_time"] is True
    assert aggregate["all_formal_stops_honored_without_continuation"] is True
    assert aggregate["refined_event_alignment_complete"] is True
    assert aggregate["Gate_9_execution_complete"] is False


@pytest.mark.coolprop_installed
def test_refined_d4_writer_emits_two_complete_column_bundles(
    installed_refined_d4,
    tmp_path: Path,
) -> None:
    paths = write_gate9_d4_refined_artifacts(
        tmp_path,
        installed_refined_d4,
    )
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["locked_cfl_columns"] == [0.05, 0.025]
    assert summary["column_count"] == 2
    assert summary["column_artifact_directories"] == [
        "cfl_0p050",
        "cfl_0p025",
    ]

    with paths["candidate_metrics"].open(
        newline="", encoding="utf-8"
    ) as handle:
        metrics = list(csv.DictReader(handle))
    assert len(metrics) == 2
    assert {float(row["cfl"]) for row in metrics} == {0.05, 0.025}
    assert {row["formal_outcome"] for row in metrics} == {
        "GUARD_FAILURE",
        "ACCEPTED_FIRST_CROSSING",
    }

    for token in ("0p050", "0p025"):
        column_dir = tmp_path / f"cfl_{token}"
        expected = {
            "summary.json",
            "event_aligned_exact_cell_stage_history.csv",
            "event_aligned_d1_cell_stage_history.csv",
            "event_aligned_interface_flux_history.csv",
            "event_aligned_acoustic_history.csv",
            "event_aligned_cfl_decision_history.csv",
            "candidate_event_timeline.csv",
            "candidate_summary.json",
            "artifact_sha256.txt",
        }
        assert expected == {path.name for path in column_dir.iterdir()}
        payload = json.loads(
            (column_dir / "summary.json").read_text(encoding="utf-8")
        )
        assert payload["exact_cell_stage_record_count"] == 180
        assert payload["d1_cell_stage_record_count"] == 108
        assert payload["interface_flux_record_count"] == 45
        assert payload["cfl_decision_record_count"] == 9
        assert payload["aligned_acoustic_record_count"] > 0
        assert payload["gate8_identity_reproduced_exactly"] is True
        assert payload["diagnostic_off_on_identity"] is True
        assert (
            (column_dir / "artifact_sha256.txt")
            .read_text(encoding="utf-8")
            .count("\n")
            == 8
        )

    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 20
