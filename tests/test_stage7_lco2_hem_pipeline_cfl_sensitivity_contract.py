from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualitySyncConfig,
)
from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
)
from liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics
from liquid_gas_transient.hem_pipeline_cfl_sensitivity import (
    CFL_CELL_COUNT,
    CFL_STEP_CAPS,
    CFL_VALUES,
    EXPECTED_128_CELL_CFL_0P10,
    FIXED_CFL_SENSITIVITY_RUN_SPECS,
    FOUR_MPA_CASE_ID,
    HEMPipelineCflSensitivityConfig,
    HEMPipelineCflSensitivityError,
    _assert_128_cell_cfl_0p10_baseline,
    classify_four_mpa_cfl_sequence,
    run_fixed_pipeline_cfl_sensitivity_matrix,
)


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/verification/"
    "stage7_lco2_hem_pipeline_cfl_sensitivity_contract_v1.json"
)


def _metric(
    cfl: float,
    *,
    case_id: str = FOUR_MPA_CASE_ID,
    crossed: bool = True,
    outcome: str = "GUARD_FAILURE",
    q: float = 1.0e-7,
    delta_u: float = 1.0e-2,
    delta_v: float = 1.0e-10,
    time: float = 0.8,
    position: float = 0.1,
    failure_reason: str = (
        "HEMPipelineDepressurizationError: "
        "crossing quality evidence is below the fixed minimum"
    ),
) -> MeshCaseMetrics:
    steps = CFL_STEP_CAPS[cfl]
    crossing_step = int(1000 * 0.10 / cfl) if crossed else None
    crossing_time = time * 0.002 if crossed else None
    return MeshCaseMetrics(
        run_id=f"{case_id}__n128__cfl{cfl}",
        case_id=case_id,
        role="liquid_negative_control",
        final_boundary_pressure_pa=4.0e6,
        n_cells=128,
        dx_m=1.0 / 128.0,
        maximum_steps=steps,
        cfl=cfl,
        outcome=outcome,
        failure_reason=failure_reason,
        step_count=steps // 8,
        final_time_s=0.002,
        initial_acoustic_time_s=0.002,
        maximum_horizon_s=0.006,
        preflight_accepted_sample_count=65,
        raw_crossing_observed=crossed,
        crossing_step=crossing_step,
        crossing_time_s=crossing_time,
        normalized_crossing_time=time if crossed else None,
        crossing_cell_index=113 if crossed else None,
        crossing_cell_center_m=(1.0 - position) if crossed else None,
        crossing_distance_from_outlet_m=position if crossed else None,
        normalized_crossing_distance_from_outlet=position if crossed else None,
        maximum_crossing_quality=q if crossed else 0.0,
        maximum_projected_quality=q if crossed else 0.0,
        maximum_void_fraction=q * 7.0 if crossed else 0.0,
        crossing_delta_u_sat_j_kg=delta_u if crossed else None,
        crossing_delta_v_sat_m3_kg=delta_v if crossed else None,
        crossing_q_from_internal_energy=q if crossed else None,
        crossing_q_from_specific_volume=q if crossed else None,
        pre_crossing_liquid_sound_speed_m_s=458.0 if crossed else None,
        raw_crossing_sound_speed_m_s=43.5 if crossed else None,
        sound_speed_ratio_raw_to_pre=(43.5 / 458.0) if crossed else None,
        closest_liquid_step=None if crossed else steps // 8,
        closest_liquid_time_s=None if crossed else 0.006,
        closest_liquid_cell_index=None if crossed else 113,
        closest_liquid_distance_from_outlet_m=None if crossed else position,
        closest_liquid_delta_u_sat_j_kg=None if crossed else -1.0e-3,
        closest_liquid_delta_v_sat_m3_kg=None if crossed else -1.0e-11,
        closest_liquid_q_from_internal_energy=None if crossed else -1.0e-8,
        closest_liquid_q_from_specific_volume=None if crossed else -1.0e-8,
        projection_vapor_source_kg=q if crossed else 0.0,
        boundary_vapor_transport_kg=0.0,
        mass_residual_kg=0.0,
        momentum_residual_kg_m_s=0.0,
        energy_residual_J=0.0,
        combined_vapor_residual_kg=0.0,
        reverse_flow_fallback_count=0,
        final_state_sha256=f"state-{cfl}",
        run_signature_sha256=f"signature-{cfl}",
    )


def test_cfl_contract_fixes_values_step_caps_and_128_cell_mesh() -> None:
    assert CFL_CELL_COUNT == 128
    assert CFL_VALUES == (0.10, 0.05, 0.025)
    assert CFL_STEP_CAPS == {0.10: 8000, 0.05: 16000, 0.025: 32000}

    for cfl in CFL_VALUES:
        config = HEMPipelineCflSensitivityConfig.for_cfl(cfl)
        assert config.n_cells == 128
        assert config.dx_m == 1.0 / 128.0
        assert config.cfl == cfl
        assert config.max_steps == CFL_STEP_CAPS[cfl]
        assert config.cfl_override == {
            "n_cells": 128,
            "dx_m": 1.0 / 128.0,
            "cfl": cfl,
            "maximum_steps": CFL_STEP_CAPS[cfl],
        }


@pytest.mark.parametrize("cfl", [True, 0.20, 0.075, 0.01, 0.0, -0.05])
def test_cfl_contract_rejects_unreviewed_cfl_values(cfl: object) -> None:
    with pytest.raises(ValueError):
        HEMPipelineCflSensitivityConfig.for_cfl(cfl)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("n_cells", 64),
        ("max_steps", 7999),
        ("length_m", 2.0),
        ("diameter_m", 0.20),
        ("n_ghost", 1),
        ("initial_pressure_pa", 4.9e6),
        ("subcooling_K", 4.0),
        ("ramp_acoustic_time_ratio", 2.0),
        ("horizon_acoustic_time_ratio", 4.0),
        ("preflight_sample_count", 33),
        ("pressure_drop_evidence_relative", 2.0e-6),
        ("crossing_evidence_min_quality", 1.0e-9),
        ("accepted_state_quality_tolerance", 2.0e-10),
        ("mass_budget_relative_tolerance", 2.0e-10),
        ("mass_budget_absolute_tolerance_kg", 2.0e-12),
        ("momentum_budget_relative_tolerance", 2.0e-10),
        ("momentum_budget_absolute_tolerance_kg_m_s", 2.0e-10),
        ("energy_budget_relative_tolerance", 2.0e-10),
        ("energy_budget_absolute_tolerance_J", 2.0e-6),
        ("vapor_budget_absolute_tolerance_kg", 2.0e-12),
        (
            "phase_config",
            replace(
                HEMPhaseClassificationConfig(),
                endpoint_tolerance=2.0e-10,
            ),
        ),
        (
            "projection_config",
            replace(
                HEMEquilibriumQualitySyncConfig(),
                activation_tolerance=2.0e-12,
            ),
        ),
    ],
)
def test_cfl_contract_rejects_non_cfl_tuning(keyword: str, value: object) -> None:
    kwargs = {"cfl": 0.10, "max_steps": 8000, keyword: value}
    with pytest.raises(ValueError):
        HEMPipelineCflSensitivityConfig(**kwargs)


def test_cfl_contract_rejects_mismatched_step_cap() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        HEMPipelineCflSensitivityConfig(cfl=0.05, max_steps=8000)


def test_fixed_run_specs_define_exact_nine_run_order() -> None:
    assert len(FIXED_CFL_SENSITIVITY_RUN_SPECS) == 9
    assert [spec.cfl for spec in FIXED_CFL_SENSITIVITY_RUN_SPECS] == (
        [0.10] * 3 + [0.05] * 3 + [0.025] * 3
    )
    assert [spec.maximum_steps for spec in FIXED_CFL_SENSITIVITY_RUN_SPECS] == (
        [8000] * 3 + [16000] * 3 + [32000] * 3
    )
    assert [spec.case_id for spec in FIXED_CFL_SENSITIVITY_RUN_SPECS[:3]] == [
        "pipeline_crossing_candidate_p5m5_to_p2m5",
        "pipeline_moderate_diagnostic_p5m5_to_p3m5",
        "pipeline_liquid_control_p5m5_to_p4m5",
    ]
    assert len({spec.run_id for spec in FIXED_CFL_SENSITIVITY_RUN_SPECS}) == 9


def test_exact_cfl_0p10_baseline_guard_accepts_all_three_rows() -> None:
    for expected in EXPECTED_128_CELL_CFL_0P10.values():
        _assert_128_cell_cfl_0p10_baseline(  # type: ignore[arg-type]
            SimpleNamespace(**expected)
        )


def test_exact_cfl_0p10_baseline_guard_rejects_changed_identity() -> None:
    expected = dict(EXPECTED_128_CELL_CFL_0P10[FOUR_MPA_CASE_ID])
    for key, value in (
        ("crossing_step", 1085),
        ("maximum_crossing_quality", 4.0e-7),
        ("crossing_delta_u_sat_j_kg", 0.1),
        ("final_state_sha256", "changed"),
        ("run_signature_sha256", "changed"),
    ):
        changed = dict(expected)
        changed[key] = value
        with pytest.raises(HEMPipelineCflSensitivityError, match="baseline mismatch"):
            _assert_128_cell_cfl_0p10_baseline(  # type: ignore[arg-type]
                SimpleNamespace(**changed)
            )


def test_classification_detects_vanishing_crossing() -> None:
    cases = (
        _metric(0.10, q=8.0e-7),
        _metric(0.05, q=4.0e-7),
        _metric(
            0.025,
            crossed=False,
            outcome="NO_CROSSING_WITHIN_HORIZON",
            failure_reason="",
        ),
    )
    categories, _ = classify_four_mpa_cfl_sequence(cases)
    assert "CROSSING_VANISHES_WITH_SMALLER_CFL" in categories


def test_classification_detects_decay_and_stable_time_position() -> None:
    cases = (
        _metric(
            0.10,
            q=9.0e-7,
            delta_u=9.0e-2,
            delta_v=9.0e-10,
            time=0.80,
            position=0.14,
        ),
        _metric(
            0.05,
            q=6.0e-7,
            delta_u=6.0e-2,
            delta_v=6.0e-10,
            time=0.84,
            position=0.12,
        ),
        _metric(
            0.025,
            q=3.0e-7,
            delta_u=3.0e-2,
            delta_v=3.0e-10,
            time=0.86,
            position=0.11,
        ),
    )
    categories, _ = classify_four_mpa_cfl_sequence(cases)
    assert "CROSSING_DEPTH_DECAYS_WITH_SMALLER_CFL" in categories
    assert "CROSSING_TIME_POSITION_TREND_STABLE" in categories
    assert "FINITE_CROSSING_PERSISTS_ACROSS_CFL" not in categories


def test_classification_detects_persistent_nonmonotone_sequence() -> None:
    cases = (
        _metric(0.10, q=4.0e-7, delta_u=4.0e-2, delta_v=4.0e-10),
        _metric(0.05, q=2.0e-7, delta_u=2.0e-2, delta_v=2.0e-10),
        _metric(0.025, q=3.0e-7, delta_u=3.0e-2, delta_v=3.0e-10),
    )
    categories, _ = classify_four_mpa_cfl_sequence(cases)
    assert "FINITE_CROSSING_PERSISTS_ACROSS_CFL" in categories
    assert "CFL_SEQUENCE_NON_MONOTONE" in categories


def test_matrix_orchestration_uses_exact_order_and_only_reviewed_configs(
    monkeypatch,
) -> None:
    calls: list[tuple[str, int, float, int]] = []

    def fake_runner(case, config):
        calls.append((case.case_id, config.n_cells, config.cfl, config.max_steps))
        return SimpleNamespace(case=case, config=config)

    def fake_metrics(raw):
        return _metric(raw.config.cfl, case_id=raw.case.case_id)

    import liquid_gas_transient.hem_pipeline_cfl_sensitivity as module

    monkeypatch.setattr(module, "_case_metrics", fake_metrics)
    monkeypatch.setattr(
        module,
        "_assert_128_cell_cfl_0p10_baseline",
        lambda metric: None,
    )
    result = run_fixed_pipeline_cfl_sensitivity_matrix(case_runner=fake_runner)

    assert len(result.cases) == 9
    assert [item[1] for item in calls] == [128] * 9
    assert [item[2] for item in calls] == [0.10] * 3 + [0.05] * 3 + [0.025] * 3
    assert [item[3] for item in calls] == [8000] * 3 + [16000] * 3 + [32000] * 3


def test_machine_readable_contract_matches_code_constants() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["schema_version"] == (
        "stage7_lco2_hem_pipeline_cfl_sensitivity_contract_v1"
    )
    assert contract["issue_number"] == 83
    assert contract["status"] == "CONTRACT_IMPLEMENTED_EXECUTION_NOT_YET_ACCEPTED"
    assert contract["fixed_matrix"]["n_cells"] == 128
    assert contract["fixed_matrix"]["cfl_values"] == [0.10, 0.05, 0.025]
    assert contract["fixed_matrix"]["maximum_steps"] == {
        "0.100": 8000,
        "0.050": 16000,
        "0.025": 32000,
    }
    assert contract["cfl_0p10_baseline"] == EXPECTED_128_CELL_CFL_0P10
    approval = contract["approval_boundary"]
    assert approval["Gate_P2_passed"] is False
    assert approval["CFL_independent_crossing_verified"] is False
    assert approval["physical_validation"] is False
    assert approval["design_use_acceptance"] is False
    assert approval["production_hem_activation_approved"] is False


def test_cfl_module_does_not_redefine_solver_flux_or_higher_order_methods() -> None:
    import liquid_gas_transient.hem_pipeline_cfl_sensitivity as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "MUSCL" not in source
    assert "SSP-RK" not in source
