from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquid_gas_transient.hem_pipeline_mesh_cfl_sensitivity import (
    P1_A3_CASE_SPECS,
    P1_A3_FORMAL_STATUS,
    P1_A3_OUTPUT_FILES,
    P1_A3_SCHEMA_VERSION,
    _cfl_record,
    _mesh_trend_record,
    analyze_mesh_cfl_sensitivity,
    write_mesh_cfl_sensitivity_artifacts,
)
from liquid_gas_transient.hem_pipeline_mesh_cfl_variant import (
    HEMMeshCflPipelineConfig,
    P1_A3_ALLOWED_MESH_CFL,
)


def test_a3_contract_preserves_matrix_and_maturity_boundary() -> None:
    assert P1_A3_SCHEMA_VERSION == "stage7_p1_mesh_cfl_sensitivity_a3_v1"
    assert P1_A3_ALLOWED_MESH_CFL == (
        (16, 0.10),
        (32, 0.10),
        (64, 0.10),
        (32, 0.05),
        (32, 0.20),
    )
    assert [(spec.n_cells, spec.cfl) for spec in P1_A3_CASE_SPECS] == list(
        P1_A3_ALLOWED_MESH_CFL
    )
    assert sum(spec.use_locked_gate6_authority for spec in P1_A3_CASE_SPECS) == 1
    assert P1_A3_OUTPUT_FILES == (
        "mesh_cfl_summary.json",
        "case_metrics.csv",
        "mesh_convergence.csv",
        "cfl_sensitivity.csv",
        "front_history.csv",
        "front_comparison.png",
        "decision_metrics.png",
        "operator_report.md",
        "mesh_cfl_manifest.json",
    )
    assert P1_A3_FORMAL_STATUS["implemented"] is True
    assert P1_A3_FORMAL_STATUS["working_vertical_slice"] is False
    assert P1_A3_FORMAL_STATUS["verified"] is False
    assert P1_A3_FORMAL_STATUS["accepted"] is False
    assert P1_A3_FORMAL_STATUS["mesh_independent_crossing_verified"] is False
    assert P1_A3_FORMAL_STATUS["cfl_independent_crossing_verified"] is False
    assert P1_A3_FORMAL_STATUS["physically_validated"] is False
    assert P1_A3_FORMAL_STATUS["design_use_accepted"] is False
    assert P1_A3_FORMAL_STATUS["production_approved"] is False


def test_a3_variant_config_allows_only_predeclared_mesh_cfl_pairs() -> None:
    for n_cells, cfl in P1_A3_ALLOWED_MESH_CFL:
        config = HEMMeshCflPipelineConfig(n_cells=n_cells, cfl=cfl)
        assert config.n_cells == n_cells
        assert config.cfl == pytest.approx(cfl)
        assert config.length_m == pytest.approx(1.0)
        assert config.diameter_m == pytest.approx(0.10)
        assert config.initial_pressure_pa == pytest.approx(5.0e6)

    with pytest.raises(ValueError, match="outside the predeclared matrix"):
        HEMMeshCflPipelineConfig(n_cells=48, cfl=0.10)
    with pytest.raises(ValueError, match="outside the predeclared matrix"):
        HEMMeshCflPipelineConfig(n_cells=32, cfl=0.15)
    with pytest.raises(ValueError, match="may vary only"):
        HEMMeshCflPipelineConfig(
            n_cells=32,
            cfl=0.10,
            initial_pressure_pa=4.9e6,
        )


def test_a3_mesh_trend_classifier_is_verdict_neutral() -> None:
    monotone = _mesh_trend_record("metric", "1", 1.0, 1.5, 1.75)
    assert monotone["trend"] == "MONOTONIC_CONVERGENT_TREND"
    assert monotone["apparent_order"] == pytest.approx(1.0)

    oscillatory = _mesh_trend_record("metric", "1", 1.0, 2.0, 1.5)
    assert oscillatory["trend"] == "OSCILLATORY_DAMPED_TREND"

    nonconvergent = _mesh_trend_record("metric", "1", 1.0, 1.2, 1.5)
    assert nonconvergent["trend"] == "NONCONVERGENT_AT_TESTED_LEVELS"


def test_a3_cfl_classifier_uses_predeclared_bands() -> None:
    low = _cfl_record("metric", "1", 0.99, 1.0, 1.01)
    assert low["classification"] == "LOW"

    moderate = _cfl_record("metric", "1", 0.95, 1.0, 1.05)
    assert moderate["classification"] == "MODERATE"

    high = _cfl_record("metric", "1", 0.8, 1.0, 1.2)
    assert high["classification"] == "HIGH"


@pytest.fixture(scope="module")
def installed_a3_result():
    pytest.importorskip("CoolProp")
    return analyze_mesh_cfl_sensitivity()


@pytest.mark.coolprop_installed
def test_a3_real_matrix_retains_locked_baseline_and_complete_evidence(
    installed_a3_result,
) -> None:
    result = installed_a3_result

    assert result.sensitivity_ready is True
    assert result.sensitivity_execution_status == "SENSITIVITY_READY"
    assert len(result.case_metrics) == 5
    assert len(result.mesh_convergence) == 8
    assert len(result.cfl_sensitivity) == 8
    assert result.common_horizon_s is not None
    assert result.common_horizon_s > 0.0
    assert all(bool(gate["passed"]) for gate in result.gates)

    by_id = {str(row["case_id"]): row for row in result.case_metrics}
    baseline = by_id["baseline_32_cfl_0p10"]
    assert baseline["source_kind"] == "LOCKED_GATE6_AUTHORITY"
    assert baseline["first_crossing_step"] == 125
    assert baseline["source_first_crossing_sha256"] == (
        "170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361"
    )

    for row in result.case_metrics:
        assert row["execution_available"] is True
        assert row["baseline_outcome"] == "ACCEPTED_FIRST_CROSSING"
        assert row["continuation_outcome"] == "COMPLETED_FIXED_CHECKPOINTS"
        assert row["successful_post_crossing_step_count"] == 64
        assert row["first_crossing_time_s"] is not None
        assert row["furthest_upstream_crossing_distance_from_outlet_m"] is not None
        assert row["common_horizon_sample_post_step"] is not None
        assert row["common_horizon_shortfall_s"] is not None
        assert row["common_horizon_shortfall_s"] >= -1.0e-15
        assert row["phase_bearing_snapshot_count_to_common_horizon"] > 0
        assert len(row["source_first_crossing_sha256"]) == 64
        assert len(row["source_last_valid_state_sha256"]) == 64


@pytest.mark.coolprop_installed
def test_a3_ordering_verdict_is_derived_not_hardcoded(
    installed_a3_result,
) -> None:
    result = installed_a3_result
    decisions = [
        row["pressure_ahead_all_phase_bearing_snapshots"]
        for row in result.case_metrics
    ]
    assert all(value is not None for value in decisions)
    expected = "ROBUST" if all(value is True for value in decisions) else "SENSITIVE"
    assert result.ordering_verdict == expected
    assert result.numerical_verdict in {
        "ROBUST_ORDERING_WITH_BOUNDED_NUMERICAL_SENSITIVITY",
        "ROBUST_ORDERING_BUT_NUMERICALLY_SENSITIVE",
        "SENSITIVE",
    }
    assert all(
        row["trend"] != "UNAVAILABLE" for row in result.mesh_convergence
    )
    assert all(
        row["classification"] != "UNAVAILABLE" for row in result.cfl_sensitivity
    )


@pytest.mark.coolprop_installed
def test_a3_writer_retains_exact_contract(
    installed_a3_result,
    tmp_path: Path,
) -> None:
    result = installed_a3_result
    paths = write_mesh_cfl_sensitivity_artifacts(tmp_path, result)

    assert set(paths) == {
        "summary",
        "case_metrics",
        "mesh_convergence",
        "cfl_sensitivity",
        "front_history",
        "front_comparison",
        "decision_metrics",
        "operator_report",
        "manifest",
    }
    assert {path.name for path in tmp_path.iterdir()} == set(P1_A3_OUTPUT_FILES)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert summary["schema_version"] == P1_A3_SCHEMA_VERSION
    assert summary["case_count"] == 5
    assert summary["sensitivity_ready"] is True
    assert summary["ordering_verdict"] == result.ordering_verdict
    assert summary["numerical_verdict"] == result.numerical_verdict
    assert summary["locked_gate6_contract_changed"] is False
    assert summary["physics_or_production_numerics_changed"] is False
    assert manifest["declared_file_count"] == 9
    assert manifest["declared_file_names"] == list(P1_A3_OUTPUT_FILES)
    assert manifest["sensitivity_sha256"] == result.sensitivity_sha256
    assert paths["front_comparison"].stat().st_size > 0
    assert paths["decision_metrics"].stat().st_size > 0
