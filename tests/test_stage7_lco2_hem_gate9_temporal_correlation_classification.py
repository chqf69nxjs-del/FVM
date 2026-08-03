from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import liquid_gas_transient.hem_gate9_temporal_correlation_classification as d6
from liquid_gas_transient.hem_gate9_temporal_correlation_classification import (
    D5_ARTIFACT_ID,
    D5_ARTIFACT_ZIP_SHA256,
    D5_REQUIRED_FILES,
    D6_OUTPUT_FILES,
    HEMGate9D6ClassificationError,
    load_gate9_d5_artifact,
    main,
    run_gate9_d6_temporal_correlation_classification,
    write_gate9_d6_artifacts,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fixed_metric_rows() -> list[dict[str, object]]:
    return [
        {
            "cfl": 0.10,
            "formal_outcome": "ACCEPTED_FIRST_CROSSING",
            "candidate_step": 125,
            "candidate_time_s": 0.0007999325695335248,
            "candidate_cell": 29,
            "distance_from_outlet_m": 0.078125,
            "maximum_candidate_q_eq": 3.773646403587342e-6,
            "threshold_distance_q": 2.773646403587342e-6,
            "candidate_dt_s": 6.023380049039216e-6,
            "q_internal_energy_coordinate": 3.7736463990403946e-6,
            "q_specific_volume_coordinate": 3.773646403138018e-6,
            "delta_e_from_saturated_liquid_J_kg": 0.6807586208742578,
            "delta_v_from_saturated_liquid_m3_kg": 2.7145165974176363e-8,
            "first_projection_delta_rho_q": 0.0033445057825772,
            "second_projection_exact_noop": True,
            "final_sound_speed_m_s": 41.642563257594254,
            "final_sound_speed_branch": "liquid_vapor_two_phase",
            "cell29_dissipative_mass_increment": 0.2207161658568415,
            "cell29_dissipative_momentum_increment": -3.7520056509082576,
            "cell29_dissipative_energy_increment": -25424.06187418283,
            "cell31_central_mass_increment": 0.001308594638239,
            "cell31_central_momentum_increment": 9.894013102226154,
            "cell31_central_energy_increment": 2953.522392886007,
            "cell31_dissipative_mass_increment": 0.3883218210376369,
            "cell31_dissipative_momentum_increment": 5.457590900329791,
            "cell31_dissipative_energy_increment": -65760.27118177639,
        },
        {
            "cfl": 0.05,
            "formal_outcome": "GUARD_FAILURE",
            "candidate_step": 249,
            "candidate_time_s": 0.0007967173062790038,
            "candidate_cell": 29,
            "distance_from_outlet_m": 0.078125,
            "maximum_candidate_q_eq": 1.1006096906989802e-7,
            "threshold_distance_q": -8.89939030930102e-7,
            "candidate_dt_s": 3.011638866144135e-6,
            "q_internal_energy_coordinate": 1.1006096370890697e-7,
            "q_specific_volume_coordinate": 1.1006096872930017e-7,
            "delta_e_from_saturated_liquid_J_kg": 0.0198506625310983,
            "delta_v_from_saturated_liquid_m3_kg": 7.913295487632642e-10,
            "first_projection_delta_rho_q": 9.753790916467432e-5,
            "second_projection_exact_noop": True,
            "final_sound_speed_m_s": 41.65469693172281,
            "final_sound_speed_branch": "liquid_vapor_two_phase",
            "cell29_dissipative_mass_increment": 0.1101403954116506,
            "cell29_dissipative_momentum_increment": -1.871894020805661,
            "cell29_dissipative_energy_increment": -12696.618326968635,
            "cell31_central_mass_increment": 0.0006631708768334,
            "cell31_central_momentum_increment": 4.946386843167602,
            "cell31_central_energy_increment": 1476.539087093195,
            "cell31_dissipative_mass_increment": 0.1940212896447816,
            "cell31_dissipative_momentum_increment": 2.7297772298844487,
            "cell31_dissipative_energy_increment": -32838.38232377252,
        },
        {
            "cfl": 0.025,
            "formal_outcome": "ACCEPTED_FIRST_CROSSING",
            "candidate_step": 499,
            "candidate_time_s": 0.0007981201399992095,
            "candidate_cell": 29,
            "distance_from_outlet_m": 0.078125,
            "maximum_candidate_q_eq": 1.3949366092287805e-6,
            "threshold_distance_q": 3.949366092287805e-7,
            "candidate_dt_s": 1.5050024184020665e-6,
            "q_internal_energy_coordinate": 1.3949366068724192e-6,
            "q_specific_volume_coordinate": 1.3949366088625311e-6,
            "delta_e_from_saturated_liquid_J_kg": 0.25163636953220703,
            "delta_v_from_saturated_liquid_m3_kg": 1.0033579527987668e-8,
            "first_projection_delta_rho_q": 0.0012363058614448,
            "second_projection_exact_noop": True,
            "final_sound_speed_m_s": 41.64388919115967,
            "final_sound_speed_branch": "liquid_vapor_two_phase",
            "cell29_dissipative_mass_increment": 0.0551290103416703,
            "cell29_dissipative_momentum_increment": -0.942789819722047,
            "cell29_dissipative_energy_increment": -6373.790987560202,
            "cell31_central_mass_increment": 0.0003690064862415,
            "cell31_central_momentum_increment": 2.4418170418696263,
            "cell31_central_energy_increment": 749.7191059941979,
            "cell31_dissipative_mass_increment": 0.0969819900356861,
            "cell31_dissipative_momentum_increment": 1.39056405863638,
            "cell31_dissipative_energy_increment": -16448.420720816783,
        },
    ]


def _write_fixed_d5_fixture(target: Path) -> Path:
    target.mkdir(parents=True)
    summary = {
        "schema_version": d6.D5_SCHEMA_VERSION,
        "scope": "verification_only_same_schema_three_cfl_integration",
        "locked_cfl_sequence": [0.10, 0.05, 0.025],
        "column_count": 3,
        "focused_cell_stage_record_count": 540,
        "focused_interface_flux_record_count": 135,
        "projection_record_count": 108,
        "budget_record_count": 27,
        "cfl_decision_record_count": 27,
        "candidate_metric_count": 3,
        "candidate_comparison_count": 3,
        "candidate_depth_sequence_status": "NON_MONOTONE",
        "D5_three_cfl_integration_complete": True,
        "D6_temporal_correlation_classification_complete": False,
        "Gate_9_execution_complete": False,
        "all_gate8_formal_identities_reproduced": True,
        "all_rusanov_reconstruction_guards_passed": True,
        "all_cfl_decisions_match_production_dt": True,
        "all_timeline_records_have_source_time": True,
        "all_second_projections_exact_noop": True,
        "budgets_traceable": True,
        "provenance": {"source_git_sha": d6.D5_SOURCE_HEAD_SHA},
    }
    (target / "summary.json").write_text(
        json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(target / "per_cfl_candidate_metrics.csv", _fixed_metric_rows())

    projection_rows = []
    for metric in _fixed_metric_rows():
        rho_q = float(metric["first_projection_delta_rho_q"])
        projection_rows.append(
            {
                "cfl": metric["cfl"],
                "absolute_step": metric["candidate_step"],
                "candidate_relative_step": 0,
                "cell_index": 29,
                "raw_rho_q": 0.0,
                "post_first_rho_q": rho_q,
                "post_second_rho_q": rho_q,
                "final_rho_q": rho_q,
                "first_projection_delta_rho_q": rho_q,
                "second_projection_delta_rho_q": 0.0,
                "second_projection_exact_noop": True,
                "final_equals_second_projection": True,
            }
        )
    _write_csv(target / "projection_history.csv", projection_rows)

    timeline_rows = []
    sequence = 1
    for metric in _fixed_metric_rows():
        for stage in ("RAW_POST_FVM", "POST_FIRST_PROJECTION"):
            timeline_rows.append(
                {
                    "cfl": metric["cfl"],
                    "column_sequence_index": sequence,
                    "absolute_step": metric["candidate_step"],
                    "candidate_relative_step": 0,
                    "stage": stage,
                    "entity_type": "CELL",
                    "entity_id": "29",
                }
            )
            sequence += 1
    _write_csv(target / "candidate_event_timeline.csv", timeline_rows)

    structured = {
        "focused_cell_stage_history.csv",
        "focused_interface_flux_decomposition.csv",
        "candidate_event_comparison.csv",
        "saturation_margin_history.csv",
        "budget_history.csv",
        "acoustic_attempt_history.csv",
        "cfl_decision_history.csv",
    }
    for name in structured:
        (target / name).write_text("placeholder\n", encoding="utf-8")
    (target / "report.md").write_text("# D5 fixture\n", encoding="utf-8")
    for name in {
        "candidate_quality_vs_physical_time.png",
        "saturation_margins_vs_physical_time.png",
        "candidate_step_flux_decomposition.png",
        "acoustic_branch_vs_margin.png",
        "cross_cfl_depth_comparison.png",
    }:
        (target / name).write_bytes(b"fixture-png")

    members = sorted(D5_REQUIRED_FILES - {"artifact_sha256.txt"})
    (target / "artifact_sha256.txt").write_text(
        "\n".join(
            f"{hashlib.sha256((target / name).read_bytes()).hexdigest()}  {name}"
            for name in members
        )
        + "\n",
        encoding="utf-8",
    )
    assert {path.name for path in target.iterdir()} == D5_REQUIRED_FILES
    return target


def test_d6_contract_is_fixed_and_non_approving() -> None:
    assert D5_ARTIFACT_ID == 8855725551
    assert D5_ARTIFACT_ZIP_SHA256 == (
        "6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850"
    )
    assert len(d6.D6_PERMITTED_LABELS) == 12
    source = inspect.getsource(d6)
    assert "run_pipeline_depressurization_case" not in source
    assert '"crossing_depth_root_cause_approved": True' not in source
    assert '"threshold_change_authorized": True' not in source
    assert '"production_hem_activation_approved": True' not in source


def test_d6_fixed_classification_assigns_only_supported_labels(
    tmp_path: Path,
) -> None:
    artifact = _write_fixed_d5_fixture(tmp_path / "d5")
    result = run_gate9_d6_temporal_correlation_classification(artifact)
    summary = result.summary()
    assert summary["assigned_labels"] == [
        "CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL",
        "CROSSING_DEPTH_CFL_SENSITIVE",
        "CROSSING_DEPTH_SEQUENCE_NON_MONOTONE",
        "SATURATION_MARGIN_DISPLACEMENT_CORRELATED",
        "PROJECTION_ACTIVITY_POSTDATES_RAW_CROSSING",
        "THRESHOLD_CLASSIFICATION_DISCONTINUITY_OBSERVED",
        "CROSSING_DEPTH_REVIEW_INCONCLUSIVE",
    ]
    assert summary["not_assigned_labels"] == [
        "CANDIDATE_STEP_OVERSHOOT_CORRELATED",
        "RUSANOV_DISSIPATION_CORRELATED",
        "BOUNDARY_FLUX_IMBALANCE_CORRELATED",
        "ACOUSTIC_BRANCH_SELECTION_CORRELATED",
        "MULTI_FACTOR_CROSSING_DEPTH",
    ]
    assert summary["D6_temporal_correlation_classification_complete"] is True
    assert summary["Gate_9_execution_complete"] is True
    assert summary["crossing_depth_CFL_sensitivity_characterized"] is True
    assert summary["crossing_depth_root_cause_approved"] is False


def test_d6_mechanism_denominators_and_temporal_order_are_explicit(
    tmp_path: Path,
) -> None:
    result = run_gate9_d6_temporal_correlation_classification(
        _write_fixed_d5_fixture(tmp_path / "d5")
    )
    labels = {row.label: row for row in result.label_evidence}
    assert (
        labels["CANDIDATE_STEP_OVERSHOOT_CORRELATED"].numerator,
        labels["CANDIDATE_STEP_OVERSHOOT_CORRELATED"].denominator,
    ) == (2, 3)
    assert (
        labels["RUSANOV_DISSIPATION_CORRELATED"].numerator,
        labels["RUSANOV_DISSIPATION_CORRELATED"].denominator,
    ) == (12, 18)
    assert (
        labels["BOUNDARY_FLUX_IMBALANCE_CORRELATED"].numerator,
        labels["BOUNDARY_FLUX_IMBALANCE_CORRELATED"].denominator,
    ) == (6, 9)
    assert (
        labels["SATURATION_MARGIN_DISPLACEMENT_CORRELATED"].numerator,
        labels["SATURATION_MARGIN_DISPLACEMENT_CORRELATED"].denominator,
    ) == (12, 12)
    assert all(
        row.raw_crossing_precedes_projection_activity
        for row in result.temporal_order_evidence
    )
    assert all(
        row.classification_matches_threshold_side
        for row in result.threshold_evidence
    )


def test_d6_loader_rejects_modified_d5_artifact(tmp_path: Path) -> None:
    artifact = _write_fixed_d5_fixture(tmp_path / "d5")
    with (artifact / "per_cfl_candidate_metrics.csv").open(
        "a", encoding="utf-8"
    ) as handle:
        handle.write("tampered\n")
    with pytest.raises(HEMGate9D6ClassificationError, match="digest mismatch"):
        load_gate9_d5_artifact(artifact)


def test_d6_writer_emits_complete_bundle_and_digest(tmp_path: Path) -> None:
    artifact = _write_fixed_d5_fixture(tmp_path / "d5")
    result = run_gate9_d6_temporal_correlation_classification(artifact)
    output = tmp_path / "d6"
    paths = write_gate9_d6_artifacts(output, result)
    assert {path.name for path in output.iterdir()} == D6_OUTPUT_FILES
    assert all(path.stat().st_size > 0 for path in output.iterdir())
    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 6
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["label_count"] == 12
    assert summary["mechanism_comparison_record_count"] == 15
    assert summary["Gate_9_execution_complete"] is True


def test_d6_cli_executes_fixed_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = _write_fixed_d5_fixture(tmp_path / "d5")
    output = tmp_path / "d6"
    assert (
        main(
            [
                "--d5-artifact-dir",
                str(artifact),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert '"Gate_9_execution_complete": true' in captured.out
    assert (output / "artifact_sha256.txt").is_file()
