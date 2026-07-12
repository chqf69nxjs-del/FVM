"""Generate headless-safe PNG plots from Stage 5 boundary-reflection artifacts.

This module reads existing CSV/JSON artifacts only. It does not run or alter the
solver, boundary conditions, numerical flux, or acceptance logic.
"""

from __future__ import annotations

import argparse
import csv
from io import BytesIO
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np


PLOT_SUFFIXES = (
    "probe_pressure_history.png",
    "characteristic_history.png",
    "boundary_face_history.png",
)


def plotting_available() -> bool:
    """Return True only when the non-GUI Agg backend can write a PNG."""

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


def _group_probe_rows(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        name = row.get("probe_name", "")
        if not name:
            raise ValueError("probe_history row is missing probe_name")
        grouped.setdefault(name, []).append(row)
    for probe_rows in grouped.values():
        probe_rows.sort(key=lambda row: _float(row, "time_s"))
    return grouped


def _load_artifacts(output_dir: Path, case_name: str | None) -> tuple[str, dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
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
    probe_rows = _read_csv(output_dir / f"{stem}_probe_history.csv")
    boundary_rows = _read_csv(output_dir / f"{stem}_boundary_history.csv")
    return stem, metrics, probe_rows, boundary_rows


def _new_figure(figsize: tuple[float, float]):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize)
    FigureCanvasAgg(figure)
    return figure


def _shade_windows(axis: Any, probe_metric: dict[str, Any]) -> None:
    windows = (
        ("incident_window_start_s", "incident_window_end_s", "incident window"),
        ("reflected_window_start_s", "reflected_window_end_s", "reflected window"),
    )
    for start_key, end_key, label in windows:
        start = probe_metric.get(start_key)
        end = probe_metric.get(end_key)
        if start is not None and end is not None:
            axis.axvspan(float(start), float(end), alpha=0.10, label=label)


def _plot_probe_pressure(
    output_dir: Path,
    stem: str,
    metrics: dict[str, Any],
    probe_rows: list[dict[str, str]],
) -> Path:
    figure = _new_figure((10, 6))
    axis = figure.subplots()
    grouped = _group_probe_rows(probe_rows)
    p0 = float(metrics["initial_pressure_pa"])
    for name, rows in grouped.items():
        time = [_float(row, "time_s") for row in rows]
        delta_p = [_float(row, "pressure_pa") - p0 for row in rows]
        axis.plot(time, delta_p, label=name)
    axis.axhline(0.0, linewidth=0.8)
    axis.set_xlabel("time [s]")
    axis.set_ylabel("delta pressure [Pa]")
    axis.set_title(f"{stem}: probe pressure history")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_probe_pressure_history.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_characteristics(
    output_dir: Path,
    stem: str,
    metrics: dict[str, Any],
    probe_rows: list[dict[str, str]],
) -> Path:
    grouped = _group_probe_rows(probe_rows)
    figure = _new_figure((10, max(4.5, 3.5 * len(grouped))))
    axes = np.atleast_1d(figure.subplots(len(grouped), 1, sharex=True))
    metric_by_name = {item["probe_name"]: item for item in metrics.get("probes", [])}
    for axis, (name, rows) in zip(axes, grouped.items()):
        time = [_float(row, "time_s") for row in rows]
        axis.plot(time, [_float(row, "A_plus_pa") for row in rows], label="A+ (right-going)")
        axis.plot(time, [_float(row, "A_minus_pa") for row in rows], label="A- (left-going)")
        if name in metric_by_name:
            _shade_windows(axis, metric_by_name[name])
        axis.axhline(0.0, linewidth=0.8)
        axis.set_ylabel("amplitude [Pa]")
        axis.set_title(name)
        axis.grid(True, alpha=0.3)
        axis.legend()
    axes[-1].set_xlabel("time [s]")
    figure.suptitle(f"{stem}: characteristic wave history")
    figure.tight_layout()
    path = output_dir / f"{stem}_characteristic_history.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_boundary_face(
    output_dir: Path,
    stem: str,
    metrics: dict[str, Any],
    boundary_rows: list[dict[str, str]],
) -> Path:
    right = [row for row in boundary_rows if row.get("side") == "right"]
    if not right:
        raise ValueError("boundary_history contains no right-boundary rows")
    right.sort(key=lambda row: _float(row, "flux_evaluation_time_s"))
    time = [_float(row, "flux_evaluation_time_s") for row in right]
    p0 = float(metrics["initial_pressure_pa"])
    delta_p = [_float(row, "boundary_face_pressure_pa") - p0 for row in right]
    velocity = [_float(row, "boundary_face_velocity_m_s") for row in right]

    figure = _new_figure((10, 7))
    pressure_axis, velocity_axis = figure.subplots(2, 1, sharex=True)
    pressure_axis.plot(time, delta_p)
    pressure_axis.axhline(0.0, linewidth=0.8)
    pressure_axis.set_ylabel("boundary delta p [Pa]")
    pressure_axis.grid(True, alpha=0.3)

    velocity_axis.plot(time, velocity)
    velocity_axis.axhline(0.0, linewidth=0.8)
    velocity_axis.set_xlabel("time [s]")
    velocity_axis.set_ylabel("boundary velocity [m/s]")
    velocity_axis.grid(True, alpha=0.3)

    figure.suptitle(f"{stem}: right-boundary face diagnostics")
    figure.tight_layout()
    path = output_dir / f"{stem}_boundary_face_history.png"
    figure.savefig(path, dpi=160)
    return path


def generate_boundary_reflection_plots(
    output_dir: Path | str,
    case_name: str | None = None,
) -> list[Path]:
    """Generate the three primary Stage 5 diagnostic plots.

    The directory must contain the PR-B metrics, probe-history, and
    boundary-history artifacts for the selected case.
    """

    directory = Path(output_dir)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    if not plotting_available():
        raise RuntimeError("matplotlib with the Agg backend is required for plotting")

    stem, metrics, probe_rows, boundary_rows = _load_artifacts(directory, case_name)
    generated = [
        _plot_probe_pressure(directory, stem, metrics, probe_rows),
        _plot_characteristics(directory, stem, metrics, probe_rows),
        _plot_boundary_face(directory, stem, metrics, boundary_rows),
    ]
    for path in generated:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"plot was not created correctly: {path}")
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path, help="directory containing PR-B artifacts")
    parser.add_argument("--case-name", help="artifact stem; auto-detected when unique")
    args = parser.parse_args(argv)
    for path in generate_boundary_reflection_plots(args.output_dir, args.case_name):
        print(path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
