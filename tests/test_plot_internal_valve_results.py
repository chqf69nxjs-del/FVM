from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from liquid_gas_transient.plot_internal_valve_results import (
    PLOT_SUFFIXES,
    plot_internal_valve_results,
)


MATPLOTLIB_AVAILABLE = importlib.util.find_spec("matplotlib") is not None


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_minimal_artifacts(directory: Path, stem: str) -> None:
    metrics = {
        "overall_observation_execution_pass": True,
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 0.0,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "relative_budget_roundoff_tolerance": 1.0e-12,
        "max_abs_pressure_disturbance_pa": 0.0,
        "pressure_roundoff_tolerance_pa": 1.0e-6,
        "max_abs_velocity_m_s": 0.0,
        "velocity_roundoff_tolerance_m_s": 1.0e-10,
        "max_abs_mass_flux_mismatch_kg_m2_s": 0.0,
        "mass_flux_roundoff_tolerance_kg_m2_s": 1.0e-12,
        "max_abs_energy_flux_mismatch_w_m2": 0.0,
        "energy_flux_roundoff_tolerance_w_m2": 1.0e-12,
        "max_abs_vapor_mass_flux_mismatch_kg_m2_s": 0.0,
        "vapor_flux_roundoff_tolerance_kg_m2_s": 1.0e-12,
        "max_abs_momentum_difference_residual_pa": 0.0,
        "momentum_roundoff_tolerance_pa": 1.0e-6,
        "max_abs_flux_q_minus_applied_q_m3_s": 0.0,
        "q_roundoff_tolerance_m3_s": 1.0e-12,
    }
    (directory / f"{stem}_metrics.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )

    valve_rows = []
    flux_rows = []
    for time_s in (0.0, 0.001, 0.002):
        valve_rows.append(
            {
                "time_s": time_s,
                "opening_requested": 0.5,
                "opening_actual": 0.5,
                "delta_p_pa": 0.0,
                "raw_target_q_m3_s": 0.0,
                "applied_q_m3_s": 0.0,
                "q_limit_m3_s": 1.0,
                "mach_cap_active": False,
            }
        )
        flux_rows.append(
            {
                "time_s": time_s,
                "mass_flux_mismatch_kg_m2_s": 0.0,
                "energy_flux_mismatch_w_m2": 0.0,
                "vapor_mass_flux_mismatch_kg_m2_s": 0.0,
                "momentum_flux_difference_pa": 0.0,
                "expected_momentum_flux_difference_pa": 0.0,
                "momentum_difference_residual_pa": 0.0,
                "flux_derived_q_m3_s": 0.0,
                "flux_q_minus_applied_q_m3_s": 0.0,
            }
        )
    _write_csv(directory / f"{stem}_valve_history.csv", valve_rows)
    _write_csv(directory / f"{stem}_interface_flux_history.csv", flux_rows)

    probe_rows = []
    for probe_name in ("upstream", "downstream"):
        for time_s in (0.0, 0.001, 0.002):
            probe_rows.append(
                {
                    "time_s": time_s,
                    "probe_name": probe_name,
                    "delta_pressure_pa": 0.0,
                    "velocity_m_s": 0.0,
                }
            )
    _write_csv(directory / f"{stem}_probe_history.csv", probe_rows)


@pytest.mark.skipif(not MATPLOTLIB_AVAILABLE, reason="matplotlib is not installed")
def test_plot_internal_valve_results_creates_four_pngs(tmp_path: Path) -> None:
    stem = "synthetic_internal_valve"
    _write_minimal_artifacts(tmp_path, stem)

    result = plot_internal_valve_results(tmp_path)

    assert result["case_name"] == stem
    assert result["plot_count"] == 4
    assert result["solver_rerun"] is False
    assert result["numerical_results_changed"] is False
    for suffix in PLOT_SUFFIXES:
        path = tmp_path / f"{stem}_{suffix}.png"
        assert path.is_file()
        assert path.stat().st_size > 0


@pytest.mark.skipif(not MATPLOTLIB_AVAILABLE, reason="matplotlib is not installed")
def test_plotter_rejects_missing_required_column(tmp_path: Path) -> None:
    stem = "synthetic_internal_valve"
    _write_minimal_artifacts(tmp_path, stem)
    valve_path = tmp_path / f"{stem}_valve_history.csv"
    with valve_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row.pop("applied_q_m3_s")
    _write_csv(valve_path, rows)

    with pytest.raises(ValueError, match="applied_q_m3_s"):
        plot_internal_valve_results(tmp_path, stem)
