from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from liquid_gas_transient.hem_pipeline_post_crossing_analysis import (
    P1_FORMAL_STATUS,
    P1_MODEL_ID,
    P1_OUTPUT_FILES,
    analyze_post_crossing_propagation,
    write_p1_post_crossing_analysis_artifacts,
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
        accepted_state_quality_tolerance=1.0e-10,
        mass_budget_relative_tolerance=1.0e-10,
        mass_budget_absolute_tolerance_kg=1.0e-12,
        momentum_budget_relative_tolerance=1.0e-10,
        momentum_budget_absolute_tolerance_kg_m_s=1.0e-10,
        energy_budget_relative_tolerance=1.0e-10,
        energy_budget_absolute_tolerance_J=1.0e-6,
        vapor_budget_absolute_tolerance_kg=1.0e-12,
    )


def _step(
    post_step: int,
    pressures: tuple[float, ...],
    open_indices: tuple[int, ...],
    *,
    mass_residual: float = 0.0,
) -> SimpleNamespace:
    distances = tuple(0.875 - 0.25 * index for index in range(4))
    furthest = min(open_indices) if open_indices else None
    return SimpleNamespace(
        case_id="synthetic_p1",
        absolute_step=125 + post_step,
        post_crossing_step=post_step,
        time_before_s=float(post_step),
        dt_s=0.1,
        time_after_s=float(post_step) + 0.1,
        raw_state_class="OPEN_TWO_PHASE",
        accepted_state_class="OPEN_TWO_PHASE",
        open_two_phase_cell_count=len(open_indices),
        open_two_phase_cell_indices=open_indices,
        furthest_upstream_two_phase_cell=furthest,
        furthest_upstream_distance_from_outlet_m=(
            None if furthest is None else distances[furthest]
        ),
        liquid_to_two_phase_event_count=0,
        reverse_transition_event_count=0,
        projection_cell_count=0,
        second_projection_cell_count=0,
        maximum_equilibrium_quality=0.02,
        integrated_equilibrium_quality=0.03,
        maximum_void_fraction=0.15,
        pressure_min_pa=min(pressures),
        pressure_max_pa=max(pressures),
        liquid_sound_speed_min_m_s=600.0,
        liquid_sound_speed_max_m_s=700.0,
        two_phase_sound_speed_min_m_s=80.0,
        two_phase_sound_speed_max_m_s=100.0,
        mass_total_kg=6.0,
        momentum_total_kg_m_s=1.0,
        energy_total_J=1.0e6,
        vapor_mass_total_kg=1.0e-4 * post_step,
        boundary_mass_residual_kg=mass_residual,
        boundary_momentum_residual_kg_m_s=0.0,
        boundary_energy_residual_J=0.0,
        phase_vapor_residual_kg=0.0,
        projection_vapor_source_step_kg=0.0,
        boundary_vapor_step_kg=0.0,
        second_projection_noop=True,
        state_sha256=f"state-{post_step}",
    )


def _cells_for_step(
    step: SimpleNamespace,
    pressures: tuple[float, ...],
    open_indices: tuple[int, ...],
) -> list[SimpleNamespace]:
    rows = []
    for index, pressure in enumerate(pressures):
        open_phase = index in open_indices
        rows.append(
            SimpleNamespace(
                case_id="synthetic_p1",
                absolute_step=step.absolute_step,
                post_crossing_step=step.post_crossing_step,
                time_s=step.time_after_s,
                cell_index=index,
                cell_center_m=(index + 0.5) * 0.25,
                distance_from_outlet_m=0.875 - 0.25 * index,
                previous_region=(
                    "OPEN_TWO_PHASE" if open_phase else "LIQUID_CANDIDATE"
                ),
                raw_region=(
                    "OPEN_TWO_PHASE" if open_phase else "LIQUID_CANDIDATE"
                ),
                post_region=(
                    "OPEN_TWO_PHASE" if open_phase else "LIQUID_CANDIDATE"
                ),
                transition_event="NO_TRANSITION",
                rho_kg_m3=800.0,
                momentum_kg_m2_s=0.0,
                rhoE_J_m3=1.0e8,
                rho_q_kg_m3=0.8 if open_phase else 0.0,
                velocity_m_s=0.0,
                internal_energy_j_kg=1.0e5,
                pressure_pa=pressure,
                temperature_K=280.0,
                q_transport_raw=0.001 if open_phase else 0.0,
                q_equilibrium=0.001 if open_phase else 0.0,
                q_post=0.001 if open_phase else 0.0,
                void_fraction=0.01 if open_phase else 0.0,
                projection_applied=False,
                delta_rho_q=0.0,
                sound_speed_status="SUCCESS",
                sound_speed_failure_category="",
                sound_speed_failure_reason="",
                sound_speed_m_s=90.0 if open_phase else 650.0,
                sound_speed_squared_m2_s2=8100.0 if open_phase else 422500.0,
                dp_drho_at_e=1.0,
                dp_de_at_rho=1.0,
                density_term_m2_s2=1.0,
                energy_term_m2_s2=1.0,
                density_step_kg_m3=1.0,
                energy_step_j_kg=1.0,
                density_step_halvings=0,
                energy_step_halvings=0,
            )
        )
    return rows


def _source(
    *,
    second_open_indices: tuple[int, ...] = (1, 2),
    second_mass_residual: float = 0.0,
) -> SimpleNamespace:
    pressures_1 = (5.0e6, 4.999e6, 4.8e6, 4.6e6)
    pressures_2 = (4.999e6, 4.8e6, 4.6e6, 4.4e6)
    step_1 = _step(1, pressures_1, (2,))
    step_2 = _step(
        2,
        pressures_2,
        second_open_indices,
        mass_residual=second_mass_residual,
    )
    cells = _cells_for_step(step_1, pressures_1, (2,))
    cells.extend(_cells_for_step(step_2, pressures_2, second_open_indices))
    baseline = SimpleNamespace(
        case=SimpleNamespace(case_id="synthetic_p1"),
        crossing_step=125,
        crossing_time_s=1.0,
        crossing_cell_indices=(2,),
        crossing_distances_from_outlet_m=(0.375,),
        pressure_drop_arrival_times_s=(0.9, 0.7, 0.5, 0.3),
        final_state_sha256="baseline-state",
        run_signature_sha256="baseline-run",
    )
    source = SimpleNamespace(
        config=SimpleNamespace(
            pipeline=_pipeline(),
            maximum_post_crossing_steps=2,
        ),
        baseline=baseline,
        outcome="COMPLETED_FIXED_CHECKPOINTS",
        failure_category="",
        failure_reason="",
        last_valid_state_sha256="state-2",
        steps=(step_1, step_2),
        cells=tuple(cells),
    )
    source.summary = lambda: {
        "schema_version": "synthetic_gate6",
        "baseline_reproduced_exactly": True,
        "outcome": source.outcome,
        "step_count": len(source.steps),
    }
    return source


def test_p1_contract_does_not_claim_maturity() -> None:
    assert P1_MODEL_ID == "HEM_EQUILIBRIUM"
    assert P1_OUTPUT_FILES == (
        "analysis_summary.json",
        "front_history.csv",
        "pressure_arrival.csv",
        "analysis_manifest.json",
    )
    assert P1_FORMAL_STATUS["implemented"] is True
    assert P1_FORMAL_STATUS["working_vertical_slice"] is False
    assert P1_FORMAL_STATUS["verified"] is False
    assert P1_FORMAL_STATUS["accepted"] is False
    assert P1_FORMAL_STATUS["physically_validated"] is False
    assert P1_FORMAL_STATUS["design_use_accepted"] is False
    assert P1_FORMAL_STATUS["production_approved"] is False


def test_p1_tracks_pressure_and_phase_fronts() -> None:
    source = _source()
    analysis = analyze_post_crossing_propagation(source)

    assert analysis.analysis_ready is True
    assert len(analysis.front_history) == 2
    first, second = analysis.front_history
    assert first.pressure_front_cell_index == 1
    assert first.pressure_front_distance_from_outlet_m == 0.625
    assert first.phase_front_cell_index == 2
    assert first.phase_front_distance_from_outlet_m == 0.375
    assert first.pressure_phase_front_separation_m == 0.25
    assert first.pressure_front_ahead_of_phase_front is True
    assert first.phase_region_occupied_length_m == 0.25
    assert first.phase_region_span_m == 0.25
    assert first.phase_region_contiguous is True

    assert second.pressure_front_cell_index == 0
    assert second.pressure_front_distance_from_outlet_m == 0.875
    assert second.phase_front_cell_index == 1
    assert second.phase_front_distance_from_outlet_m == 0.625
    assert second.phase_region_occupied_length_m == 0.5
    assert second.phase_region_span_m == 0.5
    assert second.phase_region_contiguous is True
    assert second.pressure_front_sound_speed_m_s == 650.0
    assert second.phase_front_sound_speed_m_s == 90.0


def test_p1_reports_noncontiguous_phase_region_without_hiding_it() -> None:
    analysis = analyze_post_crossing_propagation(
        _source(second_open_indices=(1, 3))
    )

    second = analysis.front_history[-1]
    assert second.phase_region_occupied_length_m == 0.5
    assert second.phase_region_span_m == 0.75
    assert second.phase_region_contiguous is False
    assert (
        "NONCONTIGUOUS_TWO_PHASE_REGION:post_crossing_step=2"
        in analysis.warnings
    )
    assert analysis.analysis_ready is True


def test_p1_fails_closed_when_existing_budget_gate_is_exceeded() -> None:
    analysis = analyze_post_crossing_propagation(
        _source(second_mass_residual=1.0e-2)
    )

    assert analysis.analysis_ready is False
    assert analysis.analysis_execution_status == "FAIL_CLOSED"
    gates = {gate.gate: gate.passed for gate in analysis.gates}
    assert gates["MASS_MOMENTUM_ENERGY_BUDGETS"] is False
    assert "FAILED_GATE:MASS_MOMENTUM_ENERGY_BUDGETS" in analysis.warnings


def test_p1_analysis_digest_is_deterministic() -> None:
    source = _source()
    first = analyze_post_crossing_propagation(source)
    second = analyze_post_crossing_propagation(source)

    assert first.analysis_sha256 == second.analysis_sha256
    assert first.source_summary_sha256 == second.source_summary_sha256
    assert first.front_history == second.front_history
    assert first.pressure_arrivals == second.pressure_arrivals


def test_p1_writer_emits_exactly_four_files(tmp_path: Path) -> None:
    analysis = analyze_post_crossing_propagation(_source())
    paths = write_p1_post_crossing_analysis_artifacts(tmp_path, analysis)

    assert set(paths) == {
        "analysis_summary",
        "front_history",
        "pressure_arrival",
        "analysis_manifest",
    }
    assert {path.name for path in tmp_path.iterdir()} == set(P1_OUTPUT_FILES)
    summary = json.loads(
        paths["analysis_summary"].read_text(encoding="utf-8")
    )
    manifest = json.loads(
        paths["analysis_manifest"].read_text(encoding="utf-8")
    )
    assert summary["analysis_ready"] is True
    assert summary["physics_or_numerics_changed"] is False
    assert summary["model_comparison_interface"]["future_model_id"] == (
        "HNE_RELAXATION"
    )
    assert manifest["declared_file_count"] == 4
    assert manifest["declared_file_names"] == list(P1_OUTPUT_FILES)
    assert set(manifest["payload_files"]) == {
        "analysis_summary.json",
        "front_history.csv",
        "pressure_arrival.csv",
    }


@pytest.fixture(scope="module")
def installed_gate6_result():
    pytest.importorskip("CoolProp")
    return run_post_crossing_propagation_review()


@pytest.mark.coolprop_installed
def test_p1_real_gate6_result_populates_bounded_analysis(
    installed_gate6_result,
    tmp_path: Path,
) -> None:
    analysis = analyze_post_crossing_propagation(installed_gate6_result)

    assert analysis.source_step_count == 64
    assert len(analysis.front_history) == 64
    assert len(analysis.pressure_arrivals) == 32
    assert analysis.analysis_ready is True
    final = analysis.front_history[-1]
    source_final = installed_gate6_result.steps[-1]
    assert final.phase_front_cell_index == (
        source_final.furthest_upstream_two_phase_cell
    )
    assert final.phase_front_distance_from_outlet_m == (
        source_final.furthest_upstream_distance_from_outlet_m
    )
    assert final.state_sha256 == source_final.state_sha256

    write_p1_post_crossing_analysis_artifacts(tmp_path, analysis)
    assert {path.name for path in tmp_path.iterdir()} == set(P1_OUTPUT_FILES)
