"""Post-process Stage 6 controlled-pressure-ramp artifacts.

The module computes observation diagnostics and optionally replays the same case
only to capture full pressure-field history for visualization. It does not define
formal regression bands, physical Validation, or design-use acceptance.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import fields
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .cases.coolprop_controlled_pressure_ramp import (
    CoolPropControlledPressureRampConfig,
    build_coolprop_controlled_pressure_ramp_solver,
)


FRACTIONS = (0.10, 0.50, 0.90)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("rows must not be empty")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _finite_float(row: dict[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid numeric column {key!r}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite value in column {key!r}")
    return value


def group_probe_rows(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        name = str(row.get("probe_name", ""))
        if not name:
            raise ValueError("probe row is missing probe_name")
        grouped.setdefault(name, []).append(dict(row))
    for probe_rows in grouped.values():
        probe_rows.sort(key=lambda row: _finite_float(row, "time_s"))
    return grouped


def detect_fraction_crossing_time(
    rows: list[dict[str, Any]],
    *,
    fraction: float,
    pressure_change_pa: float,
) -> float | None:
    """Return first linearly interpolated signed pressure-fraction crossing."""

    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be in (0, 1)")
    if not np.isfinite(pressure_change_pa) or pressure_change_pa == 0.0:
        raise ValueError("pressure_change_pa must be finite and nonzero")
    if len(rows) < 2:
        return None

    ordered = sorted(rows, key=lambda row: _finite_float(row, "time_s"))
    sign = 1.0 if pressure_change_pa > 0.0 else -1.0
    baseline = _finite_float(ordered[0], "delta_pressure_pa")
    target = fraction * abs(pressure_change_pa)

    for left, right in zip(ordered[:-1], ordered[1:]):
        t0 = _finite_float(left, "time_s")
        t1 = _finite_float(right, "time_s")
        y0 = sign * (_finite_float(left, "delta_pressure_pa") - baseline)
        y1 = sign * (_finite_float(right, "delta_pressure_pa") - baseline)
        if y0 >= target:
            return float(t0)
        if y0 < target <= y1 and t1 > t0:
            if y1 == y0:
                return float(t1)
            ratio = (target - y0) / (y1 - y0)
            return float(t0 + ratio * (t1 - t0))
    return None


def _config_from_json(path: Path) -> CoolPropControlledPressureRampConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {item.name for item in fields(CoolPropControlledPressureRampConfig)}
    data = {key: value for key, value in raw.items() if key in allowed}
    if "probe_fractions" in data:
        data["probe_fractions"] = tuple(float(value) for value in data["probe_fractions"])
    return CoolPropControlledPressureRampConfig(**data)


def build_probe_observation_metrics(
    probe_rows: list[dict[str, Any]],
    *,
    config: CoolPropControlledPressureRampConfig,
    base_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compute arrival, amplitude, direction, and linear-velocity diagnostics."""

    c0 = float(base_metrics["c0"])
    rho0 = float(base_metrics["rho0"])
    if c0 <= 0.0 or rho0 <= 0.0:
        raise ValueError("rho0 and c0 must be positive")

    sign = 1.0 if config.pressure_change_pa > 0.0 else -1.0
    summaries: list[dict[str, Any]] = []
    for name, rows in group_probe_rows(probe_rows).items():
        x_m = _finite_float(rows[0], "probe_cell_center_x_m")
        distance_m = config.pipe_length_m - x_m
        if not 0.0 < distance_m < config.pipe_length_m:
            raise ValueError("probe cell centre must lie inside the pipe")

        max_a_plus = max(abs(_finite_float(row, "A_plus_pa")) for row in rows)
        max_a_minus = max(abs(_finite_float(row, "A_minus_pa")) for row in rows)
        final_dp = _finite_float(rows[-1], "delta_pressure_pa")
        final_velocity = _finite_float(rows[-1], "velocity_m_s")
        peak_signed_dp = max(sign * _finite_float(row, "delta_pressure_pa") for row in rows)
        expected_velocity = -final_dp / (rho0 * c0)
        velocity_error = final_velocity - expected_velocity

        summary: dict[str, Any] = {
            "probe_name": name,
            "probe_cell_center_x_m": x_m,
            "probe_x_over_L": x_m / config.pipe_length_m,
            "boundary_to_probe_distance_m": distance_m,
            "max_abs_A_plus_pa": max_a_plus,
            "max_abs_A_minus_pa": max_a_minus,
            "opposite_direction_leakage_ratio": (
                max_a_plus / max_a_minus if max_a_minus > 0.0 else None
            ),
            "observed_propagation_direction": (
                "left_going" if max_a_minus > max_a_plus else "not_left_going_dominant"
            ),
            "final_delta_pressure_pa": final_dp,
            "final_amplitude_ratio": final_dp / config.pressure_change_pa,
            "peak_signed_delta_pressure_pa": peak_signed_dp,
            "peak_amplitude_ratio": peak_signed_dp / abs(config.pressure_change_pa),
            "final_velocity_m_s": final_velocity,
            "linear_acoustic_expected_velocity_m_s": expected_velocity,
            "linear_velocity_absolute_error_m_s": velocity_error,
            "linear_velocity_relative_error": (
                abs(velocity_error) / abs(expected_velocity)
                if expected_velocity != 0.0
                else None
            ),
        }

        for fraction in FRACTIONS:
            label = f"p{int(round(100.0 * fraction)):02d}"
            theoretical = (
                config.ramp_start_s
                + fraction * config.ramp_duration_s
                + distance_m / c0
            )
            numerical = detect_fraction_crossing_time(
                rows,
                fraction=fraction,
                pressure_change_pa=config.pressure_change_pa,
            )
            absolute_error = (
                abs(numerical - theoretical) if numerical is not None else None
            )
            summary[f"theoretical_{label}_arrival_time_s"] = float(theoretical)
            summary[f"numerical_{label}_arrival_time_s"] = numerical
            summary[f"{label}_arrival_absolute_error_s"] = absolute_error
            summary[f"{label}_arrival_relative_error"] = (
                absolute_error / theoretical
                if absolute_error is not None and theoretical > 0.0
                else None
            )
        summaries.append(summary)

    summaries.sort(key=lambda item: float(item["probe_cell_center_x_m"]))
    return summaries


def capture_pressure_field_history(
    config: CoolPropControlledPressureRampConfig,
    *,
    target_time_s: float,
) -> dict[str, np.ndarray]:
    """Replay the case to capture full pressure fields for an x-t map."""

    if not np.isfinite(target_time_s) or target_time_s <= 0.0:
        raise ValueError("target_time_s must be finite and positive")
    solver, _ = build_coolprop_controlled_pressure_ramp_solver(config)
    times = [float(solver.t)]
    fields = [np.asarray(solver.primitive().p, dtype=float) - config.initial_pressure_pa]

    for _ in range(config.max_steps):
        if solver.t >= target_time_s:
            break
        dt_s = solver.compute_dt(target_time_s)
        solver.step(dt_s)
        if solver.step_count % config.sample_every == 0 or solver.t >= target_time_s:
            times.append(float(solver.t))
            fields.append(
                np.asarray(solver.primitive().p, dtype=float)
                - config.initial_pressure_pa
            )
    else:
        raise RuntimeError("pressure-field replay exceeded max_steps")

    pressure = np.vstack(fields)
    if not np.all(np.isfinite(pressure)):
        raise ValueError("pressure-field history contains non-finite values")
    return {
        "times_s": np.asarray(times, dtype=float),
        "x_m": np.asarray(solver.grid.cell_centers, dtype=float),
        "delta_pressure_pa": pressure,
    }


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


def _plot_enhanced_probe_history(
    output_dir: Path,
    stem: str,
    probe_rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> Path:
    figure = _new_figure((10, 6))
    axis = figure.subplots()
    summary_by_name = {item["probe_name"]: item for item in summaries}
    for name, rows in group_probe_rows(probe_rows).items():
        (line,) = axis.plot(
            [_finite_float(row, "time_s") for row in rows],
            [_finite_float(row, "delta_pressure_pa") for row in rows],
            label=name,
        )
        summary = summary_by_name[name]
        theory = summary.get("theoretical_p50_arrival_time_s")
        numerical = summary.get("numerical_p50_arrival_time_s")
        if theory is not None:
            axis.axvline(
                float(theory),
                linestyle="--",
                linewidth=0.9,
                alpha=0.55,
                color=line.get_color(),
            )
        if numerical is not None:
            axis.axvline(
                float(numerical),
                linestyle=":",
                linewidth=1.0,
                alpha=0.8,
                color=line.get_color(),
            )
    axis.set_xlabel("time [s]")
    axis.set_ylabel("delta pressure [Pa]")
    axis.set_title(f"{stem}: probe histories with p50 arrivals")
    axis.text(
        0.01,
        0.99,
        "dashed: theoretical p50 | dotted: numerical p50",
        transform=axis.transAxes,
        va="top",
        fontsize=8,
    )
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_probe_pressure_with_arrivals.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_arrival_comparison(
    output_dir: Path,
    stem: str,
    summaries: list[dict[str, Any]],
) -> Path:
    figure = _new_figure((9, 5.5))
    axis = figure.subplots()
    labels = [str(item["probe_name"]) for item in summaries]
    x = np.arange(len(labels))
    theory = [float(item["theoretical_p50_arrival_time_s"]) for item in summaries]
    numerical = [
        float(item["numerical_p50_arrival_time_s"])
        if item["numerical_p50_arrival_time_s"] is not None
        else np.nan
        for item in summaries
    ]
    axis.plot(x, theory, marker="o", label="theoretical p50")
    axis.plot(x, numerical, marker="o", label="numerical p50")
    axis.set_xticks(x, labels)
    axis.set_xlabel("probe")
    axis.set_ylabel("arrival time [s]")
    axis.set_title(f"{stem}: p50 arrival-time comparison")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_arrival_time_comparison.png"
    figure.savefig(path, dpi=160)
    return path


def _plot_xt_pressure_map(
    output_dir: Path,
    stem: str,
    fields: dict[str, np.ndarray],
    config: CoolPropControlledPressureRampConfig,
    c0: float,
) -> Path:
    times = fields["times_s"]
    x_m = fields["x_m"]
    delta_p = fields["delta_pressure_pa"]
    figure = _new_figure((10, 6))
    axis = figure.subplots()
    mesh = axis.pcolormesh(times, x_m, delta_p.T, shading="auto")
    colorbar = figure.colorbar(mesh, ax=axis)
    colorbar.set_label("delta pressure [Pa]")

    p50_boundary_time = config.ramp_start_s + 0.5 * config.ramp_duration_s
    wave_x = config.pipe_length_m - c0 * (times - p50_boundary_time)
    valid = (wave_x >= 0.0) & (wave_x <= config.pipe_length_m)
    axis.plot(times[valid], wave_x[valid], linestyle="--", label="theoretical p50 front")
    for fraction in config.probe_fractions:
        axis.axhline(fraction * config.pipe_length_m, linewidth=0.5, alpha=0.35)
    axis.set_xlabel("time [s]")
    axis.set_ylabel("x [m]")
    axis.set_title(f"{stem}: x-t pressure map")
    axis.legend()
    figure.tight_layout()
    path = output_dir / f"{stem}_xt_pressure_map.png"
    figure.savefig(path, dpi=160)
    return path


def run_controlled_pressure_ramp_analysis(
    output_dir: Path | str,
    case_name: str | None = None,
    *,
    generate_plots: bool = True,
) -> dict[str, Any]:
    directory = Path(output_dir)
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    if case_name is None:
        candidates = sorted(directory.glob("*_metrics.json"))
        if len(candidates) != 1:
            raise ValueError(
                "case_name is required unless output_dir contains exactly one *_metrics.json"
            )
        stem = candidates[0].name.removesuffix("_metrics.json")
    else:
        stem = case_name

    metrics_path = directory / f"{stem}_metrics.json"
    config_path = directory / f"{stem}_config.json"
    probe_path = directory / f"{stem}_probe_history.csv"
    if not metrics_path.is_file() or not config_path.is_file():
        raise FileNotFoundError("metrics and config artifacts are required")

    base_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = _config_from_json(config_path)
    probe_rows = _read_csv(probe_path)
    probe_summaries = build_probe_observation_metrics(
        probe_rows,
        config=config,
        base_metrics=base_metrics,
    )
    fields = capture_pressure_field_history(
        config,
        target_time_s=float(base_metrics["target_time_s"]),
    )

    npz_name = f"{stem}_pressure_field_history.npz"
    np.savez_compressed(directory / npz_name, **fields)
    summary_csv_name = f"{stem}_probe_observation_summary.csv"
    _write_csv(directory / summary_csv_name, probe_summaries)

    generated_plots: list[str] = []
    if generate_plots:
        if not _plotting_available():
            raise RuntimeError("matplotlib with the Agg backend is required for plotting")
        generated_plots = [
            _plot_enhanced_probe_history(
                directory,
                stem,
                probe_rows,
                probe_summaries,
            ).name,
            _plot_arrival_comparison(directory, stem, probe_summaries).name,
            _plot_xt_pressure_map(
                directory,
                stem,
                fields,
                config,
                float(base_metrics["c0"]),
            ).name,
        ]

    analysis: dict[str, Any] = {
        "case_name": stem,
        "analysis_version": "controlled_pressure_ramp_analysis_v1",
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_design_status": base_metrics.get(
            "property_backend_design_status",
            "not_approved_for_design_use",
        ),
        "arrival_fractions": list(FRACTIONS),
        "probe_observations": probe_summaries,
        "pressure_field_history_path": npz_name,
        "probe_summary_csv_path": summary_csv_name,
        "generated_plots": generated_plots,
        "formal_regression_bands_defined": False,
        "notes": [
            "p10/p50/p90 arrivals use signed pressure-fraction crossings",
            "x-t history is produced by replaying the same configuration",
            "finest mesh is not an exact solution",
            "lower CFL is not truth",
        ],
    }
    analysis_path = directory / f"{stem}_analysis.json"
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    analysis = run_controlled_pressure_ramp_analysis(
        args.output_dir,
        args.case_name,
        generate_plots=not args.no_plots,
    )
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
