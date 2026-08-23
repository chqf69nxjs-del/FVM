from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from liquid_gas_transient.hne_acoustic_shadow_pipeline import (
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    NEXT_ACTION,
    OUTPUT_FILES,
    PROPERTY_BACKEND_NAME,
    SCHEMA_VERSION,
    SOLVER_AUTHORITY,
    FinitePipelineAcousticShadowObserver,
    ShadowPipelineConfig,
    _build_solver,
    _report,
    analyze_acoustic_shadow_pipeline,
    execute,
)
from liquid_gas_transient.hne_equilibrium_acoustic_closure import (
    evaluate_equilibrium_acoustic,
    state_from_pressure_quality,
)
from liquid_gas_transient.state import make_conserved


def test_a2_4_3_contract_and_maturity_boundary() -> None:
    assert SCHEMA_VERSION == "stage7_p2_hne_acoustic_shadow_pipeline_a2_4_3_v1"
    assert PROPERTY_BACKEND_NAME == "surrogate_lco2"
    assert len(OUTPUT_FILES) == 6
    assert all(value is False for value in SOLVER_AUTHORITY.values())
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["working_verification_slice"] is True
    assert FORMAL_STATUS["finite_pipeline_acoustic_shadow"] is True
    assert FORMAL_STATUS["read_only_shadow_evidence_ready"] is True
    for key in (
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False
    assert FORMAL_OUTCOME == (
        "A2_4_3_FINITE_PIPELINE_READ_ONLY_ACOUSTIC_SHADOW_READY_"
        "WITH_SOLVER_AUTHORITY_CLOSED"
    )
    assert NEXT_ACTION == (
        "PROCEED_TO_A2_4_4_FINITE_RELAXATION_DISPERSION_INVESTIGATION"
    )


def test_a2_4_2r_pressure_recovery_compatibility_bridge_is_effective() -> None:
    source = state_from_pressure_quality(2.5e6, 0.10)
    diagnostic = evaluate_equilibrium_acoustic(source.rho_kg_m3, source.e_j_kg)
    assert diagnostic.valid, diagnostic.failure_reason
    assert diagnostic.state is not None
    assert abs(diagnostic.state.pressure_pa - source.pressure_pa) <= 2.0e-4
    assert diagnostic.equilibrium_sound_speed_squared_m2_s2 is not None
    assert diagnostic.equilibrium_sound_speed_squared_m2_s2 > 0.0


def test_acoustic_observer_is_read_only_and_valid_on_focused_pipeline_state() -> None:
    config = ShadowPipelineConfig(n_cells=4, n_steps=1)
    solver, _ = _build_solver(config, 1.0e-4)
    observer = FinitePipelineAcousticShadowObserver()
    before = solver.U.copy()
    observation = observer.observe(
        case_id="READ_ONLY",
        tau_s=1.0e-4,
        U=solver.U,
        grid=solver.grid,
        step=0,
        time_s=0.0,
        dt_s=0.0,
    )
    assert np.array_equal(before, solver.U)
    assert observation.step_row["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert observation.step_row["shadow_state_read_only"] is True
    assert observation.step_row["acoustic_valid_count"] == config.n_cells
    assert observation.step_row["acoustic_invalid_count"] == 0
    assert observation.step_row["any_empirical_fallback_used"] is False
    assert observation.step_row["all_solver_authority_denied"] is True
    for row in observation.cell_rows:
        assert row["property_backend_name"] == PROPERTY_BACKEND_NAME
        assert row["valid"] is True
        assert row["equilibrium_c2_m2_s2"] > 0.0
        assert row["frozen_c2_m2_s2"] > 0.0
        assert row["subcharacteristic_margin_m2_s2"] >= 0.0
        assert row["solver_authority_granted"] is False


def test_out_of_scope_pipeline_state_is_recorded_fail_closed_without_fallback() -> None:
    config = ShadowPipelineConfig(n_cells=4, n_steps=1)
    solver, _ = _build_solver(config, 1.0e-4)
    observer = FinitePipelineAcousticShadowObserver()
    U = make_conserved(
        np.full(config.n_cells, 930.0),
        np.zeros(config.n_cells),
        np.full(config.n_cells, 1.0e5),
        np.zeros(config.n_cells),
    )
    before = U.copy()
    observation = observer.observe(
        case_id="OUT_OF_SCOPE",
        tau_s=1.0e-4,
        U=U,
        grid=solver.grid,
        step=0,
        time_s=0.0,
        dt_s=0.0,
    )
    assert np.array_equal(before, U)
    assert observation.step_row["acoustic_valid_count"] == 0
    assert observation.step_row["acoustic_invalid_count"] == config.n_cells
    assert observation.step_row["any_empirical_fallback_used"] is False
    for row in observation.cell_rows:
        assert row["valid"] is False
        assert row["equilibrium_c2_m2_s2"] is None
        assert row["frozen_c2_m2_s2"] is None
        assert row["empirical_fallback_used"] is False
        assert row["solver_authority_granted"] is False


def test_finite_pipeline_acoustic_shadow_matrix_passes_without_coupling() -> None:
    analysis = analyze_acoustic_shadow_pipeline(
        ShadowPipelineConfig(n_cells=8, n_steps=8)
    )
    summary = analysis.summary
    assert summary["a2_4_3_acoustic_shadow_ready"] is True
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert summary["property_backend"]["name"] == PROPERTY_BACKEND_NAME
    assert summary["acoustic_model"]["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert summary["hydrodynamic_coupling_allowed"] is False
    assert all(value is False for value in summary["solver_authority"].values())
    assert len(summary["case_summary"]) == 3
    for row in summary["case_summary"]:
        assert row["property_backend_name"] == PROPERTY_BACKEND_NAME
        assert row["baseline_shadow_full_trajectory_bitwise_equal"] is True
        assert row[
            "baseline_shadow_hydrodynamic_trajectory_bitwise_equal"
        ] is True
        assert row["all_pipeline_states_in_claimed_acoustic_domain"] is True
        assert row["all_acoustic_diagnostics_valid"] is True
        assert row["all_equilibrium_c2_positive"] is True
        assert row["all_frozen_c2_positive"] is True
        assert row["all_subcharacteristic_margins_nonnegative"] is True
        assert row["all_derivative_crosschecks_satisfied"] is True
        assert row["no_empirical_fallback_used"] is True
        assert row["all_solver_authority_denied"] is True
        assert row["mass_momentum_energy_conserved"] is True


def test_pipeline_acoustic_values_are_finite_ordered_and_in_claimed_domain() -> None:
    analysis = analyze_acoustic_shadow_pipeline(
        ShadowPipelineConfig(n_cells=4, n_steps=2)
    )
    for row in analysis.cell_rows:
        assert row["property_backend_name"] == PROPERTY_BACKEND_NAME
        assert row["valid"] is True
        assert row["within_claimed_domain"] is True
        assert 1.5e6 < row["p_equilibrium_acoustic_pa"] < 5.0e6
        assert 0.02 < row["q_equilibrium_acoustic"] < 0.45
        assert row["equilibrium_c2_m2_s2"] > 0.0
        assert row["frozen_c2_m2_s2"] >= row["equilibrium_c2_m2_s2"]
        assert row["derivative_crosscheck_satisfied"] is True
        assert row["subcharacteristic_satisfied"] is True


def test_repeated_analysis_is_deterministic() -> None:
    config = ShadowPipelineConfig(n_cells=4, n_steps=2)
    first = analyze_acoustic_shadow_pipeline(config)
    second = analyze_acoustic_shadow_pipeline(config)
    assert first.summary["analysis_sha256"] == second.summary["analysis_sha256"]
    assert first.case_rows == second.case_rows
    assert first.step_rows == second.step_rows
    assert first.cell_rows == second.cell_rows


def test_operator_report_stops_when_any_gate_fails() -> None:
    analysis = analyze_acoustic_shadow_pipeline(ShadowPipelineConfig(n_cells=4, n_steps=1))
    summary = dict(analysis.summary)
    summary["a2_4_3_acoustic_shadow_ready"] = False
    summary["formal_outcome"] = "A2_4_3_IMPLEMENTED_NOT_READY_WITH_FAIL_CLOSED_GATES"
    summary["next_action"] = "RESOLVE_FAILED_A2_4_3_GATES_BEFORE_A2_4_4"
    summary["failed_gates"] = ["SYNTHETIC_REVIEW_GATE"]
    report = _report(summary)
    assert "STOP: A2.4-3 gates are not green" in report
    assert "do not proceed to A2.4-4" in report
    assert "SYNTHETIC_REVIEW_GATE" in report
    assert "Proceed only according" not in report


def test_execute_writes_complete_strict_reproducible_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ANALYSIS_SOURCE_GIT_SHA", "TEST_SHA")
    first = tmp_path / "first"
    second = tmp_path / "second"
    result_first = execute(first)
    result_second = execute(second)
    assert result_first["a2_4_3_acoustic_shadow_ready"] is True
    assert result_second["a2_4_3_acoustic_shadow_ready"] is True
    assert {path.name for path in first.iterdir()} == set(OUTPUT_FILES)
    assert {path.name for path in second.iterdir()} == set(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    report = (first / "operator_report.md").read_text(encoding="utf-8")
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert summary["property_backend"]["name"] == PROPERTY_BACKEND_NAME
    assert summary["acoustic_model"]["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert manifest["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert f"Property backend: `{PROPERTY_BACKEND_NAME}`" in report
    assert f"Next action: `{NEXT_ACTION}`" in report
    assert manifest["declared_file_count"] == len(OUTPUT_FILES)
    assert manifest["declared_file_names"] == list(OUTPUT_FILES)
    assert manifest["analysis_sha256"] == summary["analysis_sha256"]
    assert manifest["a2_4_3_acoustic_shadow_ready"] is True
    assert manifest["hydrodynamic_coupling_allowed"] is False
    assert set(manifest["payload_files"]) == set(OUTPUT_FILES) - {
        "manifest.json"
    }