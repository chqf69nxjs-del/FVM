from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_mesh_cfl_sweep import (
    CoolPropInternalValveMeshCflSweepConfig,
    build_run_plan,
    case_id_for,
    run_coolprop_internal_valve_mesh_cfl_sweep,
)
from liquid_gas_transient.properties import coolprop_available


def test_default_v012_mesh_cfl_plan_has_13_unique_runs() -> None:
    config = CoolPropInternalValveMeshCflSweepConfig()
    plan = build_run_plan(config)

    assert len(plan) == 13
    assert len({row["case_id"] for row in plan}) == 13

    sentinel = [
        row for row in plan if row["verification_item"] == "V-012A"
    ]
    assert len(sentinel) == 1
    assert sentinel[0]["n_cells"] == 50
    assert sentinel[0]["cfl"] == pytest.approx(0.5)
    assert sentinel[0]["comparison_groups"] == ["preservation_sentinel"]

    for verification_item in ("V-012B", "V-012C", "V-012D"):
        rows = [
            row
            for row in plan
            if row["verification_item"] == verification_item
        ]
        assert len(rows) == 4
        assert {(row["n_cells"], row["cfl"]) for row in rows} == {
            (50, 0.5),
            (100, 0.25),
            (100, 0.5),
            (200, 0.5),
        }
        shared = [
            row
            for row in rows
            if row["n_cells"] == 100 and row["cfl"] == 0.5
        ]
        assert shared[0]["comparison_groups"] == [
            "mesh_comparison",
            "cfl_comparison",
        ]


def test_v012_mesh_cfl_config_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="unique and ascending"):
        CoolPropInternalValveMeshCflSweepConfig(
            mesh_cells=(100, 50, 200),
        )
    with pytest.raises(ValueError, match="even integers"):
        CoolPropInternalValveMeshCflSweepConfig(
            mesh_cells=(50, 101, 200),
        )
    with pytest.raises(ValueError, match="listed in mesh_cells"):
        CoolPropInternalValveMeshCflSweepConfig(
            cfl_comparison_n_cells=400,
        )
    with pytest.raises(ValueError, match="uniform_sentinel_n_cells"):
        CoolPropInternalValveMeshCflSweepConfig(
            uniform_sentinel_n_cells=21,
        )


def test_v012_sweep_case_ids_preserve_distinct_cfl_values() -> None:
    first = case_id_for("V-012B", 100, 0.25)
    second = case_id_for("V-012B", 100, 0.25000000000000006)

    assert first != second
    assert first.startswith("v012b_n0100_cfl")


def _fake_metrics(item: dict) -> dict:
    return {
        "verification_item": item["verification_item"],
        "n_cells": item["n_cells"],
        "dx_m": 100.0 / item["n_cells"],
        "cfl_target": item["cfl"],
        "overall_observation_execution_pass": True,
        "remained_single_phase": True,
        "missing_budget_fields": [],
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 0.0,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "step_count": 4,
        "property_backend_name": "coolprop_co2",
        "coolprop_version": "8.0.0",
        "property_backend_design_status": "not_approved_for_design_use",
        "all_history_finite": True,
        "positive_pressure": True,
        "positive_temperature": True,
        "positive_density": True,
        "positive_sound_speed": True,
        "mach_cap_activation_count": 0,
        "max_abs_raw_target_q_m3_s": 0.0,
        "max_abs_applied_q_m3_s": 0.0,
        "q_roundoff_tolerance_m3_s": 1.0e-14,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_fake_sentinel_artifacts(output_dir: Path, case_id: str) -> None:
    valve = {
        "time_s": 0.0,
        "opening_actual": 0.5,
        "delta_p_pa": 0.0,
        "raw_target_q_m3_s": 0.0,
        "applied_q_m3_s": 0.0,
        "applied_face_mach": 0.0,
        "mach_cap_active": False,
        "hydraulic_separation_active": True,
        "flow_direction": "none",
    }
    flux = {
        "time_s": 0.0,
        "left_mass_flux_kg_m2_s": 0.0,
        "right_mass_flux_kg_m2_s": 0.0,
        "mass_flux_mismatch_kg_m2_s": 0.0,
        "left_energy_flux_w_m2": 0.0,
        "right_energy_flux_w_m2": 0.0,
        "energy_flux_mismatch_w_m2": 0.0,
        "left_vapor_mass_flux_kg_m2_s": 0.0,
        "right_vapor_mass_flux_kg_m2_s": 0.0,
        "vapor_mass_flux_mismatch_kg_m2_s": 0.0,
        "momentum_difference_residual_pa": 0.0,
        "flux_derived_q_m3_s": 0.0,
        "flux_q_minus_applied_q_m3_s": 0.0,
    }
    _write_csv(output_dir / f"{case_id}_valve_history.csv", [valve])
    _write_csv(
        output_dir / f"{case_id}_interface_flux_history.csv",
        [flux],
    )


def test_selected_fake_sentinel_writes_one_summary_row(
    tmp_path: Path,
) -> None:
    config = CoolPropInternalValveMeshCflSweepConfig()
    sentinel_id = case_id_for("V-012A", 50, 0.5)

    def fake_adapter(
        output_dir: Path,
        item: dict,
    ) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        metrics = _fake_metrics(item)
        (output_dir / f"{item['case_id']}_metrics.json").write_text(
            json.dumps(metrics, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_fake_sentinel_artifacts(output_dir, item["case_id"])
        return metrics

    metrics = run_coolprop_internal_valve_mesh_cfl_sweep(
        tmp_path,
        config,
        selected_case_ids=(sentinel_id,),
        runner_adapters={"V-012A": fake_adapter},
    )

    assert metrics["planned_run_count"] == 13
    assert metrics["executed_run_count"] == 1
    assert metrics["partial_execution"] is True
    assert metrics["overall_selected_execution_pass"] is True
    assert metrics["overall_sweep_execution_pass"] is False
    assert len(metrics["summary_rows"]) == 1
    assert metrics["summary_rows"][0]["case_id"] == sentinel_id
    assert metrics["summary_rows"][0]["analysis_complete"] is True
    assert metrics["summary_rows"][0][
        "relative_flow_comparison_evaluated"
    ] is False

    stem = config.case_name
    for filename in (
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_summary.csv",
        f"{stem}_report.md",
    ):
        assert (tmp_path / filename).stat().st_size > 0


def test_selected_case_ids_reject_unknown_and_duplicates(
    tmp_path: Path,
) -> None:
    config = CoolPropInternalValveMeshCflSweepConfig()
    sentinel_id = case_id_for("V-012A", 50, 0.5)

    with pytest.raises(ValueError, match="unknown selected"):
        run_coolprop_internal_valve_mesh_cfl_sweep(
            tmp_path,
            config,
            selected_case_ids=("unknown",),
        )
    with pytest.raises(ValueError, match="must be unique"):
        run_coolprop_internal_valve_mesh_cfl_sweep(
            tmp_path,
            config,
            selected_case_ids=(sentinel_id, sentinel_id),
        )


@pytest.mark.coolprop_installed
@pytest.mark.skipif(
    not coolprop_available(),
    reason="CoolProp is not installed",
)
def test_real_uniform_sentinel_mini_run(tmp_path: Path) -> None:
    config = CoolPropInternalValveMeshCflSweepConfig(
        mesh_cells=(20, 40, 60),
        cfl_values=(0.25, 0.5),
        mesh_comparison_cfl=0.5,
        cfl_comparison_n_cells=40,
        uniform_sentinel_n_cells=20,
        uniform_sentinel_cfl=0.5,
    )
    sentinel_id = case_id_for("V-012A", 20, 0.5)
    metrics = run_coolprop_internal_valve_mesh_cfl_sweep(
        tmp_path,
        config,
        selected_case_ids=(sentinel_id,),
    )

    assert metrics["overall_selected_execution_pass"] is True
    assert metrics["partial_execution"] is True
    assert metrics["executed_run_count"] == 1
    row = metrics["summary_rows"][0]
    assert row["verification_item"] == "V-012A"
    assert row["execution_pass"] is True
    assert row["analysis_complete"] is True
    assert row["remained_single_phase"] is True
    assert row["max_abs_raw_target_q_m3_s_extracted"] == pytest.approx(0.0)
    assert row["max_abs_applied_q_m3_s_extracted"] == pytest.approx(0.0)
    assert row["max_abs_flux_derived_q_m3_s_extracted"] == pytest.approx(0.0)
