"""Generate headless-safe plots from Stage 6 controlled-pressure-ramp artifacts.

This module reads existing CSV/JSON artifacts only. It does not run or alter the
solver, boundary conditions, numerical flux, or acceptance logic.
"""

from __future__ import annotations

import argparse
import csv
from io import BytesIO
import json
from pathlib import Path
from typing import Any

import numpy as np


PLOT_SUFFIXES = (
    "schedule_and_boundary_pressure.png",
    "probe_pressure_history.png",
    "characteristic_history.png",
    "boundary_flux_history.png",
)


def plotting_available() -> bool:
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        figure = Figure(figsize=(1, 1))
        FigureCanvasAgg(figure)
        figure.savefig(BytesIO(), format="png")
    except Exception:
        return False
    return True


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _float(row: dict[str, str], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid numeric column {key!r}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite value in column {key!r}")
    return value


def _new_figure(figsize: tuple[float, float]):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize)
    FigureCanvasAgg(figure)
    return figure


def _group_probe_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        name = row.get("probe_name", "")
        if not name:
            raise ValueError("probe row is missing probe_name")
        grouped.setdefault(name, []).append(row)
    for probe_rows in grouped.values():
        probe_rows.sort(key=lambda row: _float(row, "time_s"))
    return grouped


def _load_artifacts(
    output_dir: Path,
    case_name: str | None,
) -> tuple[str, dict[str, Any], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if case_name is None:
        candidates = sorted(output_dir.glob("*_metrics.json"))
        if len(candidates) != 1:
            raise ValueError(
                "case_name is required unless output_dir contains exactly one *_metrics.json"
            )
        metrics_path = candidates[0]
        stem = metrics_path.name.removesuffix("_metrics.json")
    else:
        stem = case_name
        metrics_path = output_dir / f"{stem}_metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    schedule = _read_csv(output_dir / f"{stem}_pressure_schedule.csv")
    probes = _read_csv(output_dir / f"{stem}_probe_history.csv")
    boundary = _read_csv(output_dir / f"{stem}_boundary_history.csv")
    return stem, metrics, schedule, probes, boundary


def _right_boundary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    right = [row for row in rows if row.get("side") == "right"]
    if not right:
        raise ValueError("boundary history contains no right-boundary rows")
    right.sort(key=lambda row: _float(row, "flux_evaluation_time_s"))
    return right


def _plot_schedule_and_boundary(
    output_dir: Path,
    stem: str,
    metrics: dict[str, Any],
    schedule: list[dict[str, str]],
    boundary: list[dict[str, str]],
) -> Path:
    p0 = float(metrics["initial_pressure_pa"])
    right = _right_boundary_rows(boundary)
    figure = _new_figure((10, 6))
    axis = figure.subplots()
    axis.plot(
        [_float(row, "time_s") for row in schedule],
        [_float(row, "requested_boundary_pressure_pa") - p0 for row in schedule],
        label="requested schedule",
    )
    axis.plot(
        [_float(row, "time_s") for row in schedule],
        [_float(row, "actual_schedule_pressure_pa") - p0 for row in schedule],
        linestyle="--",
        label="actual schedule",
    )
    axis.plot(
        [_float(row, "flux_evaluation_time_s") for row in right],
        [_float(row, "boundary_face_pressure_pa") - p0 for row in right],
        label="diagnostic boundary-face pressure",
    )
    axis.set_xlabel("time [s]")
    axis.set_ylabel("delta pressure [Pa]")
    axis.set_title(f"{stem}: requested pressure and boundary response")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_schedule_and_boundary_pressure.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_probe_pressure(
    output_dir: Path,
    stem: str,
    probes: list[dict[str, str]],
) -> Path:
    figure = _new_figure((10, 6))
    axis = figure.subplots()
    for name, rows in _group_probe_rows(probes).items():
        axis.plot(
            [_float(row, "time_s") for row in rows],
            [_float(row, "delta_pressure_pa") for row in rows],
            label=name,
        )
    axis.set_xlabel("time [s]")
    axis.set_ylabel("delta pressure [Pa]")
    axis.set_title(f"{stem}: probe pressure histories")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_probe_pressure_history.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_characteristics(
    output_dir: Path,
    stem: str,
    probes: list[dict[str, str]],
) -> Path:
    grouped = _group_probe_rows(probes)
    figure = _new_figure((10, max(4.5, 3.2 * len(grouped))))
    axes = np.atleast_1d(figure.subplots(len(grouped), 1, sharex=True))
    for axis, (name, rows) in zip(axes, grouped.items()):
        time = [_float(row, "time_s") for row in rows]
        axis.plot(time, [_float(row, "A_plus_pa") for row in rows], label="A+ right-going")
        axis.plot(time, [_float(row, "A_minus_pa") for row in rows], label="A- left-going")
        axis.set_ylabel("amplitude [Pa]")
        axis.set_title(name)
        axis.grid(True, alpha=0.3)
        axis.legend()
    axes[-1].set_xlabel("time [s]")
    figure.suptitle(f"{stem}: characteristic direction history")
    figure.tight_layout()
    path = output_dir / f"{stem}_characteristic_history.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_boundary_fluxes(
    output_dir: Path,
    stem: str,
    boundary: list[dict[str, str]],
) -> Path:
    right = _right_boundary_rows(boundary)
    time = [_float(row, "flux_evaluation_time_s") for row in right]
    figure = _new_figure((10, 8))
    axes = np.atleast_1d(figure.subplots(3, 1, sharex=True))
    axes[0].plot(time, [_float(row, "numerical_mass_flow_rate_kg_s") for row in right])
    axes[0].set_ylabel("mass flow [kg/s]")
    axes[1].plot(time, [_float(row, "numerical_energy_flow_rate_w") for row in right])
    axes[1].set_ylabel("energy flow [W]")
    axes[2].plot(time, [_float(row, "boundary_face_velocity_m_s") for row in right])
    axes[2].set_ylabel("face velocity [m/s]")
    axes[2].set_xlabel("time [s]")
    for axis in axes:
        axis.axhline(0.0, linewidth=0.8)
        axis.grid(True, alpha=0.3)
    figure.suptitle(f"{stem}: right-boundary flux and velocity")
    figure.tight_layout()
    path = output_dir / f"{stem}_boundary_flux_history.png"
    figure.savefig(path, dpi=160)
    return path


def generate_controlled_pressure_ramp_plots(
    output_dir: Path | str,
    case_name: str | None = None,
) -> list[Path]:
    directory = Path(output_dir)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    if not plotting_available():
        raise RuntimeError("matplotlib with the Agg backend is required for plotting")
    stem, metrics, schedule, probes, boundary = _load_artifacts(directory, case_name)
    generated = [
        _plot_schedule_and_boundary(directory, stem, metrics, schedule, boundary),
        _plot_probe_pressure(directory, stem, probes),
        _plot_characteristics(directory, stem, probes),
        _plot_boundary_fluxes(directory, stem, boundary),
    ]
    for path in generated:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"plot was not created correctly: {path}")
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name")
    args = parser.parse_args(argv)
    for path in generate_controlled_pressure_ramp_plots(args.output_dir, args.case_name):
        print(path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
