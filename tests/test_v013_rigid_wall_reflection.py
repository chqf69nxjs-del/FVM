from __future__ import annotations

import ast
import inspect
import math

import numpy as np
import pytest

import liquid_gas_transient.cases.v013_rigid_wall_reflection as module
from liquid_gas_transient.cases.v013_rigid_wall_reflection import (
    V013RigidWallReflectionConfig,
    build_matched_sample_plan,
    build_probe_plan,
    build_run_plan,
    build_specification_snapshot,
    case_id_for,
    reflection_path_state,
    rigid_wall_expected_conditions,
)
from liquid_gas_transient.verification.linear_acoustic_reference import (
    boundary_reflection_coefficient,
    pressure_velocity_from_characteristics,
    reflected_incoming_characteristic,
)


def test_v013b_default_configuration_and_run_plan_are_stable() -> None:
    cfg = V013RigidWallReflectionConfig()
    assert cfg.fvm_mesh_cells == (100, 200, 400)
    assert cfg.probe_fractions == (0.75, 0.85, 0.90)
    assert cfg.pulse_center_m == 65.0
    assert cfg.pulse_sigma_m == 2.0
    assert cfg.wall_path_travel_m == 35.0
    assert cfg.window_half_width_sigma == 2.0
    assert cfg.final_reflected_center_m == 70.0
    plan = build_run_plan(cfg)
    assert [row["case_id"] for row in plan] == [
        "v013b_n0100_fvmcfl0p5_moccfl1",
        "v013b_n0200_fvmcfl0p5_moccfl1",
        "v013b_n0400_fvmcfl0p5_moccfl1",
    ]
    assert all(row["verification_item"] == "V-013B" for row in plan)
    assert all(row["right_boundary"] == "rigid_wall" for row in plan)
    assert all(row["production_solver_behavior_changed"] is False for row in plan)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pressure_amplitude_pa": 1000.0},
        {"probe_fractions": (0.90, 0.85)},
        {"probe_fractions": (0.60,)},
        {"probe_fractions": (0.95,)},
        {"fvm_mesh_cells": (200, 100)},
        {"fvm_mesh_cells": (10,)},
        {"fvm_cfl": 0.0},
        {"moc_cfl": 0.5},
        {"matched_path_travel_m": (0.0, 30.0, 45.0)},
        {"matched_path_travel_m": (0.0, 35.0)},
        {"matched_path_travel_m": (0.0, 34.3, 35.0, 45.0)},
        {"matched_path_travel_m": (0.0, 35.0, 130.0)},
        {"validation": True},
    ],
)
def test_v013b_configuration_rejects_invalid_or_out_of_scope_values(kwargs) -> None:
    with pytest.raises(ValueError):
        V013RigidWallReflectionConfig(**kwargs)


def test_case_id_rejects_invalid_cell_count_or_cfl() -> None:
    with pytest.raises(ValueError):
        case_id_for(0)
    with pytest.raises(ValueError):
        case_id_for(True)
    with pytest.raises(ValueError):
        case_id_for(100, fvm_cfl=1.1)
    with pytest.raises(ValueError):
        case_id_for(100, moc_cfl=0.5)


def test_rigid_wall_identity_matches_independent_reference_core() -> None:
    expected = rigid_wall_expected_conditions()
    outgoing = np.asarray([100.0])
    incoming = reflected_incoming_characteristic(outgoing, boundary="rigid_wall")
    pressure, velocity = pressure_velocity_from_characteristics(
        outgoing,
        incoming,
        rho0_kg_m3=900.0,
        c0_m_s=500.0,
    )
    assert boundary_reflection_coefficient("rigid_wall") == expected[
        "characteristic_reflection_coefficient"
    ]
    assert incoming[0] == pytest.approx(100.0)
    assert pressure[0] / outgoing[0] == pytest.approx(
        expected["total_wall_pressure_to_incident_pressure_ratio"]
    )
    assert velocity[0] == pytest.approx(expected["wall_velocity_perturbation_m_s"])
    assert expected["pressure_reflection_coefficient"] == 1.0
    assert expected["velocity_reflection_coefficient"] == -1.0


@pytest.mark.parametrize(
    ("distance", "phase", "center", "dominant"),
    [
        (0.0, "incident", 65.0, "A+"),
        (15.0, "incident", 80.0, "A+"),
        (25.0, "incident", 90.0, "A+"),
        (35.0, "wall_contact", 100.0, "A+ + A-"),
        (45.0, "reflected", 90.0, "A-"),
        (55.0, "reflected", 80.0, "A-"),
        (65.0, "reflected", 70.0, "A-"),
    ],
)
def test_reflection_path_state_is_fixed(distance, phase, center, dominant) -> None:
    state = reflection_path_state(distance)
    assert state["phase"] == phase
    assert state["expected_center_x_m"] == pytest.approx(center)
    assert state["expected_dominant_characteristic"] == dominant
    assert state["secondary_left_boundary_contamination_expected"] is False
    assert state["primary_wall_guard_overlap_expected"] is (phase == "wall_contact")


def test_matched_sample_plan_uses_fixed_times_without_shifting() -> None:
    rows = build_matched_sample_plan(500.0)
    assert [row["path_travel_m"] for row in rows] == [
        0.0,
        15.0,
        25.0,
        35.0,
        45.0,
        55.0,
        65.0,
    ]
    assert [row["time_s"] for row in rows] == pytest.approx(
        [0.0, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13]
    )
    assert rows[3]["phase"] == "wall_contact"
    assert rows[4]["phase"] == "reflected"
    assert all(row["time_shift_applied"] is False for row in rows)
    assert all(row["parameter_tuning_applied"] is False for row in rows)


def test_probe_plan_has_strictly_separated_windows_and_safe_end() -> None:
    rows = build_probe_plan(500.0)
    assert [row["probe_target_x_m"] for row in rows] == [75.0, 85.0, 90.0]
    assert [row["theoretical_reflected_path_m"] for row in rows] == [
        60.0,
        50.0,
        45.0,
    ]
    for row in rows:
        assert row["incident_window_end_s"] < row["boundary_window_start_s"]
        assert row["boundary_window_end_s"] < row["reflected_window_start_s"]
        assert row["evaluation_window_contaminated"] is False
        assert row["event_windows_strictly_separated"] is True
        assert row["time_shift_applied"] is False


def test_specification_snapshot_is_json_ready_and_preserves_guardrails() -> None:
    snapshot = build_specification_snapshot(500.0)
    assert snapshot["status"] == "IN_PROGRESS"
    assert snapshot["reference_calls_coolprop"] is False
    assert snapshot["production_solver_behavior_changed"] is False
    assert snapshot["validation"] is False
    assert snapshot["design_evaluation"] is False
    assert snapshot["acceptance_gate"] is False
    assert snapshot["formal_fvm_regression_band_applied"] is False
    assert len(snapshot["run_plan"]) == 3
    assert len(snapshot["matched_sample_plan"]) == 7
    assert len(snapshot["probe_plan"]) == 3


def test_v013b_scaffold_has_no_production_or_coolprop_imports() -> None:
    tree = ast.parse(inspect.getsource(module))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    prohibited = (
        "liquid_gas_transient.solver",
        "liquid_gas_transient.boundary",
        "coolprop",
        "CoolProp",
    )
    assert not any(any(token in name for token in prohibited) for name in imports)
    source = inspect.getsource(module)
    assert "FvmSolver" not in source
    assert "ReflectiveBoundary" not in source


def test_default_plan_is_aligned_with_every_moc_grid() -> None:
    cfg = V013RigidWallReflectionConfig()
    for n_cells in cfg.fvm_mesh_cells:
        dx = cfg.pipe_length_m / n_cells
        for distance in cfg.matched_path_travel_m:
            assert math.isclose(
                distance / dx,
                round(distance / dx),
                abs_tol=1.0e-12,
            )
