"""Plot right-boundary mass/energy flow rates and their time integrals.

This utility reads an existing Stage 5 ``*_boundary_history.csv`` artifact.
It does not run or modify the solver, boundary condition, numerical flux, or
acceptance logic.
"""

from __future__ import annotations

import argparse
import csv
from io import BytesIO
from pathlib import Path
from typing import Iterable

import numpy as np


PLOT_SUFFIX = "boundary_flux_budget_history.png"


def plotting_available() -> bool:
    """Return True only when the headless Agg backend can write PNG files."""

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


def _right_boundary_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    selected = [row for row in rows if row.get("side") == "right"]
    if not selected:
        raise ValueError("boundary_history contains no right-boundary rows")
    selected.sort(key=lambda row: _float(row, "flux_evaluation_time_s"))
    return selected


def _cumulative_interval_integral(
    rows: list[dict[str, str]],
    rate_key: str,
) -> np.ndarray:
    """Integrate one piecewise-constant step rate using the recorded ``dt_s``."""

    rates = np.asarray([_float(row, rate_key) for row in rows], dtype=float)
    dt = np.asarray([_float(row, "dt_s") for row in rows], dtype=float)
    if np.any(dt <= 0.0):
        raise ValueError("dt_s must be positive")
    return np.cumsum(rates * dt)


def generate_boundary_flux_budget_plot(
    output_dir: Path | str,
    case_name: str | None = None,
) -> Path:
    """Generate the Stage 5 right-boundary flow/budget diagnostic PNG.

    The directory must contain ``<case_name>_boundary_history.csv``. When
    ``case_name`` is omitted, the artifact stem is auto-detected only if the
    directory contains exactly one matching boundary-history file.
    """

    directory = Path(output_dir)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    if not plotting_available():
        raise RuntimeError("matplotlib with the Agg backend is required for plotting")

    if case_name is None:
        candidates = sorted(directory.glob("*_boundary_history.csv"))
        if len(candidates) != 1:
            raise ValueError(
                "case_name is required unless output_dir contains exactly one "
                "*_boundary_history.csv"
            )
        history_path = candidates[0]
        stem = history_path.name.removesuffix("_boundary_history.csv")
    else:
        stem = case_name
        history_path = directory / f"{stem}_boundary_history.csv"

    rows = _right_boundary_rows(_read_csv(history_path))
    time = np.asarray([_float(row, "flux_evaluation_time_s") for row in rows], dtype=float)
    mass_rate = np.asarray(
        [_float(row, "numerical_mass_flow_rate_kg_s") for row in rows], dtype=float
    )
    energy_rate = np.asarray(
        [_float(row, "numerical_energy_flow_rate_w") for row in rows], dtype=float
    )
    cumulative_mass = _cumulative_interval_integral(
        rows, "numerical_mass_flow_rate_kg_s"
    )
    cumulative_energy = _cumulative_interval_integral(
        rows, "numerical_energy_flow_rate_w"
    )

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(11, 10))
    FigureCanvasAgg(figure)
    axes = figure.subplots(4, 1, sharex=True)

    axes[0].plot(time, mass_rate)
    axes[0].axhline(0.0, linewidth=0.8)
    axes[0].set_ylabel("mass flow rate [kg/s]")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(time, energy_rate)
    axes[1].axhline(0.0, linewidth=0.8)
    axes[1].set_ylabel("energy flow rate [W]")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(time, cumulative_mass)
    axes[2].axhline(0.0, linewidth=0.8)
    axes[2].set_ylabel("cumulative mass [kg]")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(time, cumulative_energy)
    axes[3].axhline(0.0, linewidth=0.8)
    axes[3].set_xlabel("time [s]")
    axes[3].set_ylabel("cumulative energy [J]")
    axes[3].grid(True, alpha=0.3)

    figure.suptitle(f"{stem}: right-boundary numerical flux and budget history")
    figure.tight_layout()
    path = directory / f"{stem}_{PLOT_SUFFIX}"
    figure.savefig(path, dpi=160)
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"plot was not created correctly: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name")
    args = parser.parse_args(argv)
    print(generate_boundary_flux_budget_plot(args.output_dir, args.case_name))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
