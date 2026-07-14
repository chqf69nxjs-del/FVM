"""Plot Stage 6 V-012 internal-valve observation artifacts.

The plots are diagnostic software/numerical-verification evidence only. They do
not establish physical Validation, valve performance, or design-use acceptance.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import numpy as np


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _float(row: dict[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid numeric field {key!r}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite numeric field {key!r}")
    return value


def _new_figure(figsize: tuple[float, float]):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize)
    FigureCanvasAgg(figure)
    return figure


def _footer(figure) -> None:
    figure.text(
        0.01,
        0.01,
        "software/numerical verification only; not physical Validation or design-use acceptance",
        fontsize=8,
    )


def _relative_mismatch(row: dict[str, str], prefix: str) -> float:
    left = abs(_float(row, f"left_{prefix}"))
    right = abs(_float(row, f"right_{prefix}"))
    mismatch = abs(_float(row, f"{prefix.split('_flux')[0]}_flux_mismatch_{prefix.split('_', 2)[-1]}"))
    return mismatch / max(left, right, 1.0e-30)


def plot_opening_and_flow(
    output_dir: Path,
    stem: str,
    valve_rows: list[dict[str, str]],
) -> Path:
    times = np.asarray([_float(row, "time_s") for row in valve_rows])
    opening = np.asarray([_float(row, "opening") for row in valve_rows])
    raw_q = np.asarray([_float(row, "target_q_raw_m3_s") for row in valve_rows])
    limited_q = np.asarray([_float(row, "target_q_limited_m3_s") for row in valve_rows])
    actual_q = np.asarray([_float(row, "actual_q_from_mass_flux_m3_s") for row in valve_rows])

    figure = _new_figure((10, 6))
    axis = figure.subplots()
    axis.plot(times, opening, label="opening fraction")
    axis.set_xlabel("time [s]")
    axis.set_ylabel("opening fraction [-]")
    axis.set_ylim(-0.05, 1.05)
    axis.grid(True, alpha=0.3)

    flow_axis = axis.twinx()
    flow_axis.plot(times, raw_q, linestyle="--", label="raw Kv target Q")
    flow_axis.plot(times, limited_q, linestyle=":", label="Mach-limited target Q")
    flow_axis.plot(times, actual_q, label="mass-flux-derived Q")
    flow_axis.set_ylabel("volumetric flow [m3/s]")

    handles_1, labels_1 = axis.get_legend_handles_labels()
    handles_2, labels_2 = flow_axis.get_legend_handles_labels()
    axis.legend(handles_1 + handles_2, labels_1 + labels_2, loc="best")
    axis.set_title(f"{stem}: prescribed opening and valve flow")
    _footer(figure)
    figure.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    path = output_dir / f"{stem}_opening_and_flow.png"
    figure.savefig(path, dpi=160)
    return path


def plot_pressure_difference_and_mach(
    output_dir: Path,
    stem: str,
    valve_rows: list[dict[str, str]],
) -> Path:
    times = np.asarray([_float(row, "time_s") for row in valve_rows])
    dp = np.asarray([_float(row, "delta_p_pa") for row in valve_rows])
    mach = np.asarray([_float(row, "face_mach") for row in valve_rows])
    clipped = np.asarray(
        [str(row.get("mach_cap_active", "False")).lower() == "true" for row in valve_rows]
    )

    figure = _new_figure((10, 6))
    axis = figure.subplots()
    axis.plot(times, dp, label="p_left - p_right")
    axis.set_xlabel("time [s]")
    axis.set_ylabel("pressure difference [Pa]")
    axis.grid(True, alpha=0.3)

    mach_axis = axis.twinx()
    mach_axis.plot(times, mach, label="face Mach")
    if np.any(clipped):
        mach_axis.scatter(times[clipped], mach[clipped], marker="x", label="Mach cap active")
    mach_axis.set_ylabel("face Mach [-]")

    handles_1, labels_1 = axis.get_legend_handles_labels()
    handles_2, labels_2 = mach_axis.get_legend_handles_labels()
    axis.legend(handles_1 + handles_2, labels_1 + labels_2, loc="best")
    axis.set_title(f"{stem}: valve pressure difference and Mach tracking")
    _footer(figure)
    figure.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    path = output_dir / f"{stem}_pressure_difference_and_mach.png"
    figure.savefig(path, dpi=160)
    return path


def plot_interface_flux_mismatches(
    output_dir: Path,
    stem: str,
    flux_rows: list[dict[str, str]],
) -> Path:
    times = np.asarray([_float(row, "time_s") for row in flux_rows])

    specs = (
        (
            "mass",
            "left_mass_flux_kg_m2_s",
            "right_mass_flux_kg_m2_s",
            "mass_flux_mismatch_kg_m2_s",
        ),
        (
            "energy",
            "left_energy_flux_w_m2",
            "right_energy_flux_w_m2",
            "energy_flux_mismatch_w_m2",
        ),
        (
            "vapor mass",
            "left_vapor_mass_flux_kg_m2_s",
            "right_vapor_mass_flux_kg_m2_s",
            "vapor_mass_flux_mismatch_kg_m2_s",
        ),
    )

    figure = _new_figure((10, 6))
    axis = figure.subplots()
    for label, left_key, right_key, mismatch_key in specs:
        values = []
        for row in flux_rows:
            left = abs(_float(row, left_key))
            right = abs(_float(row, right_key))
            mismatch = abs(_float(row, mismatch_key))
            values.append(mismatch / max(left, right, 1.0e-30))
        axis.plot(times, np.maximum(values, 1.0e-20), label=f"{label} relative mismatch")

    axis.set_xlabel("time [s]")
    axis.set_ylabel("relative mismatch [-]")
    axis.set_yscale("log")
    axis.grid(True, alpha=0.3)
    axis.legend()
    axis.set_title(f"{stem}: two-sided conservative-flux matching")
    _footer(figure)
    figure.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    path = output_dir / f"{stem}_interface_flux_mismatch.png"
    figure.savefig(path, dpi=160)
    return path


def plot_probe_pressure_history(
    output_dir: Path,
    stem: str,
    probe_rows: list[dict[str, str]],
) -> Path:
    names = list(dict.fromkeys(row["probe_name"] for row in probe_rows))
    base_pressure = {
        name: _float(next(row for row in probe_rows if row["probe_name"] == name), "pressure_pa")
        for name in names
    }

    figure = _new_figure((10, 6))
    axis = figure.subplots()
    for name in names:
        rows = [row for row in probe_rows if row["probe_name"] == name]
        times = [_float(row, "time_s") for row in rows]
        delta_p = [_float(row, "pressure_pa") - base_pressure[name] for row in rows]
        axis.plot(times, delta_p, label=name)

    axis.set_xlabel("time [s]")
    axis.set_ylabel("pressure change from initial sample [Pa]")
    axis.grid(True, alpha=0.3)
    axis.legend()
    axis.set_title(f"{stem}: probe pressure histories")
    _footer(figure)
    figure.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    path = output_dir / f"{stem}_probe_pressure_history.png"
    figure.savefig(path, dpi=160)
    return path


def plot_internal_valve_operation_results(
    output_dir: Path | str,
    case_name: str | None = None,
) -> list[str]:
    directory = Path(output_dir)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    if case_name is None:
        candidates = sorted(directory.glob("*_valve_history.csv"))
        if len(candidates) != 1:
            raise ValueError(
                "case_name is required unless output_dir contains exactly one *_valve_history.csv"
            )
        stem = candidates[0].name.removesuffix("_valve_history.csv")
    else:
        stem = case_name

    valve_rows = _read_csv(directory / f"{stem}_valve_history.csv")
    flux_rows = _read_csv(directory / f"{stem}_interface_flux_history.csv")
    probe_rows = _read_csv(directory / f"{stem}_probe_history.csv")

    paths = [
        plot_opening_and_flow(directory, stem, valve_rows),
        plot_pressure_difference_and_mach(directory, stem, valve_rows),
        plot_interface_flux_mismatches(directory, stem, flux_rows),
        plot_probe_pressure_history(directory, stem, probe_rows),
    ]
    return [path.name for path in paths]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name")
    args = parser.parse_args(argv)
    for name in plot_internal_valve_operation_results(args.output_dir, args.case_name):
        print(name)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
