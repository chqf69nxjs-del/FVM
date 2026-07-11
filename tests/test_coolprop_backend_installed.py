"""Installed-only API checks for the optional CoolProp CO2 backend."""

from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.properties import CoolPropCO2Backend, make_property_backend


# Compressed liquid CO2 condition selected away from saturation and the critical
# point to keep the installed-only API smoke checks numerically conservative.
LIQUID_CO2_PRESSURE_PA = 8.0e6
LIQUID_CO2_TEMPERATURE_K = 280.0


def _coolprop_props_si():
    coolprop = pytest.importorskip("CoolProp")
    return coolprop.CoolProp.PropsSI


def _coolprop_phase_si():
    coolprop = pytest.importorskip("CoolProp")
    return coolprop.CoolProp.PhaseSI


def test_coolprop_density_from_pT_returns_positive_finite_density() -> None:
    _coolprop_props_si()
    backend = CoolPropCO2Backend()

    rho = backend.density_from_pT(
        np.array([LIQUID_CO2_PRESSURE_PA]),
        np.array([LIQUID_CO2_TEMPERATURE_K]),
    )

    assert rho.shape == (1,)
    assert np.all(np.isfinite(rho))
    assert np.all(rho > 0.0)


def test_coolprop_state_from_rho_e_returns_finite_primary_state() -> None:
    props_si = _coolprop_props_si()
    backend = CoolPropCO2Backend()
    rho = props_si(
        "Dmass",
        "P",
        LIQUID_CO2_PRESSURE_PA,
        "T",
        LIQUID_CO2_TEMPERATURE_K,
        "CO2",
    )
    e = props_si(
        "Umass",
        "P",
        LIQUID_CO2_PRESSURE_PA,
        "T",
        LIQUID_CO2_TEMPERATURE_K,
        "CO2",
    )

    state = backend.state_from_rho_e(np.asarray(rho), np.asarray(e))

    assert np.all(np.isfinite(state.p))
    assert np.all(np.isfinite(state.T))
    assert np.all(np.isfinite(state.rho))
    assert np.all(np.isfinite(state.e))
    assert np.all(np.isfinite(state.c))
    np.testing.assert_allclose(state.p, LIQUID_CO2_PRESSURE_PA, rtol=5.0e-3)
    np.testing.assert_allclose(state.T, LIQUID_CO2_TEMPERATURE_K, rtol=5.0e-3)


def test_coolprop_factory_returns_coolprop_backend_when_installed() -> None:
    _coolprop_props_si()

    backend = make_property_backend("coolprop_co2")

    assert isinstance(backend, CoolPropCO2Backend)


def test_coolprop_internal_energy_from_pT_round_trips_dense_single_phase_state() -> None:
    _coolprop_props_si()
    backend = CoolPropCO2Backend()

    rho = backend.density_from_pT(
        np.array([LIQUID_CO2_PRESSURE_PA]),
        np.array([LIQUID_CO2_TEMPERATURE_K]),
    )
    e = backend.internal_energy_from_pT(
        np.array([LIQUID_CO2_PRESSURE_PA]),
        np.array([LIQUID_CO2_TEMPERATURE_K]),
    )

    state = backend.state_from_rho_e(rho, e)

    assert np.all(np.isfinite(state.p))
    assert np.all(np.isfinite(state.T))
    assert np.all(np.isfinite(state.rho))
    assert np.all(np.isfinite(state.e))
    assert np.all(np.isfinite(state.c))
    assert np.all(np.isfinite(state.alpha))
    assert np.all(np.isfinite(state.quality))
    np.testing.assert_allclose(state.p, LIQUID_CO2_PRESSURE_PA, rtol=5.0e-3)
    np.testing.assert_allclose(state.T, LIQUID_CO2_TEMPERATURE_K, rtol=5.0e-3)
    np.testing.assert_allclose(state.quality, 0.0, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(state.alpha, 0.0, rtol=0.0, atol=0.0)
    assert np.all(state.c > 0.0)


def test_coolprop_subcritical_liquid_state_reports_zero_quality_and_alpha() -> None:
    phase_si = _coolprop_phase_si()
    backend = CoolPropCO2Backend()
    pressure_pa = 5.0e6
    temperature_k = 280.0

    phase = phase_si("P", pressure_pa, "T", temperature_k, "CO2")
    assert phase.lower() == "liquid"
    rho = backend.density_from_pT(np.array([pressure_pa]), np.array([temperature_k]))
    e = backend.internal_energy_from_pT(np.array([pressure_pa]), np.array([temperature_k]))

    state = backend.state_from_rho_e(rho, e)

    assert np.all(np.isfinite(state.rho))
    assert np.all(np.isfinite(state.e))
    assert np.all(np.isfinite(state.c))
    np.testing.assert_allclose(state.p, pressure_pa, rtol=5.0e-3)
    np.testing.assert_allclose(state.T, temperature_k, rtol=5.0e-3)
    np.testing.assert_allclose(state.quality, 0.0, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(state.alpha, 0.0, rtol=0.0, atol=0.0)
