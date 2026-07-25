from __future__ import annotations

import inspect
from dataclasses import replace
from types import SimpleNamespace

import pytest

from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualitySyncConfig,
)
from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
)
from liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity import (
    EXPECTED_32_CELL_4MPA,
    FOUR_MPA_CASE_ID,
    MESH_CELL_COUNTS,
    MESH_STEP_CAPS,
    HEMPipelineMeshSensitivityConfig,
    HEMPipelineMeshSensitivityError,
    MeshCaseMetrics,
    _assert_32_cell_baseline,
    classify_four_mpa_mesh_sequence,
    run_fixed_pipeline_mesh_sensitivity_matrix,
)


def _metric(
    n_cells: int,
    *,
    crossed: bool = True,
    outcome: str = "GUARD_FAILURE",
    q: float = 1.0e-8,
    delta_u: float = 1.0e-3,
    delta_v: float = 1.0e-11,
    time: float = 0.9,
    position: float = 0.2,
    failure_reason: str = (
        "HEMPipelineDepressurizationError: "
        "crossing quality evidence is below the fixed minimum"
    ),
) -> MeshCaseMetrics:
    dx = 1.0 / n_cells
    crossing_step = n_cells if crossed else None
    crossing_time = time * 0.002 if crossed else None
    return MeshCaseMetrics(
        run_id=f"{FOUR_MPA_CASE_ID}__n{n_cells}",
        case_id=FOUR_MPA_CASE_ID,
        role="liquid_negative_control",
        final_boundary_pressure_pa=4.0e6,
        n_cells=n_cells,
        dx_m=dx,
        maximum_steps=MESH_STEP_CAPS[n_cells],
        cfl=0.10,
        outcome=outcome,
        failure_reason=failure_reason,
        step_count=n_cells,
        final_time_s=0.002,
        initial_acoustic_time_s=0.002,
        maximum_horizon_s=0.006,
        preflight_accepted_sample_count=65,
        raw_crossing_observed=crossed,
        crossing_step=crossing_step,
        crossing_time_s=crossing_time,
        normalized_crossing_time=time if crossed else None,
        crossing_cell_index=(n_cells - 7) if crossed else None,
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
        pre_crossing_liquid_sound_speed_m_s=460.0 if crossed else None,
        raw_crossing_sound_speed_m_s=43.0 if crossed else None,
        sound_speed_ratio_raw_to_pre=(43.0 / 460.0) if crossed else None,
        closest_liquid_step=None if crossed else n_cells,
        closest_liquid_time_s=None if crossed else 0.006,
        closest_liquid_cell_index=None if crossed else n_cells - 7,
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
        final_state_sha256=f"state-{n_cells}",
        run_signature_sha256=f"signature-{n_cells}",
    )


def test_mesh_only_configuration_fixes_cells_dx_and_step_caps() -> None:
    assert MESH_CELL_COUNTS == (32, 64, 128)
    assert MESH_STEP_CAPS == {32: 2000, 64: 4000, 128: 8000}

    for n_cells in MESH_CELL_COUNTS:
        config = HEMPipelineMeshSensitivityConfig.for_cells(n_cells)
        assert config.n_cells == n_cells
        assert config.dx_m == 1.0 / n_cells
        assert config.max_steps == MESH_STEP_CAPS[n_cells]
        assert config.cfl == 0.10
        assert config.mesh_override == {
            "n_cells": n_cells,
            "dx_m": 1.0 / n_cells,
            "maximum_steps": MESH_STEP_CAPS[n_cells],
        }


@pytest.mark.parametrize("n_cells", [True, 16, 33, 256])
def test_mesh_only_configuration_rejects_unreviewed_cell_counts(
    n_cells: object,
) -> None:
    with pytest.raises(ValueError):
        HEMPipelineMeshSensitivityConfig.for_cells(n_cells)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("max_steps", 3999),
        ("cfl", 0.05),
        ("length_m", 2.0),
        ("diameter_m", 0.20),
        ("n_ghost", 1),
        ("initial_pressure_pa", 4.9e6),
        ("subcooling_K", 4.0),
        ("ramp_acoustic_time_ratio", 2.0),
        ("horizon_acoustic_time_ratio", 4.0),
        ("preflight_sample_count", 33),
        ("crossing_evidence_min_quality", 1.0e-9),
        ("accepted_state_quality_tolerance", 2.0e-10),
        ("mass_budget_relative_tolerance", 2.0e-10),
        ("energy_budget_absolute_tolerance_J", 2.0e-6),
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
def test_mesh_only_configuration_rejects_non_mesh_tuning(
    keyword: str,
    value: object,
) -> None:
    kwargs = {"n_cells": 64, "max_steps": 4000, keyword: value}
    with pytest.raises(ValueError):
        HEMPipelineMeshSensitivityConfig(**kwargs)


def test_exact_32_cell_baseline_guard_rejects_any_changed_identity() -> None:
    exact = SimpleNamespace(
        **EXPECTED_32_CELL_4MPA,
    )
    _assert_32_cell_baseline(exact)  # type: ignore[arg-type]

    for key, value in (
        ("crossing_step", 312),
        ("maximum_crossing_quality", 1.0e-8),
        ("final_state_sha256", "changed"),
        ("run_signature_sha256", "changed"),
    ):
        changed = dict(EXPECTED_32_CELL_4MPA)
        changed[key] = value
        with pytest.raises(HEMPipelineMeshSensitivityError, match="baseline mismatch"):
            _assert_32_cell_baseline(  # type: ignore[arg-type]
                SimpleNamespace(**changed)
            )


def test_classification_detects_vanishing_crossing() -> None:
    cases = (
        _metric(32, q=1.0e-8),
        _metric(64, q=5.0e-9),
        _metric(
            128,
            crossed=False,
            outcome="NO_CROSSING_WITHIN_HORIZON",
            failure_reason="",
        ),
    )
    categories, _ = classify_four_mpa_mesh_sequence(cases)
    assert "CROSSING_VANISHES_WITH_REFINEMENT" in categories


def test_classification_detects_decay_and_stable_time_position() -> None:
    cases = (
        _metric(32, q=9.0e-8, delta_u=9.0e-3, delta_v=9.0e-11, time=0.80, position=0.24),
        _metric(64, q=6.0e-8, delta_u=6.0e-3, delta_v=6.0e-11, time=0.88, position=0.21),
        _metric(128, q=3.0e-8, delta_u=3.0e-3, delta_v=3.0e-11, time=0.91, position=0.20),
    )
    categories, _ = classify_four_mpa_mesh_sequence(cases)
    assert "CROSSING_DEPTH_DECAYS_WITH_REFINEMENT" in categories
    assert "CROSSING_TIME_POSITION_TREND_STABLE" in categories
    assert "FINITE_CROSSING_PERSISTS_ACROSS_MESHES" not in categories


def test_classification_detects_persistent_nonmonotone_sequence() -> None:
    cases = (
        _metric(32, q=4.0e-8, delta_u=4.0e-3, delta_v=4.0e-11),
        _metric(64, q=2.0e-8, delta_u=2.0e-3, delta_v=2.0e-11),
        _metric(128, q=3.0e-8, delta_u=3.0e-3, delta_v=3.0e-11),
    )
    categories, _ = classify_four_mpa_mesh_sequence(cases)
    assert "FINITE_CROSSING_PERSISTS_ACROSS_MESHES" in categories
    assert "MESH_SEQUENCE_NON_MONOTONE" in categories


def test_classification_marks_unrelated_guard_as_inconclusive() -> None:
    cases = (
        _metric(32),
        _metric(
            64,
            crossed=False,
            outcome="BACKEND_FAILURE",
            failure_reason="backend failed",
        ),
        _metric(128),
    )
    categories, _ = classify_four_mpa_mesh_sequence(cases)
    assert "MESH_SENSITIVITY_INCONCLUSIVE" in categories


def test_matrix_orchestration_uses_exact_nine_run_order(monkeypatch) -> None:
    calls: list[tuple[str, int, int, float]] = []

    def fake_runner(case, config):
        calls.append(
            (
                case.case_id,
                config.n_cells,
                config.max_steps,
                config.cfl,
            )
        )
        return SimpleNamespace(case=case, config=config)

    def fake_metrics(raw):
        return _metric(
            raw.config.n_cells,
            crossed=True,
            outcome="GUARD_FAILURE",
            q=1.0e-8,
        )

    import liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity as module

    monkeypatch.setattr(module, "_case_metrics", fake_metrics)
    monkeypatch.setattr(module, "_assert_32_cell_baseline", lambda metric: None)
    result = run_fixed_pipeline_mesh_sensitivity_matrix(case_runner=fake_runner)

    assert len(result.cases) == 9
    assert [item[1] for item in calls] == [32, 32, 32, 64, 64, 64, 128, 128, 128]
    assert [item[2] for item in calls] == [2000] * 3 + [4000] * 3 + [8000] * 3
    assert all(item[3] == 0.10 for item in calls)


def test_mesh_module_does_not_redefine_solver_or_flux() -> None:
    import liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "MUSCL" not in source
    assert "SSP-RK" not in source
