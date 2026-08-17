from __future__ import annotations

import math

import pytest

from liquid_gas_transient.hne_thermodynamic_closure import (
    ACOUSTIC_AUTHORITY,
    FORMAL_STATUS,
    ExactRelaxationThermodynamicSource,
    HNEThermodynamicClosureError,
    SurrogateFrozenQualityThermodynamicClosure,
)


def _constructed_equilibrium_state(q_eq: float = 0.2, temperature_K: float = 260.0):
    closure = SurrogateFrozenQualityThermodynamicClosure()
    backend = closure.backend
    rho = 1.0 / (
        (1.0 - q_eq) / backend.rho_l_ref_kg_m3
        + q_eq / backend.rho_v_ref_kg_m3
    )
    cv_mix = (
        (1.0 - q_eq) * backend.cv_liquid_j_kgK
        + q_eq * backend.cv_vapor_j_kgK
    )
    e = (
        backend.e_l_ref_j_kg
        + q_eq * backend.latent_heat_ref_j_kg
        + cv_mix * (temperature_K - backend.T_sat_ref_K)
    )
    return closure, rho, e


def test_constructed_equilibrium_limit_recovers_surrogate_hem_state() -> None:
    closure, rho, e = _constructed_equilibrium_state()
    hem = closure.backend.state_from_rho_e(rho, e)
    q_eq = float(hem.quality)
    state = closure.evaluate(rho, e, q_eq)

    assert state.vapor_mass_fraction == pytest.approx(q_eq, abs=0.0)
    assert state.pressure_pa == pytest.approx(float(hem.p), rel=0.0, abs=1.0e-9)
    assert state.temperature_K == pytest.approx(float(hem.T), rel=0.0, abs=1.0e-12)
    assert state.void_fraction == pytest.approx(float(hem.alpha), rel=0.0, abs=1.0e-12)
    assert state.acoustic_speed_diagnostic_m_s == pytest.approx(float(hem.c), rel=0.0, abs=0.0)
    assert state.acoustic_authority == ACOUSTIC_AUTHORITY


def test_independent_quality_feeds_back_to_thermodynamic_state() -> None:
    closure, rho, e = _constructed_equilibrium_state()
    low_q = closure.evaluate(rho, e, 0.05)
    high_q = closure.evaluate(rho, e, 0.40)

    assert low_q.rho_kg_m3 == high_q.rho_kg_m3 == rho
    assert low_q.e_j_kg == high_q.e_j_kg == e
    assert low_q.pressure_pa != pytest.approx(high_q.pressure_pa)
    assert low_q.temperature_K != pytest.approx(high_q.temperature_K)
    assert low_q.void_fraction != pytest.approx(high_q.void_fraction)
    assert low_q.acoustic_speed_diagnostic_m_s != pytest.approx(
        high_q.acoustic_speed_diagnostic_m_s
    )


def test_exact_relaxation_conserves_rho_and_internal_energy_and_bounds_q() -> None:
    closure, rho, e = _constructed_equilibrium_state()
    source = ExactRelaxationThermodynamicSource(closure=closure, tau_s=1.0e-4)
    result = source.advance(rho, e, vapor_mass_fraction=0.0, dt_s=1.0e-5)

    assert result.after.vapor_mass_fraction > 0.0
    assert result.after.vapor_mass_fraction < result.equilibrium_vapor_mass_fraction
    assert 0.0 <= result.after.vapor_mass_fraction <= 1.0
    assert result.mass_density_residual_kg_m3 == 0.0
    assert result.specific_internal_energy_residual_j_kg == 0.0
    assert result.after.pressure_pa != pytest.approx(result.before.pressure_pa)
    assert result.after.temperature_K != pytest.approx(result.before.temperature_K)


def test_tau_to_zero_recovers_constructed_equilibrium_and_tau_infinity_freezes_q() -> None:
    closure, rho, e = _constructed_equilibrium_state()
    hem = closure.backend.state_from_rho_e(rho, e)

    stiff = ExactRelaxationThermodynamicSource(closure=closure, tau_s=1.0e-12)
    relaxed = stiff.advance(rho, e, vapor_mass_fraction=0.0, dt_s=1.0e-4)
    assert relaxed.relaxation_factor == 0.0
    assert relaxed.after.vapor_mass_fraction == pytest.approx(float(hem.quality), abs=0.0)
    assert relaxed.after.pressure_pa == pytest.approx(float(hem.p), rel=0.0, abs=1.0e-9)
    assert relaxed.after.temperature_K == pytest.approx(float(hem.T), rel=0.0, abs=1.0e-12)

    frozen = ExactRelaxationThermodynamicSource(closure=closure, tau_s=math.inf)
    frozen_result = frozen.advance(rho, e, vapor_mass_fraction=0.07, dt_s=1.0)
    assert frozen_result.relaxation_factor == 1.0
    assert frozen_result.dt_over_tau == 0.0
    assert frozen_result.after == frozen_result.before


def test_fail_closed_guards_and_maturity_boundary() -> None:
    closure, rho, e = _constructed_equilibrium_state()
    with pytest.raises(HNEThermodynamicClosureError):
        closure.evaluate(0.0, e, 0.2)
    with pytest.raises(HNEThermodynamicClosureError):
        closure.evaluate(rho, e, -1.0e-3)
    with pytest.raises(HNEThermodynamicClosureError):
        closure.evaluate(rho, e, 1.001)
    with pytest.raises(HNEThermodynamicClosureError):
        closure.evaluate(rho, -1.0e9, 0.2)
    with pytest.raises(ValueError):
        ExactRelaxationThermodynamicSource(closure=closure, tau_s=0.0)
    source = ExactRelaxationThermodynamicSource(closure=closure, tau_s=1.0e-4)
    with pytest.raises(HNEThermodynamicClosureError):
        source.advance(rho, e, 0.2, dt_s=-1.0)

    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["source_only_thermodynamic_feedback_prototype"] is True
    for key in (
        "physical_hne_vertical_slice",
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False
