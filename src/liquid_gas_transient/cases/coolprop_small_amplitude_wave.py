"""CoolProp single-phase CO2 small-amplitude Gaussian wave observation run.

This module is an independent software/numerical verification observation case.
It is not a design evaluation, validation, design-use approval of CoolProp, or a
HEM/HNE/DVCM/two-phase/flashing assessment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import importlib.metadata
from io import BytesIO
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import TransmissiveBoundary
from ..config import PipeGeometry
from ..eos import LCO2PropertyEOSAdapter
from ..grid import UniformGrid
from ..phase_change import NoPhaseChange
from ..properties import CoolPropCO2Backend, coolprop_available
from ..solver import FvmSolver
from ..source_terms import NoSource
from ..state import make_conserved


@dataclass(frozen=True)
class CoolPropSmallAmplitudeWaveConfig:
    """Configuration for the initial CoolProp small-amplitude wave run."""

    case_name: str = "coolprop_small_amplitude_wave"
    output_version: str = "coolprop_small_amplitude_wave_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    n_cells: int = 100
    cfl: float = 0.5
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_amplitude_pa: float = 1.0e3
    pulse_center_fraction: float = 0.15
    pulse_sigma_fraction: float = 0.03
    probe_fractions: tuple[float, ...] = (0.25, 0.5, 0.75)
    sample_every: int = 1
    max_steps: int = 10000
    t_end_s: float | None = None
    arrival_threshold_fraction: float = 0.5
    max_perturbation_ratio: float = 1.0e-3
    post_arrival_margin_fraction: float = 0.25
    reflection_safety_margin_fraction: float = 0.25

    def __post_init__(self) -> None:
        if self.pipe_length_m <= 0.0:
            raise ValueError("pipe_length_m must be positive")
        if self.diameter_m <= 0.0:
            raise ValueError("diameter_m must be positive")
        if self.n_cells < 10:
            raise ValueError("n_cells must be at least 10")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.initial_pressure_pa <= 0.0:
            raise ValueError("initial_pressure_pa must be positive")
        if self.initial_temperature_K <= 0.0:
            raise ValueError("initial_temperature_K must be positive")
        if self.pressure_amplitude_pa <= 0.0:
            raise ValueError("pressure_amplitude_pa must be positive")
        if self.pressure_amplitude_pa / self.initial_pressure_pa > self.max_perturbation_ratio:
            raise ValueError("pressure perturbation ratio is too large for this small-amplitude case")
        if not 0.0 < self.pulse_center_fraction < 1.0:
            raise ValueError("pulse_center_fraction must be in (0, 1)")
        if self.pulse_sigma_fraction <= 0.0:
            raise ValueError("pulse_sigma_fraction must be positive")
        if not self.probe_fractions:
            raise ValueError("at least one probe is required")
        for probe in self.probe_fractions:
            if not 0.0 < probe < 1.0:
                raise ValueError("probe fractions must be in (0, 1)")
            if probe <= self.pulse_center_fraction:
                raise ValueError("probe positions must be to the right of the pulse center")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.sample_every <= 0:
            raise ValueError("sample_every must be positive")
        if self.t_end_s is not None and self.t_end_s <= 0.0:
            raise ValueError("t_end_s must be positive when provided")
        if not 0.0 < self.arrival_threshold_fraction < 1.0:
            raise ValueError("arrival_threshold_fraction must be in (0, 1)")
        if self.post_arrival_margin_fraction <= 0.0:
            raise ValueError("post_arrival_margin_fraction must be positive")
        if not 0.0 < self.reflection_safety_margin_fraction < 1.0:
            raise ValueError("reflection_safety_margin_fraction must be in (0, 1)")


def gaussian_threshold_offset(sigma_m: float, threshold_fraction: float) -> float:
    """Return the Gaussian leading-side offset from center for a threshold fraction.

    For ``dp = A exp(-0.5 ((x - x0) / sigma)^2)``, the right-going
    leading-side threshold point is ``x0 + offset``.
    """

    if sigma_m <= 0.0:
        raise ValueError("sigma_m must be positive")
    if not 0.0 < threshold_fraction < 1.0:
        raise ValueError("threshold_fraction must be in (0, 1)")
    return float(sigma_m * math.sqrt(-2.0 * math.log(threshold_fraction)))


def gaussian_threshold_initial_x(x0_m: float, sigma_m: float, threshold_fraction: float, propagation_direction: str = "right") -> float:
    """Return initial Gaussian threshold x on the leading side.

    The case initializes a right-running pulse. With positive x to the right,
    the leading side is therefore at ``x0 + offset``; a left-running extension
    would use ``x0 - offset``.
    """

    offset = gaussian_threshold_offset(sigma_m, threshold_fraction)
    if propagation_direction == "right":
        return float(x0_m + offset)
    if propagation_direction == "left":
        return float(x0_m - offset)
    raise ValueError("propagation_direction must be 'right' or 'left'")


def _threshold_metadata(cfg: CoolPropSmallAmplitudeWaveConfig, x0: float, xp: float) -> dict[str, Any]:
    sigma = cfg.pulse_sigma_fraction * cfg.pipe_length_m
    offset = gaussian_threshold_offset(sigma, cfg.arrival_threshold_fraction)
    x_threshold = gaussian_threshold_initial_x(x0, sigma, cfg.arrival_threshold_fraction, "right")
    distance = xp - x0
    distance_sigma = distance / sigma
    initial_tail_ratio = float(math.exp(-0.5 * distance_sigma**2))
    primary = bool(distance_sigma >= 4.0)
    return {
        "gaussian_threshold_initial_x_m": float(x_threshold),
        "gaussian_threshold_offset_m": float(offset),
        "distance_from_pulse_center_in_sigma": float(distance_sigma),
        "initial_tail_ratio": initial_tail_ratio,
        "primary_for_wave_speed_assessment": primary,
        "initial_tail_contamination_warning": bool(not primary),
    }


def _coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def _reference_state(cfg: CoolPropSmallAmplitudeWaveConfig, backend: CoolPropCO2Backend, eos: LCO2PropertyEOSAdapter) -> dict[str, Any]:
    rho0 = float(np.asarray(backend.density_from_pT(cfg.initial_pressure_pa, cfg.initial_temperature_K)))
    e0 = float(np.asarray(backend.internal_energy_from_pT(cfg.initial_pressure_pa, cfg.initial_temperature_K)))
    U0 = make_conserved(rho=rho0, u=0.0, e=e0, xv=0.0)
    prim0 = eos.primitive_from_conserved(U0)
    return {
        "rho0": rho0,
        "e0": e0,
        "c0": float(np.asarray(prim0.c)),
        "phase": "single_phase_liquid_side",
        "quality": float(np.asarray(prim0.xv)),
        "alpha": float(np.asarray(prim0.alpha)),
    }


def _auto_timing(cfg: CoolPropSmallAmplitudeWaveConfig, c0: float) -> dict[str, float]:
    L = cfg.pipe_length_m
    x0 = cfg.pulse_center_fraction * L
    far_probe = max(cfg.probe_fractions) * L
    incident_far = (far_probe - x0) / c0
    right_end = (L - x0) / c0
    reflection_to_far = right_end + (L - far_probe) / c0
    gap = reflection_to_far - incident_far
    target = incident_far + cfg.post_arrival_margin_fraction * gap
    latest_safe = incident_far + (1.0 - cfg.reflection_safety_margin_fraction) * gap
    if cfg.t_end_s is not None:
        if not (incident_far < cfg.t_end_s < reflection_to_far):
            raise ValueError("t_end_s must be after last incident arrival and before first right-end reflection return")
        target = cfg.t_end_s
    return {
        "target_time_s": float(target),
        "last_probe_incident_time_s": float(incident_far),
        "right_end_incident_time_s": float(right_end),
        "last_probe_reflection_return_time_s": float(reflection_to_far),
        "latest_safe_time_s": float(latest_safe),
        "reflection_window_margin_s": float(reflection_to_far - target),
    }


def build_initial_gaussian_pulse(
    config: CoolPropSmallAmplitudeWaveConfig | None = None,
) -> dict[str, Any]:
    """Build the p-T initialized right-running Gaussian pulse state."""

    cfg = config or CoolPropSmallAmplitudeWaveConfig()
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(backend=backend, boundary_temperature_K=cfg.initial_temperature_K, quality_source="transported")
    ref = _reference_state(cfg, backend, eos)
    if not (np.isfinite(ref["rho0"]) and ref["rho0"] > 0 and np.isfinite(ref["e0"]) and ref["c0"] > 0):
        raise ValueError("CoolProp reference state must be finite and liquid-side single-phase")
    if abs(ref["quality"]) > 1.0e-12 or abs(ref["alpha"]) > 1.0e-12:
        raise ValueError("reference state must keep transported quality and alpha at zero")
    grid = UniformGrid(PipeGeometry(cfg.pipe_length_m, cfg.diameter_m), cfg.n_cells)
    x = grid.cell_centers
    x0 = cfg.pulse_center_fraction * cfg.pipe_length_m
    sigma = cfg.pulse_sigma_fraction * cfg.pipe_length_m
    dp = cfg.pressure_amplitude_pa * np.exp(-0.5 * ((x - x0) / sigma) ** 2)
    p = cfg.initial_pressure_pa + dp
    T = np.full(cfg.n_cells, cfg.initial_temperature_K)
    rho = np.asarray(backend.density_from_pT(p, T), dtype=float)
    e = np.asarray(backend.internal_energy_from_pT(p, T), dtype=float)
    # Positive velocity follows the solver convention u = momentum / rho, so this
    # creates the linear-acoustic right-running component. EOS nonlinearity can
    # still leave a small left-running residual, noted in metrics/report.
    u = dp / (ref["rho0"] * ref["c0"])
    U = make_conserved(rho=rho, u=u, e=e, xv=np.zeros(cfg.n_cells))
    return {"config": cfg, "backend": backend, "eos": eos, "grid": grid, "U": U, "x": x, "dp": dp, "p": p, "T": T, "rho": rho, "e": e, "u": u, "reference": ref}


def build_coolprop_small_amplitude_wave_solver(config: CoolPropSmallAmplitudeWaveConfig | None = None) -> FvmSolver:
    init = build_initial_gaussian_pulse(config)
    return FvmSolver(
        grid=init["grid"],
        eos=init["eos"],
        U=init["U"],
        cfl=init["config"].cfl,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        source_term=NoSource(),
        phase_change=NoPhaseChange(),
        internal_interfaces=(),
        latent_heat_placeholder_j_kg=0.0,
    )


def _probe_specs(cfg: CoolPropSmallAmplitudeWaveConfig, grid: UniformGrid) -> list[dict[str, Any]]:
    specs = []
    for frac in cfg.probe_fractions:
        target = frac * cfg.pipe_length_m
        idx = int(np.argmin(np.abs(grid.cell_centers - target)))
        specs.append({"probe_name": f"x_over_L_{frac:g}", "probe_target_x_m": float(target), "probe_cell_index": idx, "probe_cell_center_x_m": float(grid.cell_centers[idx])})
    return specs


def _sample_probes(solver: FvmSolver, cfg: CoolPropSmallAmplitudeWaveConfig, probes: list[dict[str, Any]], dt: float) -> list[dict[str, Any]]:
    prim = solver.primitive()
    rows = []
    cfl = float(np.max((np.abs(prim.u) + prim.c) * dt / solver.grid.dx)) if dt > 0 else 0.0
    for spec in probes:
        i = spec["probe_cell_index"]
        rows.append({
            "time_s": float(solver.t), "step": int(solver.step_count), "dt_s": float(dt), "cfl": cfl, **spec,
            "pressure_pa": float(prim.p[i]), "delta_pressure_pa": float(prim.p[i] - cfg.initial_pressure_pa),
            "temperature_K": float(prim.T[i]), "density_kg_m3": float(prim.rho[i]), "velocity_m_s": float(prim.u[i]),
            "sound_speed_m_s": float(prim.c[i]), "vapor_mass_fraction": float(prim.xv[i]), "alpha": float(prim.alpha[i]),
        })
    return rows


def _detect_arrival(rows: list[dict[str, Any]], cfg: CoolPropSmallAmplitudeWaveConfig, x0: float, c0: float, xp: float) -> dict[str, Any]:
    threshold_meta = _threshold_metadata(cfg, x0, xp)
    x_threshold = threshold_meta["gaussian_threshold_initial_x_m"]
    if xp <= x_threshold:
        raise ValueError("probe cell center must be to the right of the initial leading-side Gaussian threshold")
    t_theory = (xp - x_threshold) / c0
    sigma_time = cfg.pulse_sigma_fraction * cfg.pipe_length_m / c0
    t_min = max(0.0, t_theory - 4.0 * sigma_time)
    t_max = t_theory + 4.0 * sigma_time
    series = [(r["time_s"], r["delta_pressure_pa"]) for r in rows if t_min <= r["time_s"] <= t_max]
    if len(series) < 2:
        return {"arrival_detected": False, "numerical_arrival_time_s": None, "numerical_threshold_arrival_time_s": None, "arrival_threshold_pa": None, "detected_peak_delta_pressure_pa": None}
    initial_tail = rows[0]["delta_pressure_pa"]
    adjusted = [(t, dp - initial_tail) for t, dp in series]
    peak = max(dp for _, dp in adjusted)
    if not np.isfinite(peak) or peak <= 0.0:
        return {"arrival_detected": False, "numerical_arrival_time_s": None, "numerical_threshold_arrival_time_s": None, "arrival_threshold_pa": None, "detected_peak_delta_pressure_pa": float(peak) if np.isfinite(peak) else None}
    threshold = cfg.arrival_threshold_fraction * peak
    for (t0, y0), (t1, y1) in zip(adjusted[:-1], adjusted[1:]):
        if y0 < threshold <= y1 and t1 > t0:
            frac = (threshold - y0) / (y1 - y0) if y1 != y0 else 0.0
            return {"arrival_detected": True, "numerical_arrival_time_s": float(t0 + frac * (t1 - t0)), "numerical_threshold_arrival_time_s": float(t0 + frac * (t1 - t0)), "arrival_threshold_pa": float(threshold), "detected_peak_delta_pressure_pa": float(peak), "arrival_search_start_s": float(t_min), "arrival_search_end_s": float(t_max), "arrival_initial_tail_subtracted_pa": float(initial_tail)}
    return {"arrival_detected": False, "numerical_arrival_time_s": None, "numerical_threshold_arrival_time_s": None, "arrival_threshold_pa": float(threshold), "detected_peak_delta_pressure_pa": float(peak), "arrival_search_start_s": float(t_min), "arrival_search_end_s": float(t_max), "arrival_initial_tail_subtracted_pa": float(initial_tail)}


def _final_profile(solver: FvmSolver) -> list[dict[str, Any]]:
    prim = solver.primitive()
    return [{"cell_index": i, "x_m": float(solver.grid.cell_centers[i]), "pressure_pa": float(prim.p[i]), "temperature_K": float(prim.T[i]), "density_kg_m3": float(prim.rho[i]), "velocity_m_s": float(prim.u[i]), "sound_speed_m_s": float(prim.c[i]), "vapor_mass_fraction": float(prim.xv[i]), "alpha": float(prim.alpha[i])} for i in range(solver.grid.n_cells)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)


def _plotting_available() -> bool:
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: F401
        from matplotlib.figure import Figure
    except Exception:
        return False
    try:
        fig = Figure(figsize=(1, 1))
        FigureCanvasAgg(fig)
        fig.savefig(BytesIO(), format="png")
    except Exception:
        return False
    return True


def _common_plot_note(metrics: dict[str, Any]) -> str:
    return (
        f"case={metrics['case_name']} | eos={metrics['eos_model']} | "
        f"backend={metrics['property_backend_name']} | "
        f"status={metrics['property_backend_design_status']} | "
        "software_path_verification, design_evaluation=False"
    )


def _probe_rows_by_name(history: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in history:
        grouped.setdefault(row["probe_name"], []).append(row)
    return grouped


def _plot_probe_pressure_history(output_dir: Path, stem: str, metrics: dict[str, Any], history: list[dict[str, Any]]) -> str:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 6))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    grouped = _probe_rows_by_name(history)
    probe_metrics = {p["probe_name"]: p for p in metrics["probes"]}
    for probe_name, rows in grouped.items():
        probe = probe_metrics[probe_name]
        label = probe_name
        if probe.get("primary_for_wave_speed_assessment"):
            label += " (primary)"
        else:
            label += " (diagnostic)"
        ax.plot([r["time_s"] for r in rows], [r["delta_pressure_pa"] for r in rows], label=label)
        theory = probe.get("theoretical_threshold_arrival_time_cell_center_s")
        numerical = probe.get("numerical_threshold_arrival_time_s")
        if theory is not None:
            ax.axvline(theory, color="0.35", linestyle="--", linewidth=0.8, alpha=0.55)
        if numerical is not None:
            ax.axvline(numerical, color="0.05", linestyle=":", linewidth=0.9, alpha=0.65)
    ax.set_title("CoolProp small-amplitude wave: probe pressure histories")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("delta pressure [Pa]")
    ax.text(0.01, 0.99, _common_plot_note(metrics) + "\nvertical: theory dashed, numerical dotted", transform=ax.transAxes, va="top", ha="left", fontsize=8, bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"})
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    name = f"{stem}_probe_pressure_history.png"
    fig.savefig(output_dir / name, dpi=160)
    return name


def _plot_xt_pressure_map(output_dir: Path, stem: str, metrics: dict[str, Any], sampled_fields: dict[str, Any]) -> str:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    times = np.asarray(sampled_fields["times_s"], dtype=float)
    x = np.asarray(sampled_fields["x_m"], dtype=float)
    dp = np.asarray(sampled_fields["delta_pressure_pa"], dtype=float)
    fig = Figure(figsize=(10, 6))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    mesh = ax.pcolormesh(times, x, dp.T, shading="auto", cmap="coolwarm")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("delta pressure [Pa]")
    for probe in metrics["probes"]:
        ax.axhline(probe["probe_cell_center_x_m"], color="k", linewidth=0.6, alpha=0.45)
        ax.text(times[-1], probe["probe_cell_center_x_m"], " " + probe["probe_name"], va="center", fontsize=7)
    ax.axhline(metrics["pulse_center_x_m"], color="yellow", linestyle="--", linewidth=0.9, alpha=0.8, label="pulse center x0")
    ax.set_title("CoolProp small-amplitude wave: x-t pressure map")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("x [m]")
    ax.text(0.01, 0.99, _common_plot_note(metrics), transform=ax.transAxes, va="top", ha="left", fontsize=8, bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"})
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    name = f"{stem}_xt_pressure_map.png"
    fig.savefig(output_dir / name, dpi=160)
    return name


def _plot_pressure_snapshots(output_dir: Path, stem: str, metrics: dict[str, Any], sampled_fields: dict[str, Any]) -> str:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    times = np.asarray(sampled_fields["times_s"], dtype=float)
    x = np.asarray(sampled_fields["x_m"], dtype=float)
    dp = np.asarray(sampled_fields["delta_pressure_pa"], dtype=float)
    targets = [0.0]
    for frac in (0.5, 0.75):
        probe = min(metrics["probes"], key=lambda p: abs(p["probe_cell_center_x_m"] / metrics["pipe_length_m"] - frac))
        t = probe.get("theoretical_threshold_arrival_time_cell_center_s")
        if t is not None:
            targets.append(float(t))
    targets.append(0.9 * float(metrics["target_time_s"]))
    indices = []
    for target in targets:
        idx = int(np.argmin(np.abs(times - target)))
        if idx not in indices:
            indices.append(idx)
    fig = Figure(figsize=(10, 6))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    for idx in indices:
        ax.plot(x, dp[idx, :], label=f"t={times[idx]:.6g} s")
    for probe in metrics["probes"]:
        ax.axvline(probe["probe_cell_center_x_m"], color="0.25", linewidth=0.5, alpha=0.35)
    ax.set_title("CoolProp small-amplitude wave: pressure snapshots")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("delta pressure [Pa]")
    ax.text(0.01, 0.99, _common_plot_note(metrics), transform=ax.transAxes, va="top", ha="left", fontsize=8, bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"})
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    name = f"{stem}_pressure_snapshots.png"
    fig.savefig(output_dir / name, dpi=160)
    return name


def _existing_plot_name(output_dir: Path, name: str) -> str | None:
    path = output_dir / name
    return name if path.exists() and path.is_file() else None


def _generate_plots(output_dir: Path, stem: str, metrics: dict[str, Any], history: list[dict[str, Any]], sampled_fields: dict[str, Any] | None) -> list[str]:
    generated: list[str] = []
    errors: dict[str, str] = {}
    plot_jobs = [("probe_pressure_history", lambda: _plot_probe_pressure_history(output_dir, stem, metrics, history))]
    if sampled_fields is not None and len(sampled_fields.get("times_s", [])) >= 2:
        plot_jobs.extend([
            ("xt_pressure_map", lambda: _plot_xt_pressure_map(output_dir, stem, metrics, sampled_fields)),
            ("pressure_snapshots", lambda: _plot_pressure_snapshots(output_dir, stem, metrics, sampled_fields)),
        ])
    for key, plot_func in plot_jobs:
        try:
            maybe_name = _existing_plot_name(output_dir, plot_func())
            if maybe_name is not None:
                generated.append(maybe_name)
            else:
                errors[key] = "plot helper returned a path that does not exist"
        except Exception as exc:  # pragma: no cover - optional plotting must not fail run
            errors[key] = str(exc)
    if errors:
        metrics["plotting_errors"] = errors
        metrics["plotting_error"] = next(iter(errors.values()))
    return generated


def _sample_pressure_field(solver: FvmSolver, cfg: CoolPropSmallAmplitudeWaveConfig) -> np.ndarray:
    prim = solver.primitive()
    return np.asarray(prim.p, dtype=float) - cfg.initial_pressure_pa


def _write_artifacts(output_dir: Path, cfg: CoolPropSmallAmplitudeWaveConfig, metrics: dict[str, Any], history: list[dict[str, Any]], profile: list[dict[str, Any]], sampled_fields: dict[str, Any] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = cfg.case_name
    (output_dir / f"{stem}_config.json").write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir / f"{stem}_probe_history.csv", history)
    _write_csv(output_dir / f"{stem}_final_profile.csv", profile)
    generated_plots: list[str] = []
    plotting_available = _plotting_available()
    if plotting_available:
        generated_plots = _generate_plots(output_dir, stem, metrics, history, sampled_fields)
    metrics["plotting_available"] = bool(plotting_available)
    metrics["generated_plots"] = generated_plots
    metrics["figure_paths"] = [str(output_dir / name) for name in generated_plots]
    (output_dir / f"{stem}_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    probe_lines = "\n".join(f"- {p['probe_name']}: center_theory_cell={p['theoretical_center_arrival_time_cell_center_s']}, threshold_theory_cell={p['theoretical_threshold_arrival_time_cell_center_s']}, numerical_threshold={p['numerical_threshold_arrival_time_s']}, threshold_inferred_c={p['threshold_inferred_wave_speed_m_s']}, threshold_rel_err={p['threshold_wave_speed_relative_error']}, primary={p['primary_for_wave_speed_assessment']}, tail_ratio={p['initial_tail_ratio']}, amplitude_ratio={p['amplitude_ratio']}" for p in metrics["probes"])
    report = f"""# CoolProp small-amplitude wave observation report

このレポートは、CoolProp 単相 CO2 software / numerical verification の初回 observation run です。実設計評価ではなく、CoolProp backend の design-use 承認、Validation、HEM/HNE/DVCM、ESD急閉、pump trip、二相化、flashing の評価ではありません。

## 目的
右向き小振幅 Gaussian 圧力波を発生させ、各 probe の理論到達時刻と local peak 50% rising crossing による数値到達時刻を記録します。主比較は Gaussian 中心ではなく、同じ threshold fraction の立ち上がり側特徴点で行います。正式な到達時刻誤差・波速誤差 threshold は未設定です。

## 基準状態と pulse
- CoolProp version: {metrics['coolprop_version']}
- property_backend_design_status: {metrics['property_backend_design_status']}
- p0 Pa: {metrics['initial_pressure_pa']}
- T0 K: {metrics['initial_temperature_K']}
- rho0 kg/m3: {metrics['rho0']}
- c0 m/s: {metrics['c0']}
- pressure_amplitude_pa: {metrics['pressure_amplitude_pa']}
- perturbation_ratio: {metrics['perturbation_ratio']}

## Probe 到達時刻
{probe_lines}

`theoretical_center_arrival_time_*` は Gaussian 中心の到達時刻です。`theoretical_threshold_arrival_time_*`、`numerical_threshold_arrival_time_s`、`threshold_inferred_wave_speed_m_s`、および後方互換 field の `arrival_time_*` / `inferred_wave_speed_m_s` は、立ち上がり側 threshold 位置を基準にした主比較値です。`arrival_initial_tail_subtracted_pa` は t=0 の probe 圧力変化を baseline として差し引いた値です。数値拡散で観測 peak が減衰しても各 probe の local peak に対する 50% crossing を観測する設計ですが、local peak 50% 方式は波形変形の影響を受けるため、正式な acceptance threshold はメッシュ/CFL 比較後に決定します。`primary_for_wave_speed_assessment=False` は pulse center からの距離が 4 sigma 未満で、初期 Gaussian tail の影響が相対的に大きい diagnostic probe を示します。

## 可視化の読み方
- probe圧力履歴図は、到達時刻・振幅減衰・波形拡散を見るための図です。理論 threshold arrival は破線、数値 threshold arrival は点線で示します。
- x-t 図は、伝播速度・反射前評価 window・不要な波の有無を見るための図です。
- スナップショット図は、Gaussian 波形の広がりや数値拡散を見るための図です。
- 到達検出は local peak 50% crossing に基づくため、振幅減衰と波形変形の影響を受けます。
- 正式な acceptance threshold は未固定です。この observation run は design-use ではありません。
- plotting_available: {metrics.get('plotting_available')}
- generated_plots: {metrics.get('generated_plots')}

## Budget / single phase
- budget_mass_residual: {metrics['budget_mass_residual']}
- energy_budget_balance_residual_j: {metrics['energy_budget_balance_residual_j']}
- phase_vapor_mass_balance_residual_kg: {metrics['phase_vapor_mass_balance_residual_kg']}
- remained_single_phase: {metrics['remained_single_phase']}
- overall_observation_run_pass: {metrics['overall_observation_run_pass']}

実在 EOS の非線形性により、初期条件は完全な一方向波ではなく微小な反対方向成分を含む可能性があります。
"""
    (output_dir / f"{stem}_report.md").write_text(report, encoding="utf-8")


def run_coolprop_small_amplitude_wave(output_dir: Path | str | None = None, config: CoolPropSmallAmplitudeWaveConfig | None = None) -> dict[str, Any]:
    """Run the observation case and return metrics."""

    cfg = config or CoolPropSmallAmplitudeWaveConfig()
    init = build_initial_gaussian_pulse(cfg)
    solver = build_coolprop_small_amplitude_wave_solver(cfg)
    ref = init["reference"]
    timing = _auto_timing(cfg, ref["c0"])
    probes = _probe_specs(cfg, solver.grid)
    history = _sample_probes(solver, cfg, probes, 0.0)
    sampled_times: list[float] = [float(solver.t)]
    sampled_delta_pressure_fields: list[np.ndarray] = [_sample_pressure_field(solver, cfg)]
    dts: list[float] = []
    completed = False
    for _ in range(cfg.max_steps):
        if solver.t >= timing["target_time_s"]:
            completed = True; break
        dt = solver.compute_dt(timing["target_time_s"])
        solver.step(dt); dts.append(float(dt))
        if solver.step_count % cfg.sample_every == 0 or solver.t >= timing["target_time_s"]:
            history.extend(_sample_probes(solver, cfg, probes, dt))
            sampled_times.append(float(solver.t))
            sampled_delta_pressure_fields.append(_sample_pressure_field(solver, cfg))
    else:
        completed = False
    completed = completed or solver.t >= timing["target_time_s"]
    if sampled_times[-1] != float(solver.t):
        sampled_times.append(float(solver.t))
        sampled_delta_pressure_fields.append(_sample_pressure_field(solver, cfg))
    sampled_fields = {
        "times_s": sampled_times,
        "x_m": [float(v) for v in solver.grid.cell_centers],
        "delta_pressure_pa": np.vstack(sampled_delta_pressure_fields),
    }
    final_prim = solver.primitive()
    hist_vals = np.array([[float(v) for k, v in r.items() if isinstance(v, (int, float))] for r in history], dtype=float)
    diag = solver.diagnostics(dt=0.0)
    x0 = cfg.pulse_center_fraction * cfg.pipe_length_m
    probe_metrics = []
    for spec in probes:
        rows = [r for r in history if r["probe_name"] == spec["probe_name"]]
        det = _detect_arrival(rows, cfg, x0, ref["c0"], spec["probe_cell_center_x_m"])
        threshold_meta = _threshold_metadata(cfg, x0, spec["probe_cell_center_x_m"])
        x_threshold = threshold_meta["gaussian_threshold_initial_x_m"]
        if spec["probe_cell_center_x_m"] <= x_threshold:
            raise ValueError("probe cell center must be to the right of the initial leading-side Gaussian threshold")
        theory_target = (spec["probe_target_x_m"] - x0) / ref["c0"]
        theory_cell = (spec["probe_cell_center_x_m"] - x0) / ref["c0"]
        theory_threshold_target = (spec["probe_target_x_m"] - x_threshold) / ref["c0"]
        theory_threshold_cell = (spec["probe_cell_center_x_m"] - x_threshold) / ref["c0"]
        num = det["numerical_arrival_time_s"]
        err = abs(num - theory_threshold_cell) if num is not None else None
        inferred = (spec["probe_cell_center_x_m"] - x_threshold) / num if num not in (None, 0.0) else None
        center_inferred = (spec["probe_cell_center_x_m"] - x0) / num if num not in (None, 0.0) else None
        probe_metrics.append({**spec, **threshold_meta, "theoretical_arrival_time_target_s": float(theory_target), "theoretical_arrival_time_cell_center_s": float(theory_cell), "theoretical_center_arrival_time_target_s": float(theory_target), "theoretical_center_arrival_time_cell_center_s": float(theory_cell), "theoretical_threshold_arrival_time_target_s": float(theory_threshold_target), "theoretical_threshold_arrival_time_cell_center_s": float(theory_threshold_cell), **det, "threshold_arrival_time_absolute_error_s": float(err) if err is not None else None, "threshold_arrival_time_relative_error": float(err / theory_threshold_cell) if err is not None and theory_threshold_cell != 0 else None, "threshold_inferred_wave_speed_m_s": float(inferred) if inferred is not None else None, "threshold_wave_speed_relative_error": float(abs(inferred - ref["c0"]) / ref["c0"]) if inferred is not None else None, "arrival_time_absolute_error_s": float(err) if err is not None else None, "arrival_time_relative_error": float(err / theory_threshold_cell) if err is not None and theory_threshold_cell != 0 else None, "inferred_wave_speed_m_s": float(inferred) if inferred is not None else None, "wave_speed_relative_error": float(abs(inferred - ref["c0"]) / ref["c0"]) if inferred is not None else None, "inferred_center_based_wave_speed_m_s": float(center_inferred) if center_inferred is not None else None, "amplitude_ratio": float(det["detected_peak_delta_pressure_pa"] / cfg.pressure_amplitude_pa) if det.get("detected_peak_delta_pressure_pa") is not None else None})
    missing_budget = [k for k in ["budget_mass_residual", "energy_budget_balance_residual_j", "phase_vapor_mass_balance_residual_kg"] if k not in diag]
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name, "output_version": cfg.output_version, "software_path_verification": True, "numerical_verification": True,
        "design_evaluation": False, "acceptance_gate": False, "validation": False, "eos_model": "coolprop_lco2", "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use", "coolprop_available": coolprop_available(), "coolprop_version": _coolprop_version(), "quality_source": "transported",
        "pipe_length_m": cfg.pipe_length_m, "diameter_m": cfg.diameter_m, "n_cells": cfg.n_cells, "dx_m": solver.grid.dx, "cfl_target": cfg.cfl,
        "initial_pressure_pa": cfg.initial_pressure_pa, "initial_temperature_K": cfg.initial_temperature_K, "rho0": ref["rho0"], "e0": ref["e0"], "c0": ref["c0"],
        "reference_phase": ref["phase"], "reference_quality": ref["quality"], "reference_alpha": ref["alpha"],
        "pressure_amplitude_pa": cfg.pressure_amplitude_pa, "perturbation_ratio": cfg.pressure_amplitude_pa / cfg.initial_pressure_pa,
        "pulse_center_x_m": x0, "pulse_sigma_m": cfg.pulse_sigma_fraction * cfg.pipe_length_m, "theoretical_velocity_amplitude_m_s": cfg.pressure_amplitude_pa / (ref["rho0"] * ref["c0"]),
        **timing, "final_time_s": float(solver.t), "reached_target_time": bool(solver.t >= timing["target_time_s"]), "completed_without_exception": bool(completed),
        "step_count": int(solver.step_count), "sample_count": len(history), "min_positive_dt_s": min(dts) if dts else 0.0, "max_dt_s": max(dts) if dts else 0.0,
        "max_cfl": max((r["cfl"] for r in history), default=0.0), "all_history_finite": bool(np.all(np.isfinite(hist_vals))), "within_max_steps": bool(solver.step_count <= cfg.max_steps),
        "probes": probe_metrics,
        "min_pressure_pa": float(np.min(final_prim.p)), "min_temperature_K": float(np.min(final_prim.T)), "min_density_kg_m3": float(np.min(final_prim.rho)), "min_sound_speed_m_s": float(np.min(final_prim.c)),
        "max_abs_temperature_change_K": float(np.max(np.abs(final_prim.T - cfg.initial_temperature_K))), "max_abs_density_change_kg_m3": float(np.max(np.abs(final_prim.rho - ref["rho0"]))), "max_abs_velocity_m_s": float(np.max(np.abs(final_prim.u))),
        "max_vapor_mass_fraction": float(np.max(final_prim.xv)), "max_alpha": float(np.max(final_prim.alpha)), "remained_single_phase": bool(np.max(final_prim.xv) <= 1e-12 and np.max(final_prim.alpha) <= 1e-12),
        "positive_pressure": bool(np.min(final_prim.p) > 0), "positive_temperature": bool(np.min(final_prim.T) > 0), "positive_density": bool(np.min(final_prim.rho) > 0), "positive_sound_speed": bool(np.min(final_prim.c) > 0),
        "budget_mass_residual": float(diag.get("budget_mass_residual", np.nan)), "budget_mass_relative_residual": float(diag.get("budget_mass_relative_residual", np.nan)),
        "energy_budget_balance_residual_j": float(diag.get("energy_budget_balance_residual_j", np.nan)), "energy_budget_balance_relative_residual": float(diag.get("energy_budget_balance_relative_residual", np.nan)),
        "phase_vapor_mass_balance_residual_kg": float(diag.get("phase_vapor_mass_balance_residual_kg", np.nan)), "phase_vapor_mass_balance_relative_residual": float(diag.get("phase_vapor_mass_balance_relative_residual", np.nan)),
        "missing_budget_fields": missing_budget,
        "plotting_available": False,
        "generated_plots": [],
        "figure_paths": [],
    }
    metrics["overall_software_path_pass"] = bool(metrics["completed_without_exception"] and metrics["reached_target_time"] and metrics["property_backend_name"] == "coolprop_co2" and metrics["property_backend_design_status"] == "not_approved_for_design_use")
    metrics["overall_observation_run_pass"] = bool(metrics["overall_software_path_pass"] and metrics["all_history_finite"] and metrics["positive_pressure"] and metrics["positive_temperature"] and metrics["positive_density"] and metrics["positive_sound_speed"] and metrics["remained_single_phase"] and all(p["arrival_detected"] for p in probe_metrics) and not missing_budget and metrics["within_max_steps"])
    if output_dir is not None:
        _write_artifacts(Path(output_dir), cfg, metrics, history, _final_profile(solver), sampled_fields)
    return metrics


__all__ = ["CoolPropSmallAmplitudeWaveConfig", "gaussian_threshold_offset", "gaussian_threshold_initial_x", "build_initial_gaussian_pulse", "build_coolprop_small_amplitude_wave_solver", "run_coolprop_small_amplitude_wave"]
