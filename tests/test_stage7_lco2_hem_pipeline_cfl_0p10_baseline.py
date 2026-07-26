from __future__ import annotations

from types import SimpleNamespace

from liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics
from liquid_gas_transient.hem_pipeline_cfl_0p10_baseline import (
    BASELINE_ANALYSIS_ID,
    BASELINE_CFL,
    baseline_case_csv_rows,
    run_cfl_0p10_baseline,
)


TEST_PROVENANCE = {
    "analysis_id": "stage7_pipeline_cfl_sensitivity_matrix",
    "analysis_model": "HEM",
    "property_backend_name": "coolprop_co2",
    "property_backend_version": "8.0.0-test",
    "source_git_sha": "test-source-sha",
    "verification_only": True,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}


def _metric(case_id: str) -> MeshCaseMetrics:
    return MeshCaseMetrics(
        run_id=f"{case_id}__n128__cfl0p100",
        case_id=case_id,
        role="diagnostic",
        final_boundary_pressure_pa=2.0e6,
        n_cells=128,
        dx_m=1.0 / 128.0,
        maximum_steps=8000,
        cfl=0.10,
        outcome="GUARD_FAILURE",
        failure_reason="test",
        step_count=1,
        final_time_s=1.0e-6,
        initial_acoustic_time_s=2.0e-3,
        maximum_horizon_s=6.0e-3,
        preflight_accepted_sample_count=65,
        raw_crossing_observed=True,
        crossing_step=1,
        crossing_time_s=1.0e-6,
        normalized_crossing_time=5.0e-4,
        crossing_cell_index=120,
        crossing_cell_center_m=0.94,
        crossing_distance_from_outlet_m=0.06,
        normalized_crossing_distance_from_outlet=0.06,
        maximum_crossing_quality=1.0e-7,
        maximum_projected_quality=1.0e-7,
        maximum_void_fraction=7.0e-7,
        crossing_delta_u_sat_j_kg=1.0e-2,
        crossing_delta_v_sat_m3_kg=1.0e-10,
        crossing_q_from_internal_energy=1.0e-7,
        crossing_q_from_specific_volume=1.0e-7,
        pre_crossing_liquid_sound_speed_m_s=460.0,
        raw_crossing_sound_speed_m_s=43.0,
        sound_speed_ratio_raw_to_pre=43.0 / 460.0,
        closest_liquid_step=None,
        closest_liquid_time_s=None,
        closest_liquid_cell_index=None,
        closest_liquid_distance_from_outlet_m=None,
        closest_liquid_delta_u_sat_j_kg=None,
        closest_liquid_delta_v_sat_m3_kg=None,
        closest_liquid_q_from_internal_energy=None,
        closest_liquid_q_from_specific_volume=None,
        projection_vapor_source_kg=1.0e-8,
        boundary_vapor_transport_kg=0.0,
        mass_residual_kg=0.0,
        momentum_residual_kg_m_s=0.0,
        energy_residual_J=0.0,
        combined_vapor_residual_kg=0.0,
        reverse_flow_fallback_count=0,
        final_state_sha256="state",
        run_signature_sha256="signature",
    )


def _fake_result(monkeypatch):
    calls: list[tuple[str, int, float, int]] = []

    def fake_runner(case, config):
        calls.append((case.case_id, config.n_cells, config.cfl, config.max_steps))
        return SimpleNamespace(case=case, config=config)

    def fake_metrics(raw):
        return _metric(raw.case.case_id)

    import liquid_gas_transient.hem_pipeline_cfl_0p10_baseline as module

    monkeypatch.setattr(module, "_case_metrics", fake_metrics)
    monkeypatch.setattr(
        module,
        "_assert_128_cell_cfl_0p10_baseline",
        lambda metric: None,
    )
    result = run_cfl_0p10_baseline(
        case_runner=fake_runner,
        provenance=TEST_PROVENANCE,
    )
    return result, calls


def test_baseline_replay_uses_only_128_cells_cfl_0p10_and_8000_steps(
    monkeypatch,
) -> None:
    result, calls = _fake_result(monkeypatch)
    assert BASELINE_CFL == 0.10
    assert len(result.cases) == 3
    assert [item[1:] for item in calls] == [(128, 0.10, 8000)] * 3
    summary = result.summary()
    assert summary["all_pr82_rows_reproduced_exactly"] is True
    assert summary["low_cfl_matrix_executed"] is False
    assert summary["analysis_identity"] == {
        "analysis_id": BASELINE_ANALYSIS_ID,
        "model": "HEM",
        "backend": "coolprop_co2",
        "version": "8.0.0-test",
    }
    assert summary["design_use_acceptance"] is False


def test_baseline_case_csv_rows_are_standalone_and_traceable(monkeypatch) -> None:
    result, _ = _fake_result(monkeypatch)
    rows = baseline_case_csv_rows(result)
    assert len(rows) == 3
    for row in rows:
        assert row["analysis_id"] == BASELINE_ANALYSIS_ID
        assert row["analysis_model"] == "HEM"
        assert row["property_backend_name"] == "coolprop_co2"
        assert row["property_backend_version"] == "8.0.0-test"
        assert row["source_git_sha"] == "test-source-sha"
        assert row["verification_only"] is True
        assert row["design_use_acceptance"] is False
        assert row["production_hem_activation_approved"] is False
        assert row["CFL_independent_crossing_verified"] is False
        assert row["Gate_P2_passed"] is False
        assert row["case_id"]
