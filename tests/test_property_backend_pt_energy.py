from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.properties import CoolPropCO2Backend, SurrogateLCO2PropertyBackend


class NoSaturationCoolPropBackend(CoolPropCO2Backend):
    def saturation_state(self, p):  # type: ignore[no-untyped-def]
        raise AssertionError("saturation_state must not be called for endpoint qualities")


def test_coolprop_alpha_endpoint_qualities_do_not_call_saturation_state() -> None:
    backend = NoSaturationCoolPropBackend()

    alpha = backend._alpha_from_quality_pressure(
        quality=np.array([0.0, 1.0]),
        p=np.array([8.0e6, 8.0e6]),
    )

    np.testing.assert_allclose(alpha, np.array([0.0, 1.0]), rtol=0.0, atol=0.0)
    assert np.all(np.isfinite(alpha))


def test_surrogate_internal_energy_from_pT_round_trips_temperature() -> None:
    backend = SurrogateLCO2PropertyBackend()
    p = np.array([1.9e6, 8.0e6])
    T = np.array([253.15, 280.0])

    rho = backend.density_from_pT(p, T)
    e = backend.internal_energy_from_pT(p, T)
    state = backend.state_from_rho_e(rho, e)

    assert np.all(np.isfinite(rho))
    assert np.all(np.isfinite(e))
    assert np.all(np.isfinite(state.p))
    assert np.all(np.isfinite(state.T))
    assert np.all(np.isfinite(state.c))
    assert np.all(rho > 0.0)
    assert np.all(state.c > 0.0)
    np.testing.assert_allclose(state.T, T, rtol=1.0e-12, atol=1.0e-12)
