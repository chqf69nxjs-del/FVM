from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.flux import observe_rusanov_flux
from liquid_gas_transient.hne_controlled_finite_pipe_coupling import (
    BOUNDARY_MODEL_NAME,
    CONTROLLED_CONDITION_ID,
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    IMPLEMENTATION_AUTHORITY,
    NEXT_ACTION,
    OUTPUT_FILES,
    PROPERTY_BACKEND_NAME,
    PRESCRIBED_PRESSURE_RECOVERY_TOLERANCE_PA,
    SCHEMA_VERSION,
    SOURCE_A3_1_ARTIFACT_DIGEST,
    SOURCE_A3_1_ARTIFACT_ID,
    SOURCE_A3_1_JOB_ID,
    SOURCE_A3_1_SHA,
    SOURCE_A3_1_WORKFLOW_RUN_ID,
    ControlledFinitePipeConfig,
    HNEControlledFinitePipeCouplingError,
    PrescribedHNEPressureRampOutlet,
    analyze_controlled_finite_pipe_coupling,
    build_controlled_finite_pipe_solver,
    requested_boundary_pressure_pa,
    schedule_pressure_tolerance_pa,
    write_artifacts,
)
from liquid_gas_transient.hne_equilibrium_acoustic_closure import (
    state_from_pressure_quality,
)
from liquid_gas_transient.state import vapor_mass_fraction


@lru_cache(maxsize=1)
def _default_analysis():
    return analyze_controlled_finite_pipe_coupling()


def _case(case_id: str) -> dict[str, object]:
    return next(
        row for row in _default_analysis().case_rows if row["case_id"] == case_id
    )


def test_contract_source_pin_and_pre_execution_maturity_boundary() -> None:
    assert SCHEMA_VERSION == "stage7_p2_hne_controlled_finite_pipe_coupling_a3_2_v1"
    assert SOURCE_A3_1_SHA == "d4db09a6447ba4c98fcf0618e37e3ad6fe859ec1"
    assert SOURCE_A3_1_WORKFLOW_RUN_ID == 32638595911
    assert SOURCE_A3_1_JOB_ID == 97192025339
    assert SOURCE_A3_1_ARTIFACT_ID == 9493006871
    assert SOURCE_A3_1_ARTIFACT_DIGEST == (
        "sha256:21fbde78e47b271d12061dd8c2be67a2128f44645aa6434fe487d50b16d6d423"
    )
    assert PROPERTY_BACKEND_NAME == "surrogate_lco2"
    assert len(OUTPUT_FILES) == 6
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["working_verification_slice"] is False
    assert FORMAL_STATUS["working_vertical_slice"] is False
    assert FORMAL_STATUS[
        "controlled_finite_pipe_hne_hydrodynamic_coupling"
    ] is False
    for key in (
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False
    assert FORMAL_OUTCOME.endswith(
        "WORKING_VERTICAL_SLICE_WITH_PHYSICAL_DISCHARGE_AUTHORITY_CLOSED"
    )
    assert NEXT_ACTION == (
        "PROCEED_TO_U3_PHYSICAL_DISCHARGE_COUPLING_AS_A_SEPARATE_CONTROLLED_INCREMENT"
    )


def test_prescribed_pressure_ramp_boundary_is_exact_and_noncharacteristic() -> None:
    config = ControlledFinitePipeConfig(n_cells=32)
    solver, boundary = build_controlled_finite_pipe_solver(
        config,
        tau_s=config.finite_tau_s,
    )
    assert isinstance(boundary, PrescribedHNEPressureRampOutlet)
    solver.t = config.ramp_start_s + 0.5 * config.ramp_duration_s
    extended = solver.extend_with_ghosts(solver.t)
    ghost = extended[-solver.n_ghost :]
    primitive = solver.eos.primitive_from_conserved(ghost)
    target = requested_boundary_pressure_pa(solver.t, config)
    assert np.allclose(
        primitive.p,
        target,
        rtol=0.0,
        atol=PRESCRIBED_PRESSURE_RECOVERY_TOLERANCE_PA,
    )
    assert np.allclose(
        vapor_mass_fraction(ghost),
        config.initial_equilibrium_quality,
        rtol=0.0,
        atol=1.0e-15,
    )
    diagnostics = boundary.diagnostics(solver.t)
    assert diagnostics["boundary_model"] == BOUNDARY_MODEL_NAME
    assert diagnostics["hne_characteristic_boundary"] is False
    assert diagnostics["critical_discharge_law"] is False
    assert diagnostics["physical_discharge_model"] is False


def test_candidate_pressure_frozen_c_cfl_and_rusanov_are_active_in_finite_pipe() -> None:
    config = ControlledFinitePipeConfig(n_cells=32)
    solver, _ = build_controlled_finite_pipe_solver(
        config,
        tau_s=config.finite_tau_s,
    )
    source = state_from_pressure_quality(
        config.initial_pressure_pa,
        config.initial_equilibrium_quality,
    )
    candidate = solver.eos.evaluate(
        source.rho_kg_m3,
        source.e_j_kg,
        source.vapor_mass_fraction,
    )
    primitive = solver.primitive()
    assert np.allclose(primitive.p, candidate.pressure_pa, rtol=0.0, atol=0.0)
    assert np.allclose(primitive.c, candidate.frozen_c_m_s, rtol=0.0, atol=0.0)
    expected_dt = config.cfl * solver.grid.dx / candidate.frozen_c_m_s
    assert solver.compute_dt() == pytest.approx(expected_dt, rel=0.0, abs=1.0e-15)

    observations = []
    with observe_rusanov_flux(observations.append):
        solver._base_fluxes()
    assert len(observations) == 1
    assert np.allclose(
        observations[0].maximum_wave_speed,
        candidate.frozen_c_m_s,
        rtol=0.0,
        atol=1.0e-12,
    )


def test_full_a3_2_gate_passes_with_three_controlled_relaxation_regimes() -> None:
    analysis = _default_analysis()
    summary = analysis.summary
    assert summary["p2_a3_2_controlled_finite_pipe_coupling_ready"] is True
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert len(analysis.case_rows) == 3
    assert len(analysis.step_rows) > 100
    assert len(analysis.probe_rows) > 30
    assert {row["relaxation_regime"] for row in analysis.case_rows} == {
        "near_zero",
        "finite",
        "frozen",
    }
    assert {row["controlled_condition_id"] for row in analysis.case_rows} == {
        CONTROLLED_CONDITION_ID
    }
    assert summary["formal_status"]["working_verification_slice"] is True
    assert summary["formal_status"]["working_vertical_slice"] is True
    assert summary["formal_status"][
        "controlled_finite_pipe_hne_hydrodynamic_coupling"
    ] is True
    assert summary["formal_outcome"] == FORMAL_OUTCOME
    assert summary["next_action"] == NEXT_ACTION
    assert summary["existing_production_default_path_modified"] is False
    assert summary["hne_boundary_characteristics_authorized"] is False
    assert summary["critical_discharge_authorized"] is False
    assert summary["physical_discharge_authorized"] is False
    assert summary["rupture_model_authorized"] is False
    for key in (
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert summary["formal_status"][key] is False


def test_near_zero_tau_recovers_hem_limit_in_controlled_pipe() -> None:
    row = _case("TAU_NEAR_ZERO_HEM_LIMIT")
    assert row["relaxation_regime"] == "near_zero"
    assert float(row["maximum_absolute_quality_lag"]) <= 1.0e-12
    assert float(
        row["maximum_absolute_hne_equilibrium_pressure_offset_pa"]
    ) <= 1.0e-3
    assert float(row["phase_vapor_mass_source_cumulative_kg"]) > 1.0e-6
    assert float(row["actual_quality_range"]) > 5.0e-3


def test_finite_tau_closes_phase_change_pressure_wave_feedback_loop() -> None:
    row = _case("TAU_FINITE_HNE")
    frozen = _case("TAU_INFINITY_FROZEN_LIMIT")
    assert row["relaxation_regime"] == "finite"
    assert 1.0e-4 < float(row["maximum_absolute_quality_lag"])
    assert float(row["maximum_absolute_quality_lag"]) < float(
        frozen["maximum_absolute_quality_lag"]
    )
    assert float(
        row["maximum_absolute_hne_equilibrium_pressure_offset_pa"]
    ) > 1.0e3
    assert float(row["equilibrium_quality_range"]) > 5.0e-3
    assert float(row["frozen_c_range_m_s"]) > 0.5
    assert float(row["phase_vapor_mass_source_cumulative_kg"]) > 1.0e-6
    assert row["candidate_pressure_active_in_interior_flux"] is True
    assert row["candidate_frozen_c_active_in_rusanov_and_cfl"] is True


def test_tau_infinity_recovers_frozen_quality_limit() -> None:
    row = _case("TAU_INFINITY_FROZEN_LIMIT")
    assert row["relaxation_regime"] == "frozen"
    assert row["tau_is_infinite"] is True
    assert row["tau_s"] is None
    assert abs(float(row["phase_vapor_mass_source_cumulative_kg"])) <= 1.0e-14
    assert float(row["actual_quality_range"]) <= 1.0e-12
    assert float(row["maximum_absolute_quality_lag"]) > 1.0e-3
    assert float(
        row["maximum_absolute_hne_equilibrium_pressure_offset_pa"]
    ) > 1.0e4


def test_pressure_wave_arrives_from_outlet_toward_upstream_in_all_cases() -> None:
    for row in _default_analysis().case_rows:
        assert row["all_pressure_wave_probes_arrived"] is True
        assert row["pressure_wave_arrival_order_outlet_to_upstream"] is True
        times = row["probe_arrival_times_s"]
        assert times["x_over_L_0_75"] < times["x_over_L_0_50"] < times[
            "x_over_L_0_25"
        ]
        assert 0.4 <= float(
            row["minimum_front_speed_to_initial_frozen_c_ratio"]
        ) <= 2.5
        assert 0.4 <= float(
            row["maximum_front_speed_to_initial_frozen_c_ratio"]
        ) <= 2.5
        assert float(row["maximum_observed_pressure_drop_pa"]) > 4.0e5


def test_mass_momentum_energy_and_vapor_phase_budgets_close() -> None:
    for row in _default_analysis().case_rows:
        assert float(
            row["maximum_absolute_hydro_budget_relative_residual"]
        ) <= 1.0e-9
        assert float(
            row["maximum_absolute_phase_vapor_balance_relative_residual"]
        ) <= 1.0e-9
        assert row["all_states_finite"] is True
        assert row["all_states_positive"] is True
        assert row[
            "actual_and_equilibrium_states_remained_in_open_authority_domain"
        ] is True
        assert row["boundary_schedule_reached_final_pressure"] is True


def test_finite_case_repeatability_and_three_trajectories_are_distinct() -> None:
    analysis = _default_analysis()
    repeatability = analysis.summary["repeatability"]
    assert repeatability["deterministic_repeatability_passed"] is True
    assert repeatability["finite_final_state_sha256_match"] is True
    assert repeatability["finite_step_history_sha256_match"] is True
    assert repeatability["finite_probe_history_sha256_match"] is True
    hashes = {row["trajectory_sha256"] for row in analysis.case_rows}
    assert len(hashes) == 3


def test_evidence_is_complete_strict_and_byte_deterministic(tmp_path: Path) -> None:
    analysis = _default_analysis()
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_artifacts(first, analysis)
    write_artifacts(second, analysis)
    assert {path.name for path in first.iterdir()} == set(OUTPUT_FILES)
    assert {path.name for path in second.iterdir()} == set(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    report = (first / "operator_report.md").read_text(encoding="utf-8")
    assert summary["p2_a3_2_controlled_finite_pipe_coupling_ready"] is True
    assert manifest["p2_a3_2_controlled_finite_pipe_coupling_ready"] is True
    assert manifest["analysis_sha256"] == summary["analysis_sha256"]
    assert manifest["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert manifest["source_a3_1_sha"] == SOURCE_A3_1_SHA
    assert manifest["existing_production_default_path_modified"] is False
    assert manifest["hne_boundary_characteristics_authorized"] is False
    assert manifest["critical_discharge_authorized"] is False
    assert manifest["physical_discharge_authorized"] is False
    assert f"Property backend: `{PROPERTY_BACKEND_NAME}`" in report
    assert f"Next action: `{NEXT_ACTION}`" in report
    assert "STOP: P2-A3.2 gates failed" not in report


def test_boundary_and_configuration_fail_closed_outside_authority_domain() -> None:
    with pytest.raises(ValueError):
        ControlledFinitePipeConfig(initial_equilibrium_quality=0.02)
    with pytest.raises(ValueError):
        ControlledFinitePipeConfig(final_boundary_pressure_pa=1.5e6)

    config = ControlledFinitePipeConfig(n_cells=32)
    solver, boundary = build_controlled_finite_pipe_solver(
        config,
        tau_s=config.finite_tau_s,
    )
    extended = solver.extend_with_ghosts(0.0)
    with pytest.raises(NotImplementedError):
        boundary.apply(
            extended,
            solver.n_ghost,
            "left",
            0.0,
            solver.eos,
        )
    with pytest.raises(HNEControlledFinitePipeCouplingError):
        boundary.apply(
            extended,
            solver.n_ghost,
            "right",
            0.0,
            object(),
        )

    for key in (
        "hne_boundary_characteristics",
        "hne_critical_discharge",
        "physical_discharge_model",
        "rupture_model",
        "design_use",
        "production_use",
    ):
        assert IMPLEMENTATION_AUTHORITY[key] is False
