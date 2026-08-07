from __future__ import annotations

import math
from pathlib import Path

import pytest

from liquid_gas_transient.u3_b2_fvm_discharge_coupling_reference import (
    ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
    BOUNDARY_UPDATE_POSITIVITY_FAILURE,
    INVENTORY_ORIENTATION_CONTRACT_MISMATCH,
    NONFINITE_INPUT,
    REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
    STAGNATION_RECONSTRUCTION_FAILURE,
    B1Transfer,
    StaticState,
    StagnationState,
    acoustic_arrival_rows,
    build_inventory_ledger,
    evaluate_face_reference,
    interpolate_probe,
    load_contracts,
    locked_checks,
    one_step_reference,
    probe_map,
)

CONTRACT = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
)
EXTENSION = Path(
    "docs/verification/"
    "stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1.json"
)


class AnalyticPropertyProvider:
    version = "analytic"

    def saturation_temperature(self, pressure_pa: float) -> float:
        assert pressure_pa == 5.0e6
        return 300.0

    def static_from_pt(
        self, pressure_pa: float, temperature_K: float, velocity_m_s: float
    ) -> StaticState:
        if pressure_pa == 5.0e6:
            phase = "liquid" if temperature_K < 300.0 else "gas"
            rho = 10.0
            e = 100000.0
            h = 600000.0
            s = 2000.0
            c = 500.0
        else:
            phase = "gas"
            rho = 5.0
            e = 200000.0
            h = 400000.0
            s = 1000.0
            c = 300.0
        return StaticState(
            pressure_pa=pressure_pa,
            temperature_K=temperature_K,
            density_kg_m3=rho,
            internal_energy_J_kg=e,
            enthalpy_J_kg=h,
            entropy_J_kg_K=s,
            sound_speed_m_s=c,
            phase=phase,
            velocity_m_s=velocity_m_s,
        )

    def static_from_rhoe(
        self, density_kg_m3: float, internal_energy_J_kg: float, velocity_m_s: float
    ) -> StaticState:
        if density_kg_m3 == 10.0:
            return StaticState(
                pressure_pa=5.0e6,
                temperature_K=295.0,
                density_kg_m3=density_kg_m3,
                internal_energy_J_kg=internal_energy_J_kg,
                enthalpy_J_kg=600000.0,
                entropy_J_kg_K=2000.0,
                sound_speed_m_s=500.0,
                phase="liquid",
                velocity_m_s=velocity_m_s,
            )
        return StaticState(
            pressure_pa=1.0e6,
            temperature_K=320.0,
            density_kg_m3=density_kg_m3,
            internal_energy_J_kg=internal_energy_J_kg,
            enthalpy_J_kg=400000.0,
            entropy_J_kg_K=1000.0,
            sound_speed_m_s=300.0,
            phase="gas",
            velocity_m_s=velocity_m_s,
        )

    def stagnation_from_hs(
        self, enthalpy_J_kg: float, entropy_J_kg_K: float
    ) -> StagnationState:
        pressure = 5.0e6 if entropy_J_kg_K == 2000.0 else 1.0e6
        temperature = 295.0 if pressure == 5.0e6 else 320.0
        phase = "liquid" if pressure == 5.0e6 else "gas"
        return StagnationState(
            pressure_pa=pressure,
            temperature_K=temperature,
            enthalpy_J_kg=enthalpy_J_kg,
            entropy_J_kg_K=entropy_J_kg_K,
            recovered_enthalpy_J_kg=enthalpy_J_kg,
            recovered_entropy_J_kg_K=entropy_J_kg_K,
            phase=phase,
        )


class AnalyticB1Authority:
    def evaluate(
        self,
        *,
        stagnation: StagnationState,
        external_back_pressure_pa: float,
        open_area_m2: float,
        discharge_coefficient: float,
        allowed_normalized_phases: set[str],
        critical_search_required: bool,
    ) -> B1Transfer:
        assert allowed_normalized_phases
        critical_pressure = 0.55 * stagnation.pressure_pa if critical_search_required else None
        if critical_pressure is not None and external_back_pressure_pa <= critical_pressure + 1.0:
            evaluation_pressure = critical_pressure
            outcome = "SUCCESS_CHOKED_SINGLE_PHASE_DISCHARGE"
        else:
            evaluation_pressure = external_back_pressure_pa
            outcome = "SUCCESS_UNCHOKED_SINGLE_PHASE_DISCHARGE"
        rho = 5.0 if critical_search_required else 10.0
        head = max(stagnation.pressure_pa - evaluation_pressure, 0.0) / rho
        ideal_velocity = math.sqrt(2.0 * head)
        effective_velocity = discharge_coefficient * ideal_velocity
        ideal_mass_flux = rho * ideal_velocity
        effective_mass_flux = rho * effective_velocity
        mass = open_area_m2 * effective_mass_flux
        advective = mass * effective_velocity
        energy = mass * stagnation.enthalpy_J_kg
        return B1Transfer(
            formal_outcome=outcome,
            evaluation_pressure_pa=evaluation_pressure,
            critical_pressure_pa=critical_pressure,
            critical_pressure_ratio=(
                None
                if critical_pressure is None
                else critical_pressure / stagnation.pressure_pa
            ),
            candidate_temperature_K=280.0,
            candidate_density_kg_m3=rho,
            candidate_phase="gas" if critical_search_required else "liquid",
            ideal_velocity_m_s=ideal_velocity,
            effective_velocity_m_s=effective_velocity,
            ideal_mass_flux_kg_m2_s=ideal_mass_flux,
            effective_mass_flux_kg_m2_s=effective_mass_flux,
            mass_transfer_outward_kg_s=mass,
            advective_momentum_rate_outward_N=advective,
            energy_transfer_outward_W=energy,
        )


def evaluate_all():
    contract, extension = load_contracts(CONTRACT, EXTENSION)
    provider = AnalyticPropertyProvider()
    authority = AnalyticB1Authority()
    results = [
        evaluate_face_reference(contract, extension, row, provider, authority)
        for row in contract["benchmark_cases"]
    ]
    return contract, extension, results


def test_contracts_are_locked_and_reference_is_not_preapproved() -> None:
    contract, extension = load_contracts(CONTRACT, EXTENSION)
    assert contract["approval_boundary"]["u3_b2_contract_locked"] is True
    assert contract["approval_boundary"]["u3_b2_reference_implemented"] is False
    assert len(contract["benchmark_cases"]) == 26
    assert extension["acoustic_event_detection"]["unresolved_outcome"] == (
        "ACOUSTIC_EVENT_NOT_RESOLVED"
    )


def test_all_fixed_formal_outcomes_are_constructed() -> None:
    contract, _, results = evaluate_all()
    expected = {
        row["case_id"]: row["expected_outcome"]
        for row in contract["benchmark_cases"]
    }
    actual = {row.case_id: row.formal_outcome for row in results}
    assert actual == expected
    assert sum(row.succeeded for row in results) == 19
    assert sum(not row.succeeded for row in results) == 7


def test_closed_and_zero_drop_wall_identities_are_exact() -> None:
    _, _, results = evaluate_all()
    by_id = {row.case_id: row for row in results}
    for case_id in (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
    ):
        row = by_id[case_id]
        assert row.mass_transfer_outward_kg_s == 0.0
        assert row.advective_momentum_rate_outward_N == 0.0
        assert row.energy_transfer_outward_W == 0.0
        assert row.F_rho_kg_m2_s == 0.0
        assert row.F_rho_E_W_m2 == 0.0
        assert row.F_rho_xv_kg_m2_s == 0.0
        assert row.F_rho_u_pa == row.adjacent_pressure_pa


def test_face_pressure_decomposition_reconstructs_total_flux() -> None:
    _, _, results = evaluate_all()
    for row in results:
        if not row.succeeded:
            continue
        reconstructed = (
            row.advective_momentum_rate_outward_N
            + row.open_static_pressure_force_outward_N
            + row.closed_static_pressure_force_outward_N
        )
        assert row.total_momentum_rate_outward_N == pytest.approx(reconstructed)
        assert row.F_rho_u_pa == pytest.approx(
            row.total_momentum_rate_outward_N / row.pipe_area_m2
        )


def test_area_and_cd_scaling_are_distinct() -> None:
    _, _, results = evaluate_all()
    by_id = {row.case_id: row for row in results}
    area_low = by_id["B2-08A_AREA_SCALING_LOW"]
    area_high = by_id["B2-08B_AREA_SCALING_HIGH"]
    assert area_high.mass_transfer_outward_kg_s / area_low.mass_transfer_outward_kg_s == pytest.approx(2.0)
    assert area_high.energy_transfer_outward_W / area_low.energy_transfer_outward_W == pytest.approx(2.0)
    assert area_high.advective_momentum_rate_outward_N / area_low.advective_momentum_rate_outward_N == pytest.approx(2.0)

    cd_low = by_id["B2-08C_CD_SCALING_LOW"]
    cd_high = by_id["B2-08D_CD_SCALING_HIGH"]
    assert cd_high.mass_transfer_outward_kg_s / cd_low.mass_transfer_outward_kg_s == pytest.approx(2.0)
    assert cd_high.energy_transfer_outward_W / cd_low.energy_transfer_outward_W == pytest.approx(2.0)
    assert cd_high.advective_momentum_rate_outward_N / cd_low.advective_momentum_rate_outward_N == pytest.approx(4.0)
    assert cd_high.critical_pressure_pa == cd_low.critical_pressure_pa


def test_one_step_balance_and_ledger_close() -> None:
    contract, _, results = evaluate_all()
    by_id = {row.case_id: row for row in results}
    face = by_id["B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"]
    step = one_step_reference(contract, face)
    assert step.positivity_passed is True
    assert step.mass_inventory_residual_kg == pytest.approx(0.0, abs=1e-15)
    assert step.energy_inventory_residual_J == pytest.approx(0.0, abs=1e-12)
    assert step.momentum_inventory_residual_kg_m_s == pytest.approx(0.0, abs=1e-15)
    assert step.vapor_mass_kg == 0.0
    ledger = build_inventory_ledger(face, step)
    assert [row.step for row in ledger] == [0, 1]
    assert ledger[-1].cumulative_mass_out_kg == step.cumulative_mass_out_kg
    assert ledger[-1].pipe_mass_target_kg == step.final_pipe_mass_kg


def test_probe_mapping_and_affine_interpolation_are_mesh_invariant() -> None:
    contract, extension = load_contracts(CONTRACT, EXTENSION)
    for cells in contract["geometry"]["fixed_mesh_sequence"]:
        centers = [(index + 0.5) / cells for index in range(cells)]
        affine = [7.0 + 11.0 * xi for xi in centers]
        for probe in contract["acoustic_reference"]["probe_normalized_positions"]:
            mapping = probe_map(extension, cells, probe)
            assert mapping["interpolation_weight_right"] == 0.5
            assert interpolate_probe(affine, mapping) == pytest.approx(7.0 + 11.0 * probe)


def test_acoustic_arrival_order_uses_requested_probe_coordinates() -> None:
    contract, extension = load_contracts(CONTRACT, EXTENSION)
    rows = acoustic_arrival_rows(contract, extension, 500.0)
    assert len(rows) == 9
    rows32 = [row for row in rows if row.cells == 32]
    assert [
        row.probe_x_over_L for row in sorted(rows32, key=lambda item: item.direct_order_rank)
    ] == [0.75, 0.5, 0.25]
    assert [
        row.probe_x_over_L for row in sorted(rows32, key=lambda item: item.reflected_order_rank)
    ] == [0.25, 0.5, 0.75]
    probe = next(row for row in rows32 if row.probe_x_over_L == 0.75)
    assert probe.direct_arrival_time_s == pytest.approx((1.0 - 0.75) / 500.0)
    assert probe.reflected_arrival_time_s == pytest.approx((1.0 + 0.75) / 500.0)


def test_all_locked_reference_checks_pass_with_analytic_paths() -> None:
    contract, extension, results = evaluate_all()
    by_id = {row.case_id: row for row in results}
    step = one_step_reference(
        contract, by_id["B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"]
    )
    acoustic = acoustic_arrival_rows(contract, extension, 500.0)
    rows, summary = locked_checks(contract, extension, results, step, acoustic)
    assert rows
    assert summary["all_expected_outcomes_match"] is True
    assert summary["all_locked_checks_passed"] is True


def test_synthetic_guards_are_explicit_and_atomic() -> None:
    _, _, results = evaluate_all()
    by_id = {row.case_id: row for row in results}
    expected = {
        "G-01_REVERSE_PRESSURE": REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
        "G-02_REVERSE_ADJACENT_VELOCITY": REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
        "G-03_NONFINITE_ADJACENT_STATE": NONFINITE_INPUT,
        "G-04_SINGLE_PHASE_SCOPE_FAILURE": ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
        "G-05_STAGNATION_RECONSTRUCTION_FAILURE": STAGNATION_RECONSTRUCTION_FAILURE,
        "G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE": BOUNDARY_UPDATE_POSITIVITY_FAILURE,
        "G-07_INVENTORY_ORIENTATION_MISMATCH": INVENTORY_ORIENTATION_CONTRACT_MISMATCH,
    }
    for case_id, outcome in expected.items():
        row = by_id[case_id]
        assert row.formal_outcome == outcome
        assert row.succeeded is False
        assert row.mass_transfer_outward_kg_s == 0.0
        assert row.energy_transfer_outward_W == 0.0
