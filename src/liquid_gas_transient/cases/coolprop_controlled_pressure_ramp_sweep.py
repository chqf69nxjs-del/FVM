"""Stage 6 V-011 mesh/CFL observations for the controlled pressure ramp.

Software/numerical verification only. This module does not define physical
Validation, design-use acceptance, a formal accuracy band, or an exact solution.
The finest mesh is a comparison reference and lower CFL is not treated as truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
import time
from typing import Any, Callable

import numpy as np

from ..analyze_controlled_pressure_ramp_front_fit import (
    run_controlled_pressure_ramp_front_fit,
)
from ..analyze_controlled_pressure_ramp_results import (
    run_controlled_pressure_ramp_analysis,
)
from .coolprop_controlled_pressure_ramp import (
    CoolPropControlledPressureRampConfig,
    run_coolprop_controlled_pressure_ramp,
)


@dataclass(frozen=True)
class CoolPropControlledPressureRampSweepConfig:
    """Configuration for the first V-011 mesh/CFL observation."""

    case_name: str = "coolprop_controlled_pressure_ramp_sweep"
    output_version: str = "coolprop_controlled_pressure_ramp_sweep_v1"
    mesh_cells: tuple[int, ...] = (50, 100, 200)
    cfl_values: tuple[float, ...] = (0.25, 0.5)
    mesh_comparison_cfl: float = 0.5
    cfl_comparison_n_cells: int = 100
    primary_probe_fraction: float = 0.75
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_change_pa: float = 1.0e3
    ramp_start_s: float = 5.0e-3
    ramp_duration_s: float = 1.0e-2
    probe_fractions: tuple[float, ...] = (0.25, 0.50, 0.75)
    sample_every: int = 1
    max_steps: int = 30000
    post_arrival_margin_fraction: float = 0.10
    generate_comparison_plots: bool = True

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.mesh_cells))) != self.mesh_cells:
            raise ValueError("mesh_cells must be unique and ascending")
        if not self.mesh_cells or any(value < 10 for value in self.mesh_cells):
            raise ValueError("mesh_cells must contain values >= 10")
        if tuple(sorted(set(self.cfl_values))) != self.cfl_values:
            raise ValueError("cfl_values must be unique and ascending")
        if not self.cfl_values or any(not 0.0 < value <= 1.0 for value in self.cfl_values):
            raise ValueError("cfl_values must lie in (0, 1]")
        if self.mesh_comparison_cfl not in self.cfl_values:
            raise ValueError("mesh_comparison_cfl must be listed in cfl_values")
        if self.cfl_comparison_n_cells not in self.mesh_cells:
            raise ValueError("cfl_comparison_n_cells must be listed in mesh_cells")
        if self.primary_probe_fraction not in self.probe_fractions:
            raise ValueError("primary_probe_fraction must be listed in probe_fractions")
        if self.pipe_length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.initial_pressure_pa <= 0.0 or self.initial_temperature_K <= 0.0:
            raise ValueError("initial pressure and temperature must be positive")
        if self.pressure_change_pa == 0.0:
            raise ValueError("pressure_change_pa must be nonzero")
        if self.ramp_start_s < 0.0 or self.ramp_duration_s < 0.0:
            raise ValueError("ramp times must be non-negative")
        if self.sample_every <= 0 or self.max_steps <= 0:
            raise ValueError("sample_every and max_steps must be positive")


def case_id_for(n_cells: int, cfl: float) -> str:
    """Return a stable identifier for one unique numerical run."""

    return f"n{int(n_cells):04d}_cfl{int(round(float(cfl) * 100)):03d}"


def build_run_plan(
    config: CoolPropControlledPressureRampSweepConfig,
) -> list[dict[str, Any]]:
    """Return the de-duplicated mesh/CFL run plan."""

    pairs = {(n_cells, config.mesh_comparison_cfl) for n_cells in config.mesh_cells}
    pairs.update(
        (config.cfl_comparison_n_cells, cfl) for cfl in config.cfl_values
    )
    plan: list[dict[str, Any]] = []
    for n_cells, cfl in sorted(pairs):
        groups: list[str] = []
        if cfl == config.mesh_comparison_cfl:
            groups.append("mesh_comparison")
        if n_cells == config.cfl_comparison_n_cells:
            groups.append("cfl_comparison")
        plan.append(
            {
                "case_id": case_id_for(n_cells, cfl),
                "n_cells": int(n_cells),
                "cfl": float(cfl),
                "comparison_groups": groups,
            }
        )
    return plan


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _probe_name(fraction: float) -> str:
    return f"x_over_L_{fraction:g}"


def _primary_probe(
    observations: list[dict[str, Any]],
    fraction: float,
) -> dict[str, Any]:
    name = _probe_name(fraction)
    for item in observations:
        if item.get("probe_name") == name:
            return item
    raise KeyError(f"primary probe observation not found: {name}")


def _arrival_stats(
    observations: list[dict[str, Any]],
    label: str,
) -> tuple[float | None, float | None]:
    values = [
        _number(item.get(f"{label}_arrival_relative_error"))
        for item in observations
    ]
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None, None
    return float(np.mean(numeric)), float(np.max(numeric))


def _summary_row(
    plan_item: dict[str, Any],
    base_metrics: dict[str, Any],
    analysis: dict[str, Any],
    front_fit: dict[str, Any],
    *,
    primary_probe_fraction: float,
    baseline_runtime_s: float,
    postprocess_runtime_s: float,
) -> dict[str, Any]:
    observations = list(analysis["probe_observations"])
    primary = _primary_probe(observations, primary_probe_fraction)
    fit = dict(front_fit["p50_propagation_fit"])
    row: dict[str, Any] = {
        "case_id": plan_item["case_id"],
        "comparison_groups": ";".join(plan_item["comparison_groups"]),
        "n_cells": int(base_metrics["n_cells"]),
        "dx_m": float(base_metrics["dx_m"]),
        "cfl": float(base_metrics["cfl_target"]),
        "execution_pass": bool(base_metrics["overall_observation_execution_pass"]),
        "remained_single_phase": bool(base_metrics["remained_single_phase"]),
        "inferred_wave_speed_m_s": float(fit["inferred_wave_speed_m_s"]),
        "reference_sound_speed_m_s": float(fit["reference_sound_speed_m_s"]),
        "wave_speed_relative_error": float(fit["wave_speed_relative_error"]),
        "common_boundary_launch_delay_s": float(
            fit["common_boundary_launch_delay_s"]
        ),
        "abs_common_boundary_launch_delay_s": abs(
            float(fit["common_boundary_launch_delay_s"])
        ),
        "fit_residual_rms_s": float(fit["fit_residual_rms_s"]),
        "fit_residual_max_abs_s": float(fit["fit_residual_max_abs_s"]),
        "fit_r_squared": float(fit["fit_r_squared"]),
        "primary_probe_name": primary["probe_name"],
        "primary_peak_amplitude_ratio": _number(
            primary.get("peak_amplitude_ratio")
        ),
        "primary_peak_amplitude_error": (
            abs(abs(float(primary["peak_amplitude_ratio"])) - 1.0)
            if _number(primary.get("peak_amplitude_ratio")) is not None
            else None
        ),
        "primary_final_amplitude_ratio": _number(
            primary.get("final_amplitude_ratio")
        ),
        "primary_opposite_direction_leakage_ratio": _number(
            primary.get("opposite_direction_leakage_ratio")
        ),
        "primary_linear_velocity_relative_error": _number(
            primary.get("linear_velocity_relative_error")
        ),
        "budget_mass_relative_residual": _number(
            base_metrics.get("budget_mass_relative_residual")
        ),
        "energy_budget_balance_relative_residual": _number(
            base_metrics.get("energy_budget_balance_relative_residual")
        ),
        "phase_vapor_mass_balance_relative_residual": _number(
            base_metrics.get("phase_vapor_mass_balance_relative_residual")
        ),
        "baseline_runtime_s": float(baseline_runtime_s),
        "postprocess_runtime_s": float(postprocess_runtime_s),
        "total_case_runtime_s": float(baseline_runtime_s + postprocess_runtime_s),
        "property_backend_design_status": base_metrics[
            "property_backend_design_status"
        ],
    }
    for label in ("p10", "p50", "p90"):
        mean_value, max_value = _arrival_stats(observations, label)
        row[f"{label}_arrival_relative_error_mean"] = mean_value
        row[f"{label}_arrival_relative_error_max"] = max_value
    row["analysis_complete"] = bool(
        observations
        and int(fit["probe_count"]) >= 2
        and int(front_fit["numerical_p50_front_point_count"]) > 0
    )
    return row


def _trend(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["n_cells"]))
    values = [_number(row.get(key)) for row in ordered]
    if len(values) < 3 or any(value is None for value in values):
        return {"classification": "insufficient_data", "values": values}
    numeric = [float(value) for value in values if value is not None]
    tolerance = 1.0e-12
    if all(
        numeric[index + 1] <= numeric[index] + tolerance
        for index in range(len(numeric) - 1)
    ):
        classification = "monotonic_improvement"
    elif numeric[-1] < numeric[0]:
        classification = "improved_but_non_monotonic"
    else:
        classification = "no_clear_improvement"
    return {"classification": classification, "values": numeric}


def classify_mesh_observation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify observation-only mesh trends without defining a gate."""

    keys = (
        "wave_speed_relative_error",
        "abs_common_boundary_launch_delay_s",
        "p50_arrival_relative_error_mean",
        "primary_peak_amplitude_error",
        "primary_opposite_direction_leakage_ratio",
    )
    trends = {key: _trend(rows, key) for key in keys}
    classes = [item["classification"] for item in trends.values()]
    if all(value == "monotonic_improvement" for value in classes):
        overall = "monotonic_improvement"
    elif any(
        value in {"monotonic_improvement", "improved_but_non_monotonic"}
        for value in classes
    ):
        overall = "mixed_behavior"
    elif all(value == "insufficient_data" for value in classes):
        overall = "insufficient_data"
    else:
        overall = "no_clear_improvement"
    return {"overall_classification": overall, "metric_trends": trends}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _plot_comparisons(
    output_dir: Path,
    config: CoolPropControlledPressureRampSweepConfig,
    rows: list[dict[str, Any]],
) -> tuple[list[str], dict[str, str]]:
    generated: list[str] = []
    errors: dict[str, str] = {}
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception as exc:
        return [], {"matplotlib_import": str(exc)}

    specs: tuple[
        tuple[str, str, str, Callable[[float], float]], ...
    ] = (
        (
            "wave_speed_error_vs_dx",
            "wave_speed_relative_error",
            "wave-speed relative error",
            lambda value: value,
        ),
        (
            "launch_delay_vs_dx",
            "abs_common_boundary_launch_delay_s",
            "absolute common launch delay [ms]",
            lambda value: 1.0e3 * value,
        ),
        (
            "p50_timing_error_vs_dx",
            "p50_arrival_relative_error_mean",
            "mean p50 arrival relative error",
            lambda value: value,
        ),
        (
            "amplitude_error_vs_dx",
            "primary_peak_amplitude_error",
            "primary peak-amplitude error",
            lambda value: value,
        ),
        (
            "characteristic_leakage_vs_dx",
            "primary_opposite_direction_leakage_ratio",
            "opposite-direction leakage ratio",
            lambda value: value,
        ),
    )
    mesh_rows = sorted(
        [row for row in rows if "mesh_comparison" in row["comparison_groups"]],
        key=lambda row: float(row["dx_m"]),
        reverse=True,
    )
    for suffix, key, y_label, transform in specs:
        try:
            pairs = [
                (float(row["dx_m"]), _number(row.get(key))) for row in mesh_rows
            ]
            pairs = [
                (x_value, transform(float(y_value)))
                for x_value, y_value in pairs
                if y_value is not None
            ]
            figure = Figure(figsize=(8, 5))
            FigureCanvasAgg(figure)
            axis = figure.subplots()
            axis.plot(
                [item[0] for item in pairs],
                [item[1] for item in pairs],
                marker="o",
            )
            axis.set_xlabel("dx [m] (coarse to fine)")
            axis.set_ylabel(y_label)
            axis.set_title(f"{config.case_name}: {suffix.replace('_', ' ')}")
            axis.grid(True, alpha=0.3)
            figure.text(
                0.01,
                0.01,
                "software/numerical verification; not approved for design use",
                fontsize=8,
            )
            figure.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
            name = f"{config.case_name}_{suffix}.png"
            figure.savefig(output_dir / name, dpi=160)
            generated.append(name)
        except Exception as exc:  # pragma: no cover
            errors[suffix] = str(exc)
    return generated, errors


def _report_lines(
    config: CoolPropControlledPressureRampSweepConfig,
    metrics: dict[str, Any],
) -> list[str]:
    lines = [
        "# CoolProp controlled-pressure-ramp mesh/CFL observation",
        "",
        "Software / numerical verification only. This is not physical Validation or design-use acceptance.",
        "",
        f"- overall_sweep_execution_pass: {metrics['overall_sweep_execution_pass']}",
        f"- unique_run_count: {metrics['unique_run_count']}",
        "- formal_accuracy_threshold_applied: false",
        "- property_backend_design_status: not_approved_for_design_use",
        f"- mesh_classification: {metrics['mesh_observation']['overall_classification']}",
        "",
        "## Summary",
        "",
        "| case | n | CFL | wave-speed error | common delay [ms] | mean p50 error | amplitude error | leakage |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics["summary_rows"]:
        lines.append(
            "| {case_id} | {n_cells} | {cfl:.3g} | {speed:.6g} | {delay:.6g} | {p50:.6g} | {amplitude:.6g} | {leakage:.6g} |".format(
                case_id=row["case_id"],
                n_cells=row["n_cells"],
                cfl=row["cfl"],
                speed=float(row["wave_speed_relative_error"]),
                delay=1.0e3 * float(row["abs_common_boundary_launch_delay_s"]),
                p50=float(row["p50_arrival_relative_error_mean"]),
                amplitude=float(row["primary_peak_amplitude_error"]),
                leakage=float(row["primary_opposite_direction_leakage_ratio"]),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- the finest mesh is a comparison reference, not an exact solution",
            "- lower CFL is not treated as truth",
            "- no formal regression or acceptance band is defined in this observation",
            "- 400 cells should only be considered if the 50/100/200 trend is unclear",
        ]
    )
    return lines


def run_coolprop_controlled_pressure_ramp_sweep(
    output_dir: Path | str,
    config: CoolPropControlledPressureRampSweepConfig | None = None,
) -> dict[str, Any]:
    """Run the four unique V-011 mesh/CFL observation cases."""

    cfg = config or CoolPropControlledPressureRampSweepConfig()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    plan = build_run_plan(cfg)
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()

    for item in plan:
        run_dir = directory / item["case_id"]
        case_name = f"{cfg.case_name}_{item['case_id']}"
        run_cfg = CoolPropControlledPressureRampConfig(
            case_name=case_name,
            output_version="coolprop_controlled_pressure_ramp_v1",
            pipe_length_m=cfg.pipe_length_m,
            diameter_m=cfg.diameter_m,
            n_cells=item["n_cells"],
            cfl=item["cfl"],
            initial_pressure_pa=cfg.initial_pressure_pa,
            initial_temperature_K=cfg.initial_temperature_K,
            pressure_change_pa=cfg.pressure_change_pa,
            ramp_start_s=cfg.ramp_start_s,
            ramp_duration_s=cfg.ramp_duration_s,
            probe_fractions=cfg.probe_fractions,
            sample_every=cfg.sample_every,
            max_steps=cfg.max_steps,
            post_arrival_margin_fraction=cfg.post_arrival_margin_fraction,
        )

        baseline_started = time.perf_counter()
        base_metrics = run_coolprop_controlled_pressure_ramp(run_dir, run_cfg)
        baseline_runtime = time.perf_counter() - baseline_started

        post_started = time.perf_counter()
        analysis = run_controlled_pressure_ramp_analysis(
            run_dir,
            case_name,
            generate_plots=False,
        )
        front_fit = run_controlled_pressure_ramp_front_fit(
            run_dir,
            case_name,
            generate_plots=False,
        )
        postprocess_runtime = time.perf_counter() - post_started
        rows.append(
            _summary_row(
                item,
                base_metrics,
                analysis,
                front_fit,
                primary_probe_fraction=cfg.primary_probe_fraction,
                baseline_runtime_s=baseline_runtime,
                postprocess_runtime_s=postprocess_runtime,
            )
        )

    mesh_rows = [
        row for row in rows if "mesh_comparison" in row["comparison_groups"]
    ]
    cfl_rows = [
        row for row in rows if "cfl_comparison" in row["comparison_groups"]
    ]
    plots, plotting_errors = (
        _plot_comparisons(directory, cfg, rows)
        if cfg.generate_comparison_plots
        else ([], {})
    )
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "formal_accuracy_threshold_applied": False,
        "property_backend_design_status": "not_approved_for_design_use",
        "unique_run_count": len(plan),
        "run_plan": plan,
        "summary_rows": rows,
        "mesh_observation": classify_mesh_observation(mesh_rows),
        "cfl_observation": {
            "classification": "observation_only_lower_cfl_not_truth",
            "rows": cfl_rows,
        },
        "overall_sweep_execution_pass": all(
            bool(row["execution_pass"])
            and bool(row["analysis_complete"])
            and bool(row["remained_single_phase"])
            for row in rows
        ),
        "generated_comparison_plots": plots,
        "plotting_errors": plotting_errors,
        "runtime_s": float(time.perf_counter() - started),
        "limitations": [
            "finest mesh is a comparison reference, not an exact solution",
            "lower CFL is not treated as truth",
            "no formal accuracy threshold is applied",
            "400 cells are excluded unless 50/100/200 trends are unclear",
            "not physical Validation or design-use acceptance",
        ],
    }
    stem = cfg.case_name
    (directory / f"{stem}_sweep_config.json").write_text(
        json.dumps(asdict(cfg), indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / f"{stem}_sweep_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(directory / f"{stem}_sweep_summary.csv", rows)
    (directory / f"{stem}_sweep_report.md").write_text(
        "\n".join(_report_lines(cfg, metrics)) + "\n",
        encoding="utf-8",
    )
    return metrics
