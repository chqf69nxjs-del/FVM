from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_uniform import (
    CoolPropInternalValveUniformConfig,
    build_coolprop_internal_valve_uniform_solver,
    opening_roundoff_tolerance,
    run_coolprop_internal_valve_uniform,
)
from liquid_gas_transient.interfaces import InternalValveInterface
from liquid_gas_transient.properties import coolprop_available


def test_uniform_internal_valve_config_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even integer"):
        CoolPropInternalValveUniformConfig(n_cells=21)
    with pytest.raises(ValueError, match="constant_opening"):
        CoolPropInternalValveUniformConfig(constant_opening=0.0)
    with pytest.raises(ValueError, match="unique and ascending"):
        CoolPropInternalValveUniformConfig(
            probe_fractions=(0.75, 0.25),
        )


def test_opening_tolerance_is_machine_scale() -> None:
    cfg = CoolPropInternalValveUniformConfig()

    tolerance = opening_roundoff_tolerance(cfg)

    assert tolerance == pytest.approx(8.0 * np.spacing(1.0))
    assert tolerance < 1.0e-14


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_uniform_internal_valve_solver_builds_at_midpoint() -> None:
    cfg = CoolPropInternalValveUniformConfig(
        n_cells=20,
        probe_fractions=(0.25, 0.75),
    )

    solver, context = build_coolprop_internal_valve_uniform_solver(cfg)
    interface = context["interface"]

    assert isinstance(interface, InternalValveInterface)
    assert interface.left_cell == 9
    assert interface.right_cell == 10
    assert context["valve_x_m"] == pytest.approx(0.5 * cfg.pipe_length_m)
    assert context["kv_m3_per_h"] > 0.0

    telemetry = interface.flow_diagnostics(
        U=solver.U,
        eos=solver.eos,
        t=0.0,
    )
    assert telemetry["opening"] == pytest.approx(cfg.constant_opening)
    assert telemetry["raw_target_q_m3_s"] == 0.0
    assert telemetry["applied_q_m3_s"] == 0.0
    assert telemetry["mach_cap_active"] is False
    assert telemetry["hydraulic_separation_active"] is True


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_uniform_internal_valve_mini_run_and_artifacts(
    tmp_path: Path,
) -> None:
    cfg = CoolPropInternalValveUniformConfig(
        n_cells=20,
        cfl=0.5,
        probe_fractions=(0.25, 0.75),
        t_end_s=5.0e-3,
        sample_every=1,
        max_steps=1000,
    )

    metrics = run_coolprop_internal_valve_uniform(tmp_path, cfg)

    assert metrics["reached_target_time"] is True
    assert metrics["all_history_finite"] is True
    assert metrics["remained_single_phase"] is True
    assert metrics["budgets_within_roundoff"] is True
    assert metrics["max_abs_opening_error"] <= metrics[
        "opening_roundoff_tolerance"
    ]
    assert metrics["max_abs_raw_target_q_m3_s"] <= metrics[
        "q_roundoff_tolerance_m3_s"
    ]
    assert metrics["max_abs_applied_q_m3_s"] <= metrics[
        "q_roundoff_tolerance_m3_s"
    ]
    assert metrics["mach_cap_activation_count"] == 0
    assert metrics["hydraulic_separation_count"] == metrics[
        "valve_history_row_count"
    ]
    assert metrics["max_abs_pressure_disturbance_pa"] <= metrics[
        "pressure_roundoff_tolerance_pa"
    ]
    assert metrics["max_abs_velocity_m_s"] <= metrics[
        "velocity_roundoff_tolerance_m_s"
    ]
    assert metrics["property_backend_design_status"] == (
        "not_approved_for_design_use"
    )
    assert metrics["validation"] is False
    assert metrics["overall_observation_execution_pass"] is True
    assert metrics["boundary_history_row_count"] == 2 * metrics[
        "step_count"
    ]
    assert metrics["interface_flux_history_row_count"] == metrics[
        "step_count"
    ]

    stem = cfg.case_name
    required = [
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_valve_schedule.csv",
        f"{stem}_valve_history.csv",
        f"{stem}_interface_flux_history.csv",
        f"{stem}_probe_history.csv",
        f"{stem}_boundary_history.csv",
        f"{stem}_final_profile.csv",
        f"{stem}_observation_report.md",
    ]
    for name in required:
        path = tmp_path / name
        assert path.is_file(), name
        assert path.stat().st_size > 0

    saved = json.loads(
        (tmp_path / f"{stem}_metrics.json").read_text(encoding="utf-8")
    )
    assert saved["overall_observation_execution_pass"] is True

    with (
        tmp_path / f"{stem}_interface_flux_history.csv"
    ).open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))

    assert float(row["mass_flux_mismatch_kg_m2_s"]) == 0.0
    assert float(row["energy_flux_mismatch_w_m2"]) == 0.0
    assert float(row["vapor_mass_flux_mismatch_kg_m2_s"]) == 0.0
    assert float(row["flux_q_minus_applied_q_m3_s"]) == 0.0
