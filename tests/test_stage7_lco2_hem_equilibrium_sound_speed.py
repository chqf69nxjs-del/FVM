from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedConfig,
    HEMEquilibriumSoundSpeedError,
    PressurePhaseSample,
    build_representative_equilibrium_sound_speed_map,
    estimate_coolprop_equilibrium_sound_speed,
    estimate_equilibrium_sound_speed,
    write_equilibrium_sound_speed_artifacts,
)


def _supported_sample(pressure: float, phase: str = "analytic") -> PressurePhaseSample:
    return PressurePhaseSample(
        pressure_pa=pressure,
        phase_class=phase,
        scope_status="supported_candidate",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("relative_density_step", 0.0),
        ("relative_energy_step", -1.0),
        ("minimum_density_step_kg_m3", 0.0),
        ("minimum_energy_step_j_kg", np.nan),
        ("max_step_halvings", -1),
        ("minimum_sound_speed_squared_m2_s2", -1.0),
    ],
)
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMEquilibriumSoundSpeedConfig(**{field: value})


def test_ideal_gas_identity_matches_analytic_sound_speed():
    gamma = 1.4
    rho = 3.0
    e = 2.5e5

    def evaluator(rho_value: float, e_value: float) -> PressurePhaseSample:
        pressure = (gamma - 1.0) * rho_value * e_value
        return _supported_sample(pressure)

    estimate = estimate_equilibrium_sound_speed(rho, e, evaluator)
    expected_c_squared = gamma * (gamma - 1.0) * e

    assert estimate.sound_speed_squared_m2_s2 == pytest.approx(
        expected_c_squared, rel=2.0e-9
    )
    assert estimate.sound_speed_m_s == pytest.approx(
        np.sqrt(expected_c_squared), rel=1.0e-9
    )
    assert estimate.density_term_m2_s2 == pytest.approx((gamma - 1.0) * e)
    assert estimate.energy_term_m2_s2 == pytest.approx(
        (gamma - 1.0) ** 2 * e
    )


def test_adaptive_stencil_halves_until_phase_class_is_preserved():
    center_rho = 10.0

    def evaluator(rho_value: float, e_value: float) -> PressurePhaseSample:
        phase = "target" if abs(rho_value - center_rho) <= 0.5 else "other"
        return _supported_sample(1.0e6 + 1.0e4 * rho_value + 2.0 * e_value, phase)

    estimate = estimate_equilibrium_sound_speed(
        center_rho,
        1.0e5,
        evaluator,
        config=HEMEquilibriumSoundSpeedConfig(
            relative_density_step=0.2,
            relative_energy_step=1.0e-4,
            max_step_halvings=6,
        ),
    )

    assert estimate.density_step_halvings >= 2
    assert estimate.stencil_phase_preserved is True
    assert estimate.sound_speed_m_s > 0.0


def test_unsupported_center_state_is_rejected():
    def evaluator(rho_value: float, e_value: float) -> PressurePhaseSample:
        return PressurePhaseSample(
            pressure_pa=1.0e6,
            phase_class="critical_region",
            scope_status="guarded_out",
        )

    with pytest.raises(HEMEquilibriumSoundSpeedError, match="outside"):
        estimate_equilibrium_sound_speed(10.0, 1.0e5, evaluator)


def test_nonpositive_sound_speed_squared_is_rejected():
    def evaluator(rho_value: float, e_value: float) -> PressurePhaseSample:
        pressure = 2.0e6 - 1.0e4 * rho_value
        return _supported_sample(pressure)

    with pytest.raises(HEMEquilibriumSoundSpeedError, match="non-positive"):
        estimate_equilibrium_sound_speed(10.0, 1.0e5, evaluator)


@pytest.mark.parametrize(
    ("rho", "e"),
    [(0.0, 1.0e5), (-1.0, 1.0e5), (1.0, np.nan)],
)
def test_invalid_center_inputs_are_rejected(rho, e):
    with pytest.raises(HEMEquilibriumSoundSpeedError):
        estimate_equilibrium_sound_speed(
            rho, e, lambda r, u: _supported_sample(1.0e6)
        )


def _coolprop_props_si():
    coolprop = pytest.importorskip("CoolProp")
    return coolprop.CoolProp.PropsSI


@pytest.mark.parametrize(
    ("pressure_pa", "temperature_K"),
    [(8.0e6, 280.0), (5.0e6, 280.0), (1.0e6, 280.0)],
)
def test_coolprop_single_phase_estimate_matches_backend_reference(
    pressure_pa, temperature_K
):
    props_si = _coolprop_props_si()
    rho = float(props_si("Dmass", "P", pressure_pa, "T", temperature_K, "CO2"))
    e = float(props_si("Umass", "P", pressure_pa, "T", temperature_K, "CO2"))
    reference = float(props_si("A", "Dmass", rho, "Umass", e, "CO2"))

    estimate = estimate_coolprop_equilibrium_sound_speed(rho, e)

    assert estimate.sound_speed_m_s > 0.0
    assert estimate.sound_speed_m_s == pytest.approx(reference, rel=1.0e-2)


@pytest.mark.parametrize("quality", [0.05, 0.10, 0.50, 0.90, 0.95])
def test_coolprop_open_two_phase_estimate_is_positive_and_phase_preserving(quality):
    props_si = _coolprop_props_si()
    rho = float(props_si("Dmass", "P", 2.0e6, "Q", quality, "CO2"))
    e = float(props_si("Umass", "P", 2.0e6, "Q", quality, "CO2"))

    estimate = estimate_coolprop_equilibrium_sound_speed(rho, e)

    assert estimate.phase_class == "liquid_vapor_two_phase"
    assert estimate.sound_speed_m_s > 0.0
    assert np.isfinite(estimate.dp_drho_at_e)
    assert np.isfinite(estimate.dp_de_at_rho)
    assert estimate.stencil_phase_preserved is True


def test_two_phase_estimate_is_stable_to_moderate_step_refinement():
    props_si = _coolprop_props_si()
    rho = float(props_si("Dmass", "P", 2.0e6, "Q", 0.50, "CO2"))
    e = float(props_si("Umass", "P", 2.0e6, "Q", 0.50, "CO2"))

    coarse = estimate_coolprop_equilibrium_sound_speed(
        rho,
        e,
        config=HEMEquilibriumSoundSpeedConfig(
            relative_density_step=2.0e-4,
            relative_energy_step=2.0e-4,
        ),
    )
    fine = estimate_coolprop_equilibrium_sound_speed(
        rho,
        e,
        config=HEMEquilibriumSoundSpeedConfig(
            relative_density_step=1.0e-4,
            relative_energy_step=1.0e-4,
        ),
    )

    assert fine.sound_speed_m_s == pytest.approx(coarse.sound_speed_m_s, rel=5.0e-2)


def test_representative_map_never_requests_coolprop_two_phase_sound_speed():
    _coolprop_props_si()
    records = build_representative_equilibrium_sound_speed_map()

    assert len(records) == 10
    assert all(record.estimated_equilibrium_sound_speed_m_s > 0.0 for record in records)
    assert all(record.coolprop_two_phase_sound_speed_requested is False for record in records)

    two_phase = [
        record for record in records
        if record.phase_class == "liquid_vapor_two_phase"
    ]
    single_phase = [
        record for record in records
        if record.phase_class != "liquid_vapor_two_phase"
    ]
    assert len(two_phase) == 7
    assert all(record.single_phase_reference_evaluated is False for record in two_phase)
    assert all(record.single_phase_reference_sound_speed_m_s is None for record in two_phase)
    assert all(record.single_phase_reference_evaluated is True for record in single_phase)
    assert all(
        record.single_phase_reference_relative_error is not None
        and record.single_phase_reference_relative_error < 1.0e-2
        for record in single_phase
    )


def test_artifacts_keep_all_approval_flags_false(tmp_path):
    _coolprop_props_si()
    records = build_representative_equilibrium_sound_speed_map()
    files = write_equilibrium_sound_speed_artifacts(tmp_path, records)

    assert set(files) == {"json", "csv", "markdown"}
    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["scope"] == "verification_only"
    assert payload["production_solver_connected"] is False
    assert payload["production_cfl_connected"] is False
    assert payload["production_flux_connected"] is False
    assert payload["equilibrium_two_phase_sound_speed_closure_approved"] is False
    assert payload["coolprop_two_phase_sound_speed_requested"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert payload["numeric_accuracy_band_approved"] is False
    assert len(payload["results"]) == 10
