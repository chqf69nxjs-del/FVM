from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from liquid_gas_transient.hem_pipeline_crossing_event_alignment import (
    P1_A3G_AUTHORITATIVE_A3,
    P1_A3G_EVIDENCE_FLOOR,
    P1_A3G_FORMAL_STATUS,
    P1_A3G_MAX_SHADOW_STEPS,
    P1_A3G_OUTPUT_FILES,
    P1_A3G_SCHEMA_VERSION,
    analyze_crossing_event_alignment,
    write_crossing_event_alignment_artifacts,
)


def test_a3g_contract_freezes_a3_authority_and_maturity() -> None:
    assert P1_A3G_SCHEMA_VERSION == "stage7_p1_a3_crossing_event_alignment_v1"
    assert P1_A3G_EVIDENCE_FLOOR == pytest.approx(1.0e-6)
    assert P1_A3G_MAX_SHADOW_STEPS == 64
    assert P1_A3G_AUTHORITATIVE_A3 == {
        "sensitivity_execution_status": "FAIL_CLOSED",
        "ordering_verdict": "INCONCLUSIVE",
        "numerical_verdict": "INCONCLUSIVE",
    }
    assert P1_A3G_OUTPUT_FILES == (
        "event_alignment_summary.json",
        "event_alignment_cases.csv",
        "event_a_cells.csv",
        "event_b_cells.csv",
        "event_interval_history.csv",
        "event_ab_time_comparison.png",
        "event_ab_step_comparison.png",
        "operator_report.md",
        "event_alignment_manifest.json",
    )
    assert P1_A3G_FORMAL_STATUS["implemented"] is True
    assert P1_A3G_FORMAL_STATUS["diagnostic_evidence_ready"] is True
    assert P1_A3G_FORMAL_STATUS["working_vertical_slice"] is False
    assert P1_A3G_FORMAL_STATUS["verified"] is False
    assert P1_A3G_FORMAL_STATUS["accepted"] is False
    assert P1_A3G_FORMAL_STATUS["mesh_independent_crossing_verified"] is False
    assert P1_A3G_FORMAL_STATUS["cfl_independent_crossing_verified"] is False
    assert P1_A3G_FORMAL_STATUS["physically_validated"] is False
    assert P1_A3G_FORMAL_STATUS["design_use_accepted"] is False
    assert P1_A3G_FORMAL_STATUS["production_approved"] is False


@pytest.fixture(scope="module")
def installed_a3g_summary():
    pytest.importorskip("CoolProp")
    return analyze_crossing_event_alignment()


@pytest.mark.coolprop_installed
def test_a3g_real_matrix_aligns_event_a_and_event_b(installed_a3g_summary) -> None:
    summary = installed_a3g_summary
    assert summary["alignment_ready"] is True
    assert summary["alignment_execution_status"] == "ALIGNMENT_READY"
    assert summary["threshold_or_tolerance_changed"] is False
    assert summary["solver_or_physics_changed"] is False
    assert summary["authoritative_a3_verdict_changed"] is False
    assert summary["authoritative_a3_verdict"] == P1_A3G_AUTHORITATIVE_A3
    assert summary["subthreshold_case_ids"] == [
        "mesh_64_cfl_0p10",
        "cfl_32_0p05",
    ]
    assert summary["event_b_unreached_case_ids"] == []
    assert all(summary["gate_results"].values())

    by_id = {row["case_id"]: row for row in summary["case_alignment"]}
    assert list(by_id) == [
        "mesh_16_cfl_0p10",
        "baseline_32_cfl_0p10",
        "mesh_64_cfl_0p10",
        "cfl_32_0p05",
        "cfl_32_0p20",
    ]
    for case_id in (
        "mesh_16_cfl_0p10",
        "baseline_32_cfl_0p10",
        "cfl_32_0p20",
    ):
        row = by_id[case_id]
        assert row["authoritative_outcome"] == "ACCEPTED_FIRST_CROSSING"
        assert row["shadow_continuation_used"] is False
        assert row["delta_step_a_to_b"] == 0
        assert row["delta_t_a_to_b_s"] == pytest.approx(0.0, abs=0.0)

    for case_id in ("mesh_64_cfl_0p10", "cfl_32_0p05"):
        row = by_id[case_id]
        assert row["authoritative_outcome"] == "GUARD_FAILURE"
        assert "crossing quality evidence is below the fixed minimum" in row[
            "authoritative_failure_reason"
        ]
        assert row["shadow_continuation_used"] is True
        assert row["event_b_reached"] is True
        assert row["delta_step_a_to_b"] > 0
        assert row["delta_t_a_to_b_s"] > 0.0
        assert not row["shadow_failure_reason"]


@pytest.mark.coolprop_installed
def test_a3g_records_required_event_state_and_hashes(installed_a3g_summary) -> None:
    required = {
        "time_s",
        "absolute_step",
        "distance_from_outlet_m",
        "quality",
        "pressure_pa",
        "temperature_K",
        "rho_kg_m3",
        "internal_energy_j_kg",
        "void_fraction",
        "state_sha256",
    }
    for row in installed_a3g_summary["case_alignment"]:
        assert row["event_a_reproduced"] is True
        assert row["event_a_quality"] > 0.0
        assert row["event_b_reached"] is True
        assert row["event_b_quality"] >= P1_A3G_EVIDENCE_FLOOR
        assert len(row["event_a_state_sha256"]) == 64
        assert len(row["event_b_state_sha256"]) == 64
        assert row["event_a_dt_s"] > 0.0
        assert row["dx_m"] > 0.0
        assert math.isfinite(float(row["delta_x_front_a_to_b_m"]))

    assert installed_a3g_summary["event_a_cells"]
    assert installed_a3g_summary["event_b_cells"]
    for event_name, rows in (
        ("A", installed_a3g_summary["event_a_cells"]),
        ("B", installed_a3g_summary["event_b_cells"]),
    ):
        for row in rows:
            assert row["event"] == event_name
            assert required <= set(row)
            assert row["region"] == "OPEN_TWO_PHASE"
            assert row["quality"] > 0.0
            assert row["pressure_pa"] > 0.0
            assert row["temperature_K"] > 0.0
            assert row["rho_kg_m3"] > 0.0
            assert math.isfinite(row["internal_energy_j_kg"])
            assert 0.0 <= row["void_fraction"] <= 1.0
            assert len(row["state_sha256"]) == 64


@pytest.mark.coolprop_installed
def test_a3g_shadow_history_closes_budgets_and_avoids_reverse_flow(
    installed_a3g_summary,
) -> None:
    rows = installed_a3g_summary["event_interval_history"]
    assert rows
    shadow_rows = [row for row in rows if int(row["shadow_step"]) > 0]
    assert shadow_rows
    assert {row["case_id"] for row in shadow_rows} == {
        "mesh_64_cfl_0p10",
        "cfl_32_0p05",
    }
    for row in rows:
        assert math.isfinite(float(row["time_s"]))
        assert math.isfinite(float(row["maximum_equilibrium_quality"]))
        assert math.isfinite(float(row["boundary_mass_residual_kg"]))
        assert math.isfinite(float(row["boundary_momentum_residual_kg_m_s"]))
        assert math.isfinite(float(row["boundary_energy_residual_J"]))
        assert math.isfinite(float(row["phase_vapor_residual_kg"]))
        assert int(row["reverse_flow_fallback_count"]) == 0
        assert len(row["state_sha256"]) == 64


@pytest.mark.coolprop_installed
def test_a3g_writer_retains_exact_nine_file_contract(
    installed_a3g_summary,
    tmp_path: Path,
) -> None:
    paths = write_crossing_event_alignment_artifacts(tmp_path, installed_a3g_summary)
    assert {path.name for path in tmp_path.iterdir()} == set(P1_A3G_OUTPUT_FILES)
    assert set(paths) == {
        "summary",
        "cases",
        "event_a_cells",
        "event_b_cells",
        "history",
        "time_plot",
        "step_plot",
        "operator_report",
        "manifest",
    }
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert summary["alignment_ready"] is True
    assert manifest["declared_file_count"] == 9
    assert manifest["declared_file_names"] == list(P1_A3G_OUTPUT_FILES)
    assert manifest["event_alignment_sha256"] == summary["event_alignment_sha256"]
    assert manifest["threshold_or_tolerance_changed"] is False
    assert manifest["solver_or_physics_changed"] is False
    assert manifest["authoritative_a3_verdict_changed"] is False
    assert set(manifest["payload_files"]) == set(P1_A3G_OUTPUT_FILES) - {
        "event_alignment_manifest.json"
    }
    for item in manifest["payload_files"].values():
        assert item["size_bytes"] > 0
        assert len(item["sha256"]) == 64
    assert paths["time_plot"].stat().st_size > 0
    assert paths["step_plot"].stat().st_size > 0
