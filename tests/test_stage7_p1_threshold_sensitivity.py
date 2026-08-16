from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquid_gas_transient.hem_pipeline_post_crossing_analysis import (
    analyze_post_crossing_propagation,
)
from liquid_gas_transient.hem_pipeline_post_crossing_propagation import (
    run_post_crossing_propagation_review,
)
from liquid_gas_transient.hem_pipeline_pressure_phase_relationship import (
    analyze_pressure_phase_relationship,
)
from liquid_gas_transient.hem_pipeline_threshold_sensitivity import (
    P1_A2_FORMAL_STATUS,
    P1_A2_OUTPUT_FILES,
    P1_A2_SCHEMA_VERSION,
    P1_A2_THRESHOLD_MULTIPLIERS,
    _numeric_summary,
    analyze_threshold_sensitivity,
    write_threshold_sensitivity_artifacts,
)


def test_a2_contract_preserves_exact_scope_and_maturity_boundary() -> None:
    assert P1_A2_SCHEMA_VERSION == "stage7_p1_threshold_sensitivity_a2_v1"
    assert P1_A2_THRESHOLD_MULTIPLIERS == (0.5, 1.0, 2.0)
    assert P1_A2_OUTPUT_FILES == (
        "threshold_summary.json",
        "threshold_comparison.csv",
        "threshold_cell_arrivals.csv",
        "threshold_front_history.csv",
        "threshold_pressure_front_speed.csv",
        "threshold_front_position.png",
        "threshold_phase_lag.png",
        "operator_report.md",
        "threshold_manifest.json",
    )
    assert P1_A2_FORMAL_STATUS["implemented"] is True
    assert P1_A2_FORMAL_STATUS["working_vertical_slice"] is False
    assert P1_A2_FORMAL_STATUS["verified"] is False
    assert P1_A2_FORMAL_STATUS["accepted"] is False
    assert P1_A2_FORMAL_STATUS["physically_validated"] is False
    assert P1_A2_FORMAL_STATUS["design_use_accepted"] is False
    assert P1_A2_FORMAL_STATUS["production_approved"] is False


def test_a2_numeric_summary_is_explicit_and_finite() -> None:
    summary = _numeric_summary((1.0, 2.0, 4.0))
    assert summary["minimum"] == pytest.approx(1.0)
    assert summary["median"] == pytest.approx(2.0)
    assert summary["mean"] == pytest.approx(7.0 / 3.0)
    assert summary["maximum"] == pytest.approx(4.0)
    assert _numeric_summary(()) == {
        "minimum": None,
        "median": None,
        "mean": None,
        "maximum": None,
    }


@pytest.fixture(scope="module")
def installed_a2_bundle():
    pytest.importorskip("CoolProp")
    source = run_post_crossing_propagation_review()
    a0_analysis = analyze_post_crossing_propagation(source)
    a1_relationship = analyze_pressure_phase_relationship(source, a0_analysis)
    result = analyze_threshold_sensitivity(source, a0_analysis, a1_relationship)
    return source, a0_analysis, a1_relationship, result


@pytest.mark.coolprop_installed
def test_a2_real_gate6_source_produces_an_unbiased_sensitivity_verdict(
    installed_a2_bundle,
) -> None:
    source, _, a1_relationship, result = installed_a2_bundle

    assert result.sensitivity_ready is True
    assert result.sensitivity_execution_status == "SENSITIVITY_READY"
    assert result.sensitivity_verdict in {"ROBUST", "SENSITIVE"}
    expected_verdict = (
        "ROBUST" if all(result.decision_checks.values()) else "SENSITIVE"
    )
    assert result.sensitivity_verdict == expected_verdict
    assert result.threshold_multipliers == (0.5, 1.0, 2.0)
    assert len(result.cell_arrivals) == source.config.pipeline.n_cells * 3
    assert len(result.threshold_comparisons) == 3
    assert len(result.front_history) % 3 == 0
    assert result.pressure_front_speeds
    assert all(gate.passed for gate in result.gates)

    phase_cell_count = a1_relationship.summary()["phase_onset_cell_count"]
    assert phase_cell_count == 7
    for row in result.threshold_comparisons:
        assert 0 < row.available_pressure_arrival_cell_count <= 32
        assert 0 <= row.comparable_phase_cell_count <= phase_cell_count
        assert row.phase_bearing_snapshot_count > 0
        assert 0 <= row.pressure_strictly_ahead_snapshot_count <= (
            row.phase_bearing_snapshot_count
        )
        assert row.final_pressure_front_distance_from_outlet_m is not None
        assert 0.0 <= row.final_pressure_front_distance_from_outlet_m <= 1.0
        assert row.final_phase_front_distance_from_outlet_m is not None
        assert 0.0 <= row.final_phase_front_distance_from_outlet_m <= 1.0
        assert row.pressure_front_speed_segment_count > 0
        assert row.median_discrete_pressure_front_speed_m_s is not None
        assert row.median_discrete_pressure_front_speed_m_s > 0.0
        if row.minimum_pressure_to_phase_lag_s is not None:
            assert row.maximum_pressure_to_phase_lag_s is not None
            assert row.minimum_pressure_to_phase_lag_s <= (
                row.maximum_pressure_to_phase_lag_s
            )


@pytest.mark.coolprop_installed
def test_a2_cell_arrivals_are_monotone_and_reference_locked(
    installed_a2_bundle,
) -> None:
    source, _, _, result = installed_a2_bundle
    for cell in range(source.config.pipeline.n_cells):
        rows = {
            row.threshold_multiplier: row
            for row in result.cell_arrivals
            if row.cell_index == cell
        }
        times = [
            rows[multiplier].pressure_arrival_time_s
            for multiplier in P1_A2_THRESHOLD_MULTIPLIERS
        ]
        available = [value for value in times if value is not None]
        assert available == sorted(available)
        assert rows[1.0].reference_threshold is True
        if rows[1.0].pressure_arrival_time_s is not None:
            assert rows[1.0].arrival_shift_from_reference_s == pytest.approx(0.0)

    phase_rows = [
        row
        for row in result.cell_arrivals
        if row.first_phase_onset_time_s is not None
    ]
    assert len(phase_rows) == 21
    for row in phase_rows:
        if row.pressure_to_phase_lag_s is None:
            assert row.pressure_arrived_before_phase is None
        else:
            assert row.pressure_arrived_before_phase == (
                row.pressure_to_phase_lag_s > 1.0e-15
            )


@pytest.mark.coolprop_installed
def test_a2_digest_and_writer_are_deterministic(
    installed_a2_bundle,
    tmp_path: Path,
) -> None:
    source, a0_analysis, a1_relationship, first = installed_a2_bundle
    second = analyze_threshold_sensitivity(source, a0_analysis, a1_relationship)

    assert first.sensitivity_sha256 == second.sensitivity_sha256
    assert first.cell_arrivals == second.cell_arrivals
    assert first.front_history == second.front_history
    assert first.pressure_front_speeds == second.pressure_front_speeds
    assert first.threshold_comparisons == second.threshold_comparisons

    paths = write_threshold_sensitivity_artifacts(tmp_path, first)
    assert set(paths) == {
        "threshold_summary",
        "threshold_comparison",
        "threshold_cell_arrivals",
        "threshold_front_history",
        "threshold_pressure_front_speed",
        "threshold_front_position",
        "threshold_phase_lag",
        "operator_report",
        "threshold_manifest",
    }
    assert {path.name for path in tmp_path.iterdir()} == set(P1_A2_OUTPUT_FILES)

    summary = json.loads(paths["threshold_summary"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["threshold_manifest"].read_text(encoding="utf-8"))
    assert summary["schema_version"] == P1_A2_SCHEMA_VERSION
    assert summary["threshold_multipliers"] == [0.5, 1.0, 2.0]
    assert summary["sensitivity_ready"] is True
    assert summary["sensitivity_verdict"] == first.sensitivity_verdict
    assert summary["decision_checks"] == first.decision_checks
    assert summary["physics_or_numerics_changed"] is False
    assert manifest["declared_file_count"] == 9
    assert manifest["declared_file_names"] == list(P1_A2_OUTPUT_FILES)
    assert manifest["sensitivity_sha256"] == first.sensitivity_sha256
    assert paths["threshold_front_position"].stat().st_size > 0
    assert paths["threshold_phase_lag"].stat().st_size > 0
