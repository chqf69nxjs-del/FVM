from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_pipeline_pressure_phase_relationship import (
    P1_A1_FORMAL_STATUS,
    P1_A1_MIN_PERSISTENT_SAMPLES,
    P1_A1_OUTPUT_FILES,
    P1_A1_THRESHOLD_MULTIPLIERS,
    P1PressurePhaseRelationshipError,
    analyze_pressure_phase_relationship,
    write_pressure_phase_relationship_artifacts,
)

from liquid_gas_transient.hem_pipeline_post_crossing_propagation import (
    run_post_crossing_propagation_review,
)


def _pipeline() -> SimpleNamespace:
    return SimpleNamespace(
        length_m=1.0,
        n_cells=4,
        initial_pressure_pa=5.0e6,
        pressure_drop_evidence_relative=1.0e-6,
    )


def _baseline_cell(
    step: int,
    time_s: float,
    cell: int,
    *,
    region: str,
    transition: str = "NO_TRANSITION",
    sound: float = 650.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        step_index=step,
        time_s=time_s,
        cell_index=cell,
        post_region=region,
        transition_event=transition,
        sound_speed_post_m_s=sound,
    )


def _post_cell(
    post_step: int,
    absolute_step: int,
    time_s: float,
    cell: int,
    pressure: float,
    *,
    region: str,
    transition: str = "NO_TRANSITION",
    sound: float = 650.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        post_crossing_step=post_step,
        absolute_step=absolute_step,
        time_s=time_s,
        cell_index=cell,
        pressure_pa=pressure,
        post_region=region,
        transition_event=transition,
        sound_speed_m_s=sound,
    )


def _source(*, nonmonotone_time: bool = False) -> SimpleNamespace:
    # Index 3 is nearest the outlet; index 0 is furthest upstream.
    times = np.asarray([0.0, 0.1, 0.2, 0.3])
    pressure = np.asarray(
        [
            [5.0e6, 5.0e6, 5.0e6, 5.0e6],
            [5.0e6, 5.0e6, 5.0e6, 4.999e6],
            [5.0e6, 5.0e6, 4.999e6, 4.99e6],
            [5.0e6, 4.999e6, 4.99e6, 4.98e6],
        ],
        dtype=float,
    )
    baseline_cells = []
    for step in range(1, 4):
        for cell in range(4):
            crossing = step == 3 and cell == 2
            baseline_cells.append(
                _baseline_cell(
                    step,
                    float(times[step]),
                    cell,
                    region="OPEN_TWO_PHASE" if crossing else "LIQUID_CANDIDATE",
                    transition="LIQUID_TO_TWO_PHASE" if crossing else "NO_TRANSITION",
                    sound=90.0 if crossing else 650.0,
                )
            )

    post_time_1 = 0.25 if nonmonotone_time else 0.4
    post_time_2 = 0.5
    post_pressures = (
        (4.999e6, 4.98e6, 4.97e6, 4.96e6),
        (4.98e6, 4.97e6, 4.96e6, 4.95e6),
    )
    # Cell 3 opens at +1 and closes at +2: explicit local toggle.
    post_regions = (
        ("LIQUID_CANDIDATE", "LIQUID_CANDIDATE", "OPEN_TWO_PHASE", "OPEN_TWO_PHASE"),
        ("LIQUID_CANDIDATE", "OPEN_TWO_PHASE", "OPEN_TWO_PHASE", "LIQUID_CANDIDATE"),
    )
    post_cells = []
    for post_step, (time_s, pressures, regions) in enumerate(
        zip((post_time_1, post_time_2), post_pressures, post_regions), start=1
    ):
        for cell, (p, region) in enumerate(zip(pressures, regions)):
            transition = "NO_TRANSITION"
            if post_step == 1 and cell == 3:
                transition = "LIQUID_TO_TWO_PHASE"
            if post_step == 2 and cell == 1:
                transition = "LIQUID_TO_TWO_PHASE"
            if post_step == 2 and cell == 3:
                transition = "REVERSE_TRANSITION"
            post_cells.append(
                _post_cell(
                    post_step,
                    3 + post_step,
                    time_s,
                    cell,
                    p,
                    region=region,
                    transition=transition,
                    sound=90.0 if region == "OPEN_TWO_PHASE" else 650.0,
                )
            )

    baseline = SimpleNamespace(
        case=SimpleNamespace(case_id="synthetic_p1_a1"),
        step_count=3,
        crossing_step=3,
        crossing_time_s=0.3,
        crossing_cell_indices=(2,),
        pressure_drop_arrival_times_s=(None, 0.3, 0.2, 0.1),
        time_history_s=times,
        pressure_history_pa=pressure,
        cells=tuple(baseline_cells),
    )
    steps = (
        SimpleNamespace(post_crossing_step=1, absolute_step=4, time_after_s=post_time_1),
        SimpleNamespace(post_crossing_step=2, absolute_step=5, time_after_s=post_time_2),
    )
    p1_analysis = SimpleNamespace(
        analysis_ready=True,
        analysis_sha256="synthetic-a0-analysis",
    )
    source = SimpleNamespace(
        config=SimpleNamespace(pipeline=_pipeline(), maximum_post_crossing_steps=2),
        baseline=baseline,
        outcome="COMPLETED_FIXED_CHECKPOINTS",
        steps=steps,
        cells=tuple(post_cells),
        last_valid_state_sha256="synthetic-final-state",
        p1_analysis=p1_analysis,
    )
    return source


def test_a1_contract_preserves_maturity_boundary() -> None:
    assert P1_A1_THRESHOLD_MULTIPLIERS == (0.1, 1.0, 10.0)
    assert P1_A1_MIN_PERSISTENT_SAMPLES == 2
    assert P1_A1_OUTPUT_FILES == (
        "relationship_summary.json",
        "cell_lag.csv",
        "front_speed.csv",
        "threshold_sensitivity.csv",
        "front_relationship.png",
        "cell_phase_lag.png",
        "operator_report.md",
        "relationship_manifest.json",
    )
    assert P1_A1_FORMAL_STATUS["implemented"] is True
    assert P1_A1_FORMAL_STATUS["working_vertical_slice"] is False
    assert P1_A1_FORMAL_STATUS["verified"] is False
    assert P1_A1_FORMAL_STATUS["accepted"] is False
    assert P1_A1_FORMAL_STATUS["physically_validated"] is False


def test_a1_computes_first_and_persistent_cell_lags() -> None:
    source = _source()
    result = analyze_pressure_phase_relationship(source, source.p1_analysis)

    assert result.relationship_ready is True
    assert len(result.cell_lags) == 4
    cell_2 = result.cell_lags[2]
    assert cell_2.pressure_arrival_time_s == pytest.approx(0.2)
    assert cell_2.first_phase_onset_time_s == pytest.approx(0.3)
    assert cell_2.persistent_phase_onset_time_s == pytest.approx(0.3)
    assert cell_2.first_phase_lag_s == pytest.approx(0.1)
    assert cell_2.persistent_phase_lag_s == pytest.approx(0.1)
    assert cell_2.first_onset_persistent_through_horizon is True
    assert cell_2.persistent_phase_sample_count == 3

    cell_1 = result.cell_lags[1]
    assert cell_1.pressure_arrival_time_s == pytest.approx(0.3)
    assert cell_1.first_phase_onset_time_s == pytest.approx(0.5)
    assert cell_1.persistent_phase_onset_time_s is None
    assert cell_1.persistent_phase_sample_count == 0
    assert cell_1.first_phase_lag_s == pytest.approx(0.2)

    cell_3 = result.cell_lags[3]
    assert cell_3.first_phase_onset_time_s == pytest.approx(0.4)
    assert cell_3.persistent_phase_onset_time_s is None
    assert cell_3.phase_toggled is True
    assert cell_3.liquid_to_two_phase_transition_count == 1
    assert cell_3.two_phase_to_liquid_transition_count == 1
    assert "PHASE_TOGGLE_OBSERVED:cell=3" in result.warnings


def test_a1_extends_reference_pressure_arrival_into_post_crossing_history() -> None:
    source = _source()
    result = analyze_pressure_phase_relationship(source, source.p1_analysis)

    cell_0 = result.cell_lags[0]
    assert cell_0.pressure_arrival_time_s == pytest.approx(0.4)
    assert cell_0.pressure_arrival_source == "POST_CROSSING"
    assert cell_0.first_phase_onset_time_s is None


def test_a1_threshold_sensitivity_is_monotone_and_reference_locked() -> None:
    source = _source()
    result = analyze_pressure_phase_relationship(source, source.p1_analysis)

    by_cell = {}
    for row in result.threshold_sensitivity:
        by_cell.setdefault(row.cell_index, {})[row.threshold_multiplier] = row
    for rows in by_cell.values():
        times = [rows[m].arrival_time_s for m in P1_A1_THRESHOLD_MULTIPLIERS]
        available = [value for value in times if value is not None]
        assert available == sorted(available)
        assert rows[1.0].reference_threshold is True
        assert rows[1.0].arrival_shift_from_reference_s == pytest.approx(0.0)

    gates = {gate.gate: gate.passed for gate in result.gates}
    assert gates["REFERENCE_PRESSURE_ARRIVALS_MATCH_A0_SOURCE"] is True
    assert gates["THRESHOLD_ARRIVAL_ORDERING_MONOTONE"] is True


def test_a1_records_both_pressure_and_phase_discrete_speeds() -> None:
    source = _source()
    result = analyze_pressure_phase_relationship(source, source.p1_analysis)

    kinds = {row.front_kind for row in result.front_speeds}
    assert kinds == {"PRESSURE_FRONT", "PHASE_FRONT"}
    pressure_rows = [row for row in result.front_speeds if row.front_kind == "PRESSURE_FRONT"]
    phase_rows = [row for row in result.front_speeds if row.front_kind == "PHASE_FRONT"]
    assert pressure_rows
    assert phase_rows
    assert all(row.discrete_segment_speed_m_s > 0.0 for row in result.front_speeds)
    assert all(row.speed_to_local_sound_ratio > 0.0 for row in result.front_speeds)
    assert "DISCRETE_FRONT_SPEED_NOT_PHYSICALLY_VALIDATED" in result.warnings


def test_a1_digest_and_writer_are_deterministic(tmp_path: Path) -> None:
    source = _source()
    first = analyze_pressure_phase_relationship(source, source.p1_analysis)
    second = analyze_pressure_phase_relationship(source, source.p1_analysis)
    assert first.relationship_sha256 == second.relationship_sha256
    assert first.cell_lags == second.cell_lags
    assert first.front_speeds == second.front_speeds

    paths = write_pressure_phase_relationship_artifacts(tmp_path, first)
    assert set(paths) == {
        "relationship_summary",
        "cell_lag",
        "front_speed",
        "threshold_sensitivity",
        "front_relationship",
        "cell_phase_lag",
        "operator_report",
        "relationship_manifest",
    }
    assert {path.name for path in tmp_path.iterdir()} == set(P1_A1_OUTPUT_FILES)
    summary = json.loads(paths["relationship_summary"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["relationship_manifest"].read_text(encoding="utf-8"))
    assert summary["relationship_ready"] is True
    assert summary["physics_or_numerics_changed"] is False
    assert manifest["declared_file_count"] == 8
    assert manifest["declared_file_names"] == list(P1_A1_OUTPUT_FILES)
    assert paths["front_relationship"].stat().st_size > 0
    assert paths["cell_phase_lag"].stat().st_size > 0


def test_a1_fails_closed_when_a0_is_not_analysis_ready() -> None:
    source = _source()
    not_ready = SimpleNamespace(
        analysis_ready=False,
        analysis_sha256="synthetic-a0-not-ready",
    )

    result = analyze_pressure_phase_relationship(source, not_ready)

    assert result.relationship_ready is False
    assert result.relationship_execution_status == "FAIL_CLOSED"
    gates = {gate.gate: gate.passed for gate in result.gates}
    assert gates["SOURCE_A0_ANALYSIS_READY"] is False
    assert "FAILED_GATE:SOURCE_A0_ANALYSIS_READY" in result.warnings


def test_a1_fails_closed_on_nonmonotone_combined_time() -> None:
    source = _source(nonmonotone_time=True)
    with pytest.raises(P1PressurePhaseRelationshipError, match="strictly increasing"):
        analyze_pressure_phase_relationship(source, source.p1_analysis)


@pytest.fixture(scope="module")
def installed_gate6_source():
    pytest.importorskip("CoolProp")
    return run_post_crossing_propagation_review()


@pytest.mark.coolprop_installed
def test_a1_real_gate6_source_produces_relationship_bundle(
    installed_gate6_source,
    tmp_path: Path,
) -> None:
    result = analyze_pressure_phase_relationship(installed_gate6_source)

    assert result.relationship_ready is True
    assert len(result.cell_lags) == 32
    assert len(result.threshold_sensitivity) == 96
    assert {row.front_kind for row in result.front_speeds} == {
        "PRESSURE_FRONT",
        "PHASE_FRONT",
    }
    crossing_cell = installed_gate6_source.baseline.crossing_cell_indices[0]
    assert result.cell_lags[crossing_cell].first_phase_onset_source == "CROSSING"
    assert result.cell_lags[30].phase_toggled is True
    assert result.cell_lags[30].liquid_to_two_phase_transition_count == 25
    assert result.cell_lags[30].two_phase_to_liquid_transition_count == 24
    assert all(gate.passed for gate in result.gates)

    paths = write_pressure_phase_relationship_artifacts(tmp_path, result)
    assert {path.name for path in tmp_path.iterdir()} == set(P1_A1_OUTPUT_FILES)
    assert paths["front_relationship"].stat().st_size > 0
    assert paths["cell_phase_lag"].stat().st_size > 0
