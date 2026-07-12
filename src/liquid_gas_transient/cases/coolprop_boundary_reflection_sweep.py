"""Stage 5 PR-C mesh/CFL observations for ideal boundary reflections.

Software/numerical verification only; not physical Validation or design-use
acceptance. Rigid-wall and fixed-pressure boundaries remain idealizations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import math
from pathlib import Path
import time
from typing import Any

import numpy as np

from .coolprop_boundary_reflection import (
    BoundaryKind,
    CoolPropBoundaryReflectionConfig,
    run_coolprop_boundary_reflection,
)
from .coolprop_small_amplitude_wave_sweep import common_time_grid, temporal_fwhm


@dataclass(frozen=True)
class CoolPropBoundaryReflectionSweepConfig:
    case_name: str = "coolprop_boundary_reflection_sweep"
    output_version: str = "coolprop_boundary_reflection_sweep_v1"
    boundary_kinds: tuple[BoundaryKind, ...] = ("rigid_wall", "fixed_pressure")
    mesh_cells: tuple[int, ...] = (50, 100, 200)
    cfl_values: tuple[float, ...] = (0.25, 0.5)
    mesh_comparison_cfl: float = 0.5
    cfl_comparison_n_cells: int = 100
    primary_probe_fraction: float = 0.90
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_amplitude_pa: float = 1.0e3
    pulse_center_fraction: float = 0.50
    pulse_sigma_fraction: float = 0.03
    probe_fractions: tuple[float, ...] = (0.75, 0.90)
    sample_every: int = 1
    max_steps: int = 30000
    window_half_width_sigma: float = 2.5
    generate_comparison_plots: bool = True

    def __post_init__(self) -> None:
        if not self.boundary_kinds:
            raise ValueError("at least one boundary kind is required")
        if any(kind not in {"rigid_wall", "fixed_pressure"} for kind in self.boundary_kinds):
            raise ValueError("unsupported boundary kind")
        if tuple(sorted(set(self.mesh_cells))) != self.mesh_cells or any(n < 10 for n in self.mesh_cells):
            raise ValueError("mesh_cells must be unique, ascending, and >= 10")
        if not self.cfl_values or any(c <= 0.0 or c > 1.0 for c in self.cfl_values):
            raise ValueError("cfl_values must lie in (0, 1]")
        if self.mesh_comparison_cfl not in self.cfl_values:
            raise ValueError("mesh_comparison_cfl must be listed in cfl_values")
        if self.cfl_comparison_n_cells not in self.mesh_cells:
            raise ValueError("cfl_comparison_n_cells must be listed in mesh_cells")
        if self.primary_probe_fraction not in self.probe_fractions:
            raise ValueError("primary_probe_fraction must be listed in probe_fractions")


def case_id_for(boundary_kind: str, n_cells: int, cfl: float) -> str:
    return f"{boundary_kind}_n{n_cells:04d}_cfl{int(round(cfl * 100)):03d}"


def build_run_plan(config: CoolPropBoundaryReflectionSweepConfig) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for boundary_kind in config.boundary_kinds:
        pairs = {(n, config.mesh_comparison_cfl) for n in config.mesh_cells}
        pairs.update({(config.cfl_comparison_n_cells, c) for c in config.cfl_values})
        for n_cells, cfl in sorted(pairs):
            groups: list[str] = []
            if cfl == config.mesh_comparison_cfl:
                groups.append("mesh_comparison")
            if n_cells == config.cfl_comparison_n_cells:
                groups.append("cfl_comparison")
            plan.append({
                "case_id": case_id_for(boundary_kind, n_cells, cfl),
                "boundary_kind": boundary_kind,
                "n_cells": n_cells,
                "cfl": cfl,
                "comparison_groups": groups,
            })
    return plan


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _probe_name(frac: float) -> str:
    return f"x_over_L_{frac:g}"


def _probe_metric(metrics: dict[str, Any], fraction: float) -> dict[str, Any]:
    name = _probe_name(fraction)
    for item in metrics.get("probes", []):
        if item.get("probe_name") == name:
            return item
    raise KeyError(f"probe metrics not found: {name}")


def _window_series(rows: list[dict[str, str]], probe: dict[str, Any], key: str, reflected: bool, sign: float) -> tuple[np.ndarray, np.ndarray]:
    prefix = "reflected" if reflected else "incident"
    start = float(probe[f"{prefix}_window_start_s"])
    end = float(probe[f"{prefix}_window_end_s"])
    name = str(probe["probe_name"])
    pairs = [
        (float(row["time_s"]), sign * float(row[key]))
        for row in rows
        if row.get("probe_name") == name and start <= float(row["time_s"]) <= end
    ]
    if len(pairs) < 3:
        return np.array([]), np.array([])
    return np.asarray([p[0] for p in pairs]), np.asarray([p[1] for p in pairs])


def _shape_data(rows: list[dict[str, str]], probe: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    expected = float(probe["expected_pressure_reflection_coefficient"])
    incident_t, incident_y = _window_series(rows, probe, "A_plus_pa", False, 1.0)
    reflected_t, reflected_y = _window_series(rows, probe, "A_minus_pa", True, 1.0 if expected > 0.0 else -1.0)
    incident = temporal_fwhm(incident_t, incident_y)
    reflected = temporal_fwhm(reflected_t, reflected_y)
    ratio = None
    if incident.get("fwhm_detected") and reflected.get("fwhm_detected"):
        width = float(incident["temporal_fwhm_s"])
        if width > 0.0:
            ratio = float(reflected["temporal_fwhm_s"] / width)
    if reflected_t.size:
        aligned_t = reflected_t - reflected_t[int(np.argmax(reflected_y))]
    else:
        aligned_t = reflected_t
    return ({
        "incident_temporal_fwhm_s": incident.get("temporal_fwhm_s"),
        "reflected_temporal_fwhm_s": reflected.get("temporal_fwhm_s"),
        "reflected_to_incident_fwhm_ratio": ratio,
    }, {"time_s": aligned_t, "value_pa": reflected_y})


def _shape_difference(target: dict[str, np.ndarray], reference: dict[str, np.ndarray]) -> tuple[float | None, float | None]:
    if min(target["time_s"].size, reference["time_s"].size) < 3:
        return None, None
    try:
        grid, a, b = common_time_grid(target["time_s"], target["value_pa"], reference["time_s"], reference["value_pa"])
    except ValueError:
        return None, None
    norm = float(np.sqrt(np.trapezoid(b * b, grid)))
    if norm <= 0.0:
        return None, None
    l2 = float(np.sqrt(np.trapezoid((a - b) ** 2, grid)) / norm)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    corr = float(np.dot(a, b) / denom) if denom > 0.0 else None
    return l2, corr


def _leakage(numerator: Any, denominator: Any) -> float | None:
    num, den = _number(numerator), _number(denominator)
    if num is None or den is None or den == 0.0:
        return None
    return float(abs(num) / abs(den))


def _boundary_residual(metrics: dict[str, Any]) -> tuple[str, float | None]:
    boundary = metrics.get("boundary_metrics", {})
    if metrics["boundary_kind"] == "rigid_wall":
        value = _number(boundary.get("max_abs_wall_velocity_m_s"))
        scale = float(metrics["pressure_amplitude_pa"]) / float(metrics["Z0"])
        return "normalized_wall_velocity_residual", (float(value / scale) if value is not None and scale > 0.0 else None)
    return "normalized_fixed_pressure_residual", _number(boundary.get("normalized_fixed_pressure_residual"))


def _summary_row(item: dict[str, Any], metrics: dict[str, Any], shape: dict[str, Any], primary_probe_fraction: float) -> dict[str, Any]:
    probe = _probe_metric(metrics, primary_probe_fraction)
    coefficient = _number(probe.get("pressure_reflection_coefficient"))
    expected = float(probe["expected_pressure_reflection_coefficient"])
    residual_name, residual = _boundary_residual(metrics)
    return {
        "case_id": item["case_id"],
        "boundary_kind": metrics["boundary_kind"],
        "comparison_groups": ";".join(item["comparison_groups"]),
        "n_cells": int(metrics["n_cells"]),
        "dx_m": float(metrics["dx_m"]),
        "cfl": float(metrics["cfl_target"]),
        "execution_pass": bool(metrics["overall_observation_execution_pass"]),
        "pressure_reflection_coefficient": coefficient,
        "expected_pressure_reflection_coefficient": expected,
        "pressure_reflection_magnitude_error": (float(abs(abs(coefficient) - 1.0)) if coefficient is not None else None),
        "reflected_arrival_time_relative_error": _number(probe.get("reflected_arrival_time_relative_error")),
        "incident_characteristic_leakage_ratio": _leakage(probe.get("incident_A_minus_leakage_peak_pa"), probe.get("incident_A_plus_peak_pa")),
        "reflected_characteristic_leakage_ratio": _leakage(probe.get("reflected_A_plus_leakage_peak_pa"), probe.get("reflected_A_minus_signed_extremum_pa")),
        "boundary_residual_metric": residual_name,
        "boundary_residual": residual,
        "budget_mass_relative_residual": _number(metrics.get("budget_mass_relative_residual")),
        "energy_budget_balance_relative_residual": _number(metrics.get("energy_budget_balance_relative_residual")),
        "phase_vapor_mass_balance_relative_residual": _number(metrics.get("phase_vapor_mass_balance_relative_residual")),
        "remained_single_phase": bool(metrics["remained_single_phase"]),
        "property_backend_design_status": metrics["property_backend_design_status"],
        **shape,
    }


def _trend(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [_number(row.get(key)) for row in rows]
    if len(values) < 3 or any(value is None for value in values):
        return {"classification": "insufficient_data", "values": values}
    numeric = [float(value) for value in values if value is not None]
    if all(numeric[i + 1] <= numeric[i] + 1e-12 for i in range(len(numeric) - 1)):
        result = "monotonic_improvement"
    elif numeric[-1] < numeric[0]:
        result = "improved_but_non_monotonic"
    else:
        result = "no_clear_improvement"
    return {"classification": result, "values": numeric}


def classify_mesh_observation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["n_cells"]))
    keys = (
        "pressure_reflection_magnitude_error",
        "reflected_arrival_time_relative_error",
        "boundary_residual",
        "reflected_characteristic_leakage_ratio",
        "waveform_l2_difference_vs_finest",
    )
    trends = {key: _trend(ordered, key) for key in keys}
    classes = [item["classification"] for item in trends.values()]
    if all(value == "monotonic_improvement" for value in classes):
        overall = "monotonic_improvement"
    elif any(value in {"monotonic_improvement", "improved_but_non_monotonic"} for value in classes):
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


def _plots(output_dir: Path, cfg: CoolPropBoundaryReflectionSweepConfig, rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    generated: list[str] = []
    errors: dict[str, str] = {}
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception as exc:
        return [], {"matplotlib_import": str(exc)}
    specs = (
        ("reflection_magnitude_error_vs_dx", "pressure_reflection_magnitude_error"),
        ("arrival_time_error_vs_dx", "reflected_arrival_time_relative_error"),
        ("boundary_residual_vs_dx", "boundary_residual"),
        ("characteristic_leakage_vs_dx", "reflected_characteristic_leakage_ratio"),
        ("waveform_difference_vs_dx", "waveform_l2_difference_vs_finest"),
    )
    for suffix, key in specs:
        try:
            fig = Figure(figsize=(8, 5)); FigureCanvasAgg(fig); ax = fig.subplots()
            for boundary in cfg.boundary_kinds:
                selected = sorted([row for row in rows if row["boundary_kind"] == boundary and "mesh_comparison" in row["comparison_groups"]], key=lambda row: float(row["dx_m"]), reverse=True)
                pairs = [(float(row["dx_m"]), _number(row.get(key))) for row in selected]
                pairs = [(x, y) for x, y in pairs if y is not None]
                ax.plot([p[0] for p in pairs], [p[1] for p in pairs], marker="o", label=boundary)
            ax.set_xlabel("dx [m] (coarse to fine)"); ax.set_ylabel(key); ax.grid(True, alpha=.3); ax.legend()
            fig.text(.01, .01, "software/numerical verification; not approved for design use", fontsize=8)
            fig.tight_layout(rect=(0, .03, 1, 1))
            name = f"{cfg.case_name}_{suffix}.png"; fig.savefig(output_dir / name, dpi=160); generated.append(name)
        except Exception as exc:  # pragma: no cover
            errors[suffix] = str(exc)
    return generated, errors


def run_coolprop_boundary_reflection_sweep(output_dir: Path | str, config: CoolPropBoundaryReflectionSweepConfig | None = None) -> dict[str, Any]:
    cfg = config or CoolPropBoundaryReflectionSweepConfig()
    directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True)
    plan = build_run_plan(cfg)
    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for item in plan:
        case_name = f"{cfg.case_name}_{item['case_id']}"
        run_dir = directory / item["case_id"]
        run_cfg = CoolPropBoundaryReflectionConfig(
            boundary_kind=item["boundary_kind"], case_name=case_name,
            pipe_length_m=cfg.pipe_length_m, diameter_m=cfg.diameter_m,
            n_cells=item["n_cells"], cfl=item["cfl"],
            initial_pressure_pa=cfg.initial_pressure_pa,
            initial_temperature_K=cfg.initial_temperature_K,
            pressure_amplitude_pa=cfg.pressure_amplitude_pa,
            pulse_center_fraction=cfg.pulse_center_fraction,
            pulse_sigma_fraction=cfg.pulse_sigma_fraction,
            probe_fractions=cfg.probe_fractions, sample_every=cfg.sample_every,
            max_steps=cfg.max_steps, window_half_width_sigma=cfg.window_half_width_sigma,
        )
        run_started = time.perf_counter()
        metrics = run_coolprop_boundary_reflection(run_dir, run_cfg)
        probe = _probe_metric(metrics, cfg.primary_probe_fraction)
        probe_rows = _read_csv(run_dir / f"{case_name}_probe_history.csv")
        shape, series = _shape_data(probe_rows, probe)
        row = _summary_row(item, metrics, shape, cfg.primary_probe_fraction)
        row["runtime_s"] = float(time.perf_counter() - run_started)
        rows.append(row); records.append({**item, "row": row, "series": series})
    for boundary in cfg.boundary_kinds:
        mesh = [record for record in records if record["boundary_kind"] == boundary and "mesh_comparison" in record["comparison_groups"]]
        reference = max(mesh, key=lambda record: int(record["n_cells"]))
        for record in mesh:
            l2, corr = _shape_difference(record["series"], reference["series"])
            record["row"]["waveform_l2_difference_vs_finest"] = l2
            record["row"]["waveform_correlation_vs_finest"] = corr
            record["row"]["finest_mesh_comparison_reference"] = reference["case_id"]
    mesh_observations = {
        boundary: classify_mesh_observation([row for row in rows if row["boundary_kind"] == boundary and "mesh_comparison" in row["comparison_groups"]])
        for boundary in cfg.boundary_kinds
    }
    cfl_observations = {
        boundary: {
            "classification": "observation_only_lower_cfl_not_truth",
            "rows": [row for row in rows if row["boundary_kind"] == boundary and "cfl_comparison" in row["comparison_groups"]],
        }
        for boundary in cfg.boundary_kinds
    }
    plots, plot_errors = _plots(directory, cfg, rows) if cfg.generate_comparison_plots else ([], {})
    metrics = {
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
        "mesh_observations": mesh_observations,
        "cfl_observations": cfl_observations,
        "overall_sweep_execution_pass": all(bool(row["execution_pass"]) for row in rows),
        "generated_comparison_plots": plots,
        "plotting_errors": plot_errors,
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
    (directory / f"{stem}_sweep_config.json").write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8")
    (directory / f"{stem}_sweep_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    _write_csv(directory / f"{stem}_sweep_summary.csv", rows)
    report = [
        "# CoolProp boundary-reflection mesh/CFL observation", "",
        "Software / numerical verification only.", "",
        f"- overall_sweep_execution_pass: {metrics['overall_sweep_execution_pass']}",
        "- formal_accuracy_threshold_applied: false",
        "- property_backend_design_status: not_approved_for_design_use", "",
        "## Mesh observation",
    ]
    report.extend(f"- {key}: {value['overall_classification']}" for key, value in mesh_observations.items())
    report.extend(["", "Lower CFL is not treated as truth. The finest mesh is not an exact solution."])
    (directory / f"{stem}_sweep_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return metrics
