from __future__ import annotations

import math
from pathlib import Path

import pytest

from liquid_gas_transient.u3_b1_critical_state_reference import (
    CRITICAL_SEARCH_NOT_BRACKETED,
    NONFINITE_INPUT,
    NONPOSITIVE_KINETIC_ENERGY_HEAD,
    CandidateState,
    ReferenceInput,
    UpstreamState,
    construct_result,
    critical_search,
    evaluate_case,
    golden_section_maximize,
    load_contract,
    normalize_phase,
)

CONTRACT = Path("docs/verification/stage7_u3_b1_critical_state_contract_v1.json")


class AnalyticProvider:
    version = "analytic"

    def saturation_temperature(self, pressure_pa: float) -> float:
        return 300.0

    def upstream_snapshot(
        self, pressure_pa: float, temperature_K: float
    ) -> UpstreamState:
        if pressure_pa == 1.0e6:
            return UpstreamState(
                pressure_pa=pressure_pa,
                temperature_K=temperature_K,
                density_kg_m3=1.0,
                enthalpy_J_kg=1.0,
                entropy_J_kg_K=1.0,
                phase="gas",
            )
        return UpstreamState(
            pressure_pa=pressure_pa,
            temperature_K=temperature_K,
            density_kg_m3=10.0,
            enthalpy_J_kg=100000.0,
            entropy_J_kg_K=2.0,
            phase="liquid" if temperature_K < 300.0 else "gas",
        )

    def isentropic_candidate(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> CandidateState:
        if entropy_J_kg_K == 1.0:
            ratio = pressure_pa / 1.0e6
            return CandidateState(
                pressure_pa=pressure_pa,
                temperature_K=250.0 + 70.0 * ratio,
                density_kg_m3=ratio,
                enthalpy_J_kg=ratio,
                entropy_J_kg_K=1.0,
                phase="gas",
            )
        delta_p = 5.0e6 - pressure_pa
        return CandidateState(
            pressure_pa=pressure_pa,
            temperature_K=295.0,
            density_kg_m3=10.0,
            enthalpy_J_kg=100000.0 - delta_p / 10.0,
            entropy_J_kg_K=2.0,
            phase="liquid",
        )


def test_contract_is_locked_before_results() -> None:
    contract = load_contract(CONTRACT)
    assert contract["approval_boundary"]["u3_b1_contract_locked"] is True
    assert contract["approval_boundary"]["u3_b1_reference_implemented"] is False
    assert len(contract["benchmark_cases"]) == 17


def test_phase_normalization() -> None:
    assert normalize_phase("supercritical_gas") == "supercriticalgas"
    assert normalize_phase("Two Phase") == "twophase"


def test_golden_section_maximization_is_deterministic() -> None:
    pressure, value, iterations, width = golden_section_maximize(
        lambda x: -(x - 3.0) ** 2 + 7.0,
        0.0,
        8.0,
        1e-8,
        128,
    )
    assert pressure == pytest.approx(3.0, abs=1e-6)
    assert value == pytest.approx(7.0, abs=1e-10)
    assert iterations > 0
    assert width <= 1e-8


def test_analytic_critical_search_finds_interior_maximum() -> None:
    contract = load_contract(CONTRACT)
    provider = AnalyticProvider()
    upstream = provider.upstream_snapshot(1.0e6, 320.0)
    critical, records, outcome, message = critical_search(
        contract,
        provider,
        upstream,
        {"gas"},
        0.8,
    )
    assert outcome is None, message
    assert critical is not None
    assert critical.pressure_ratio == pytest.approx(2.0 / 3.0, abs=5e-5)
    assert 0 < critical.coarse_index < len(records) - 1
    assert critical.final_bracket_width_pa <= 1.0
    assert critical.peak_prominence_relative >= 1e-8


def test_synthetic_guards_are_explicit() -> None:
    contract = load_contract(CONTRACT)
    provider = AnalyticProvider()
    rows = {row["case_id"]: row for row in contract["benchmark_cases"]}
    critical_cache = {}
    candidates: list[dict[str, object]] = []

    nonfinite = evaluate_case(
        contract,
        provider,
        rows["G-02_NONFINITE_INPUT"],
        critical_cache=critical_cache,
        candidate_records=candidates,
    )
    kinetic = evaluate_case(
        contract,
        provider,
        rows["G-04_NONPOSITIVE_KINETIC_ENERGY_HEAD"],
        critical_cache=critical_cache,
        candidate_records=candidates,
    )
    bracket = evaluate_case(
        contract,
        provider,
        rows["G-05_CRITICAL_SEARCH_NOT_BRACKETED"],
        critical_cache=critical_cache,
        candidate_records=candidates,
    )
    assert nonfinite.formal_outcome == NONFINITE_INPUT
    assert kinetic.formal_outcome == NONPOSITIVE_KINETIC_ENERGY_HEAD
    assert bracket.formal_outcome == CRITICAL_SEARCH_NOT_BRACKETED


def test_transfer_construction_uses_effective_stream_velocity() -> None:
    upstream = UpstreamState(1.0e6, 320.0, 4.0, 200000.0, 1000.0, "gas")
    candidate = CandidateState(8.0e5, 300.0, 3.0, 195000.0, 1000.0, "gas")
    from liquid_gas_transient.u3_b1_critical_state_reference import StreamState

    stream = StreamState(
        candidate=candidate,
        kinetic_energy_head_J_kg=5000.0,
        ideal_velocity_m_s=100.0,
        effective_velocity_m_s=80.0,
        ideal_mass_flux_kg_m2_s=300.0,
        effective_mass_flux_kg_m2_s=240.0,
        entropy_residual_J_kg_K=0.0,
    )
    inputs = ReferenceInput(
        case_id="unit",
        state_id="GAS_CRITICAL",
        upstream_pressure_pa=1.0e6,
        upstream_temperature_K=320.0,
        back_pressure_pa=8.0e5,
        reference_area_m2=1.0e-4,
        opening_fraction=0.5,
        discharge_coefficient=0.8,
    )
    result = construct_result(inputs, upstream, stream, "SUCCESS_UNCHOKED_SINGLE_PHASE_DISCHARGE", None)
    expected_mass = 5.0e-5 * 240.0
    assert result.mass_transfer_outward_kg_s == pytest.approx(expected_mass)
    assert result.momentum_stream_transfer_outward_N == pytest.approx(expected_mass * 80.0)
    assert result.energy_transfer_outward_W == pytest.approx(expected_mass * 200000.0)
    assert result.static_pressure_force_included is False
    assert result.production_fvm_connected is False
