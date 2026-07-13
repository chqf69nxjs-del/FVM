from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.plot_controlled_pressure_ramp_results import (
    generate_controlled_pressure_ramp_plots,
    plotting_available,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_artifacts(output_dir: Path, stem: str = "synthetic_pressure_ramp") -> None:
    metrics = {"case_name": stem, "initial_pressure_pa": 8.0e6}
    (output_dir / f"{stem}_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    schedule = [
        {
            "time_s": t,
            "requested_boundary_pressure_pa": 8.0e6 + dp,
            "actual_schedule_pressure_pa": 8.0e6 + dp,
        }
        for t, dp in ((0.0, 0.0), (0.1, 500.0), (0.2, 1000.0))
    ]
    _write_csv(output_dir / f"{stem}_pressure_schedule.csv", schedule)
    probes: list[dict[str, object]] = []
    for name, delay in (("x_over_L_0.25", 0.2), ("x_over_L_0.5", 0.1), ("x_over_L_0.75", 0.0)):
        for t in (0.0, 0.1, 0.2, 0.3):
            dp = 1000.0 if t >= 0.1 + delay else 0.0
            probes.append({
                "time_s": t,
                "probe_name": name,
                "delta_pressure_pa": dp,
                "A_plus_pa": 0.0,
                "A_minus_pa": dp,
            })
    _write_csv(output_dir / f"{stem}_probe_history.csv", probes)
    boundary: list[dict[str, object]] = []
    for t, dp in ((0.0, 0.0), (0.1, 500.0), (0.2, 1000.0)):
        for side in ("left", "right"):
            boundary.append({
                "side": side,
                "flux_evaluation_time_s": t,
                "boundary_face_pressure_pa": 8.0e6 + (dp if side == "right" else 0.0),
                "boundary_face_velocity_m_s": -0.001 if side == "right" else 0.0,
                "numerical_mass_flow_rate_kg_s": -1.0 if side == "right" else 0.0,
                "numerical_energy_flow_rate_w": -2.0e5 if side == "right" else 0.0,
            })
    _write_csv(output_dir / f"{stem}_boundary_history.csv", boundary)


def test_plotting_available_returns_bool() -> None:
    assert isinstance(plotting_available(), bool)


def test_generate_controlled_pressure_ramp_plots(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    stem = "synthetic_pressure_ramp"
    _write_artifacts(tmp_path, stem)
    generated = generate_controlled_pressure_ramp_plots(tmp_path, stem)
    expected = {
        tmp_path / f"{stem}_schedule_and_boundary_pressure.png",
        tmp_path / f"{stem}_probe_pressure_history.png",
        tmp_path / f"{stem}_characteristic_history.png",
        tmp_path / f"{stem}_boundary_flux_history.png",
    }
    assert set(generated) == expected
    assert all(path.is_file() and path.stat().st_size > 0 for path in expected)


def test_generate_controlled_pressure_ramp_plots_auto_detects_case(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    _write_artifacts(tmp_path)
    generated = generate_controlled_pressure_ramp_plots(tmp_path)
    assert len(generated) == 4
