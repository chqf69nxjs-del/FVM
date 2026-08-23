from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.flux import observe_rusanov_flux
from liquid_gas_transient.hne_equilibrium_acoustic_closure import (
    recover_equilibrium_state,
    state_from_pressure_quality,
)
from liquid_gas_transient.hne_limited_interior_coupling_facade import (
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    IMPLEMENTATION_AUTHORITY,
    NEXT_ACTION,
    OUTPUT_FILES,
    PROPERTY_BACKEND_NAME,
    SCHEMA_VERSION,
    SOURCE_AUTHORITY_GATE_RUN_ID,
    SOURCE_AUTHORITY_GATE_SHA,
    AcousticCompatibleHNEVerificationEOS,
    HNEAcousticAuthorityGateError,
    InteriorCouplingConfig,
    analyze_limited_interior_coupling,
    build_candidate_solver,
    write_artifacts,
)
from liquid_gas_transient.state import (
    IDX_RHO,
    IDX_RHO_XV,
    internal_energy,
    vapor_mass_fraction,
)


@lru_cache(maxsize=1)
def _default_analysis():
    return analyze_limited_interior_coupling()


def _case(case_id: str) -> dict[str, object]:
    analysis = _default_analysis()
    return next(row for row in analysis.case_rows if row["case_id"] == case_id)


def test_contract_source_pin_and_pre_execution_maturity_boundary() -> None:
    assert SCHEMA_VERSION == "stage7_p2_hne_limited_interior_coupling_a3_1_v1"
    assert SOURCE_AUTHORITY_GATE_SHA == "d4c1daf4db9c6e367a75d77c6660f417a9aee061"
    assert SOURCE_AUTHORITY_GATE_RUN_ID == 32629047962
    assert PROPERTY_BACKEND_NAME == "surrogate_lco2"
    assert len(OUTPUT_FILES) == 5
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["limited_interior_hne_hydrodynamic_coupling"] is False
    assert FORMAL_STATUS["working_vertical_slice"] is False
    for key in (
        "finite_pipeline_hne_coupling",
        "boundary_characteristics_authorized",
        "critical_discharge_authorized",
        "discharge_feedback_authorized",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False
    assert FORMAL_OUTCOME == (
        "P2_A3_1_LIMITED_INTERIOR_HNE_COUPLING_WORKING_VERTICAL_SLICE_"
        "WITH_BOUNDARY_AND_DISCHARGE_AUTHORITY_CLOSED"
    )
    assert NEXT_ACTION == "PROCEED_TO_P2_A3_2_CONTROLLED_FINITE_PIPE_HNE_COUPLING"

    assert IMPLEMENTATION_AUTHORITY[
        "candidate_pressure_to_dedicated_interior_euler_flux"
    ] is True
    assert IMPLEMENTATION_AUTHORITY[
        "candidate_frozen_c_to_dedicated_interior_rusanov"
    ] is True
    assert IMPLEMENTATION_AUTHORITY[
        "candidate_frozen_c_to_dedicated_interior_cfl"
    ] is True
    for key in (
        "existing_production_default_path_modified",
        "equilibrium_c_to_solver",
        "finite_relaxation_phase_speed_to_solver",
        "hne_boundary_characteristics",
        "hne_critical_discharge",
        "finite_pipe_discharge_feedback",
        "design_use",
        "production_use",
    ):
        assert IMPLEMENTATION_AUTHORITY[key] is False


def test_candidate_pressure_frozen_c_cfl_and_rusanov_are_active_together() -> None:
    config = InteriorCouplingConfig(n_cells=80)
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    solver = build_candidate_solver(config, actual_quality=actual_q, tau_s=math.inf)
    source = state_from_pressure_quality(
        config.base_pressure_pa,
        config.equilibrium_quality,
    )
    candidate = solver.eos.evaluate(source.rho_kg_m3, source.e_j_kg, actual_q)
    primitive = solver.primitive()
    assert np.array_equal(
        primitive.p,
        np.full(config.n_cells, candidate.pressure_pa),
    )
    assert np.array_equal(
        primitive.c,
        np.full(config.n_cells, candidate.frozen_c_m_s),
    )

    expected_dt = config.cfl * solver.grid.dx / (
        abs(config.base_velocity_m_s) + candidate.frozen_c_m_s
    )
    assert solver.compute_dt() == pytest.approx(expected_dt, rel=0.0, abs=1.0e-15)

    observations = []
    with observe_rusanov_flux(observations.append):
        solver._base_fluxes()
    assert len(observations) == 1
    expected_smax = abs(config.base_velocity_m_s) + candidate.frozen_c_m_s
    assert np.allclose(
        observations[0].maximum_wave_speed,
        expected_smax,
        rtol=0.0,
        atol=1.0e-12,
    )


def test_uniform_nonequilibrium_state_is_preserved_by_coupled_interior_step() -> None:
    config = InteriorCouplingConfig(n_cells=80)
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    solver = build_candidate_solver(config, actual_quality=actual_q, tau_s=math.inf)
    initial = solver.U.copy()
    for _ in range(6):
        solver.step(float(solver.compute_dt()))
    assert solver.step_count == 6
    assert np.array_equal(solver.U, initial)


def test_tau_infinity_recovers_exact_frozen_no_phase_change_limit() -> None:
    row = _case("TAU_INFINITY_FROZEN_LIMIT")
    assert row["trajectory_bitwise_equal_to_no_phase_change"] is True
    assert row["candidate_final_state_sha256"] == row["reference_final_state_sha256"]


def test_tau_near_zero_recovers_declared_equilibrium_map_without_hydro_damage() -> None:
    row = _case("TAU_NEAR_ZERO_EQUILIBRIUM_LIMIT")
    assert float(row["maximum_equilibrium_quality_error"]) <= 1.0e-15
    assert row["hydrodynamic_state_unchanged_by_uniform_step_and_relaxation"] is True
    assert row["candidate_pressure_recovers_equilibrium_pressure"] is True
    assert row["candidate_temperature_recovers_equilibrium_temperature"] is True

    config = InteriorCouplingConfig(n_cells=80)
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    solver = build_candidate_solver(config, actual_quality=actual_q, tau_s=1.0e-18)
    rho = float(solver.U[0, IDX_RHO])
    e = float(internal_energy(solver.U)[0])
    expected = recover_equilibrium_state(rho, e)
    hydro_before = solver.U[..., :IDX_RHO_XV].copy()
    solver.step(float(solver.compute_dt()))
    assert np.array_equal(solver.U[..., :IDX_RHO_XV], hydro_before)
    assert np.max(
        np.abs(vapor_mass_fraction(solver.U) - expected.vapor_mass_fraction)
    ) <= 1.0e-15


def test_small_amplitude_pressure_pulse_propagates_at_frozen_speed() -> None:
    row = _case("SMALL_AMPLITUDE_PRESSURE_PULSE")
    assert row["wave_speed_within_focused_tolerance"] is True
    assert float(row["relative_wave_speed_error"]) <= 0.20
    assert float(row["left_right_speed_symmetry_relative_error"]) <= 0.05
    assert row["pulse_remained_inside_domain"] is True
    assert int(row["solver_step_count"]) > 0


def test_full_p2_a3_1_gate_passes_without_boundary_or_discharge_authority() -> None:
    analysis = _default_analysis()
    summary = analysis.summary
    assert summary["p2_a3_1_limited_interior_coupling_ready"] is True
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert len(analysis.case_rows) == 4
    assert len(analysis.pulse_rows) > 2
    assert summary["formal_status"][
        "limited_interior_hne_hydrodynamic_coupling"
    ] is True
    assert summary["formal_status"]["working_vertical_slice"] is True
    assert summary["existing_production_default_path_modified"] is False
    assert summary["boundary_characteristics_authorized"] is False
    assert summary["critical_discharge_authorized"] is False
    assert summary["discharge_feedback_authorized"] is False
    assert summary["physically_validated"] is False
    assert summary["next_action"] == NEXT_ACTION
    for key in (
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert summary["formal_status"][key] is False


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
    assert summary["p2_a3_1_limited_interior_coupling_ready"] is True
    assert manifest["p2_a3_1_limited_interior_coupling_ready"] is True
    assert manifest["analysis_sha256"] == summary["analysis_sha256"]
    assert manifest["existing_production_default_path_modified"] is False
    assert manifest["boundary_characteristics_authorized"] is False
    assert manifest["critical_discharge_authorized"] is False
    assert manifest["discharge_feedback_authorized"] is False
    assert f"Property backend: `{PROPERTY_BACKEND_NAME}`" in report
    assert f"Next action: `{NEXT_ACTION}`" in report


def test_candidate_eos_fails_closed_outside_open_quality_domain() -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    source = state_from_pressure_quality(2.5e6, 0.10)
    with pytest.raises(HNEAcousticAuthorityGateError):
        eos.evaluate(source.rho_kg_m3, source.e_j_kg, 0.02)
    with pytest.raises(HNEAcousticAuthorityGateError):
        eos.evaluate(source.rho_kg_m3, source.e_j_kg, 0.45)
