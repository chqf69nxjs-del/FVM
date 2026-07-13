"""Fit the Stage 6 controlled-pressure-ramp p50 propagation front.

This post-processor separates propagation speed from a common boundary launch-time
offset. It reads existing observation artifacts only and does not define formal
regression bands, physical Validation, or design-use acceptance.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _finite_float(row: dict[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid numeric field {key!r}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite numeric field {key!r}")
    return value


def fit_p50_propagation(
    probe_summaries: Iterable[dict[str, Any]],
    *,
    reference_sound_speed_m_s: float,
    expected_boundary_p50_time_s: float,
) -> dict[str, Any]:
    """Fit ``arrival_time = launch_time + distance / wave_speed``.

    The slope diagnoses propagation speed while the intercept diagnoses a common
    boundary launch-time offset. The fit is observational only.
    """

    c0 = float(reference_sound_speed_m_s)
    expected_launch = float(expected_boundary_p50_time_s)
    if not np.isfinite(c0) or c0 <= 0.0:
        raise ValueError("reference_sound_speed_m_s must be finite and positive")
    if not np.isfinite(expected_launch) or expected_launch < 0.0:
        raise ValueError("expected_boundary_p50_time_s must be finite and non-negative")

    points: list[dict[str, float | str]] = []
    for item in probe_summaries:
        numerical = item.get("numerical_p50_arrival_time_s")
        if numerical is None:
            continue
        distance = _finite_float(item, "boundary_to_probe_distance_m")
        arrival = float(numerical)
        if not np.isfinite(arrival) or arrival <= 0.0:
            raise ValueError("numerical p50 arrival times must be finite and positive")
        points.append(
            {
                "probe_name": str(item.get("probe_name", "")),
                "distance_m": distance,
                "numerical_arrival_time_s": arrival,
                "theoretical_arrival_time_s": expected_launch + distance / c0,
            }
        )

    if len(points) < 2:
        raise ValueError("at least two numerical p50 probe arrivals are required")
    points.sort(key=lambda item: float(item["distance_m"]))

    distance = np.asarray([float(item["distance_m"]) for item in points], dtype=float)
    arrival = np.asarray(
        [float(item["numerical_arrival_time_s"]) for item in points], dtype=float
    )
    if np.ptp(distance) <= 0.0:
        raise ValueError("probe distances must not all be equal")

    design = np.column_stack((np.ones_like(distance), distance))
    coefficients, _, _, _ = np.linalg.lstsq(design, arrival, rcond=None)
    launch_time = float(coefficients[0])
    slope_s_m = float(coefficients[1])
    if not np.isfinite(slope_s_m) or slope_s_m <= 0.0:
        raise ValueError("fitted propagation slope must be finite and positive")
    inferred_speed = float(1.0 / slope_s_m)

    fitted = launch_time + slope_s_m * distance
    residual = arrival - fitted
    rms = float(np.sqrt(np.mean(residual**2)))
    max_abs = float(np.max(np.abs(residual)))
    total = float(np.sum((arrival - np.mean(arrival)) ** 2))
    residual_sum = float(np.sum(residual**2))
    r_squared = 1.0 if total == 0.0 else float(1.0 - residual_sum / total)

    theoretical = expected_launch + distance / c0
    direct_error = arrival - theoretical

    pairwise: list[dict[str, Any]] = []
    for left, right in zip(points[:-1], points[1:]):
        dx = float(right["distance_m"]) - float(left["distance_m"])
        dt = float(right["numerical_arrival_time_s"]) - float(
            left["numerical_arrival_time_s"]
        )
        speed = dx / dt if dx > 0.0 and dt > 0.0 else None
        pairwise.append(
            {
                "near_probe": left["probe_name"],
                "far_probe": right["probe_name"],
                "distance_difference_m": dx,
                "arrival_time_difference_s": dt,
                "pairwise_inferred_speed_m_s": speed,
            }
        )

    return {
        "fit_model": "arrival_time_s = launch_time_s + distance_m / inferred_speed_m_s",
        "probe_count": len(points),
        "reference_sound_speed_m_s": c0,
        "expected_boundary_p50_time_s": expected_launch,
        "fitted_boundary_p50_launch_time_s": launch_time,
        "common_boundary_launch_delay_s": launch_time - expected_launch,
        "fitted_slope_s_m": slope_s_m,
        "inferred_wave_speed_m_s": inferred_speed,
        "wave_speed_relative_error": abs(inferred_speed - c0) / c0,
        "fit_residual_rms_s": rms,
        "fit_residual_max_abs_s": max_abs,
        "fit_r_squared": r_squared,
        "mean_direct_arrival_delay_s": float(np.mean(direct_error)),
        "direct_arrival_delay_std_s": float(np.std(direct_error)),
        "points": points,
        "pairwise_speed_observations": pairwise,
        "formal_regression_band_defined": False,
    }


def extract_numerical_fraction_front(
    *,
    times_s: np.ndarray,
    x_m: np.ndarray,
    delta_pressure_pa: np.ndarray,
    pressure_change_pa: float,
    fraction: float = 0.50,
) -> list[dict[str, float]]:
    """Extract a linearly interpolated pressure-fraction front from x-t fields."""

    times = np.asarray(times_s, dtype=float)
    x = np.asarray(x_m, dtype=float)
    field = np.asarray(delta_pressure_pa, dtype=float)
    change = float(pressure_change_pa)
    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be in (0, 1)")
    if not np.isfinite(change) or change == 0.0:
        raise ValueError("pressure_change_pa must be finite and nonzero")
    if times.ndim != 1 or x.ndim != 1 or field.shape != (times.size, x.size):
        raise ValueError("pressure field dimensions are inconsistent")
    if not (
        np.all(np.isfinite(times))
        and np.all(np.isfinite(x))
        and np.all(np.isfinite(field))
    ):
        raise ValueError("front inputs must be finite")

    sign = 1.0 if change > 0.0 else -1.0
    target = fraction * abs(change)
    points: list[dict[str, float]] = []
    for time_s, profile_raw in zip(times, field):
        profile = sign * profile_raw
        candidates = np.flatnonzero(
            (profile[:-1] <= target) & (target <= profile[1:])
        )
        if candidates.size == 0:
            continue
        index = int(candidates[-1])
        x0 = float(x[index])
        x1 = float(x[index + 1])
        y0 = float(profile[index])
        y1 = float(profile[index + 1])
        if y1 == y0:
            front_x = 0.5 * (x0 + x1)
        else:
            front_x = x0 + (target - y0) * (x1 - x0) / (y1 - y0)
        points.append({"time_s": float(time_s), "front_x_m": float(front_x)})
    return points


def _plotting_available() -> bool:
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        figure = Figure(figsize=(1, 1))
        FigureCanvasAgg(figure)
        figure.canvas.draw()
    except Exception:
        return False
    return True


def _new_figure(figsize: tuple[float, float]):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize)
    FigureCanvasAgg(figure)
    return figure


def _plot_arrival_fit(
    output_dir: Path,
    stem: str,
    fit: dict[str, Any],
) -> Path:
    points = fit["points"]
    distance = np.asarray([float(item["distance_m"]) for item in points])
    numerical = np.asarray(
        [float(item["numerical_arrival_time_s"]) for item in points]
    )
    x_line = np.linspace(0.0, max(distance) * 1.05, 100)
    expected_launch = float(fit["expected_boundary_p50_time_s"])
    c0 = float(fit["reference_sound_speed_m_s"])
    fitted_launch = float(fit["fitted_boundary_p50_launch_time_s"])
    fitted_speed = float(fit["inferred_wave_speed_m_s"])

    figure = _new_figure((9, 5.8))
    axis = figure.subplots()
    axis.scatter(distance, numerical, label="numerical p50 probes")
    axis.plot(
        x_line,
        expected_launch + x_line / c0,
        linestyle="--",
        label="theoretical front",
    )
    axis.plot(
        x_line,
        fitted_launch + x_line / fitted_speed,
        linestyle=":",
        label="fitted numerical front",
    )
    axis.set_xlabel("boundary-to-probe distance [m]")
    axis.set_ylabel("p50 arrival time [s]")
    axis.set_title(f"{stem}: p50 propagation fit")
    axis.text(
        0.02,
        0.97,
        (
            f"inferred speed={fitted_speed:.6g} m/s\n"
            f"reference c0={c0:.6g} m/s\n"
            f"common launch delay={float(fit['common_boundary_launch_delay_s']):.6g} s\n"
            f"fit R2={float(fit['fit_r_squared']):.8f}"
        ),
        transform=axis.transAxes,
        va="top",
        fontsize=9,
    )
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_p50_propagation_fit.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_xt_front_overlay(
    output_dir: Path,
    stem: str,
    *,
    times_s: np.ndarray,
    x_m: np.ndarray,
    delta_pressure_pa: np.ndarray,
    pressure_change_pa: float,
    expected_boundary_p50_time_s: float,
    c0_m_s: float,
    numerical_front: list[dict[str, float]],
) -> Path:
    figure = _new_figure((10, 6))
    axis = figure.subplots()
    mesh = axis.pcolormesh(times_s, x_m, delta_pressure_pa.T, shading="auto")
    colorbar = figure.colorbar(mesh, ax=axis)
    colorbar.set_label("delta pressure [Pa]")

    theoretical_x = max(x_m) + 0.5 * (x_m[1] - x_m[0]) - c0_m_s * (
        times_s - expected_boundary_p50_time_s
    )
    valid = (theoretical_x >= min(x_m)) & (theoretical_x <= max(x_m))
    axis.plot(
        times_s[valid],
        theoretical_x[valid],
        linestyle="--",
        label="theoretical p50 front",
    )
    if numerical_front:
        axis.plot(
            [item["time_s"] for item in numerical_front],
            [item["front_x_m"] for item in numerical_front],
            linestyle=":",
            label="numerical p50 front",
        )
    axis.set_xlabel("time [s]")
    axis.set_ylabel("x [m]")
    axis.set_title(f"{stem}: x-t pressure map with p50 fronts")
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_xt_pressure_map_with_fronts.png"
    figure.savefig(path, dpi=160)
    return path


def run_controlled_pressure_ramp_front_fit(
    output_dir: Path | str,
    case_name: str | None = None,
    *,
    generate_plots: bool = True,
) -> dict[str, Any]:
    directory = Path(output_dir)
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    if case_name is None:
        candidates = sorted(directory.glob("*_analysis.json"))
        if len(candidates) != 1:
            raise ValueError(
                "case_name is required unless output_dir contains exactly one *_analysis.json"
            )
        stem = candidates[0].name.removesuffix("_analysis.json")
    else:
        stem = case_name

    metrics_path = directory / f"{stem}_metrics.json"
    config_path = directory / f"{stem}_config.json"
    summary_path = directory / f"{stem}_probe_observation_summary.csv"
    field_path = directory / f"{stem}_pressure_field_history.npz"
    for required in (metrics_path, config_path, summary_path, field_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    summaries = _read_csv(summary_path)
    c0 = float(metrics["c0"])
    expected_launch = float(config["ramp_start_s"]) + 0.5 * float(
        config["ramp_duration_s"]
    )
    fit = fit_p50_propagation(
        summaries,
        reference_sound_speed_m_s=c0,
        expected_boundary_p50_time_s=expected_launch,
    )

    with np.load(field_path) as data:
        times = np.asarray(data["times_s"], dtype=float)
        x_m = np.asarray(data["x_m"], dtype=float)
        delta_p = np.asarray(data["delta_pressure_pa"], dtype=float)
    numerical_front = extract_numerical_fraction_front(
        times_s=times,
        x_m=x_m,
        delta_pressure_pa=delta_p,
        pressure_change_pa=float(config["pressure_change_pa"]),
        fraction=0.50,
    )

    generated_plots: list[str] = []
    if generate_plots:
        if not _plotting_available():
            raise RuntimeError("matplotlib with the Agg backend is required for plotting")
        generated_plots = [
            _plot_arrival_fit(directory, stem, fit).name,
            _plot_xt_front_overlay(
                directory,
                stem,
                times_s=times,
                x_m=x_m,
                delta_pressure_pa=delta_p,
                pressure_change_pa=float(config["pressure_change_pa"]),
                expected_boundary_p50_time_s=expected_launch,
                c0_m_s=c0,
                numerical_front=numerical_front,
            ).name,
        ]

    result: dict[str, Any] = {
        "case_name": stem,
        "analysis_version": "controlled_pressure_ramp_front_fit_v1",
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_design_status": metrics.get(
            "property_backend_design_status",
            "not_approved_for_design_use",
        ),
        "p50_propagation_fit": fit,
        "numerical_p50_front_point_count": len(numerical_front),
        "generated_plots": generated_plots,
        "formal_regression_bands_defined": False,
        "notes": [
            "slope diagnoses propagation speed",
            "intercept diagnoses common boundary launch-time offset",
            "the numerical p50 front is interpolated from replayed cell-centre fields",
            "this is not physical Validation or design-use acceptance",
        ],
    }
    output_path = directory / f"{stem}_front_fit.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    result = run_controlled_pressure_ramp_front_fit(
        args.output_dir,
        args.case_name,
        generate_plots=not args.no_plots,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
