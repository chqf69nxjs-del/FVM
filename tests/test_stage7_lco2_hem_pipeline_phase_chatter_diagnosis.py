from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.hem_pipeline_phase_chatter_diagnosis import (
    APPROVAL_BOUNDARY,
    CHATTER_CELL,
    CORRELATION_FRACTION,
    EXPECTED_CELL30_TOGGLE_COUNT,
    EXPECTED_GATE6_FINAL_STATE_SHA256,
    EXPECTED_POST_CROSSING_STEPS,
    FIXED_INTERFACE_SPECS,
    FOCUS_CELLS,
    HEMPhaseChatterDiagnosisConfig,
    run_phase_chatter_diagnosis,
    write_phase_chatter_diagnosis_artifacts,
)


def test_gate7_contract_is_locked_before_results() -> None:
    config = HEMPhaseChatterDiagnosisConfig()

    assert FOCUS_CELLS == (29, 30, 31)
    assert CHATTER_CELL == 30
    assert FIXED_INTERFACE_SPECS == (
        ("cell_29_30", 29, 30),
        ("cell_30_31", 30, 31),
        ("right_boundary", 31, None),
    )
    assert EXPECTED_POST_CROSSING_STEPS == 64
    assert EXPECTED_CELL30_TOGGLE_COUNT == 49
    assert CORRELATION_FRACTION == 0.90
    assert config.focus_cells == FOCUS_CELLS
    assert config.chatter_cell == CHATTER_CELL
    assert config.propagation.maximum_post_crossing_steps == 64
    assert all(value is False for value in APPROVAL_BOUNDARY.values())


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("focus_cells", (28, 29, 30)),
        ("chatter_cell", 29),
        ("correlation_fraction", 0.80),
    ],
)
def test_gate7_rejects_result_dependent_contract_changes(
    keyword: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        HEMPhaseChatterDiagnosisConfig(**{keyword: value})


def test_gate7_rejects_gate6_configuration_changes() -> None:
    base = HEMPhaseChatterDiagnosisConfig()
    with pytest.raises(ValueError):
        changed_propagation = replace(
            base.propagation,
            continuation_offsets=(1, 4, 16, 32),
        )
        HEMPhaseChatterDiagnosisConfig(
            propagation=changed_propagation,
        )


def test_gate7_module_is_verification_orchestration_only() -> None:
    import liquid_gas_transient.hem_pipeline_phase_chatter_diagnosis as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "class VerificationHEMLiquidOpenTwoPhaseEOS" not in source
    assert "class HEMEquilibriumQualityProjection" not in source
    assert "chatter suppression / hysteresis" not in source.lower()
    assert "production_default_changed" in source


@pytest.fixture(scope="module")
def installed_gate7_result():
    pytest.importorskip("CoolProp")
    return run_phase_chatter_diagnosis()


@pytest.mark.coolprop_installed
def test_gate7_reproduces_gate6_identity_and_fixed_chatter(
    installed_gate7_result,
) -> None:
    result = installed_gate7_result
    summary = result.summary()

    assert summary["gate6_final_state_reproduced_exactly"] is True
    assert summary["final_state_sha256"] == EXPECTED_GATE6_FINAL_STATE_SHA256
    assert summary["fixed_post_crossing_steps"] == 64
    assert summary["cell30_toggle_count"] == 49
    assert result.cell_toggle_counts[29] == 0
    assert result.cell_toggle_counts[30] == 49
    assert result.cell_toggle_counts[31] == 0
    assert len(result.focused_cells) == 64 * 3 * 3
    assert len(result.interface_fluxes) == 64 * 3
    assert len(result.transition_events) == 49
    assert "STABLE_FRONT_SEPARATED_FROM_CHATTER" in result.classifications
    assert "CHATTER_REVIEW_INCONCLUSIVE" in result.classifications
    assert all(summary[key] is False for key in APPROVAL_BOUNDARY)


@pytest.mark.coolprop_installed
def test_gate7_focused_cell_evidence_is_complete(
    installed_gate7_result,
) -> None:
    result = installed_gate7_result
    stages = {
        "pre_step_accepted",
        "raw_post_fvm",
        "post_projection_accepted",
    }

    for post_step in range(1, 65):
        rows = [
            row
            for row in result.focused_cells
            if row.post_crossing_step == post_step
        ]
        assert len(rows) == 9
        assert {row.cell_index for row in rows} == {29, 30, 31}
        assert {row.state_stage for row in rows} == stages

    for row in result.focused_cells:
        assert np.isfinite(row.rho_kg_m3)
        assert row.rho_kg_m3 > 0.0
        assert np.isfinite(row.internal_energy_j_kg)
        assert np.isfinite(row.pressure_pa)
        assert row.pressure_pa > 0.0
        assert np.isfinite(row.temperature_K)
        assert row.temperature_K > 0.0
        assert np.isfinite(row.q_transport)
        assert np.isfinite(row.q_equilibrium)
        assert np.isfinite(row.q_after_projection)
        assert 0.0 <= row.q_equilibrium <= 1.0
        assert 0.0 <= row.q_after_projection <= 1.0
        assert np.isfinite(row.saturated_liquid_rho_kg_m3)
        assert row.saturated_liquid_rho_kg_m3 > 0.0
        assert np.isfinite(row.saturated_liquid_e_j_kg)
        assert np.isfinite(row.delta_e_from_saturated_liquid_j_kg)
        assert np.isfinite(row.delta_v_from_saturated_liquid_m3_kg)

        if row.state_stage == "post_projection_accepted":
            assert row.sound_speed_status == "SUCCESS"
            assert row.sound_speed_m_s is not None
            assert row.sound_speed_m_s > 0.0


@pytest.mark.coolprop_installed
def test_gate7_interface_and_event_evidence_is_fixed(
    installed_gate7_result,
) -> None:
    result = installed_gate7_result

    for post_step in range(1, 65):
        rows = [
            row
            for row in result.interface_fluxes
            if row.post_crossing_step == post_step
        ]
        assert len(rows) == 3
        assert {row.interface_label for row in rows} == {
            "cell_29_30",
            "cell_30_31",
            "right_boundary",
        }
        for row in rows:
            assert row.state_stage == "pre_step_accepted_flux_evaluation"
            assert np.isfinite(row.mass_flux)
            assert np.isfinite(row.momentum_flux)
            assert np.isfinite(row.energy_flux)
            assert np.isfinite(row.vapor_flux)
            assert row.left_wave_speed_m_s > 0.0
            assert row.right_wave_speed_m_s > 0.0
        boundary = next(
            row for row in rows if row.interface_label == "right_boundary"
        )
        assert boundary.boundary_pressure_requested_pa is not None
        assert boundary.boundary_temperature_requested_K is not None
        assert boundary.boundary_rho_kg_m3 is not None
        assert boundary.boundary_e_j_kg is not None

    event_steps = [row.post_crossing_step for row in result.transition_events]
    assert event_steps == sorted(event_steps)
    assert len(set(event_steps)) == 49
    assert min(event_steps) == 6
    assert max(event_steps) == 64
    for row in result.transition_events:
        assert row.previous_region != row.event_region
        assert row.previous_region in {
            "LIQUID_CANDIDATE",
            "OPEN_TWO_PHASE",
        }
        assert row.event_region in {
            "LIQUID_CANDIDATE",
            "OPEN_TWO_PHASE",
        }
        assert np.isfinite(row.previous_delta_e_j_kg)
        assert np.isfinite(row.event_delta_e_j_kg)
        assert np.isfinite(row.previous_delta_v_m3_kg)
        assert np.isfinite(row.event_delta_v_m3_kg)
        assert row.previous_sound_speed_m_s > 0.0
        assert row.event_sound_speed_m_s > 0.0


@pytest.mark.coolprop_installed
def test_gate7_artifact_bundle_is_complete(
    installed_gate7_result,
    tmp_path: Path,
) -> None:
    paths = write_phase_chatter_diagnosis_artifacts(
        tmp_path,
        installed_gate7_result,
    )

    assert set(paths) == {
        "summary_json",
        "cell_history_csv",
        "transition_events_csv",
        "interface_flux_csv",
        "saturation_margin_csv",
        "markdown",
        "digest",
    }
    expected_files = {
        "summary.json",
        "cell_29_30_31_history.csv",
        "cell_30_transition_events.csv",
        "interface_flux_history.csv",
        "saturation_margin_history.csv",
        "report.md",
        "artifact_sha256.txt",
        "phase_margin_sound_speed.png",
        "interface_flux_boundary_pressure.png",
        "projection_quality.png",
    }
    assert expected_files <= {path.name for path in tmp_path.iterdir()}
    payload = json.loads(
        paths["summary_json"].read_text(encoding="utf-8")
    )
    assert payload["gate6_final_state_reproduced_exactly"] is True
    assert payload["cell30_toggle_count"] == 49
    assert payload["focused_cell_record_count"] == 576
    assert payload["interface_flux_record_count"] == 192
    assert payload["transition_event_record_count"] == 49
    assert payload["config"]["production_solver_changed"] is False
    assert payload["config"]["rusanov_flux_changed"] is False
    assert payload["config"]["boundary_changed"] is False
    assert payload["config"]["phase_classifier_changed"] is False
    assert payload["config"]["sound_speed_formula_changed"] is False
    assert payload["config"]["quality_projection_changed"] is False
    assert payload["config"]["threshold_or_tolerance_tuned"] is False
    assert payload["config"]["chatter_suppression_added"] is False
    assert all(payload[key] is False for key in APPROVAL_BOUNDARY)
    assert paths["digest"].read_text(encoding="utf-8").strip()
