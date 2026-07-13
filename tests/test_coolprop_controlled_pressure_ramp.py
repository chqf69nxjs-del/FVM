from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.cases.coolprop_controlled_pressure_ramp import (
    CoolPropControlledPressureRampConfig,
    build_coolprop_controlled_pressure_ramp_solver,
    pressure_ramp_fraction,
    requested_boundary_pressure_pa,
    schedule_pressure_tolerance_pa,
    run_coolprop_controlled_pressure_ramp,
)
from liquid_gas_transient.properties import coolprop_available


def test_pressure_ramp_schedule_before_during_and_after() -> None:
    cfg = CoolPropControlledPressureRampConfig(
        pressure_change_pa=1000.0,
        ramp_start_s=1.0,
        ramp_duration_s=2.0,
    )

    assert pressure_ramp_fraction(0.5, cfg) == 0.0
    assert pressure_ramp_fraction(2.0, cfg) == pytest.approx(0.5)
    assert pressure_ramp_fraction(4.0, cfg) == 1.0
    assert requested_boundary_pressure_pa(0.5, cfg) == cfg.initial_pressure_pa
    assert requested_boundary_pressure_pa(2.0, cfg) == pytest.approx(
        cfg.initial_pressure_pa + 500.0
    )
    assert requested_boundary_pressure_pa(4.0, cfg) == cfg.final_pressure_pa


def test_zero_duration_schedule_changes_at_start_time() -> None:
    cfg = CoolPropControlledPressureRampConfig(
        ramp_start_s=1.0,
        ramp_duration_s=0.0,
    )

    assert pressure_ramp_fraction(0.999, cfg) == 0.0
    assert pressure_ramp_fraction(1.0, cfg) == 1.0
    assert requested_boundary_pressure_pa(1.0, cfg) == cfg.final_pressure_pa


def test_config_rejects_non_small_or_invalid_pressure_change() -> None:
    with pytest.raises(ValueError, match="nonzero"):
        CoolPropControlledPressureRampConfig(pressure_change_pa=0.0)
    with pytest.raises(ValueError, match="too large"):
        CoolPropControlledPressureRampConfig(pressure_change_pa=1.0e5)
    with pytest.raises(ValueError, match="final pressure"):
        CoolPropControlledPressureRampConfig(
            initial_pressure_pa=100.0,
            pressure_change_pa=-200.0,
            max_perturbation_ratio=10.0,
        )


def test_schedule_pressure_tolerance_is_machine_scale() -> None:
    cfg = CoolPropControlledPressureRampConfig()

    one_ulp = float(
        np.spacing(max(cfg.initial_pressure_pa, cfg.final_pressure_pa))
    )
    tolerance = schedule_pressure_tolerance_pa(cfg)

    assert tolerance == pytest.approx(8.0 * one_ulp)
    assert tolerance >= one_ulp
    assert tolerance < 1.0e-6


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_controlled_pressure_ramp_solver_builds() -> None:
    cfg = CoolPropControlledPressureRampConfig(
        n_cells=20,
        ramp_start_s=1.0e-3,
        ramp_duration_s=2.0e-3,
        probe_fractions=(0.25, 0.75),
    )
    solver, context = build_coolprop_controlled_pressure_ramp_solver(cfg)

    assert solver.grid.n_cells == 20
    assert context["reference"]["rho0"] > 0.0
    assert context["reference"]["c0"] > 0.0
    assert context["right_boundary"].pressure_pa(0.0) == cfg.initial_pressure_pa
    assert context["right_boundary"].pressure_pa(cfg.ramp_end_s) == cfg.final_pressure_pa


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_controlled_pressure_ramp_right_ghost_matches_requested_pressure() -> None:
    cfg = CoolPropControlledPressureRampConfig()
    solver, _ = build_coolprop_controlled_pressure_ramp_solver(cfg)

    times = (
        0.0,
        cfg.ramp_start_s,
        cfg.ramp_start_s + 0.5 * cfg.ramp_duration_s,
        cfg.ramp_end_s,
    )

    for time_s in times:
        extended = solver.extend_with_ghosts(time_s)
        right_ghost_index = solver.n_ghost + solver.grid.n_cells
        ghost = solver.eos.primitive_from_conserved(
            extended[right_ghost_index][np.newaxis, :]
        )

        ghost_pressure_pa = float(np.asarray(ghost.p)[0])
        ghost_temperature_K = float(np.asarray(ghost.T)[0])
        requested_pressure_pa = requested_boundary_pressure_pa(time_s, cfg)

        assert ghost_pressure_pa == pytest.approx(
            requested_pressure_pa,
            rel=1.0e-9,
            abs=1.0e-3,
        )
        assert ghost_temperature_K == pytest.approx(
            cfg.initial_temperature_K,
            abs=1.0e-7,
        )


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_controlled_pressure_ramp_mini_run_and_artifacts(tmp_path: Path) -> None:
    cfg = CoolPropControlledPressureRampConfig(
        n_cells=20,
        cfl=0.5,
        ramp_start_s=1.0e-3,
        ramp_duration_s=2.0e-3,
        probe_fractions=(0.25, 0.75),
        sample_every=1,
        max_steps=5000,
        t_end_s=1.0e-2,
    )
    metrics = run_coolprop_controlled_pressure_ramp(tmp_path, cfg)

    assert metrics["reached_target_time"] is True
    assert metrics["all_history_finite"] is True
    assert metrics["remained_single_phase"] is True
    assert (
        metrics["max_abs_schedule_pressure_error_pa"]
        <= metrics["schedule_pressure_tolerance_pa"]
    )
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["validation"] is False
    assert metrics["overall_observation_execution_pass"] is True
    assert metrics["boundary_history_row_count"] == 2 * metrics["step_count"]

    stem = cfg.case_name
    required = [
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_pressure_schedule.csv",
        f"{stem}_probe_history.csv",
        f"{stem}_boundary_history.csv",
    ]
    for name in required:
        path = tmp_path / name
        assert path.is_file(), name
        assert path.stat().st_size > 0

    saved = json.loads((tmp_path / f"{stem}_metrics.json").read_text(encoding="utf-8"))
    assert saved["overall_observation_execution_pass"] is True
