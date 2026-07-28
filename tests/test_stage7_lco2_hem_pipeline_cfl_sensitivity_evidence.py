from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics
from liquid_gas_transient.hem_pipeline_cfl_sensitivity import (
    CFL_ANALYSIS_ID,
    CFL_STEP_CAPS,
    CFL_VALUES,
    FOUR_MPA_CASE_ID,
    HEMPipelineCflSensitivityResult,
    THRESHOLD_GUARD_FAILURE_REASON,
)
from liquid_gas_transient.hem_pipeline_cfl_sensitivity_evidence import (
    HEMPipelineCflEvidenceError,
    PLOT_KEYS,
    _assert_same_runtime_provenance,
    _identity_prefix,
    standalone_case_rows,
    write_pipeline_cfl_sensitivity_artifacts,
)
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
    PipelineCellRecord,
    PipelineStepRecord,
)


TEST_PROVENANCE = {
    "analysis_id": CFL_ANALYSIS_ID,
    "analysis_model": "HEM",
    "property_backend_name": "coolprop_co2",
    "property_backend_version": "8.0.0-test",
    "source_git_sha": "source-sha",
    "checkout_git_sha": "checkout-sha",
    "git_status_porcelain": "",
    "python_version": "3.12-test",
    "numpy_version": "2.5-test",
    "verification_only": True,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}


def _metric(case_id: str, pressure_pa: float, cfl: float, index: int) -> MeshCaseMetrics:
    distance = 0.10 + 0.01 * index
    q = 1.0e-7 * (index + 1)
    return MeshCaseMetrics(
        run_id=f"{case_id}__n128__cfl{cfl}",
        case_id=case_id,
        role="diagnostic",
        final_boundary_pressure_pa=pressure_pa,
        n_cells=128,
        dx_m=1.0 / 128.0,
        maximum_steps=CFL_STEP_CAPS[cfl],
        cfl=cfl,
        outcome="GUARD_FAILURE",
        failure_reason=THRESHOLD_GUARD_FAILURE_REASON,
        step_count=100 + index,
        final_time_s=1.0e-3 + index * 1.0e-6,
        initial_acoustic_time_s=2.0e-3,
        maximum_horizon_s=6.0e-3,
        preflight_accepted_sample_count=65,
        raw_crossing_observed=True,
        crossing_step=100 + index,
        crossing_time_s=1.0e-3 + index * 1.0e-6,
        normalized_crossing_time=0.5 + index * 1.0e-3,
        crossing_cell_index=110 + index,
        crossing_cell_center_m=1.0 - distance,
        crossing_distance_from_outlet_m=distance,
        normalized_crossing_distance_from_outlet=distance,
        maximum_crossing_quality=q,
        maximum_projected_quality=q,
        maximum_void_fraction=7.0 * q,
        crossing_delta_u_sat_j_kg=0.01 * (index + 1),
        crossing_delta_v_sat_m3_kg=1.0e-10 * (index + 1),
        crossing_q_from_internal_energy=q,
        crossing_q_from_specific_volume=q,
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
        projection_vapor_source_kg=q,
        boundary_vapor_transport_kg=0.0,
        mass_residual_kg=0.0,
        momentum_residual_kg_m_s=0.0,
        energy_residual_J=0.0,
        combined_vapor_residual_kg=0.0,
        reverse_flow_fallback_count=0,
        final_state_sha256=f"state-{index}",
        run_signature_sha256=f"signature-{index}",
    )


def _result() -> HEMPipelineCflSensitivityResult:
    cases = []
    index = 0
    for cfl in CFL_VALUES:
        for case_id, pressure in (
            ("pipeline_crossing_candidate_p5m5_to_p2m5", 2.0e6),
            ("pipeline_moderate_diagnostic_p5m5_to_p3m5", 3.0e6),
            (FOUR_MPA_CASE_ID, 4.0e6),
        ):
            cases.append(_metric(case_id, pressure, cfl, index))
            index += 1
    return HEMPipelineCflSensitivityResult(
        cases=tuple(cases),
        four_mpa_classifications=("FINITE_CROSSING_PERSISTS_ACROSS_CFL",),
        four_mpa_classification_rationale={
            "FINITE_CROSSING_PERSISTS_ACROSS_CFL": "synthetic test sequence"
        },
        provenance=dict(TEST_PROVENANCE),
    )


def _step_record() -> PipelineStepRecord:
    return PipelineStepRecord(
        case_id=FOUR_MPA_CASE_ID,
        step_index=1,
        time_before_s=0.0,
        dt_s=1.0e-6,
        time_after_s=1.0e-6,
        boundary_pressure_pa=4.0e6,
        boundary_temperature_K=270.0,
        boundary_rho_kg_m3=900.0,
        boundary_e_j_kg=2.0e5,
        boundary_equilibrium_quality=0.0,
        boundary_void_fraction=0.0,
        boundary_sound_speed_m_s=500.0,
        boundary_region="LIQUID_CANDIDATE",
        reverse_flow_fallback_count=0,
        raw_outcome="OPEN_TWO_PHASE",
        projected_outcome="ACCEPTED",
        crossing_cell_indices=(113,),
        first_projection_cell_indices=(113,),
        second_projection_cell_indices=(),
        max_raw_equilibrium_quality=1.0e-7,
        max_post_quality_mismatch=0.0,
        pressure_min_pa=4.0e6,
        pressure_max_pa=5.0e6,
        left_mass_flux_rate_kg_s=0.0,
        right_mass_flux_rate_kg_s=1.0,
        left_energy_flux_rate_W=0.0,
        right_energy_flux_rate_W=1.0,
        boundary_vapor_step_kg=0.0,
        projection_vapor_step_kg=1.0e-9,
        raw_boundary_vapor_residual_kg=0.0,
        projection_source_consistency_residual_kg=0.0,
        combined_vapor_balance_residual_kg=0.0,
        state_sha256="step-state",
    )


def _cell_record() -> PipelineCellRecord:
    return PipelineCellRecord(
        case_id=FOUR_MPA_CASE_ID,
        step_index=1,
        time_s=1.0e-6,
        cell_index=113,
        cell_center_m=0.88671875,
        distance_from_outlet_m=0.11328125,
        previous_region="LIQUID_CANDIDATE",
        raw_region="OPEN_TWO_PHASE",
        post_region="OPEN_TWO_PHASE",
        transition_event="LIQUID_TO_TWO_PHASE_CROSSING",
        rho_raw_kg_m3=876.0,
        velocity_raw_m_s=1.0,
        e_raw_j_kg=2.15e5,
        pressure_raw_pa=4.2e6,
        temperature_raw_K=280.0,
        q_transport_raw=0.0,
        q_equilibrium=1.0e-7,
        q_post=1.0e-7,
        alpha_post=7.0e-7,
        sound_speed_post_m_s=43.0,
        first_projection_applied=True,
        second_projection_applied=False,
        relative_pressure_drop=0.1,
        first_pressure_drop_arrival_time_s=1.0e-6,
    )


def test_standalone_case_rows_embed_identity_and_keep_acceptance_false() -> None:
    rows = standalone_case_rows(_result())
    assert len(rows) == 9
    for row in rows:
        assert row["analysis_id"] == CFL_ANALYSIS_ID
        assert row["analysis_model"] == "HEM"
        assert row["property_backend_name"] == "coolprop_co2"
        assert row["property_backend_version"] == "8.0.0-test"
        assert row["source_git_sha"] == "source-sha"
        assert row["checkout_is_clean"] is True
        assert row["local_pc_checkpoint_completed"] is True
        assert row["low_cfl_result_accepted"] is False
        assert row["central_record_promotion_allowed"] is False
        assert row["CFL_independent_crossing_verified"] is False
        assert row["physical_validation"] is False
        assert row["design_use_acceptance"] is False
        assert row["production_hem_activation_approved"] is False


def test_identity_prefix_rejects_incomplete_provenance() -> None:
    broken = dict(TEST_PROVENANCE)
    del broken["checkout_git_sha"]
    with pytest.raises(HEMPipelineCflEvidenceError, match="missing fields"):
        _identity_prefix(broken)


def test_runtime_provenance_guard_rejects_backend_or_sha_drift() -> None:
    changed = dict(TEST_PROVENANCE)
    changed["property_backend_version"] = "different"
    with pytest.raises(HEMPipelineCflEvidenceError, match="changed during"):
        _assert_same_runtime_provenance(TEST_PROVENANCE, changed)


def test_writer_emits_complete_traceable_bundle_without_accepting_result(
    monkeypatch, tmp_path: Path
) -> None:
    synthetic = _result()

    def fake_run(*, case_runner=None, on_case_result=None, provenance=None):
        assert case_runner is not None
        assert provenance == TEST_PROVENANCE
        if on_case_result is not None:
            raw = SimpleNamespace(steps=(_step_record(),), cells=(_cell_record(),))
            on_case_result(raw, synthetic.cases[0])
        return synthetic

    def fake_plots(target, result):
        assert result is synthetic
        paths = {}
        for key in PLOT_KEYS:
            path = target / f"{key}.png"
            path.write_bytes(b"test-png")
            paths[key] = path
        return paths

    import liquid_gas_transient.hem_pipeline_cfl_sensitivity_evidence as module

    monkeypatch.setattr(module, "collect_cfl_runtime_provenance", lambda: dict(TEST_PROVENANCE))
    monkeypatch.setattr(module, "run_fixed_pipeline_cfl_sensitivity_matrix", fake_run)
    monkeypatch.setattr(module, "_generate_plots", fake_plots)

    result, paths = write_pipeline_cfl_sensitivity_artifacts(tmp_path)
    assert result is synthetic
    assert set(PLOT_KEYS).issubset(paths)
    for path in paths.values():
        assert path.is_file()

    summary = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    assert summary["case_count"] == 9
    assert summary["cfl_values"] == [0.10, 0.05, 0.025]
    assert summary["gate4_execution_completed_in_ci"] is True
    assert summary["local_pc_checkpoint_completed"] is True
    assert summary["low_cfl_result_accepted"] is False
    assert summary["central_record_promotion_allowed"] is False
    assert summary["CFL_independent_crossing_verified"] is False

    with paths["cases_csv"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 9
    assert {row["cfl"] for row in rows} == {"0.1", "0.05", "0.025"}
    assert all(row["low_cfl_result_accepted"] == "False" for row in rows)

    with paths["steps_csv"].open(newline="", encoding="utf-8") as handle:
        step_rows = list(csv.DictReader(handle))
    with paths["cells_csv"].open(newline="", encoding="utf-8") as handle:
        cell_rows = list(csv.DictReader(handle))
    assert len(step_rows) == 1
    assert len(cell_rows) == 1
    assert step_rows[0]["source_git_sha"] == "source-sha"
    assert cell_rows[0]["property_backend_version"] == "8.0.0-test"

    arrays = np.load(paths["npz"])
    assert arrays["cfl"].shape == (9,)
    assert arrays["maximum_crossing_quality"].shape == (9,)

    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "GATE 3 COMPLETE; RESULT NOT ACCEPTED" in markdown
    assert "low_cfl_result_accepted = false" in markdown
    assert "CFL_independent_crossing_verified = false" in markdown


def test_evidence_module_does_not_redefine_solver_or_change_production_scope() -> None:
    import liquid_gas_transient.hem_pipeline_cfl_sensitivity_evidence as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "production_hem_activation_approved\": True" not in source
    assert "low_cfl_result_accepted\": True" not in source
