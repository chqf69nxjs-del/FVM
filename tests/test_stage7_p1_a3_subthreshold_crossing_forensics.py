from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from liquid_gas_transient.hem_pipeline_subthreshold_crossing_forensics import (
    P1_A3F_EVIDENCE_FLOOR,
    P1_A3F_FORMAL_STATUS,
    P1_A3F_OUTPUT_FILES,
    P1_A3F_SCHEMA_VERSION,
    _crossing_status,
    analyze_subthreshold_crossing_forensics,
    write_subthreshold_crossing_forensic_artifacts,
)


def test_a3f_contract_preserves_threshold_and_maturity_boundary() -> None:
    assert P1_A3F_SCHEMA_VERSION == (
        "stage7_p1_a3_subthreshold_crossing_forensics_v1"
    )
    assert P1_A3F_EVIDENCE_FLOOR == pytest.approx(1.0e-6)
    assert P1_A3F_OUTPUT_FILES == (
        "forensic_summary.json",
        "case_forensics.csv",
        "cell_forensics.csv",
        "quality_scaling.csv",
        "quality_vs_dx.png",
        "quality_vs_cfl.png",
        "operator_report.md",
        "forensic_manifest.json",
    )
    assert P1_A3F_FORMAL_STATUS["implemented"] is True
    assert P1_A3F_FORMAL_STATUS["diagnostic_evidence_ready"] is False
    assert P1_A3F_FORMAL_STATUS["working_vertical_slice"] is False
    assert P1_A3F_FORMAL_STATUS["verified"] is False
    assert P1_A3F_FORMAL_STATUS["accepted"] is False
    assert P1_A3F_FORMAL_STATUS["mesh_independent_crossing_verified"] is False
    assert P1_A3F_FORMAL_STATUS["cfl_independent_crossing_verified"] is False
    assert P1_A3F_FORMAL_STATUS["physically_validated"] is False
    assert P1_A3F_FORMAL_STATUS["design_use_accepted"] is False
    assert P1_A3F_FORMAL_STATUS["production_approved"] is False


def test_a3f_crossing_status_distinguishes_guard_from_other_failures() -> None:
    accepted = SimpleNamespace(
        outcome="ACCEPTED_FIRST_CROSSING",
        crossing_step=10,
        maximum_crossing_quality=2.0e-6,
        failure_reason="",
    )
    assert _crossing_status(accepted) == "ACCEPTED_ABOVE_FIXED_FLOOR"

    subthreshold = SimpleNamespace(
        outcome="GUARD_FAILURE",
        crossing_step=20,
        maximum_crossing_quality=4.0e-7,
        failure_reason=(
            "HEMPipelineDepressurizationError: "
            "crossing quality evidence is below the fixed minimum"
        ),
    )
    assert _crossing_status(subthreshold) == "SUBTHRESHOLD_CROSSING_RETAINED"

    unrelated = SimpleNamespace(
        outcome="BACKEND_FAILURE",
        crossing_step=None,
        maximum_crossing_quality=0.0,
        failure_reason="CoolProp backend failed",
    )
    assert _crossing_status(unrelated) == "NO_RETAINED_CROSSING"


@pytest.fixture(scope="module")
def installed_a3f_summary():
    pytest.importorskip("CoolProp")
    return analyze_subthreshold_crossing_forensics()


@pytest.mark.coolprop_installed
def test_a3f_real_matrix_confirms_direct_failure_mechanism(
    installed_a3f_summary,
) -> None:
    summary = installed_a3f_summary

    assert summary["forensics_ready"] is True
    assert summary["forensic_execution_status"] == "FORENSICS_READY"
    assert summary["direct_failure_mechanism"] == "CONFIRMED"
    assert summary["resolution_interaction_hypothesis"] == (
        "SUPPORTED_BY_FINE_MESH_AND_LOW_CFL"
    )
    assert summary["cfl_crossing_quality_trend"] == (
        "STRICTLY_INCREASING_WITH_CFL"
    )
    assert summary["fine_mesh_crosses_below_fixed_floor"] is True
    assert summary["low_cfl_crosses_below_fixed_floor"] is True
    assert summary["subthreshold_case_ids"] == [
        "mesh_64_cfl_0p10",
        "cfl_32_0p05",
    ]
    assert summary["unrelated_failure_case_ids"] == []
    assert summary["threshold_or_tolerance_changed"] is False
    assert summary["solver_or_physics_changed"] is False
    assert all(summary["gate_results"].values())

    by_id = {
        row["case_id"]: row
        for row in summary["case_forensics"]
    }
    assert list(by_id) == [
        "mesh_16_cfl_0p10",
        "baseline_32_cfl_0p10",
        "mesh_64_cfl_0p10",
        "cfl_32_0p05",
        "cfl_32_0p20",
    ]
    assert by_id["baseline_32_cfl_0p10"]["final_state_sha256"] == (
        "170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361"
    )

    for row in by_id.values():
        assert row["crossing_detected"] is True
        assert row["crossing_time_s"] > 0.0
        assert row["crossing_dt_s"] > 0.0
        assert row["maximum_crossing_quality"] > 0.0
        assert len(row["final_state_sha256"]) == 64
        assert len(row["run_signature_sha256"]) == 64
        if row["crossing_status"] == "ACCEPTED_ABOVE_FIXED_FLOOR":
            assert row["outcome"] == "ACCEPTED_FIRST_CROSSING"
            assert row["quality_to_floor_ratio"] >= 1.0
        else:
            assert row["crossing_status"] == "SUBTHRESHOLD_CROSSING_RETAINED"
            assert row["outcome"] == "GUARD_FAILURE"
            assert 0.0 < row["quality_to_floor_ratio"] < 1.0


@pytest.mark.coolprop_installed
def test_a3f_cell_records_preserve_pre_and_post_crossing_state(
    installed_a3f_summary,
) -> None:
    rows = installed_a3f_summary["cell_forensics"]
    assert len(rows) >= 5
    assert {row["case_id"] for row in rows} == {
        "mesh_16_cfl_0p10",
        "baseline_32_cfl_0p10",
        "mesh_64_cfl_0p10",
        "cfl_32_0p05",
        "cfl_32_0p20",
    }
    for row in rows:
        assert row["transition_event"] == "LIQUID_TO_TWO_PHASE_CROSSING"
        assert row["previous_region"] in {
            "LIQUID_CANDIDATE",
            "SATURATED_LIQUID_ENDPOINT",
        }
        assert row["raw_region"] == "OPEN_TWO_PHASE"
        assert row["post_region"] == "OPEN_TWO_PHASE"
        assert row["quality_previous_accepted"] <= P1_A3F_EVIDENCE_FLOOR
        assert row["quality_raw_equilibrium"] > 0.0
        assert row["quality_post_projection"] == pytest.approx(
            row["quality_raw_equilibrium"]
        )
        assert row["quality_reconstructed_accepted"] == pytest.approx(
            row["quality_raw_equilibrium"]
        )
        assert row["first_projection_applied"] is True
        assert row["second_projection_applied"] is False
        assert row["dt_s"] > 0.0
        assert row["pressure_previous_pa"] > 0.0
        assert row["pressure_raw_pa"] > 0.0
        assert row["pressure_post_pa"] > 0.0


@pytest.mark.coolprop_installed
def test_a3f_writer_retains_exact_eight_file_contract(
    installed_a3f_summary,
    tmp_path: Path,
) -> None:
    paths = write_subthreshold_crossing_forensic_artifacts(
        tmp_path,
        installed_a3f_summary,
    )
    assert set(paths) == {
        "summary",
        "case_forensics",
        "cell_forensics",
        "quality_scaling",
        "quality_vs_dx",
        "quality_vs_cfl",
        "operator_report",
        "manifest",
    }
    assert {path.name for path in tmp_path.iterdir()} == set(P1_A3F_OUTPUT_FILES)

    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert summary["forensics_ready"] is True
    assert summary["direct_failure_mechanism"] == "CONFIRMED"
    assert manifest["declared_file_count"] == 8
    assert manifest["declared_file_names"] == list(P1_A3F_OUTPUT_FILES)
    assert manifest["forensic_sha256"] == summary["forensic_sha256"]
    assert manifest["threshold_or_tolerance_changed"] is False
    assert manifest["solver_or_physics_changed"] is False
    assert paths["quality_vs_dx"].stat().st_size > 0
    assert paths["quality_vs_cfl"].stat().st_size > 0
