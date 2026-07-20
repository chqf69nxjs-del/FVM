from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_thermodynamics import (
    HEMThermodynamicConfig,
    HEMThermodynamicError,
    build_surrogate_zero_d_flash_path,
    classify_quality_regime,
    evaluate_hem_thermodynamic_state,
    write_zero_d_flash_artifacts,
)
from liquid_gas_transient.properties import (
    PropertyEvaluationError,
    PropertyState,
    SurrogateLCO2PropertyBackend,
)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quality_tolerance", -1.0),
        ("alpha_tolerance", -1.0),
        ("minimum_pressure_pa", -1.0),
        ("minimum_temperature_K", -1.0),
        ("minimum_reported_sound_speed_m_s", -1.0),
        ("quality_tolerance", np.nan),
    ],
)
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMThermodynamicConfig(**{field: value})


def test_quality_regime_classifies_endpoints_and_open_interval():
    quality = np.array([0.0, 1.0e-12, 0.25, 0.75, 1.0 - 1.0e-12, 1.0])
    regime = classify_quality_regime(quality, tolerance=1.0e-10)
    assert regime.tolist() == [
        "liquid_endpoint",
        "liquid_endpoint",
        "two_phase",
        "two_phase",
        "vapor_endpoint",
        "vapor_endpoint",
    ]


@pytest.mark.parametrize(
    "quality",
    [
        np.array([np.nan]),
        np.array([-1.0e-3]),
        np.array([1.001]),
    ],
)
def test_quality_regime_rejects_nonfinite_or_out_of_range_values(quality):
    with pytest.raises(HEMThermodynamicError):
        classify_quality_regime(quality)


class NegativeReferenceEnergyBackend:
    name = "negative_reference_energy"

    def state_from_rho_e(self, rho, e):  # type: ignore[no-untyped-def]
        rho_arr, e_arr = np.broadcast_arrays(
            np.asarray(rho, dtype=float),
            np.asarray(e, dtype=float),
        )
        return PropertyState(
            rho=rho_arr,
            p=np.full_like(rho_arr, 2.0e6),
            T=np.full_like(rho_arr, 250.0),
            e=e_arr,
            quality=np.full_like(rho_arr, 0.25),
            alpha=np.full_like(rho_arr, 0.80),
            c=np.full_like(rho_arr, 100.0),
        )


def test_real_fluid_validation_allows_finite_negative_reference_energy():
    state = evaluate_hem_thermodynamic_state(
        NegativeReferenceEnergyBackend(),
        rho=np.array([500.0]),
        e=np.array([-2.0e4]),
    )
    assert state.e[0] == pytest.approx(-2.0e4)
    assert state.quality_regime.tolist() == ["two_phase"]


class FailingBackend:
    name = "failing_backend"

    def state_from_rho_e(self, rho, e):  # type: ignore[no-untyped-def]
        raise PropertyEvaluationError("intentional")


def test_backend_property_failure_is_wrapped_with_context():
    with pytest.raises(HEMThermodynamicError, match="failing_backend"):
        evaluate_hem_thermodynamic_state(
            FailingBackend(),
            rho=np.array([500.0]),
            e=np.array([1.0e5]),
        )


def test_input_density_is_checked_before_backend_evaluation():
    with pytest.raises(HEMThermodynamicError, match="rho"):
        evaluate_hem_thermodynamic_state(
            FailingBackend(),
            rho=np.array([0.0]),
            e=np.array([1.0e5]),
        )


class InvalidQualityBackend(NegativeReferenceEnergyBackend):
    def state_from_rho_e(self, rho, e):  # type: ignore[no-untyped-def]
        state = super().state_from_rho_e(rho, e)
        return PropertyState(
            rho=state.rho,
            p=state.p,
            T=state.T,
            e=state.e,
            quality=np.full_like(state.quality, 1.2),
            alpha=state.alpha,
            c=state.c,
        )


def test_invalid_backend_quality_is_rejected():
    with pytest.raises(HEMThermodynamicError, match="quality"):
        evaluate_hem_thermodynamic_state(
            InvalidQualityBackend(),
            rho=np.array([500.0]),
            e=np.array([1.0e5]),
        )


def test_surrogate_zero_d_path_covers_liquid_two_phase_and_vapor():
    path = build_surrogate_zero_d_flash_path(n_two_phase_points=11)
    state = path.state

    assert state.backend_name == "surrogate_lco2"
    assert state.quality_regime[0] == "liquid_endpoint"
    assert "two_phase" in set(state.quality_regime.tolist())
    assert state.quality_regime[-1] == "vapor_endpoint"
    assert np.all(np.isfinite(state.p))
    assert np.all(np.isfinite(state.T))
    assert np.all(np.isfinite(state.reported_sound_speed))
    assert np.all(state.p > 0.0)
    assert np.all(state.T > 0.0)
    assert np.all(state.reported_sound_speed > 0.0)
    assert np.all(np.diff(state.quality) >= -1.0e-14)
    assert np.all(np.diff(state.alpha) >= -1.0e-14)
    assert np.all(np.diff(state.rho) < 0.0)
    assert np.all(np.diff(state.e) >= 0.0)


def test_evaluation_does_not_mutate_input_arrays():
    backend = SurrogateLCO2PropertyBackend()
    rho = np.array([900.0, 500.0, 50.0])
    e = np.array([1.0e5, 2.0e5, 3.0e5])
    rho_before = rho.copy()
    e_before = e.copy()

    state = evaluate_hem_thermodynamic_state(backend, rho, e)

    np.testing.assert_array_equal(rho, rho_before)
    np.testing.assert_array_equal(e, e_before)
    assert not np.shares_memory(state.rho, rho)
    assert not np.shares_memory(state.e, e)


def test_artifacts_are_traceable_and_keep_approval_flags_false(tmp_path):
    path = build_surrogate_zero_d_flash_path(n_two_phase_points=7)
    files = write_zero_d_flash_artifacts(tmp_path, path)

    assert set(files) == {"json", "csv", "markdown", "npz"}
    assert all(file.is_file() for file in files.values())

    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "stage7_lco2_hem_zero_d_flash_v1"
    assert payload["scope"] == "verification_only"
    assert payload["production_solver_connected"] is False
    assert payload["production_solver_behavior_changed"] is False
    assert payload["pure_co2_hem_thermodynamic_core_complete"] is False
    assert payload["equilibrium_two_phase_sound_speed_closure_approved"] is False
    assert payload["backend_reported_sound_speed_is_diagnostic_only"] is True
    assert payload["solid_phase_supported"] is False
    assert payload["critical_region_validated"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert payload["numeric_accuracy_band_approved"] is False
    assert len(payload["results"]) == 9

    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "VERIFICATION ONLY; NOT PRODUCTION ACTIVATION" in markdown
    assert "equilibrium two-phase sound-speed closure approved: `False`" in markdown
