from __future__ import annotations

import csv
import json
import math

import pytest

from liquid_gas_transient.cases.coolprop_boundary_reflection import (
    CoolPropBoundaryReflectionConfig,
    build_coolprop_boundary_reflection_solver,
    run_coolprop_boundary_reflection,
)


def test_boundary_reflection_config_names_cases() -> None:
    rigid = CoolPropBoundaryReflectionConfig(boundary_kind="rigid_wall")
    fixed = CoolPropBoundaryReflectionConfig(boundary_kind="fixed_pressure")
    assert rigid.case_name == "coolprop_rigid_wall_boundary_reflection"
    assert fixed.case_name == "coolprop_fixed_pressure_boundary_reflection"


@pytest.mark.parametrize("boundary_kind", ["rigid_wall", "fixed_pressure"])
def test_boundary_reflection_solver_builds_with_coolprop(boundary_kind: str) -> None:
    pytest.importorskip("CoolProp")
    cfg = CoolPropBoundaryReflectionConfig(
        boundary_kind=boundary_kind,
        n_cells=30,
        probe_fractions=(0.75, 0.90),
        max_steps=5000,
    )
    solver, init = build_coolprop_boundary_reflection_solver(cfg)
    assert solver.grid.n_cells == 30
    assert init["reference"]["rho0"] > 0.0
    assert init["reference"]["c0"] > 0.0


@pytest.mark.parametrize(
    ("boundary_kind", "expected_sign"),
    [("rigid_wall", 1.0), ("fixed_pressure", -1.0)],
)
def test_boundary_reflection_baseline_observation_and_artifacts(
    tmp_path,
    boundary_kind: str,
    expected_sign: float,
) -> None:
    pytest.importorskip("CoolProp")
    cfg = CoolPropBoundaryReflectionConfig(
        boundary_kind=boundary_kind,
        n_cells=30,
        probe_fractions=(0.75, 0.90),
        sample_every=1,
        max_steps=5000,
    )
    metrics = run_coolprop_boundary_reflection(output_dir=tmp_path, config=cfg)

    assert metrics["execution_complete"] is True
    assert metrics["reached_target_time"] is True
    assert metrics["all_history_finite"] is True
    assert metrics["remained_single_phase"] is True
    assert metrics["reflection_detected"] is True
    assert metrics["expected_sign_observed"] is True
    assert metrics["evaluation_window_contaminated"] is False
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["design_evaluation"] is False
    assert metrics["acceptance_gate"] is False
    assert metrics["validation"] is False
    assert metrics["actual_equipment_model"] is False
    assert metrics["boundary_history_row_count"] == 2 * metrics["step_count"]
    assert not metrics["missing_budget_fields"]

    for probe in metrics["probes"]:
        assert probe["expected_pressure_reflection_sign"] == expected_sign
        assert probe["observed_pressure_reflection_sign"] == expected_sign
        assert probe["pressure_reflection_coefficient"] is not None
        assert math.isfinite(probe["pressure_reflection_coefficient"])
        assert math.isfinite(probe["reflected_arrival_time_error_s"])

    stem = str(cfg.case_name)
    required = [
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_probe_history.csv",
        f"{stem}_boundary_history.csv",
        f"{stem}_final_profile.csv",
        f"{stem}_report.md",
    ]
    for name in required:
        assert (tmp_path / name).exists(), name
        assert (tmp_path / name).stat().st_size > 0

    saved = json.loads((tmp_path / f"{stem}_metrics.json").read_text(encoding="utf-8"))
    assert saved["boundary_kind"] == boundary_kind
    assert saved["property_backend_design_status"] == "not_approved_for_design_use"

    with (tmp_path / f"{stem}_boundary_history.csv").open(encoding="utf-8", newline="") as stream:
        boundary_rows = list(csv.DictReader(stream))
    assert len(boundary_rows) == metrics["boundary_history_row_count"]
    assert {row["side"] for row in boundary_rows} == {"left", "right"}
    assert all(row["schema_version"] == "boundary_history_v1" for row in boundary_rows)

    report = (tmp_path / f"{stem}_report.md").read_text(encoding="utf-8")
    assert "numerical verification" in report
    assert "physical_validation: false" in report
    assert "design_use_acceptance: false" in report
    assert "not_approved_for_design_use" in report



def test_fixed_pressure_boundary_velocity_amplification_is_dimensionless() -> None:
    from liquid_gas_transient.cases.coolprop_boundary_reflection import (
        _boundary_metrics,
    )

    rho0 = 1000.0
    c0 = 500.0
    pressure_amplitude = 1000.0
    incident_velocity = pressure_amplitude / (rho0 * c0)

    cfg = CoolPropBoundaryReflectionConfig(
        boundary_kind="fixed_pressure",
        pressure_amplitude_pa=pressure_amplitude,
    )
    rows = [
        {
            "side": "right",
            "flux_evaluation_time_s": 0.1,
            "boundary_face_pressure_pa": cfg.initial_pressure_pa,
            "boundary_face_velocity_m_s": 2.0 * incident_velocity,
            "numerical_mass_flux_kg_m2_s": 0.0,
            "numerical_energy_flux_w_m2": 0.0,
            "dt_s": 1.0e-3,
            "numerical_mass_flow_rate_kg_s": 0.0,
            "numerical_energy_flow_rate_w": 0.0,
        }
    ]

    metrics = _boundary_metrics(cfg, rows, rho0, c0)

    assert math.isclose(
        metrics["theoretical_incident_velocity_amplitude_m_s"],
        incident_velocity,
    )
    assert math.isclose(
        metrics["boundary_velocity_amplification_ratio"],
        2.0,
    )
