"""Mesh/CFL sweep for CoolProp single-phase CO2 small-amplitude wave verification.

This module is for software/numerical verification observations only. It is not
a design-use evaluation, validation, CoolProp approval, or HEM/HNE/DVCM study.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import math
from pathlib import Path
import tempfile
import time
from typing import Any

import numpy as np

from .coolprop_small_amplitude_wave import CoolPropSmallAmplitudeWaveConfig, run_coolprop_small_amplitude_wave


@dataclass(frozen=True)
class CoolPropSmallAmplitudeWaveSweepConfig:
    case_name: str = "coolprop_small_amplitude_wave_sweep"
    output_version: str = "coolprop_small_amplitude_wave_sweep_v1"
    mesh_cells: tuple[int, ...] = (50, 100, 200)
    cfl_values: tuple[float, ...] = (0.25, 0.5)
    mesh_comparison_cfl: float = 0.5
    cfl_comparison_n_cells: int = 100
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_amplitude_pa: float = 1.0e3
    pulse_center_fraction: float = 0.15
    pulse_sigma_fraction: float = 0.03
    probe_fractions: tuple[float, ...] = (0.25, 0.5, 0.75)
    sample_every: int = 1
    max_steps: int = 10000
    arrival_threshold_fraction: float = 0.5
    primary_probe_fractions: tuple[float, ...] = (0.5, 0.75)
    comparison_reference_probe_fraction: float = 0.5
    generate_case_plots: bool = True
    generate_comparison_plots: bool = True

    def __post_init__(self) -> None:
        if tuple(sorted(self.mesh_cells)) != self.mesh_cells or any(n < 10 for n in self.mesh_cells):
            raise ValueError("mesh_cells must be ascending and each value must be >= 10")
        if not self.cfl_values or any((c <= 0.0 or c > 1.0) for c in self.cfl_values):
            raise ValueError("cfl_values must be in (0, 1]")
        if self.mesh_comparison_cfl not in self.cfl_values:
            raise ValueError("mesh_comparison_cfl must be included in cfl_values")
        if self.cfl_comparison_n_cells not in self.mesh_cells:
            raise ValueError("cfl_comparison_n_cells must be included in mesh_cells")
        if not self.primary_probe_fractions or any(p <= self.pulse_center_fraction for p in self.primary_probe_fractions):
            raise ValueError("primary probe fractions must be to the right of the pulse center")
        CoolPropSmallAmplitudeWaveConfig(
            pipe_length_m=self.pipe_length_m,
            diameter_m=self.diameter_m,
            n_cells=self.mesh_cells[0],
            cfl=self.cfl_values[0],
            initial_pressure_pa=self.initial_pressure_pa,
            initial_temperature_K=self.initial_temperature_K,
            pressure_amplitude_pa=self.pressure_amplitude_pa,
            pulse_center_fraction=self.pulse_center_fraction,
            pulse_sigma_fraction=self.pulse_sigma_fraction,
            probe_fractions=self.probe_fractions,
            sample_every=self.sample_every,
            max_steps=self.max_steps,
            arrival_threshold_fraction=self.arrival_threshold_fraction,
        )


def gaussian_fwhm_m(sigma_m: float) -> float:
    if sigma_m <= 0.0:
        raise ValueError("sigma_m must be positive")
    return float(2.0 * math.sqrt(2.0 * math.log(2.0)) * sigma_m)


def case_id_for(n_cells: int, cfl: float) -> str:
    return f"n{n_cells:04d}_cfl{int(round(cfl * 100)):03d}"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _as_float_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        rr: dict[str, Any] = {}
        for k, v in row.items():
            try:
                rr[k] = float(v)
            except (TypeError, ValueError):
                rr[k] = v
        out.append(rr)
    return out


def _probe_name(frac: float) -> str:
    return f"x_over_L_{frac:g}"


def _window_series(rows: list[dict[str, Any]], theory_center: float, sigma_t: float) -> tuple[np.ndarray, np.ndarray]:
    tmin = max(0.0, theory_center - 5.0 * sigma_t)
    tmax = theory_center + 5.0 * sigma_t
    pairs = [(float(r["time_s"]), float(r["delta_pressure_pa"])) for r in rows if tmin <= float(r["time_s"]) <= tmax]
    if len(pairs) < 2:
        return np.array([]), np.array([])
    t = np.asarray([p[0] for p in pairs], dtype=float)
    y = np.asarray([p[1] for p in pairs], dtype=float)
    y = y - float(rows[0]["delta_pressure_pa"])
    return t, y


def temporal_fwhm(t: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    if t.size < 3 or y.size != t.size or not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        return {"fwhm_detected": False, "fwhm_reason": "insufficient_or_nonfinite"}
    imax = int(np.argmax(y)); peak = float(y[imax])
    if peak <= 0.0:
        return {"fwhm_detected": False, "fwhm_reason": "nonpositive_peak"}
    half = 0.5 * peak
    rising = None
    for i in range(0, imax):
        if y[i] < half <= y[i + 1] and t[i + 1] > t[i]:
            rising = float(t[i] + (half - y[i]) * (t[i + 1] - t[i]) / (y[i + 1] - y[i]))
            break
    falling = None
    for i in range(imax, len(t) - 1):
        if y[i] >= half > y[i + 1] and t[i + 1] > t[i]:
            falling = float(t[i] + (half - y[i]) * (t[i + 1] - t[i]) / (y[i + 1] - y[i]))
            break
    if rising is None or falling is None:
        return {"fwhm_detected": False, "fwhm_reason": "crossing_not_detected", "fwhm_rising_time_s": rising, "fwhm_falling_time_s": falling, "peak_delta_pressure_pa": peak}
    return {"fwhm_detected": True, "fwhm_rising_time_s": rising, "fwhm_falling_time_s": falling, "temporal_fwhm_s": float(falling - rising), "peak_delta_pressure_pa": peak}


def temporal_centroid(t: np.ndarray, y: np.ndarray, area_floor: float = 1e-20) -> dict[str, Any]:
    if t.size < 2 or y.size != t.size:
        return {"centroid_detected": False, "centroid_reason": "insufficient"}
    w = np.maximum(y, 0.0)
    area = float(np.trapezoid(w, t))
    if not np.isfinite(area) or area <= area_floor:
        return {"centroid_detected": False, "centroid_reason": "nonpositive_area", "positive_pressure_area_pa_s": area}
    return {"centroid_detected": True, "temporal_centroid_time_s": float(np.trapezoid(t * w, t) / area), "positive_pressure_area_pa_s": area}


def common_time_grid(t1: np.ndarray, y1: np.ndarray, t2: np.ndarray, y2: np.ndarray, n: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lo = max(float(np.min(t1)), float(np.min(t2))); hi = min(float(np.max(t1)), float(np.max(t2)))
    if not hi > lo:
        raise ValueError("series do not overlap")
    if n is None:
        n = max(16, min(len(t1), len(t2)))
    tg = np.linspace(lo, hi, n)
    return tg, np.interp(tg, t1, y1), np.interp(tg, t2, y2)


def cross_correlation_lag(t1: np.ndarray, y1: np.ndarray, t2: np.ndarray, y2: np.ndarray) -> dict[str, Any]:
    lo = min(float(np.min(t1)), float(np.min(t2))); hi = max(float(np.max(t1)), float(np.max(t2)))
    n = max(32, min(2048, len(t1) + len(t2)))
    tg = np.linspace(lo, hi, n); dt = float(tg[1] - tg[0])
    a = np.interp(tg, t1, y1, left=0.0, right=0.0); b = np.interp(tg, t2, y2, left=0.0, right=0.0)
    a = a - np.mean(a); b = b - np.mean(b)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0.0:
        return {"cross_correlation_detected": False, "cross_correlation_reason": "zero_norm"}
    corr = np.correlate(b, a, mode="full") / denom
    lags = np.arange(-len(a) + 1, len(a), dtype=float) * dt
    mask = lags > 0.0
    if not np.any(mask):
        return {"cross_correlation_detected": False, "cross_correlation_reason": "no_positive_lag"}
    idxs = np.where(mask)[0]; idx = int(idxs[np.argmax(corr[mask])])
    return {"cross_correlation_detected": True, "cross_correlation_lag_s": float(lags[idx]), "cross_correlation_coefficient": float(corr[idx])}


def apparent_order(dx: list[float], errors: list[float], floor: float = 1e-14) -> dict[str, Any]:
    if len(dx) < 3 or len(errors) < 3:
        return {"apparent_order": None, "reason": "insufficient_data"}
    d = np.asarray(dx[:3], dtype=float); e = np.asarray(errors[:3], dtype=float)
    if not (np.all(np.isfinite(d)) and np.all(np.isfinite(e)) and np.all(e > floor)):
        return {"apparent_order": None, "reason": "nonfinite_or_too_small_error"}
    if not (d[0] > d[1] > d[2] and e[0] >= e[1] >= e[2]):
        return {"apparent_order": None, "reason": "not_monotonic"}
    return {"apparent_order": float(math.log(e[0] / e[1]) / math.log(d[0] / d[1])), "reason": None}


def _run_plan(cfg: CoolPropSmallAmplitudeWaveSweepConfig) -> list[dict[str, Any]]:
    cases: dict[tuple[int, float], set[str]] = {}
    for n in cfg.mesh_cells:
        cases.setdefault((n, cfg.mesh_comparison_cfl), set()).add("mesh_comparison")
    for c in cfg.cfl_values:
        cases.setdefault((cfg.cfl_comparison_n_cells, c), set()).add("cfl_comparison")
    return [{"n_cells": n, "cfl": c, "comparison_groups": sorted(groups), "case_id": case_id_for(n, c)} for (n, c), groups in sorted(cases.items())]


def _single_config(cfg: CoolPropSmallAmplitudeWaveSweepConfig, n: int, cfl: float) -> CoolPropSmallAmplitudeWaveConfig:
    return CoolPropSmallAmplitudeWaveConfig(
        case_name="coolprop_small_amplitude_wave", output_version=cfg.output_version,
        pipe_length_m=cfg.pipe_length_m, diameter_m=cfg.diameter_m, n_cells=n, cfl=cfl,
        initial_pressure_pa=cfg.initial_pressure_pa, initial_temperature_K=cfg.initial_temperature_K,
        pressure_amplitude_pa=cfg.pressure_amplitude_pa, pulse_center_fraction=cfg.pulse_center_fraction,
        pulse_sigma_fraction=cfg.pulse_sigma_fraction, probe_fractions=cfg.probe_fractions,
        sample_every=cfg.sample_every, max_steps=cfg.max_steps, arrival_threshold_fraction=cfg.arrival_threshold_fraction)


def _enrich(metrics: dict[str, Any], history: list[dict[str, Any]], cfg: CoolPropSmallAmplitudeWaveSweepConfig) -> dict[str, Any]:
    by_probe = {name: [r for r in history if r["probe_name"] == name] for name in {_probe_name(f) for f in cfg.probe_fractions}}
    sigma_t = float(metrics["pulse_sigma_m"] / metrics["c0"])
    theory_fwhm = gaussian_fwhm_m(float(metrics["pulse_sigma_m"]))
    ext: dict[str, Any] = {"waveform_metrics_by_probe": {}}
    for p in metrics["probes"]:
        rows = by_probe.get(p["probe_name"], [])
        t, y = _window_series(rows, float(p["theoretical_center_arrival_time_cell_center_s"]), sigma_t)
        peak_t = float(t[int(np.argmax(y))]) if t.size else None
        f = temporal_fwhm(t, y); c = temporal_centroid(t, y)
        if f.get("temporal_fwhm_s") is not None:
            f["equivalent_spatial_fwhm_m"] = float(f["temporal_fwhm_s"] * metrics["c0"])
            f["theoretical_initial_fwhm_m"] = theory_fwhm
            f["fwhm_broadening_ratio"] = float(f["equivalent_spatial_fwhm_m"] / theory_fwhm)
        ext["waveform_metrics_by_probe"][p["probe_name"]] = {"peak_arrival_time_s": peak_t, "peak_delta_pressure_pa": f.get("peak_delta_pressure_pa"), **f, **c}
    prim = [_probe_name(f) for f in cfg.primary_probe_fractions[:2]]
    if len(prim) == 2:
        pmap = {p["probe_name"]: p for p in metrics["probes"]}; w = ext["waveform_metrics_by_probe"]
        x1 = pmap[prim[0]]["probe_cell_center_x_m"]; x2 = pmap[prim[1]]["probe_cell_center_x_m"]; dx = x2 - x1
        for kind, key in [("peak", "peak_arrival_time_s"), ("centroid", "temporal_centroid_time_s")]:
            t1 = w[prim[0]].get(key); t2 = w[prim[1]].get(key)
            speed = dx / (t2 - t1) if t1 is not None and t2 is not None and t2 > t1 else None
            ext[f"interprobe_{kind}_speed_m_s"] = float(speed) if speed else None
            ext[f"interprobe_{kind}_speed_relative_error"] = float(abs(speed - metrics["c0"]) / metrics["c0"]) if speed else None
        t1, y1 = _window_series(by_probe[prim[0]], pmap[prim[0]]["theoretical_center_arrival_time_cell_center_s"], sigma_t)
        t2, y2 = _window_series(by_probe[prim[1]], pmap[prim[1]]["theoretical_center_arrival_time_cell_center_s"], sigma_t)
        cc = cross_correlation_lag(t1, y1, t2, y2) if t1.size and t2.size else {"cross_correlation_detected": False}
        ext.update(cc)
        lag = cc.get("cross_correlation_lag_s")
        speed = dx / lag if lag and lag > 0.0 else None
        ext["interprobe_cross_correlation_speed_m_s"] = float(speed) if speed else None
        ext["interprobe_cross_correlation_speed_relative_error"] = float(abs(speed - metrics["c0"]) / metrics["c0"]) if speed else None
        th1 = pmap[prim[0]].get("numerical_threshold_arrival_time_s"); th2 = pmap[prim[1]].get("numerical_threshold_arrival_time_s")
        speed = dx / (th2 - th1) if th1 is not None and th2 is not None and th2 > th1 else None
        ext["interprobe_threshold_speed_m_s"] = float(speed) if speed else None
        ext["interprobe_threshold_speed_relative_error"] = float(abs(speed - metrics["c0"]) / metrics["c0"]) if speed else None
    metrics.update(ext)
    return metrics


def _summary_row(m: dict[str, Any], cfg: CoolPropSmallAmplitudeWaveSweepConfig) -> dict[str, Any]:
    probes = {p["probe_name"]: p for p in m["probes"]}; wm = m.get("waveform_metrics_by_probe", {})
    def at(frac: float, key: str) -> Any:
        return wm.get(_probe_name(frac), {}).get(key)
    def pa(frac: float, key: str) -> Any:
        return probes.get(_probe_name(frac), {}).get(key)
    return {
        "case_id": m["case_id"], "n_cells": m["n_cells"], "dx_m": m["dx_m"], "cfl": m["cfl_target"], "step_count": m["step_count"], "runtime_seconds": m.get("runtime_seconds"), "c0": m["c0"],
        "overall_observation_run_pass": m["overall_observation_run_pass"], "remained_single_phase": m["remained_single_phase"], "budget_mass_relative_residual": m.get("budget_mass_relative_residual"), "energy_budget_balance_relative_residual": m.get("energy_budget_balance_relative_residual"),
        "primary_probe_amplitude_ratio_L2": pa(0.5, "amplitude_ratio"), "primary_probe_amplitude_ratio_3L4": pa(0.75, "amplitude_ratio"),
        "primary_probe_fwhm_broadening_ratio_L2": at(0.5, "fwhm_broadening_ratio"), "primary_probe_fwhm_broadening_ratio_3L4": at(0.75, "fwhm_broadening_ratio"),
        "interprobe_threshold_speed_m_s": m.get("interprobe_threshold_speed_m_s"), "interprobe_peak_speed_m_s": m.get("interprobe_peak_speed_m_s"), "interprobe_centroid_speed_m_s": m.get("interprobe_centroid_speed_m_s"), "interprobe_cross_correlation_speed_m_s": m.get("interprobe_cross_correlation_speed_m_s"),
        "interprobe_threshold_speed_relative_error": m.get("interprobe_threshold_speed_relative_error"), "interprobe_peak_speed_relative_error": m.get("interprobe_peak_speed_relative_error"), "interprobe_centroid_speed_relative_error": m.get("interprobe_centroid_speed_relative_error"), "interprobe_cross_correlation_speed_relative_error": m.get("interprobe_cross_correlation_speed_relative_error"),
        "cross_correlation_coefficient": m.get("cross_correlation_coefficient"), "waveform_l1_difference_vs_finest": m.get("waveform_l1_difference_vs_finest"), "waveform_l2_difference_vs_finest": m.get("waveform_l2_difference_vs_finest"),
    }


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def _write_report(path: Path, cfg: CoolPropSmallAmplitudeWaveSweepConfig, metrics: dict[str, Any]) -> None:
    lines = ["# CoolProp small-amplitude wave sweep report", "", "これは software / numerical verification 用の観察整理です。design-use評価、Validation、CoolProp backend承認、HEM/HNE/DVCM評価ではありません。", "", "## 全実行条件"]
    for r in metrics["summary_rows"]:
        lines.append(f"- {r['case_id']}: n_cells={r['n_cells']}, CFL={r['cfl']}, pass={r['overall_observation_run_pass']}")
    lines += ["", "## 波速評価法", "- threshold: local peak 50% rising crossing。波形拡散による早着biasを受ける可能性があります。", "- peak: incident window内の最大圧力時刻。振幅低下の追跡に有用です。", "- centroid: 正のdelta pressure面積の時間重心。波形全体の位相を見ます。", "- cross-correlation: primary probe 2点の波形ラグ。最細meshは真値ではなく finest-grid comparison reference です。", "", "## 観察区分", f"- overall_sweep_execution_pass: {metrics['overall_sweep_execution_pass']}", f"- numerical_convergence_observation: {metrics['numerical_convergence_observation']}", "", "正式な wave-speed / arrival / amplitude acceptance threshold は未設定です。次PRで実測結果を確認して判断してください。"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_comparison_plots(output_dir: Path, cfg: CoolPropSmallAmplitudeWaveSweepConfig, runs: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    generated: list[str] = []; errors: dict[str, str] = {}
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception as exc:
        return generated, {"matplotlib_import": str(exc)}
    def save(name: str, fig: Any) -> None:
        fig.tight_layout(); fig.savefig(output_dir / name, dpi=150, bbox_inches="tight"); generated.append(name)
    def plot_overlay(name: str, selected: list[dict[str, Any]], title: str) -> None:
        fig = Figure(figsize=(8,5)); FigureCanvasAgg(fig); ax = fig.subplots(); pn = _probe_name(cfg.comparison_reference_probe_fraction)
        for run in selected:
            rows = [r for r in run["history"] if r["probe_name"] == pn]
            ax.plot([r["time_s"] for r in rows], [r["delta_pressure_pa"] for r in rows], label=run["case_id"])
        ax.set_title(title); ax.set_xlabel("time [s]"); ax.set_ylabel("delta pressure [Pa]"); ax.grid(True, alpha=.3); ax.legend(fontsize=8); save(name, fig)
    jobs = [
        ("mesh_overlay_L2", lambda: plot_overlay(f"{cfg.case_name}_mesh_overlay_L2.png", [r for r in runs if "mesh_comparison" in r["comparison_groups"]], "Mesh overlay at L/2 (absolute time)")),
        ("cfl_overlay_L2", lambda: plot_overlay(f"{cfg.case_name}_cfl_overlay_L2.png", [r for r in runs if "cfl_comparison" in r["comparison_groups"]], "CFL overlay at L/2 (absolute time)")),
    ]
    for key, job in jobs:
        try: job()
        except Exception as exc: errors[key] = str(exc)
    for key, col, ylabel in [("speed_error_vs_dx", "interprobe_peak_speed_relative_error", "relative error"), ("amplitude_ratio_vs_dx", "primary_probe_amplitude_ratio_L2", "amplitude ratio"), ("fwhm_broadening_vs_dx", "primary_probe_fwhm_broadening_ratio_L2", "FWHM broadening"), ("waveform_difference_vs_dx", "waveform_l2_difference_vs_finest", "L2 difference")]:
        try:
            fig = Figure(figsize=(7,5)); FigureCanvasAgg(fig); ax = fig.subplots(); rows = [r for r in [run["summary_row"] for run in runs] if r.get(col) not in (None, "")]
            ax.plot([r["dx_m"] for r in rows], [r[col] for r in rows], marker="o"); ax.set_title(key); ax.set_xlabel("dx [m]"); ax.set_ylabel(ylabel); ax.grid(True, alpha=.3); save(f"{cfg.case_name}_{key}.png", fig)
        except Exception as exc: errors[key] = str(exc)
    return generated, errors


def run_coolprop_small_amplitude_wave_sweep(output_dir: Path | str | None = None, config: CoolPropSmallAmplitudeWaveSweepConfig | None = None) -> dict[str, Any]:
    cfg = config or CoolPropSmallAmplitudeWaveSweepConfig()
    base = Path(output_dir) if output_dir is not None else Path(tempfile.mkdtemp(prefix="coolprop_wave_sweep_"))
    base.mkdir(parents=True, exist_ok=True)
    runs = []
    for item in _run_plan(cfg):
        run_dir = base / item["case_id"]
        start = time.perf_counter(); exc = None
        try:
            m = run_coolprop_small_amplitude_wave(run_dir if cfg.generate_case_plots else run_dir, _single_config(cfg, item["n_cells"], item["cfl"]))
        except Exception as e:  # pragma: no cover - failure captured in metrics
            m = {"completed_without_exception": False, "overall_observation_run_pass": False, "n_cells": item["n_cells"], "cfl_target": item["cfl"]}; exc = str(e)
        runtime = time.perf_counter() - start
        hist_path = run_dir / "coolprop_small_amplitude_wave_probe_history.csv"
        history = _as_float_rows(_read_csv(hist_path)) if hist_path.exists() else []
        m.update(item); m["runtime_seconds"] = runtime; m["completed_without_exception"] = bool(exc is None and m.get("completed_without_exception")); m["exception"] = exc
        if history and exc is None:
            m = _enrich(m, history, cfg)
        runs.append({"case_id": item["case_id"], "comparison_groups": item["comparison_groups"], "metrics": m, "history": history})
    # waveform difference vs finest-grid comparison reference at primary L/2
    ref = next((r for r in runs if r["metrics"].get("n_cells") == max(cfg.mesh_cells) and r["metrics"].get("cfl_target") == cfg.mesh_comparison_cfl), None)
    if ref and ref["history"]:
        pn = _probe_name(cfg.comparison_reference_probe_fraction)
        rr = [x for x in ref["history"] if x["probe_name"] == pn]
        tr = np.asarray([x["time_s"] for x in rr]); yr = np.asarray([x["delta_pressure_pa"] for x in rr]) - rr[0]["delta_pressure_pa"]
        norm1 = float(np.trapezoid(np.abs(yr), tr)); norm2 = float(math.sqrt(np.trapezoid(yr*yr, tr)))
        for run in runs:
            rows = [x for x in run["history"] if x["probe_name"] == pn]
            if len(rows) >= 2:
                t = np.asarray([x["time_s"] for x in rows]); y = np.asarray([x["delta_pressure_pa"] for x in rows]) - rows[0]["delta_pressure_pa"]
                try:
                    tg, a, b = common_time_grid(t, y, tr, yr)
                    run["metrics"]["waveform_l1_difference_vs_finest"] = float(np.trapezoid(np.abs(a-b), tg) / norm1) if norm1 > 0 else None
                    run["metrics"]["waveform_l2_difference_vs_finest"] = float(math.sqrt(np.trapezoid((a-b)**2, tg)) / norm2) if norm2 > 0 else None
                except Exception:
                    pass
    rows = [_summary_row(r["metrics"], cfg) for r in runs]
    for run, row in zip(runs, rows): run["summary_row"] = row
    all_pass = all(r["metrics"].get("completed_without_exception") and r["metrics"].get("overall_observation_run_pass") and not r["metrics"].get("missing_budget_fields") for r in runs)
    mesh_rows = [row for row in rows if row["cfl"] == cfg.mesh_comparison_cfl]
    order = apparent_order([r["dx_m"] for r in mesh_rows], [r.get("interprobe_peak_speed_relative_error") or math.nan for r in mesh_rows])
    obs = "run_failure" if not all_pass else ("monotonic_improvement_observed" if order.get("apparent_order") is not None else "mixed_convergence_behavior")
    metrics = {"case_name": cfg.case_name, "output_version": cfg.output_version, "design_evaluation": False, "property_backend_design_status": "not_approved_for_design_use", "run_plan": _run_plan(cfg), "runs": [r["metrics"] for r in runs], "summary_rows": rows, "apparent_order_peak_speed": order, "overall_sweep_execution_pass": bool(all_pass), "numerical_convergence_observation": obs, "finest_grid_comparison_reference": case_id_for(max(cfg.mesh_cells), cfg.mesh_comparison_cfl)}
    stem = cfg.case_name
    (base / f"{stem}_sweep_config.json").write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    _write_summary_csv(base / f"{stem}_sweep_summary.csv", rows)
    generated, errors = ([], {})
    if cfg.generate_comparison_plots:
        generated, errors = _generate_comparison_plots(base, cfg, runs)
    metrics["generated_plots"] = generated; metrics["plotting_errors"] = errors
    (base / f"{stem}_sweep_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    _write_report(base / f"{stem}_sweep_report.md", cfg, metrics)
    return metrics


__all__ = ["CoolPropSmallAmplitudeWaveSweepConfig", "run_coolprop_small_amplitude_wave_sweep", "gaussian_fwhm_m", "temporal_fwhm", "temporal_centroid", "common_time_grid", "cross_correlation_lag", "apparent_order", "case_id_for"]
