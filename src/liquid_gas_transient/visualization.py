"""Visualization and post-processing utilities for Case C Ver.0.6.1.

This module intentionally does not alter the numerical solver.  It reruns the
Case C trial variants and records sampled cell profiles so that the transient
phenomena can be viewed as x--t maps.  The primary design goal is human review:
pressure-wave motion, vapor generation, void distribution and mixture sound-speed
reduction should be visible at a glance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

import numpy as np

from .case_c_trial_evaluation import (
    CaseCTrialEvaluationConfig,
    DEFAULT_TRIAL_VARIANTS,
    _engineering_flags,
    standard_trial_parameters,
)
from .cases.case_c import (
    CaseCParameters,
    _case_c_sample,
    build_case_c_solver,
    build_discretized_case_c_network,
    effective_phase_change_model,
)
from .reporting import ReportVariant, summarize_history


@dataclass(frozen=True)
class VisualizationConfig:
    """Configuration for Case C visual post-processing."""

    version: str = "0.6.1"
    sample_every: int = 5
    max_steps: int = 100_000
    include_figures: bool = True
    include_gif: bool = True
    vapor_visibility_xv_threshold: float = 1.0e-8
    vapor_visibility_alpha_threshold: float = 1.0e-6
    focus_variant_for_pipeline_overlay: str = "hne_tau005"


@dataclass(frozen=True)
class FieldSnapshotSet:
    """Sampled x--t fields for one Case C variant."""

    variant: str
    label: str
    phase_change_model: str
    x_m: np.ndarray
    elevation_m: np.ndarray
    segment: tuple[str, ...]
    time_s: np.ndarray
    pressure_pa: np.ndarray
    velocity_m_s: np.ndarray
    xv: np.ndarray
    alpha: np.ndarray
    c_m_s: np.ndarray
    rho_kg_m3: np.ndarray


def _import_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _finite(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, obj: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _variant_params(base: CaseCParameters, variant: ReportVariant) -> CaseCParameters:
    from dataclasses import replace

    kwargs: dict[str, object] = {
        "phase_change_model": variant.phase_change_model,
        "enable_hem": variant.phase_change_model == "hem",
        "eos_model": base.eos_model,
    }
    if variant.hne_tau_s is not None:
        kwargs["hne_tau_s"] = variant.hne_tau_s
    return replace(base, **kwargs)


def _primitive_arrays(solver) -> dict[str, np.ndarray]:
    prim = solver.primitive()
    return {
        "pressure_pa": prim.p.copy(),
        "velocity_m_s": prim.u.copy(),
        "xv": prim.xv.copy(),
        "alpha": prim.alpha.copy(),
        "c_m_s": prim.c.copy(),
        "rho_kg_m3": prim.rho.copy(),
    }


def run_case_c_with_field_snapshots(
    params: CaseCParameters,
    variant: ReportVariant,
    *,
    sample_every: int = 5,
    max_steps: int = 100_000,
) -> tuple[list[dict[str, float]], FieldSnapshotSet]:
    """Run Case C and collect full cell profiles at sampled times."""

    discretized = build_discretized_case_c_network(params)
    solver = build_case_c_solver(params)

    history: list[dict[str, float]] = [_case_c_sample(solver, discretized, params, dt=0.0)]
    times: list[float] = [float(solver.t)]
    fields: dict[str, list[np.ndarray]] = {key: [value] for key, value in _primitive_arrays(solver).items()}

    while solver.t < params.t_end_s:
        dt = solver.compute_dt(params.t_end_s)
        solver.step(dt)
        if solver.step_count % sample_every == 0 or solver.t >= params.t_end_s:
            history.append(_case_c_sample(solver, discretized, params, dt=dt))
            times.append(float(solver.t))
            prim_arrays = _primitive_arrays(solver)
            for key, value in prim_arrays.items():
                fields[key].append(value)
        if solver.step_count > max_steps:
            raise RuntimeError("max_steps reached before t_end")

    snapshot = FieldSnapshotSet(
        variant=variant.name,
        label=variant.label,
        phase_change_model=effective_phase_change_model(params),
        x_m=discretized.grid.cell_centers.copy(),
        elevation_m=discretized.cell_elevation_m.copy(),
        segment=tuple(discretized.cell_segment_names),
        time_s=np.array(times, dtype=float),
        pressure_pa=np.vstack(fields["pressure_pa"]),
        velocity_m_s=np.vstack(fields["velocity_m_s"]),
        xv=np.vstack(fields["xv"]),
        alpha=np.vstack(fields["alpha"]),
        c_m_s=np.vstack(fields["c_m_s"]),
        rho_kg_m3=np.vstack(fields["rho_kg_m3"]),
    )
    return history, snapshot


def _snapshot_field_rows(snapshot: FieldSnapshotSet) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    n_t, n_x = snapshot.pressure_pa.shape
    for it in range(n_t):
        for ix in range(n_x):
            rows.append(
                {
                    "variant": snapshot.variant,
                    "phase_change_model": snapshot.phase_change_model,
                    "time_s": float(snapshot.time_s[it]),
                    "cell": ix,
                    "x_m": float(snapshot.x_m[ix]),
                    "segment": snapshot.segment[ix],
                    "elevation_m": float(snapshot.elevation_m[ix]),
                    "p_pa": float(snapshot.pressure_pa[it, ix]),
                    "u_m_s": float(snapshot.velocity_m_s[it, ix]),
                    "xv": float(snapshot.xv[it, ix]),
                    "alpha": float(snapshot.alpha[it, ix]),
                    "c_m_s": float(snapshot.c_m_s[it, ix]),
                    "rho_kg_m3": float(snapshot.rho_kg_m3[it, ix]),
                }
            )
    return rows


def _plot_xt_contour(path: Path, snapshot: FieldSnapshotSet, field: np.ndarray, *, ylabel: str, title: str) -> None:
    plt = _import_matplotlib()
    fig = plt.figure(figsize=(10, 5.4))
    ax = fig.add_subplot(1, 1, 1)
    mesh = ax.pcolormesh(snapshot.x_m, snapshot.time_s, field, shading="auto")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label(ylabel)
    ax.set_xlabel("position x [m]")
    ax.set_ylabel("time [s]")
    ax.set_title(title)
    _add_event_markers(ax, snapshot)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _add_event_markers(ax, snapshot: FieldSnapshotSet) -> None:
    # Draw segment changes and ESD face as unobtrusive reference lines.
    seg = snapshot.segment
    x = snapshot.x_m
    last = seg[0]
    for i, name in enumerate(seg[1:], start=1):
        if name != last:
            ax.axvline(float(x[i]), linewidth=0.7, linestyle="--")
            ax.text(float(x[i]), ax.get_ylim()[1], name, rotation=90, va="top", ha="right", fontsize=7)
            last = name


def _plot_variant_xt_set(out: Path, snapshot: FieldSnapshotSet) -> list[Path]:
    specs = [
        ("pressure_xt", snapshot.pressure_pa, "pressure [Pa]", "Pressure x-t map"),
        ("xv_xt", snapshot.xv, "vapor mass fraction x_v [-]", "Vapor mass fraction x-t map"),
        ("alpha_xt", snapshot.alpha, "void fraction alpha [-]", "Void fraction x-t map"),
        ("sound_speed_xt", snapshot.c_m_s, "mixture sound speed [m/s]", "Mixture sound speed x-t map"),
    ]
    paths: list[Path] = []
    for stem, field, ylabel, title in specs:
        path = out / f"case_c_{snapshot.variant}_{stem}_v0_6_1.png"
        _plot_xt_contour(path, snapshot, field, ylabel=ylabel, title=f"{title} — {snapshot.variant}")
        paths.append(path)
    return paths


def _plot_comparison_panel(path: Path, snapshots: Mapping[str, FieldSnapshotSet], field_name: str, ylabel: str, title: str) -> None:
    plt = _import_matplotlib()
    n = len(snapshots)
    fig, axes = plt.subplots(n, 1, figsize=(10, 4.0 * n), sharex=True, squeeze=False)
    all_values = [getattr(s, field_name) for s in snapshots.values()]
    vmin = min(float(np.nanmin(v)) for v in all_values)
    vmax = max(float(np.nanmax(v)) for v in all_values)
    # If the field is identically zero, keep a nonzero range so matplotlib is stable.
    if math.isclose(vmin, vmax):
        vmax = vmin + 1.0
    mesh = None
    for ax, (name, snap) in zip(axes[:, 0], snapshots.items()):
        mesh = ax.pcolormesh(snap.x_m, snap.time_s, getattr(snap, field_name), shading="auto", vmin=vmin, vmax=vmax)
        ax.set_ylabel("time [s]")
        ax.set_title(name)
        _add_event_markers(ax, snap)
    axes[-1, 0].set_xlabel("position x [m]")
    if mesh is not None:
        cbar = fig.colorbar(mesh, ax=axes[:, 0].tolist())
        cbar.set_label(ylabel)
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _plot_pipeline_overlay(path: Path, snapshot: FieldSnapshotSet, *, xv_threshold: float, alpha_threshold: float) -> None:
    """Draw a simple human-readable pipeline overlay for the maximum vapor field."""

    plt = _import_matplotlib()
    max_xv = np.max(snapshot.xv, axis=0)
    max_alpha = np.max(snapshot.alpha, axis=0)
    visible = (max_xv > xv_threshold) | (max_alpha > alpha_threshold)

    fig = plt.figure(figsize=(11, 3.2))
    ax = fig.add_subplot(1, 1, 1)
    x = snapshot.x_m
    elev = snapshot.elevation_m
    y_base = elev - float(np.min(elev))
    if float(np.max(y_base)) > 0:
        y_base = y_base / float(np.max(y_base))
    ax.plot(x, y_base, linewidth=2.0, label="pipeline elevation profile")

    # Plot vapor markers above the line. Marker size scales with max void fraction.
    marker_size = 20.0 + 3500.0 * np.clip(max_alpha, 0.0, None)
    if np.any(visible):
        ax.scatter(x[visible], y_base[visible] + 0.10, s=marker_size[visible], alpha=0.75, label="vapor/void detected")
    else:
        ax.text(0.5, 0.62, "No visible vapor/void region above thresholds", transform=ax.transAxes, ha="center")

    # Segment boundary annotations.
    last = snapshot.segment[0]
    ax.text(float(x[0]), -0.10, last, ha="left", va="top", fontsize=8)
    for i, name in enumerate(snapshot.segment[1:], start=1):
        if name != last:
            ax.axvline(float(x[i]), linewidth=0.7, linestyle="--")
            ax.text(float(x[i]), -0.10, name, rotation=0, ha="left", va="top", fontsize=8)
            last = name
    ax.set_xlabel("position x [m]")
    ax.set_yticks([])
    ax.set_title(f"Pipeline overlay: vapor/void occurrence — {snapshot.variant}")
    ax.legend(loc="upper right", fontsize="small")
    ax.set_ylim(-0.18, 1.35)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_vapor_onset(path: Path, snapshots: Mapping[str, FieldSnapshotSet], *, xv_threshold: float, alpha_threshold: float) -> None:
    """Plot first time at which vapor/void becomes visible at each cell."""

    plt = _import_matplotlib()
    fig = plt.figure(figsize=(10, 4.8))
    ax = fig.add_subplot(1, 1, 1)
    for name, snap in snapshots.items():
        mask = (snap.xv > xv_threshold) | (snap.alpha > alpha_threshold)
        onset = np.full(mask.shape[1], np.nan)
        for ix in range(mask.shape[1]):
            idx = np.where(mask[:, ix])[0]
            if idx.size > 0:
                onset[ix] = snap.time_s[int(idx[0])]
        if np.any(np.isfinite(onset)):
            ax.plot(snap.x_m, onset, marker=".", linestyle="", label=name)
    ax.set_xlabel("position x [m]")
    ax.set_ylabel("first visible vapor/void time [s]")
    ax.set_title("Vapor/void onset map")
    ax.grid(True)
    ax.legend(fontsize="small")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _make_gif(path: Path, snapshot: FieldSnapshotSet) -> bool:
    """Create a compact GIF animation if imageio is available."""

    try:
        import imageio.v2 as imageio
    except Exception:
        return False
    plt = _import_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    # Limit frames so the artifact stays compact.
    n_t = len(snapshot.time_s)
    frame_indices = np.linspace(0, n_t - 1, min(n_t, 40), dtype=int)
    vmin = float(np.nanmin(snapshot.alpha))
    vmax = float(np.nanmax(snapshot.alpha))
    if math.isclose(vmin, vmax):
        vmax = vmin + 1.0
    temp_dir = path.parent / f".{path.stem}_frames"
    temp_dir.mkdir(exist_ok=True)
    try:
        for k, it in enumerate(frame_indices):
            fig = plt.figure(figsize=(8, 3.8))
            ax = fig.add_subplot(1, 1, 1)
            ax.plot(snapshot.x_m, snapshot.pressure_pa[it] / 1.0e6, label="pressure [MPa]")
            ax2 = ax.twinx()
            ax2.plot(snapshot.x_m, snapshot.alpha[it], label="void fraction [-]")
            ax.set_xlabel("position x [m]")
            ax.set_ylabel("pressure [MPa]")
            ax2.set_ylabel("void fraction [-]")
            ax.set_title(f"{snapshot.variant}: t = {snapshot.time_s[it]:.4f} s")
            ax.grid(True)
            fig.tight_layout()
            frame_path = temp_dir / f"frame_{k:04d}.png"
            fig.savefig(frame_path, dpi=110)
            plt.close(fig)
            frames.append(imageio.imread(frame_path))
        imageio.mimsave(path, frames, duration=0.12)
        return True
    finally:
        for f in temp_dir.glob("*.png"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def _md_table(rows: Sequence[Mapping[str, object]], columns: Sequence[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body: list[str] = []
    for row in rows:
        cells: list[str] = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                if abs(value) >= 1.0e4 or (0.0 < abs(value) < 1.0e-3):
                    cells.append(f"{value:.6e}")
                else:
                    cells.append(f"{value:.6g}")
            else:
                cells.append(str(value))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *body])


def _write_visual_report(
    path: Path,
    *,
    cfg: VisualizationConfig,
    base: CaseCParameters,
    summary_rows: Sequence[Mapping[str, object]],
    figure_paths: Sequence[Path],
    data_paths: Sequence[Path],
    gif_paths: Sequence[Path],
) -> None:
    summary_table = _md_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("p_max_overall_pa", "p max [Pa]"),
            ("xv_max_overall", "xv max"),
            ("alpha_max_overall", "alpha max"),
            ("c_min_overall_m_s", "c min [m/s]"),
            ("vapor_mass_final_kg", "vapor mass [kg]"),
            ("two_phase_length_final_m", "2-phase length [m]"),
        ],
    )
    figs = "\n\n".join(f"![{p.stem}]({p.name})" for p in figure_paths)
    gifs = "\n".join(f"- `{p.name}`" for p in gif_paths) if gif_paths else "- GIF output was skipped because the optional encoder was unavailable or disabled."
    data = "\n".join(f"- `{p.name}`" for p in data_paths)
    text = f"""# Case C Visualization & Post-Processor — Ver.{cfg.version}

## 1. Purpose

This package adds human-readable visual output to the Case C trial evaluation.  The solver is unchanged; sampled field data are post-processed into x--t maps and pipeline overlays.

The priority is direct visual interpretation:

- where pressure waves travel,
- where vapor mass fraction appears,
- where void fraction becomes visible,
- where the mixture sound speed drops,
- and whether HEM/HNE differ in a way a reviewer can understand at a glance.

## 2. Case setup

- Main event: land-side ESD closure from `{base.valve_close_start_s:.3f} s` to `{base.valve_close_start_s + base.valve_close_time_s:.3f} s`
- Backend: `{base.eos_model}`
- Phase models compared: single phase, HEM, HNE
- Sample interval: every `{cfg.sample_every}` solver steps

## 3. Summary

{summary_table}

## 4. Visual interpretation

The most useful figures are:

1. `case_c_hne_tau005_xv_xt_v0_6_1.png` — vapor mass fraction x--t map.
2. `case_c_hne_tau005_alpha_xt_v0_6_1.png` — void fraction x--t map.
3. `case_c_hne_tau005_sound_speed_xt_v0_6_1.png` — mixture sound-speed x--t map.
4. `case_c_pipeline_vapor_overlay_hne_tau005_v0_6_1.png` — simple pipeline overlay of vapor/void occurrence.
5. `case_c_xv_xt_comparison_v0_6_1.png` and `case_c_alpha_xt_comparison_v0_6_1.png` — single-phase / HEM / HNE comparison panels.

In the default surrogate trial, vapor generation remains light. HEM gives the largest visible vapor/void region because it is an instantaneous equilibrium model. HNE is lower because finite relaxation delays vapor generation. DVCM is not included yet; the comparison slots are intentionally prepared for Ver.0.6.2.

## 5. Figures

{figs}

## 6. Animation outputs

{gifs}

## 7. Data outputs

{data}

## 8. Limitations

This is still a surrogate-LCO₂ trial visualization.  It is suitable for checking the software workflow, the visibility of phenomena, and review output quality.  It is not a final design-use result until a project-approved real-fluid property reference passes the acceptance gate.
"""
    path.write_text(text, encoding="utf-8")


def generate_case_c_visualization_package(
    output_dir: str | Path,
    *,
    base_params: CaseCParameters | None = None,
    variants: Sequence[ReportVariant] = DEFAULT_TRIAL_VARIANTS,
    config: VisualizationConfig | None = None,
) -> dict[str, object]:
    """Generate Ver.0.6.1 visual post-processing artifacts."""

    cfg = config or VisualizationConfig()
    base = base_params or standard_trial_parameters()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    histories: dict[str, list[dict[str, float]]] = {}
    snapshots: dict[str, FieldSnapshotSet] = {}
    summary_rows: list[dict[str, object]] = []
    all_history_rows: list[dict[str, object]] = []
    all_field_rows: list[dict[str, object]] = []

    trial_cfg = CaseCTrialEvaluationConfig(version=cfg.version)
    for variant in variants:
        params = _variant_params(base, variant)
        history, snapshot = run_case_c_with_field_snapshots(
            params,
            variant,
            sample_every=cfg.sample_every,
            max_steps=cfg.max_steps,
        )
        histories[variant.name] = history
        snapshots[variant.name] = snapshot
        for row in history:
            all_history_rows.append({"variant": variant.name, **row})
        all_field_rows.extend(_snapshot_field_rows(snapshot))
        summary = summarize_history(history)
        summary_rows.append(
            {
                "variant": variant.name,
                "label": variant.label,
                "phase_change_model": effective_phase_change_model(params),
                **summary,
                **_engineering_flags(summary, trial_cfg),
            }
        )

    data_paths: list[Path] = []
    history_csv = out / "case_c_visual_history_v0_6_1.csv"
    fields_csv = out / "case_c_visual_xt_fields_v0_6_1.csv"
    summary_csv = out / "case_c_visual_summary_v0_6_1.csv"
    metrics_json = out / "case_c_visual_metrics_v0_6_1.json"
    _write_csv(history_csv, all_history_rows)
    _write_csv(fields_csv, all_field_rows)
    _write_csv(summary_csv, summary_rows)
    data_paths.extend([history_csv, fields_csv, summary_csv, metrics_json])

    figure_paths: list[Path] = []
    gif_paths: list[Path] = []
    if cfg.include_figures:
        for snap in snapshots.values():
            figure_paths.extend(_plot_variant_xt_set(out, snap))
        comparison_specs = [
            ("pressure_pa", "pressure [Pa]", "Case C pressure x-t comparison", "case_c_pressure_xt_comparison_v0_6_1.png"),
            ("xv", "vapor mass fraction x_v [-]", "Case C vapor mass fraction x-t comparison", "case_c_xv_xt_comparison_v0_6_1.png"),
            ("alpha", "void fraction alpha [-]", "Case C void fraction x-t comparison", "case_c_alpha_xt_comparison_v0_6_1.png"),
            ("c_m_s", "mixture sound speed [m/s]", "Case C sound speed x-t comparison", "case_c_sound_speed_xt_comparison_v0_6_1.png"),
        ]
        for field_name, ylabel, title, fname in comparison_specs:
            path = out / fname
            _plot_comparison_panel(path, snapshots, field_name, ylabel, title)
            figure_paths.append(path)
        focus = snapshots.get(cfg.focus_variant_for_pipeline_overlay) or next(iter(snapshots.values()))
        overlay = out / f"case_c_pipeline_vapor_overlay_{focus.variant}_v0_6_1.png"
        _plot_pipeline_overlay(
            overlay,
            focus,
            xv_threshold=cfg.vapor_visibility_xv_threshold,
            alpha_threshold=cfg.vapor_visibility_alpha_threshold,
        )
        figure_paths.append(overlay)
        onset = out / "case_c_vapor_onset_map_v0_6_1.png"
        _plot_vapor_onset(
            onset,
            snapshots,
            xv_threshold=cfg.vapor_visibility_xv_threshold,
            alpha_threshold=cfg.vapor_visibility_alpha_threshold,
        )
        figure_paths.append(onset)

    if cfg.include_gif:
        focus = snapshots.get(cfg.focus_variant_for_pipeline_overlay)
        if focus is not None:
            gif_path = out / f"case_c_{focus.variant}_pressure_void_animation_v0_6_1.gif"
            if _make_gif(gif_path, focus):
                gif_paths.append(gif_path)

    metrics: dict[str, object] = {
        "version": cfg.version,
        "config": asdict(cfg),
        "base_params": asdict(base),
        "summary_rows": summary_rows,
        "n_figures": len(figure_paths),
        "n_gifs": len(gif_paths),
        "n_field_rows": len(all_field_rows),
        "paths": {
            "report_md": str(out / "case_c_visual_report_v0_6_1.md"),
            "history_csv": str(history_csv),
            "fields_csv": str(fields_csv),
            "summary_csv": str(summary_csv),
            "metrics_json": str(metrics_json),
        },
    }
    _write_json(metrics_json, metrics)
    report_md = out / "case_c_visual_report_v0_6_1.md"
    _write_visual_report(
        report_md,
        cfg=cfg,
        base=base,
        summary_rows=summary_rows,
        figure_paths=figure_paths,
        data_paths=data_paths,
        gif_paths=gif_paths,
    )
    return metrics
