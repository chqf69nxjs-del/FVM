from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.verification.linear_acoustic_reference import (
    LinearAcousticReferenceConfig,
    acoustic_energy_proxy,
    boundary_reflection_coefficient,
    characteristics_from_pressure_velocity,
    evaluate_analytical_characteristics,
    evaluate_gaussian_reference,
    gaussian_profile,
    initialize_moc_characteristics,
    make_gaussian_profile,
    moc_step,
    pressure_velocity_from_characteristics,
    reflected_incoming_characteristic,
    run_moc_reference,
    write_moc_reference_json,
)


def _config(
    *,
    n_cells: int = 100,
    left_boundary: str = "transmissive",
    right_boundary: str = "transmissive",
) -> LinearAcousticReferenceConfig:
    return LinearAcousticReferenceConfig(
        p0_pa=8.0e6,
        rho0_kg_m3=900.0,
        c0_m_s=500.0,
        length_m=100.0,
        n_cells=n_cells,
        left_boundary=left_boundary,
        right_boundary=right_boundary,
    )


def _zero_profile(x: np.ndarray) -> np.ndarray:
    return np.zeros_like(x, dtype=float)


def test_characteristic_round_trip_and_pure_directions() -> None:
    pressure = np.array([100.0, -50.0, 0.0])
    velocity = np.array([100.0, -50.0, 0.0]) / (900.0 * 500.0)
    pressure_before = pressure.copy()
    velocity_before = velocity.copy()

    a_plus, a_minus = characteristics_from_pressure_velocity(
        pressure,
        velocity,
        rho0_kg_m3=900.0,
        c0_m_s=500.0,
    )
    reconstructed_pressure, reconstructed_velocity = (
        pressure_velocity_from_characteristics(
            a_plus,
            a_minus,
            rho0_kg_m3=900.0,
            c0_m_s=500.0,
        )
    )

    assert np.allclose(a_plus, pressure)
    assert np.allclose(a_minus, 0.0)
    assert np.allclose(reconstructed_pressure, pressure)
    assert np.allclose(reconstructed_velocity, velocity)
    assert np.array_equal(pressure, pressure_before)
    assert np.array_equal(velocity, velocity_before)

    left_velocity = -pressure / (900.0 * 500.0)
    left_plus, left_minus = characteristics_from_pressure_velocity(
        pressure,
        left_velocity,
        rho0_kg_m3=900.0,
        c0_m_s=500.0,
    )
    assert np.allclose(left_plus, 0.0)
    assert np.allclose(left_minus, pressure)


def test_gaussian_profile_and_analytical_translation() -> None:
    x = np.linspace(0.0, 100.0, 101)
    initial = gaussian_profile(
        x,
        amplitude_pa=100.0,
        center_m=20.0,
        sigma_m=2.0,
    )
    result = evaluate_gaussian_reference(
        x,
        0.02,
        length_m=100.0,
        rho0_kg_m3=900.0,
        c0_m_s=500.0,
        amplitude_pa=100.0,
        center_m=20.0,
        sigma_m=2.0,
    )
    expected = gaussian_profile(
        x,
        amplitude_pa=100.0,
        center_m=30.0,
        sigma_m=2.0,
    )
    expected[x < 10.0] = 0.0

    assert np.allclose(result["a_plus_pa"], expected)
    assert np.allclose(result["a_minus_pa"], 0.0)
    assert np.allclose(result["pressure_perturbation_pa"], expected)
    assert np.allclose(
        result["velocity_m_s"],
        expected / (900.0 * 500.0),
    )
    assert initial[np.argmax(initial)] == pytest.approx(100.0)


@pytest.mark.parametrize(
    ("boundary", "coefficient"),
    [
        ("transmissive", 0.0),
        ("rigid_wall", 1.0),
        ("fixed_pressure", -1.0),
    ],
)
def test_boundary_reflection_coefficients(
    boundary: str,
    coefficient: float,
) -> None:
    outgoing = np.array([2.0, -3.0])
    reflected = reflected_incoming_characteristic(
        outgoing,
        boundary=boundary,
    )
    assert boundary_reflection_coefficient(boundary) == coefficient
    assert np.array_equal(reflected, coefficient * outgoing)


def test_right_boundary_identities_reconstruct_expected_conditions() -> None:
    outgoing = np.array([25.0])
    for boundary in ("rigid_wall", "fixed_pressure"):
        incoming = reflected_incoming_characteristic(
            outgoing,
            boundary=boundary,
        )
        pressure, velocity = pressure_velocity_from_characteristics(
            outgoing,
            incoming,
            rho0_kg_m3=900.0,
            c0_m_s=500.0,
        )
        if boundary == "rigid_wall":
            assert pressure[0] == pytest.approx(50.0)
            assert velocity[0] == pytest.approx(0.0)
        else:
            assert pressure[0] == pytest.approx(0.0)
            assert velocity[0] == pytest.approx(50.0 / (900.0 * 500.0))


def test_moc_one_cell_translation_is_exact_and_inputs_are_not_mutated() -> None:
    a_plus = np.array([1.0, 2.0, 3.0, 4.0])
    a_minus = np.array([10.0, 20.0, 30.0, 40.0])
    before = deepcopy((a_plus, a_minus))

    next_plus, next_minus = moc_step(
        a_plus,
        a_minus,
        left_boundary="transmissive",
        right_boundary="transmissive",
    )

    assert np.array_equal(next_plus, [0.0, 1.0, 2.0, 3.0])
    assert np.array_equal(next_minus, [20.0, 30.0, 40.0, 0.0])
    assert np.array_equal(a_plus, before[0])
    assert np.array_equal(a_minus, before[1])


@pytest.mark.parametrize(
    ("boundary", "expected_incoming"),
    [
        ("rigid_wall", 3.0),
        ("fixed_pressure", -3.0),
    ],
)
def test_moc_right_boundary_reflection_identity(
    boundary: str,
    expected_incoming: float,
) -> None:
    next_plus, next_minus = moc_step(
        np.array([0.0, 0.0, 3.0, 0.0]),
        np.zeros(4),
        left_boundary="transmissive",
        right_boundary=boundary,
    )
    assert next_plus[-1] == pytest.approx(3.0)
    assert next_minus[-1] == pytest.approx(expected_incoming)


def test_moc_matches_analytical_at_grid_aligned_incident_samples() -> None:
    config = _config()
    profile = make_gaussian_profile(
        amplitude_pa=100.0,
        center_m=20.0,
        sigma_m=2.0,
    )
    a_plus, a_minus = initialize_moc_characteristics(
        config,
        initial_a_plus=profile,
        initial_a_minus=_zero_profile,
    )
    a_plus_before = a_plus.copy()
    a_minus_before = a_minus.copy()
    history = run_moc_reference(
        config,
        initial_a_plus_pa=a_plus,
        initial_a_minus_pa=a_minus,
        n_steps=25,
    )
    analytical = evaluate_gaussian_reference(
        config.grid(),
        25 * config.dt_s,
        length_m=config.length_m,
        rho0_kg_m3=config.rho0_kg_m3,
        c0_m_s=config.c0_m_s,
        amplitude_pa=100.0,
        center_m=20.0,
        sigma_m=2.0,
    )

    assert np.allclose(
        history["a_plus_pa"][-1],
        analytical["a_plus_pa"],
        rtol=0.0,
        atol=1.0e-14,
    )
    assert np.allclose(
        history["a_minus_pa"][-1],
        analytical["a_minus_pa"],
        rtol=0.0,
        atol=1.0e-14,
    )
    assert np.array_equal(a_plus, a_plus_before)
    assert np.array_equal(a_minus, a_minus_before)


@pytest.mark.parametrize("boundary", ["rigid_wall", "fixed_pressure"])
def test_moc_matches_analytical_after_one_right_reflection(boundary: str) -> None:
    config = _config(right_boundary=boundary)
    profile = make_gaussian_profile(
        amplitude_pa=100.0,
        center_m=80.0,
        sigma_m=2.0,
    )
    a_plus, a_minus = initialize_moc_characteristics(
        config,
        initial_a_plus=profile,
        initial_a_minus=_zero_profile,
    )
    history = run_moc_reference(
        config,
        initial_a_plus_pa=a_plus,
        initial_a_minus_pa=a_minus,
        n_steps=30,
    )
    analytical = evaluate_gaussian_reference(
        config.grid(),
        30 * config.dt_s,
        length_m=config.length_m,
        rho0_kg_m3=config.rho0_kg_m3,
        c0_m_s=config.c0_m_s,
        amplitude_pa=100.0,
        center_m=80.0,
        sigma_m=2.0,
        right_boundary=boundary,
    )

    assert np.allclose(
        history["a_plus_pa"][-1],
        analytical["a_plus_pa"],
        rtol=0.0,
        atol=1.0e-13,
    )
    assert np.allclose(
        history["a_minus_pa"][-1],
        analytical["a_minus_pa"],
        rtol=0.0,
        atol=1.0e-13,
    )
    boundary_pressure = history["pressure_perturbation_pa"][-1, -1]
    boundary_velocity = history["velocity_m_s"][-1, -1]
    if boundary == "rigid_wall":
        assert boundary_velocity == pytest.approx(0.0, abs=1.0e-15)
    else:
        assert boundary_pressure == pytest.approx(0.0, abs=1.0e-12)


def test_generic_analytical_left_going_profile_and_left_reflection() -> None:
    x = np.linspace(0.0, 100.0, 101)
    profile = make_gaussian_profile(
        amplitude_pa=50.0,
        center_m=20.0,
        sigma_m=2.0,
    )
    a_plus, a_minus = evaluate_analytical_characteristics(
        x,
        0.08,
        length_m=100.0,
        c0_m_s=500.0,
        initial_a_plus=_zero_profile,
        initial_a_minus=profile,
        left_boundary="rigid_wall",
    )
    assert np.max(a_plus) == pytest.approx(50.0)
    assert np.max(a_minus) < 1.0e-10


def test_acoustic_energy_proxy_matches_right_going_identity() -> None:
    x = np.linspace(0.0, 100.0, 1001)
    pressure = gaussian_profile(
        x,
        amplitude_pa=100.0,
        center_m=50.0,
        sigma_m=2.0,
    )
    velocity = pressure / (900.0 * 500.0)
    energy = acoustic_energy_proxy(
        x,
        pressure,
        velocity,
        rho0_kg_m3=900.0,
        c0_m_s=500.0,
    )
    expected_density = pressure**2 / (900.0 * 500.0**2)
    expected = np.sum(
        0.5 * (expected_density[:-1] + expected_density[1:]) * np.diff(x)
    )
    assert energy == pytest.approx(expected, rel=1.0e-14)


def test_deterministic_reference_json(tmp_path: Path) -> None:
    config = _config(n_cells=4)
    initial_plus = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    initial_minus = np.zeros(5)
    history = run_moc_reference(
        config,
        initial_a_plus_pa=initial_plus,
        initial_a_minus_pa=initial_minus,
        n_steps=2,
    )
    first = write_moc_reference_json(
        tmp_path / "first.json",
        config=config,
        history=history,
    )
    second = write_moc_reference_json(
        tmp_path / "second.json",
        config=config,
        history=history,
    )

    assert first.read_bytes() == second.read_bytes()
    assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(
        second.read_bytes()
    ).hexdigest()
    text = first.read_text(encoding="utf-8")
    assert '"coolprop_called": false' in text
    assert '"production_solver_imported": false' in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rho0_kg_m3": 0.0},
        {"c0_m_s": float("nan")},
        {"length_m": -1.0},
        {"n_cells": 1.5},
        {"right_boundary": "unsupported"},
        {"validation": True},
        {"calls_coolprop": True},
    ],
)
def test_invalid_reference_configuration_is_rejected(kwargs: dict) -> None:
    values = {
        "p0_pa": 8.0e6,
        "rho0_kg_m3": 900.0,
        "c0_m_s": 500.0,
        "length_m": 100.0,
        "n_cells": 100,
    }
    values.update(kwargs)
    with pytest.raises(ValueError):
        LinearAcousticReferenceConfig(**values)


def test_reference_module_has_no_prohibited_imports() -> None:
    import liquid_gas_transient.verification.linear_acoustic_reference as module

    tree = ast.parse(inspect.getsource(module))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots <= {
        "__future__",
        "dataclasses",
        "json",
        "math",
        "pathlib",
        "typing",
        "numpy",
    }
    source = inspect.getsource(module)
    for prohibited in (
        "FvmSolver",
        "import CoolProp",
        "from CoolProp",
        "liquid_gas_transient.cases",
        "liquid_gas_transient.boundary",
        "liquid_gas_transient.solver",
    ):
        assert prohibited not in source
