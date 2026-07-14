from __future__ import annotations

from pathlib import Path

import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_operation import (
    CoolPropInternalValveOperationConfig,
    build_coolprop_internal_valve_operation_solver,
    run_coolprop_internal_valve_operation,
)
from liquid_gas_transient.properties import coolprop_available


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_internal_valve_solver_builds_for_all_operation_kinds() -> None:
    for kind in ("constant", "opening_ramp", "closing_ramp"):
        solver, context = build_coolprop_internal_valve_operation_solver(
            CoolPropInternalValveOperationConfig(
                operation_kind=kind,
                n_cells=20,
                probe_fractions=(0.25, 0.45, 0.55, 0.75),
            )
        )
        assert solver.grid.n_cells == 20
        assert context["interface"].left_cell == 9


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_internal_valve_constant_opening_mini_run_and_artifacts(
    tmp_path: Path,
) -> None:
    cfg = CoolPropInternalValveOperationConfig(
        case_name="coolprop_internal_valve_mini",
        operation_kind="constant",
        n_cells=20,
        cfl=0.5,
        constant_opening=0.5,
        t_end_s=0.01,
        probe_fractions=(0.25, 0.45, 0.55, 0.75),
    )
    metrics = run_coolprop_internal_valve_operation(tmp_path, cfg)

    assert metrics["overall_observation_execution_pass"] is True
    assert metrics["remained_single_phase"] is True
    assert metrics["opening_history_monotonic"] is True
    assert metrics["common_mass_flux_match"] is True
    assert metrics["common_energy_flux_match"] is True
    assert metrics["common_vapor_mass_flux_match"] is True
    assert metrics["property_backend_name"] == "coolprop_co2"
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"

    stem = cfg.case_name
    expected = (
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_valve_history.csv",
        f"{stem}_interface_flux_history.csv",
        f"{stem}_probe_history.csv",
        f"{stem}_final_profile.csv",
        f"{stem}_report.md",
    )
    assert all((tmp_path / name).is_file() for name in expected)
