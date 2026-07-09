"""Automated Case-C result reporting for Ver.0.4.4.

This module turns the numerical diagnostics added through Ver.0.4.3 into a
repeatable design-evaluation package.  It intentionally does not change the
solver.  It only orchestrates case runs, collects histories/final profiles,
creates CSV/JSON/PNG artifacts, and writes a Markdown evaluation report.
"""

from __future__ import annotations

from dataclasses import dataclass, replace, asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import csv
import json
import math

import numpy as np

from .cases.case_c import (
    CaseCParameters,
    _case_c_sample,
    build_case_c_solver,
    build_discretized_case_c_network,
    effective_phase_change_model,
)


@dataclass(frozen=True)
class ReportVariant:
    """One report variant.

    Parameters
    ----------
    name:
        Stable identifier used in CSV files.
    label:
        Human-readable label used in report tables.
    phase_change_model:
        Case-C phase-change selector: ``none``, ``hem`` or ``hne``.
    hne_tau_s:
        Optional relaxation time override for HNE.
    """

    name: str
    label: str
    phase_change_model: str
    hne_tau_s: float | None = None


DEFAULT_REPORT_VARIANTS: tuple[ReportVariant, ...] = (
    ReportVariant(name="none", label="single-phase / no phase change", phase_change_model="none"),
    ReportVariant(name="hem", label="toy HEM equilibrium flash", phase_change_model="hem"),
    ReportVariant(name="hne", label="toy HNE relaxation", phase_change_model="hne", hne_tau_s=0.05),
)


@dataclass(frozen=True)
class CaseCReportConfig:
    """Configuration for automated Case-C report generation."""

    title: str = "Case C automated evaluation report"
    version: str = "0.4.4"
    sample_every: int = 10
    max_steps: int = 100_000
    include_profile_csv: bool = True
    include_figures: bool = True


def standard_report_parameters() -> CaseCParameters:
    """Return a moderately informative default setup for report generation.

    The setup is still a toy-model verification/evaluation case, not a validated
    LCO2 design case.  It gives nonzero pump work, ESD closure, phase diagnostics,
    gravity/source energy terms and latent-heat placeholders so the report can
    exercise all ledgers.
    """

    return CaseCParameters(
        n_cells=400,
        t_end_s=0.20,
        pump_delta_p_nominal_pa=2.5e5,
        pump_trip_start_s=0.12,
        pump_trip_duration_s=0.04,
        pump_delta_p_final_pa=5.0e4,
        valve_close_start_s=0.05,
        valve_close_time_s=0.02,
        latent_heat_placeholder_j_kg=2.0e5,
    )


def variant_parameters(base: CaseCParameters, variant: ReportVariant) -> CaseCParameters:
    """Return ``base`` parameters modified for one report variant."""

    kwargs: dict[str, object] = {
        "enable_hem": variant.phase_change_model == "hem",
        "phase_change_model": variant.phase_change_model,
    }
    if variant.hne_tau_s is not None:
        kwargs["hne_tau_s"] = variant.hne_tau_s
    return replace(base, **kwargs)


def run_case_c_for_report(
    params: CaseCParameters,
    *,
    sample_every: int = 10,
    max_steps: int = 100_000,
) -> tuple[list[dict[str, float]], dict[str, np.ndarray | tuple[str, ...]]]:
    """Run Case C and return diagnostic history plus final cell profiles."""

    discretized = build_discretized_case_c_network(params)
    solver = build_case_c_solver(params)
    history: list[dict[str, float]] = [_case_c_sample(solver, discretized, params, dt=0.0)]
    while solver.t < params.t_end_s:
        dt = solver.compute_dt(params.t_end_s)
        solver.step(dt)
        if solver.step_count % sample_every == 0 or solver.t >= params.t_end_s:
            history.append(_case_c_sample(solver, discretized, params, dt=dt))
        if solver.step_count > max_steps:
            raise RuntimeError("max_steps reached before t_end")

    prim = solver.primitive()
    profiles: dict[str, np.ndarray | tuple[str, ...]] = {
        "x_m": discretized.grid.cell_centers.copy(),
        "elevation_m": discretized.cell_elevation_m.copy(),
        "segment": discretized.cell_segment_names,
        "rho_kg_m3": prim.rho.copy(),
        "u_m_s": prim.u.copy(),
        "p_pa": prim.p.copy(),
        "e_j_kg": prim.e.copy(),
        "xv": prim.xv.copy(),
        "alpha": prim.alpha.copy(),
        "c_m_s": prim.c.copy(),
    }
    return history, profiles


def _finite(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return out if math.isfinite(out) else default


def summarize_history(history: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """Return report-level extrema and final ledger values for one history."""

    if len(history) == 0:
        raise ValueError("history must not be empty")
    final = dict(history[-1])

    def min_key(key: str) -> float:
        return float(min(_finite(row.get(key), np.nan) for row in history if key in row))

    def max_key(key: str) -> float:
        return float(max(_finite(row.get(key), np.nan) for row in history if key in row))

    out = {
        "time_final_s": _finite(final.get("time_s")),
        "n_samples": float(len(history)),
        "p_min_overall_pa": min_key("p_min_pa"),
        "p_max_overall_pa": max_key("p_max_pa"),
        "u_min_overall_m_s": min_key("u_min_m_s"),
        "u_max_overall_m_s": max_key("u_max_m_s"),
        "rho_min_overall_kg_m3": min_key("rho_min_kg_m3"),
        "rho_max_overall_kg_m3": max_key("rho_max_kg_m3"),
        "xv_max_overall": max_key("xv_max"),
        "alpha_max_overall": max_key("alpha_max"),
        "c_min_overall_m_s": min_key("c_min_m_s"),
        "vapor_mass_final_kg": _finite(final.get("vapor_mass_total")),
        "phase_vapor_source_final_kg": _finite(final.get("phase_vapor_mass_source_cumulative_kg")),
        "mass_residual_final_kg": _finite(final.get("budget_mass_residual")),
        "mass_relative_residual_final": _finite(final.get("budget_mass_relative_residual")),
        "phase_vapor_residual_final_kg": _finite(final.get("phase_vapor_mass_balance_residual_kg")),
        "energy_balance_residual_final_j": _finite(final.get("energy_budget_balance_residual_j")),
        "latent_requirement_final_j": _finite(final.get("energy_phase_latent_requirement_cumulative_j")),
        "pump_work_final_j": _finite(final.get("energy_interface_pump_hydraulic_work_cumulative_j")),
        "valve_loss_final_j": _finite(final.get("energy_interface_valve_loss_proxy_cumulative_j")),
        "interface_net_final_j": _finite(final.get("energy_interface_net_diagnostic_cumulative_j")),
        "high_elevation_two_phase_flag_final": max(
            _finite(final.get("hem_high_elevation_two_phase_flag")),
            _finite(final.get("hne_high_elevation_two_phase_flag")),
        ),
        "two_phase_length_final_m": max(
            _finite(final.get("hem_two_phase_length_m")),
            _finite(final.get("hne_two_phase_length_m")),
            0.0,
        ),
    }
    return out


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if len(rows) == 0:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _profile_rows(variant_name: str, profiles: Mapping[str, np.ndarray | tuple[str, ...]]) -> list[dict[str, object]]:
    n = len(profiles["x_m"])  # type: ignore[arg-type]
    rows: list[dict[str, object]] = []
    for i in range(n):
        rows.append(
            {
                "variant": variant_name,
                "cell": i,
                "x_m": float(profiles["x_m"][i]),  # type: ignore[index]
                "elevation_m": float(profiles["elevation_m"][i]),  # type: ignore[index]
                "segment": profiles["segment"][i],  # type: ignore[index]
                "rho_kg_m3": float(profiles["rho_kg_m3"][i]),  # type: ignore[index]
                "u_m_s": float(profiles["u_m_s"][i]),  # type: ignore[index]
                "p_pa": float(profiles["p_pa"][i]),  # type: ignore[index]
                "e_j_kg": float(profiles["e_j_kg"][i]),  # type: ignore[index]
                "xv": float(profiles["xv"][i]),  # type: ignore[index]
                "alpha": float(profiles["alpha"][i]),  # type: ignore[index]
                "c_m_s": float(profiles["c_m_s"][i]),  # type: ignore[index]
            }
        )
    return rows


def _import_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _series(history: Sequence[Mapping[str, object]], key: str) -> np.ndarray:
    return np.array([_finite(row.get(key), np.nan) for row in history], dtype=float)


def _time(history: Sequence[Mapping[str, object]]) -> np.ndarray:
    return _series(history, "time_s")


def _plot_time_series(
    path: Path,
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    keys: Sequence[str],
    ylabel: str,
    title: str,
) -> None:
    plt = _import_matplotlib()
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(1, 1, 1)
    for name, history in histories.items():
        t = _time(history)
        for key in keys:
            y = _series(history, key)
            if np.all(~np.isfinite(y)):
                continue
            label = f"{name}: {key}"
            ax.plot(t, y, label=label)
    ax.set_xlabel("time [s]")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True)
    ax.legend(fontsize="small")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_profile(
    path: Path,
    profiles_by_variant: Mapping[str, Mapping[str, np.ndarray | tuple[str, ...]]],
    y_key: str,
    ylabel: str,
    title: str,
) -> None:
    plt = _import_matplotlib()
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(1, 1, 1)
    for name, prof in profiles_by_variant.items():
        ax.plot(prof["x_m"], prof[y_key], label=name)  # type: ignore[arg-type]
    ax.set_xlabel("x [m]")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True)
    ax.legend(fontsize="small")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _markdown_table(rows: Sequence[Mapping[str, object]], columns: Sequence[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body: list[str] = []
    for row in rows:
        cells = []
        for key, _label in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                if abs(value) >= 1.0e4 or (abs(value) > 0.0 and abs(value) < 1.0e-3):
                    cells.append(f"{value:.6e}")
                else:
                    cells.append(f"{value:.6g}")
            else:
                cells.append(str(value))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *body])


def write_markdown_report(
    path: Path,
    *,
    config: CaseCReportConfig,
    base_params: CaseCParameters,
    network_summary: Mapping[str, object],
    summary_rows: Sequence[Mapping[str, object]],
    figure_paths: Sequence[Path],
    data_paths: Sequence[Path],
) -> None:
    """Write the automated Markdown evaluation report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    rel_figs = [p.relative_to(path.parent).as_posix() for p in figure_paths]
    rel_data = [p.relative_to(path.parent).as_posix() for p in data_paths]

    summary_table = _markdown_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("p_max_overall_pa", "p_max [Pa]"),
            ("p_min_overall_pa", "p_min [Pa]"),
            ("xv_max_overall", "xv_max"),
            ("alpha_max_overall", "alpha_max"),
            ("c_min_overall_m_s", "c_min [m/s]"),
            ("vapor_mass_final_kg", "vapor mass [kg]"),
            ("two_phase_length_final_m", "two-phase length [m]"),
        ],
    )
    budget_table = _markdown_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("mass_relative_residual_final", "mass rel. residual"),
            ("phase_vapor_source_final_kg", "phase vapor source [kg]"),
            ("phase_vapor_residual_final_kg", "phase residual [kg]"),
            ("energy_balance_residual_final_j", "energy residual [J]"),
            ("pump_work_final_j", "pump work [J]"),
            ("valve_loss_final_j", "valve loss proxy [J]"),
            ("latent_requirement_final_j", "latent placeholder [J]"),
        ],
    )

    segments = network_summary.get("segments", [])
    segment_rows = []
    if isinstance(segments, list):
        for segment in segments:
            if isinstance(segment, Mapping):
                segment_rows.append(segment)
    segment_table = _markdown_table(
        segment_rows,
        [
            ("name", "Segment"),
            ("length_m", "L [m]"),
            ("n_cells", "cells"),
            ("darcy_friction_factor", "f_D"),
            ("elevation_start_m", "z_start [m]"),
            ("elevation_end_m", "z_end [m]"),
        ],
    )

    figure_md = "\n\n".join(f"![{Path(fig).stem}]({fig})" for fig in rel_figs)
    data_list = "\n".join(f"- `{p}`" for p in rel_data)

    text = f"""# {config.title} — Ver.{config.version}

## 1. 位置づけ

本レポートは、Phase 2 Ver.0.4.4 の自動評価レポート生成器により作成された Case C 評価結果である。
対象は toy EOS ベースの保存形FVM skeleton であり、LCO₂実在物性による設計確定値ではない。

目的は、今後の実在物性化・Validation へ進む前に、以下を一括で確認できるようにすることである。

- 単相 / HEM / HNE の同一条件比較
- 圧力・速度・密度・二相化指標の最大最小値
- 蒸気質量 inventory と相変化 source budget
- 質量・エネルギー・interface budget の残差
- ポンプ仕事・弁損失 proxy・潜熱 placeholder
- 最終時刻の軸方向プロファイル

## 2. ベンチマーク条件

```json
{json.dumps(asdict(base_params), indent=2, ensure_ascii=False)}
```

## 3. ネットワーク構成

{segment_table}

ESD 弁 face index: `{network_summary.get('devices', {}).get('land_side_esd_valve') if isinstance(network_summary.get('devices'), Mapping) else 'n/a'}`

## 4. 主要比較表

{summary_table}

## 5. Budget 比較表

{budget_table}

## 6. 図

{figure_md}

## 7. 出力データ

{data_list}

## 8. 判定

Ver.0.4.4 の自動レポート生成機能は、Case C の `none / HEM / HNE` を同じ手順で実行し、比較表・履歴CSV・最終プロファイルCSV・PNG図・Markdown レポートを生成できた。

数値ソルバそのものは Ver.0.4.3 から変更していない。したがって、本バージョンの Verification 対象は **レポート生成器の完全性、再現性、出力整合性**である。

## 9. 注意事項

- HEM/HNE は toy EOS に基づく skeleton である。
- `latent_requirement`、`valve_loss_proxy`、摩擦散逸 proxy は現段階では診断値であり、`rhoE` へ熱として反映していない。
- 実在 LCO₂ 物性、エンタルピ整合、ポンプ効率、弁損失熱化は Ver.0.5 以降で扱う。
"""
    path.write_text(text, encoding="utf-8")


def generate_case_c_report(
    output_dir: str | Path,
    *,
    base_params: CaseCParameters | None = None,
    variants: Sequence[ReportVariant] = DEFAULT_REPORT_VARIANTS,
    config: CaseCReportConfig | None = None,
) -> dict[str, object]:
    """Generate a complete Case-C comparison report package.

    Returns a dictionary with paths and summary metrics.  All paths are absolute
    strings to make verification straightforward.
    """

    cfg = config or CaseCReportConfig()
    base = base_params or standard_report_parameters()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    histories: dict[str, list[dict[str, float]]] = {}
    profiles: dict[str, dict[str, np.ndarray | tuple[str, ...]]] = {}
    summary_rows: list[dict[str, object]] = []
    all_history_rows: list[dict[str, object]] = []
    all_profile_rows: list[dict[str, object]] = []

    network_summary = build_discretized_case_c_network(base).summary()

    for variant in variants:
        params = variant_parameters(base, variant)
        history, profile = run_case_c_for_report(params, sample_every=cfg.sample_every, max_steps=cfg.max_steps)
        histories[variant.name] = history
        profiles[variant.name] = profile

        for row in history:
            all_history_rows.append({"variant": variant.name, **row})
        if cfg.include_profile_csv:
            all_profile_rows.extend(_profile_rows(variant.name, profile))

        summary = summarize_history(history)
        summary_rows.append(
            {
                "variant": variant.name,
                "label": variant.label,
                "phase_change_model": effective_phase_change_model(params),
                **summary,
            }
        )

    data_paths: list[Path] = []
    history_csv = out / "case_c_history_comparison_v0_4_4.csv"
    _write_csv(history_csv, all_history_rows)
    data_paths.append(history_csv)

    summary_csv = out / "case_c_summary_comparison_v0_4_4.csv"
    _write_csv(summary_csv, summary_rows)
    data_paths.append(summary_csv)

    if cfg.include_profile_csv:
        profile_csv = out / "case_c_final_profile_comparison_v0_4_4.csv"
        _write_csv(profile_csv, all_profile_rows)
        data_paths.append(profile_csv)

    summary_json = out / "case_c_report_summary_v0_4_4.json"
    summary_data = {
        "version": cfg.version,
        "config": asdict(cfg),
        "base_params": asdict(base),
        "network_summary": network_summary,
        "variants": summary_rows,
    }
    _write_json(summary_json, summary_data)
    data_paths.append(summary_json)

    figure_paths: list[Path] = []
    if cfg.include_figures:
        figs = {
            "case_c_pressure_extrema_v0_4_4.png": (["p_min_pa", "p_max_pa"], "pressure [Pa]", "Pressure extrema"),
            "case_c_velocity_extrema_v0_4_4.png": (["u_min_m_s", "u_max_m_s"], "velocity [m/s]", "Velocity extrema"),
            "case_c_phase_inventory_v0_4_4.png": (["vapor_mass_total", "phase_vapor_mass_source_cumulative_kg"], "mass [kg]", "Vapor inventory and source"),
            "case_c_energy_interface_ledger_v0_4_4.png": (["energy_interface_pump_hydraulic_work_cumulative_j", "energy_interface_valve_loss_proxy_cumulative_j"], "energy [J]", "Pump work and valve loss proxy"),
            "case_c_budget_residuals_v0_4_4.png": (["budget_mass_relative_residual", "energy_budget_balance_residual_j"], "residual", "Budget residual diagnostics"),
            "case_c_cmin_v0_4_4.png": (["c_min_m_s"], "sound speed [m/s]", "Minimum sound speed"),
        }
        for fname, (keys, ylabel, title) in figs.items():
            pfig = out / fname
            _plot_time_series(pfig, histories, keys, ylabel, title)
            figure_paths.append(pfig)

        profile_figs = {
            "case_c_final_pressure_profile_v0_4_4.png": ("p_pa", "pressure [Pa]", "Final pressure profile"),
            "case_c_final_velocity_profile_v0_4_4.png": ("u_m_s", "velocity [m/s]", "Final velocity profile"),
            "case_c_final_xv_profile_v0_4_4.png": ("xv", "vapor mass fraction [-]", "Final vapor mass fraction profile"),
            "case_c_final_alpha_profile_v0_4_4.png": ("alpha", "void fraction [-]", "Final void fraction profile"),
            "case_c_final_sound_speed_profile_v0_4_4.png": ("c_m_s", "sound speed [m/s]", "Final sound-speed profile"),
        }
        for fname, (key, ylabel, title) in profile_figs.items():
            pfig = out / fname
            _plot_profile(pfig, profiles, key, ylabel, title)
            figure_paths.append(pfig)

    report_path = out / "case_c_auto_evaluation_report_v0_4_4.md"
    write_markdown_report(
        report_path,
        config=cfg,
        base_params=base,
        network_summary=network_summary,
        summary_rows=summary_rows,
        figure_paths=figure_paths,
        data_paths=data_paths,
    )

    return {
        "version": cfg.version,
        "report_path": str(report_path),
        "output_dir": str(out),
        "data_paths": [str(p) for p in data_paths],
        "figure_paths": [str(p) for p in figure_paths],
        "summary_rows": summary_rows,
        "network_summary": network_summary,
    }
