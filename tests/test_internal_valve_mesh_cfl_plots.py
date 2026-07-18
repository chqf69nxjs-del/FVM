from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.plot_internal_valve_mesh_cfl_results import (
    PLOT_SUFFIXES,
    generate_internal_valve_mesh_cfl_plots,
    matplotlib_available,
)


def _summary_row(
    verification_item: str,
    n_cells: int,
    cfl: float,
) -> dict[str, object]:
    dx_m = 100.0 / n_cells
    level = {50: 1.0, 100: 0.8, 200: 0.7}[n_cells]
    if cfl == 0.25:
        level *= 0.98
    groups = []
    if cfl == 0.5:
        groups.append("mesh_comparison")
    if n_cells == 100:
        groups.append("cfl_comparison")
    base: dict[str, object] = {
        "case_id": (
            f"{verification_item.lower().replace('-', '')}_"
            f"n{n_cells:04d}_cfl{str(cfl).replace('.', 'p')}"
        ),
        "verification_item": verification_item,
        "n_cells": n_cells,
        "dx_m": dx_m,
        "cfl": cfl,
        "comparison_groups": ";".join(groups),
        "runtime_s": n_cells / cfl,
        "step_count": int(n_cells / cfl),
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 0.0,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "near_probe_characteristic_p50_time_offset_max_abs_s": (
            0.001 * level
        ),
        "near_probe_characteristic_peak_abs_mean_pa": 100.0 / level,
        "near_probe_characteristic_max_leakage_ratio": 1.0e-6 * level,
        "max_applied_q_m3_s_extracted": 7.0e-5 / level,
        "final_applied_q_m3_s_extracted": 5.0e-5 / level,
        "min_finite_opening_applied_q_m3_s_extracted": 4.0e-6 / level,
        "max_abs_post_closure_flux_derived_q_m3_s_extracted": (
            1.0e-24 * level
        ),
        "max_abs_post_closure_mass_flux_kg_m2_s_extracted": (
            1.0e-20 * level
        ),
    }
    return base


def _write_summary(path: Path) -> None:
    rows: list[dict[str, object]] = [
        {
            "case_id": "v012a_n0050_cfl0p5",
            "verification_item": "V-012A",
            "n_cells": 50,
            "dx_m": 2.0,
            "cfl": 0.5,
            "comparison_groups": "preservation_sentinel",
            "runtime_s": 1.0,
            "step_count": 10,
            "budget_mass_relative_residual": 0.0,
            "energy_budget_balance_relative_residual": 0.0,
            "phase_vapor_mass_balance_relative_residual": 0.0,
        }
    ]
    for item in ("V-012B", "V-012C", "V-012D"):
        for n_cells, cfl in (
            (50, 0.5),
            (100, 0.25),
            (100, 0.5),
            (200, 0.5),
        ):
            rows.append(_summary_row(item, n_cells, cfl))
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.skipif(
    not matplotlib_available(),
    reason="matplotlib is not installed",
)
def test_mesh_cfl_plotter_generates_nine_figures(tmp_path: Path) -> None:
    case_name = "v012_internal_valve_mesh_cfl_sweep"
    metrics_path = tmp_path / f"{case_name}_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "case_name": case_name,
                "partial_execution": False,
                "comparison_plots_complete": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_summary(tmp_path / f"{case_name}_summary.csv")

    result = generate_internal_valve_mesh_cfl_plots(tmp_path, case_name)

    assert result["plot_count"] == len(PLOT_SUFFIXES) == 9
    assert result["solver_rerun"] is False
    assert result["numerical_results_changed"] is False
    for filename in result["plot_files"]:
        assert (tmp_path / filename).stat().st_size > 0
    manifest = json.loads(
        (tmp_path / f"{case_name}_plot_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["plot_count"] == 9
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["comparison_plots_complete"] is True
    assert metrics["solver_rerun_for_plotting"] is False
    assert metrics["numerical_results_changed_by_plotting"] is False


def test_mesh_cfl_plotter_rejects_partial_execution(tmp_path: Path) -> None:
    case_name = "v012_internal_valve_mesh_cfl_sweep"
    (tmp_path / f"{case_name}_metrics.json").write_text(
        json.dumps({"partial_execution": True}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / f"{case_name}_summary.csv").write_text(
        "case_id\npartial\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="complete 13-run sweep"):
        generate_internal_valve_mesh_cfl_plots(tmp_path, case_name)
