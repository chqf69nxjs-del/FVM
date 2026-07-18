from __future__ import annotations

import csv
from pathlib import Path

import pytest

from liquid_gas_transient.cases.internal_valve_mesh_cfl_analysis import (
    build_aggregate_observation,
    extract_case_artifacts,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _valve_row(
    time_s: float,
    opening: float,
    q_m3_s: float,
    *,
    closed: bool = False,
) -> dict:
    return {
        "time_s": time_s,
        "opening_actual": opening,
        "delta_p_pa": 1000.0,
        "raw_target_q_m3_s": q_m3_s,
        "applied_q_m3_s": q_m3_s,
        "applied_face_mach": abs(q_m3_s) * 0.01,
        "mach_cap_active": False,
        "hydraulic_separation_active": closed,
        "flow_direction": "none" if closed else "left_to_right",
    }


def _flux_row(
    time_s: float,
    q_m3_s: float,
    *,
    branch: str = "finite_opening",
    mass_flux: float | None = None,
    momentum_residual: float = 0.0,
) -> dict:
    through = q_m3_s if mass_flux is None else mass_flux
    return {
        "time_s": time_s,
        "left_mass_flux_kg_m2_s": through,
        "right_mass_flux_kg_m2_s": through,
        "mass_flux_mismatch_kg_m2_s": 0.0,
        "left_energy_flux_w_m2": 0.0,
        "right_energy_flux_w_m2": 0.0,
        "energy_flux_mismatch_w_m2": 0.0,
        "left_vapor_mass_flux_kg_m2_s": 0.0,
        "right_vapor_mass_flux_kg_m2_s": 0.0,
        "vapor_mass_flux_mismatch_kg_m2_s": 0.0,
        "momentum_difference_residual_pa": momentum_residual,
        "flux_derived_q_m3_s": q_m3_s,
        "flux_q_minus_applied_q_m3_s": 0.0,
        "interface_branch": branch,
    }


def _probe_rows(
    *,
    name: str,
    side: str,
    x_m: float,
    desired_values: list[float],
    undesired_values: list[float],
    pressure_values: list[float],
) -> list[dict]:
    times = [0.0, 1.0, 1.1, 1.6, 2.1, 2.3]
    rows: list[dict] = []
    for time_s, desired, undesired, pressure in zip(
        times,
        desired_values,
        undesired_values,
        pressure_values,
    ):
        row = {
            "time_s": time_s,
            "probe_name": name,
            "probe_side": side,
            "probe_cell_center_x_m": x_m,
            "delta_pressure_pa": pressure,
            "velocity_m_s": desired * 1.0e-6,
            "A_plus_pa": undesired if side == "left" else desired,
            "A_minus_pa": desired if side == "left" else undesired,
        }
        rows.append(row)
    return rows


def _dynamic_metrics(verification_item: str) -> dict:
    metrics = {
        "valve_x_m": 50.0,
        "left_c0_m_s": 100.0,
        "right_c0_m_s": 100.0,
        "q_roundoff_tolerance_m3_s": 1.0e-14,
        "closed_opening_threshold": 1.0e-12,
    }
    if verification_item in {"V-012C", "V-012D"}:
        metrics.update({"ramp_start_s": 1.0, "ramp_end_s": 2.0})
    return metrics


def test_opening_artifact_analysis_extracts_near_probe_timing(
    tmp_path: Path,
) -> None:
    case_id = "v012c_n0100_cfl0p5"
    item = {
        "case_id": case_id,
        "verification_item": "V-012C",
    }
    valve = [
        _valve_row(0.0, 0.0, 0.0, closed=True),
        _valve_row(1.0, 0.0, 0.0, closed=True),
        _valve_row(1.6, 0.5, 5.0e-5),
        _valve_row(2.1, 1.0, 1.0e-4),
    ]
    flux = [
        _flux_row(row["time_s"], row["applied_q_m3_s"])
        for row in valve
    ]
    probes = _probe_rows(
        name="near_left",
        side="left",
        x_m=40.0,
        desired_values=[0.0, 0.0, 0.0, -5.0, -10.0, -10.0],
        undesired_values=[0.0, 0.0, 0.0, 0.005, 0.01, 0.01],
        pressure_values=[0.0, 0.0, 0.0, -5.0, -10.0, -10.0],
    )
    probes += _probe_rows(
        name="near_right",
        side="right",
        x_m=60.0,
        desired_values=[0.0, 0.0, 0.0, 5.0, 10.0, 10.0],
        undesired_values=[0.0, 0.0, 0.0, 0.005, 0.01, 0.01],
        pressure_values=[0.0, 0.0, 0.0, 5.0, 10.0, 10.0],
    )
    _write_csv(tmp_path / f"{case_id}_valve_history.csv", valve)
    _write_csv(tmp_path / f"{case_id}_interface_flux_history.csv", flux)
    _write_csv(tmp_path / f"{case_id}_probe_history.csv", probes)

    result = extract_case_artifacts(
        tmp_path,
        item,
        _dynamic_metrics("V-012C"),
    )

    assert result["analysis_complete"] is True
    assert result["near_probe_characteristic_direction_pass"] is True
    assert result["near_left_p50_time_offset_s"] == pytest.approx(0.0)
    assert result["near_right_p50_time_offset_s"] == pytest.approx(0.0)
    assert result[
        "near_probe_characteristic_peak_time_offset_max_abs_s"
    ] == pytest.approx(0.0)
    assert result["near_probe_characteristic_max_leakage_ratio"] == pytest.approx(
        1.0e-3
    )


def test_closing_artifact_analysis_rebases_and_separates_wall_momentum(
    tmp_path: Path,
) -> None:
    case_id = "v012d_n0100_cfl0p5"
    item = {
        "case_id": case_id,
        "verification_item": "V-012D",
    }
    valve = [
        _valve_row(0.0, 1.0, 1.0e-4),
        _valve_row(1.5, 0.5, 5.0e-5),
        _valve_row(2.0, 0.0, 0.0, closed=True),
        _valve_row(2.5, 0.0, 0.0, closed=True),
    ]
    flux = [
        _flux_row(0.0, 1.0e-4),
        _flux_row(1.5, 5.0e-5),
        _flux_row(
            2.0,
            0.0,
            branch="closed_wall",
            mass_flux=1.0e-20,
            momentum_residual=100.0,
        ),
        _flux_row(
            2.5,
            0.0,
            branch="closed_wall",
            mass_flux=2.0e-20,
            momentum_residual=120.0,
        ),
    ]
    probes = _probe_rows(
        name="near_left",
        side="left",
        x_m=40.0,
        desired_values=[-3.0, -3.0, -3.0, 2.0, 7.0, 7.0],
        undesired_values=[0.2, 0.2, 0.2, 0.205, 0.21, 0.21],
        pressure_values=[-2.0, -2.0, -2.0, 3.0, 8.0, 8.0],
    )
    probes += _probe_rows(
        name="near_right",
        side="right",
        x_m=60.0,
        desired_values=[3.0, 3.0, 3.0, -2.0, -7.0, -7.0],
        undesired_values=[-0.2, -0.2, -0.2, -0.205, -0.21, -0.21],
        pressure_values=[2.0, 2.0, 2.0, -3.0, -8.0, -8.0],
    )
    _write_csv(tmp_path / f"{case_id}_valve_history.csv", valve)
    _write_csv(tmp_path / f"{case_id}_interface_flux_history.csv", flux)
    _write_csv(tmp_path / f"{case_id}_probe_history.csv", probes)

    result = extract_case_artifacts(
        tmp_path,
        item,
        _dynamic_metrics("V-012D"),
    )

    assert result["analysis_complete"] is True
    assert result["near_left_baseline_time_s"] == pytest.approx(1.0)
    assert result["near_right_baseline_time_s"] == pytest.approx(1.0)
    assert result["near_left_p50_time_offset_s"] == pytest.approx(0.0)
    assert result["near_right_p50_time_offset_s"] == pytest.approx(0.0)
    assert result["post_closure_sample_count_extracted"] == 2
    assert result[
        "post_closure_hydraulic_separation_fraction_extracted"
    ] == pytest.approx(1.0)
    assert result[
        "max_abs_post_closure_mass_flux_kg_m2_s_extracted"
    ] == pytest.approx(2.0e-20)
    assert result[
        "max_abs_finite_opening_momentum_residual_pa_extracted"
    ] == pytest.approx(0.0)
    assert result[
        "max_abs_closed_wall_momentum_residual_pa_diagnostic_extracted"
    ] == pytest.approx(120.0)
    assert result[
        "finite_opening_momentum_relation_applied_to_closed_rows_extracted"
    ] is False


def test_dynamic_analysis_rejects_missing_artifacts(tmp_path: Path) -> None:
    item = {
        "case_id": "v012b_n0050_cfl0p5",
        "verification_item": "V-012B",
    }
    with pytest.raises(FileNotFoundError):
        extract_case_artifacts(
            tmp_path,
            item,
            _dynamic_metrics("V-012B"),
        )


def _aggregate_row(
    verification_item: str,
    n_cells: int,
    cfl: float,
) -> dict:
    level = {50: 0, 100: 1, 200: 2}[n_cells]
    if n_cells == 100 and cfl == 0.25:
        level = 1
    solution = [1.0, 1.1, 1.15][level]
    error = [3.0e-2, 2.0e-2, 1.0e-2][level]
    row = {
        "verification_item": verification_item,
        "n_cells": n_cells,
        "dx_m": 100.0 / n_cells,
        "cfl": cfl,
        "comparison_groups": (
            "mesh_comparison;cfl_comparison"
            if n_cells == 100 and cfl == 0.5
            else "cfl_comparison"
            if n_cells == 100 and cfl == 0.25
            else "mesh_comparison"
        ),
        "runtime_s": float(n_cells) / cfl,
        "step_count": int(n_cells / cfl),
        "near_probe_characteristic_p50_time_offset_max_abs_s": error,
        "near_probe_characteristic_max_leakage_ratio": error,
        "near_probe_characteristic_peak_abs_mean_pa": 10.0 * solution,
        "max_abs_flux_q_minus_applied_q_m3_s_extracted": error * 1.0e-10,
        "max_applied_q_m3_s_extracted": solution * 1.0e-4,
        "final_applied_q_m3_s_extracted": solution * 1.0e-4,
        "min_finite_opening_applied_q_m3_s_extracted": solution * 1.0e-5,
        "max_abs_post_closure_flux_derived_q_m3_s_extracted": error * 1.0e-12,
        "max_abs_post_closure_mass_flux_kg_m2_s_extracted": error * 1.0e-10,
    }
    return row


def test_aggregate_observation_classifies_complete_run_set() -> None:
    rows = [
        {
            "verification_item": "V-012A",
            "n_cells": 50,
            "dx_m": 2.0,
            "cfl": 0.5,
            "comparison_groups": "preservation_sentinel",
            "runtime_s": 1.0,
            "step_count": 10,
        }
    ]
    for verification_item in ("V-012B", "V-012C", "V-012D"):
        for n_cells, cfl in (
            (50, 0.5),
            (100, 0.25),
            (100, 0.5),
            (200, 0.5),
        ):
            rows.append(_aggregate_row(verification_item, n_cells, cfl))

    observation = build_aggregate_observation(rows)

    assert observation["mesh_observation_complete"] is True
    assert observation["cfl_observation_complete"] is True
    assert observation["unclear_primary_metrics"] == []
    assert observation["cell_400_decision"] == (
        "not_required_by_initial_50_100_200_observation"
    )
    b_metrics = observation["mesh_observation"]["V-012B"]["metrics"]
    assert {row["classification"] for row in b_metrics} == {
        "monotonic_improvement",
        "contracting_differences",
    }
