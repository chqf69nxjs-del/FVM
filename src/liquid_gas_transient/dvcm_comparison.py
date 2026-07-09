"""Case C DVCM legacy comparison package for Ver.0.6.2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence
import json
import math

import numpy as np

from .case_c_trial_evaluation import DEFAULT_TRIAL_VARIANTS, standard_trial_parameters
from .cases.case_c import CaseCParameters, effective_phase_change_model
from .dvcm_legacy import (
    DVCMLegacyConfig,
    build_dvcm_legacy_snapshot,
    dvcm_field_rows,
    dvcm_history_rows,
    summarize_dvcm_legacy,
    summary_asdict,
    write_csv,
    write_json,
)
from .reporting import ReportVariant, summarize_history
from .visualization import (
    FieldSnapshotSet,
    VisualizationConfig,
    _md_table,
    _plot_comparison_panel,
    _plot_pipeline_overlay,
    _plot_vapor_onset,
    _plot_xt_contour,
    _snapshot_field_rows,
    run_case_c_with_field_snapshots,
)


@dataclass(frozen=True)
class DVCMComparisonConfig:
    """Configuration for Ver.0.6.2 DVCM legacy comparison."""

    version: str = "0.6.2"
    sample_every: int = 5
    max_steps: int = 100_000
    include_figures: bool = True
    include_single_phase_baseline: bool = True
    vapor_visibility_xv_threshold: float = 1.0e-8
    vapor_visibility_alpha_threshold: float = 1.0e-6


DEFAULT_DVCM_COMPARISON_VARIANTS: tuple[ReportVariant, ...] = DEFAULT_TRIAL_VARIANTS


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


def _comparison_summary_row_from_history(name: str, label: str, phase_model: str, history: Sequence[Mapping[str, float]]) -> dict[str, object]:
    summary = summarize_history(history)
    return {
        "variant": name,
        "label": label,
        "model_role": "primary candidate" if phase_model in {"hem", "hne"} else "baseline",
        "phase_change_model": phase_model,
        "p_min_overall_pa": summary.get("p_min_overall_pa", math.nan),
        "p_max_overall_pa": summary.get("p_max_overall_pa", math.nan),
        "xv_or_equiv_xv_max": summary.get("xv_max_overall", 0.0),
        "alpha_or_cavity_alpha_max": summary.get("alpha_max_overall", 0.0),
        "c_min_or_proxy_m_s": summary.get("c_min_overall_m_s", math.nan),
        "vapor_or_cavity_inventory": summary.get("vapor_mass_final_kg", 0.0),
        "inventory_units": "kg vapor mass",
        "two_phase_or_cavity_length_final_m": summary.get("two_phase_length_final_m", 0.0),
    }


def _comparison_summary_row_from_dvcm(summary: Mapping[str, object]) -> dict[str, object]:
    return {
        "variant": summary["variant"],
        "label": summary["label"],
        "model_role": "legacy reference / not primary",
        "phase_change_model": "dvcm_legacy",
        "p_min_overall_pa": summary["p_min_overall_pa"],
        "p_max_overall_pa": summary["p_max_overall_pa"],
        "xv_or_equiv_xv_max": summary["xv_equiv_max_overall"],
        "alpha_or_cavity_alpha_max": summary["alpha_max_overall"],
        "c_min_or_proxy_m_s": summary["c_min_overall_m_s"],
        "vapor_or_cavity_inventory": summary["cavity_volume_proxy_final_m3"],
        "inventory_units": "m3 cavity proxy",
        "two_phase_or_cavity_length_final_m": summary["cavity_length_final_m"],
        "cavity_volume_proxy_max_m3": summary["cavity_volume_proxy_max_m3"],
        "cavity_present": summary["cavity_present"],
        "first_cavity_time_s": summary["first_cavity_time_s"],
    }


def _write_report(
    path: Path,
    *,
    cfg: DVCMComparisonConfig,
    dvcm_cfg: DVCMLegacyConfig,
    base: CaseCParameters,
    summary_rows: Sequence[Mapping[str, object]],
    figure_paths: Sequence[Path],
    data_paths: Sequence[Path],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = _md_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("model_role", "Role"),
            ("p_max_overall_pa", "p max [Pa]"),
            ("xv_or_equiv_xv_max", "xv / equiv. xv"),
            ("alpha_or_cavity_alpha_max", "alpha / cavity alpha"),
            ("c_min_or_proxy_m_s", "c min/proxy [m/s]"),
            ("vapor_or_cavity_inventory", "inventory"),
            ("inventory_units", "units"),
            ("two_phase_or_cavity_length_final_m", "final length [m]"),
        ],
    )
    figs = "\n\n".join(f"![{p.stem}]({p.name})" for p in figure_paths)
    data = "\n".join(f"- `{p.name}`" for p in data_paths)
    text = f"""# Case C DVCM Legacy Comparison — Ver.{cfg.version}

## 1. Purpose

This package adds DVCM as a legacy/reference comparison to the Case C trial-evaluation workflow.

DVCM is **not** promoted to the primary liquefied-gas two-phase model.  Its purpose is to answer a review question that often appears in design work:

> What would the older water-hammer style cavity model show, compared with the FVM+HEM/HNE branches?

## 2. Model positioning

| Model | Role |
|---|---|
| FVM + HEM | equilibrium two-phase upper-side reference |
| FVM + HNE | main candidate for delayed phase-change behavior |
| DVCM legacy proxy | legacy reference / cavity-volume comparison |

The Ver.0.6.2 DVCM path is a diagnostic proxy. It maps the sampled single-phase FVM field to a DVCM-like cavity field by pressure clipping and density-deficit cavity-volume estimation. It is **not** a full MOC-DVCM solver.

## 3. Case setup

- Event: land-side ESD closure from `{base.valve_close_start_s:.3f} s` to `{base.valve_close_start_s + base.valve_close_time_s:.3f} s`
- Backend: `{base.eos_model}`
- DVCM vapor pressure: `{dvcm_cfg.vapor_pressure_pa:.6e} Pa`
- DVCM saturated liquid density: `{dvcm_cfg.saturated_liquid_density_kg_m3:.6g} kg/m3`
- DVCM saturated vapor density: `{dvcm_cfg.saturated_vapor_density_kg_m3:.6g} kg/m3`

## 4. Comparison summary

{table}

## 5. Interpretation

- HEM/HNE report vapor **mass** and homogeneous-equilibrium/relaxation void fraction.
- DVCM reports a **cavity-volume proxy**. Its equivalent vapor mass fraction is only provided so it can appear on the same x--t visualization frame.
- HNE should generally show less vapor generation than HEM when phase change is delayed.
- DVCM may highlight locations where the pressure reaches vapor pressure, but it does not represent continuous vapor advection or homogeneous two-phase sound-speed reduction in the same way as HEM/HNE.

For the default surrogate Case C trial, the event remains pressure-wave dominated and the vapor/cavity indicators remain light. This is consistent with the Ver.0.6.0 and Ver.0.6.1 findings.

## 6. Figures

{figs}

## 7. Data outputs

{data}

## 8. Limitations

This is still a surrogate-LCO2 software-path comparison. It is useful for reviewing differences in modeling assumptions and visualization output. It is not a design-use DVCM validation result, nor is it an accepted real-fluid LCO2 assessment.
"""
    path.write_text(text, encoding="utf-8")


def generate_dvcm_legacy_comparison_package(
    output_dir: str | Path,
    *,
    base_params: CaseCParameters | None = None,
    variants: Sequence[ReportVariant] = DEFAULT_DVCM_COMPARISON_VARIANTS,
    config: DVCMComparisonConfig | None = None,
    dvcm_config: DVCMLegacyConfig | None = None,
) -> dict[str, object]:
    """Generate Ver.0.6.2 DVCM-vs-HEM/HNE comparison artifacts."""

    cfg = config or DVCMComparisonConfig()
    dvcm_cfg = dvcm_config or DVCMLegacyConfig()
    base = base_params or standard_trial_parameters()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    histories: dict[str, list[dict[str, float]]] = {}
    snapshots: dict[str, FieldSnapshotSet] = {}
    summary_rows: list[dict[str, object]] = []
    all_history_rows: list[dict[str, object]] = []
    all_field_rows: list[dict[str, object]] = []

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
        if cfg.include_single_phase_baseline or variant.name != "single_phase":
            summary_rows.append(
                _comparison_summary_row_from_history(
                    variant.name,
                    variant.label,
                    effective_phase_change_model(params),
                    history,
                )
            )

    single = snapshots.get("single_phase")
    if single is None:
        raise RuntimeError("DVCM legacy comparison requires a single_phase baseline snapshot")
    dvcm_snapshot = build_dvcm_legacy_snapshot(single, config=dvcm_cfg)
    dvcm_summary = summary_asdict(summarize_dvcm_legacy(dvcm_snapshot, config=dvcm_cfg))
    snapshots["dvcm_legacy"] = dvcm_snapshot
    histories["dvcm_legacy"] = [dict(row) for row in dvcm_history_rows(dvcm_snapshot, config=dvcm_cfg)]  # type: ignore[list-item]
    all_history_rows.extend(histories["dvcm_legacy"])
    all_field_rows.extend(dvcm_field_rows(dvcm_snapshot))
    summary_rows.append(_comparison_summary_row_from_dvcm(dvcm_summary))

    # For main comparison panels, show HEM/HNE/DVCM.  Single-phase is still in
    # the data/summary but can obscure two-phase comparison panels.
    panel_snapshots = {
        name: snapshots[name]
        for name in ["hem", "hne_tau005", "dvcm_legacy"]
        if name in snapshots
    }

    figure_paths: list[Path] = []
    if cfg.include_figures:
        # DVCM-specific maps.
        dvcm_alpha = out / "case_c_dvcm_legacy_cavity_alpha_xt_v0_6_2.png"
        _plot_xt_contour(
            dvcm_alpha,
            dvcm_snapshot,
            dvcm_snapshot.alpha,
            ylabel="DVCM cavity alpha proxy [-]",
            title="DVCM legacy cavity-volume proxy x-t map",
        )
        figure_paths.append(dvcm_alpha)
        dvcm_xv = out / "case_c_dvcm_legacy_equiv_xv_xt_v0_6_2.png"
        _plot_xt_contour(
            dvcm_xv,
            dvcm_snapshot,
            dvcm_snapshot.xv,
            ylabel="equivalent vapor mass fraction proxy [-]",
            title="DVCM equivalent xv proxy x-t map",
        )
        figure_paths.append(dvcm_xv)

        comparison_specs = [
            ("pressure_pa", "pressure [Pa]", "Case C pressure x-t: HEM/HNE/DVCM", "case_c_pressure_xt_hem_hne_dvcm_v0_6_2.png"),
            ("alpha", "void/cavity fraction [-]", "Case C alpha/cavity x-t: HEM/HNE/DVCM", "case_c_alpha_xt_hem_hne_dvcm_v0_6_2.png"),
            ("xv", "xv or equivalent xv proxy [-]", "Case C vapor indicator x-t: HEM/HNE/DVCM", "case_c_xv_xt_hem_hne_dvcm_v0_6_2.png"),
            ("c_m_s", "sound speed or proxy [m/s]", "Case C sound-speed/proxy x-t: HEM/HNE/DVCM", "case_c_sound_speed_xt_hem_hne_dvcm_v0_6_2.png"),
        ]
        for field_name, ylabel, title, fname in comparison_specs:
            path = out / fname
            _plot_comparison_panel(path, panel_snapshots, field_name, ylabel, title)
            figure_paths.append(path)

        overlay = out / "case_c_pipeline_cavity_overlay_dvcm_legacy_v0_6_2.png"
        _plot_pipeline_overlay(
            overlay,
            dvcm_snapshot,
            xv_threshold=cfg.vapor_visibility_xv_threshold,
            alpha_threshold=cfg.vapor_visibility_alpha_threshold,
        )
        figure_paths.append(overlay)
        onset = out / "case_c_vapor_cavity_onset_hem_hne_dvcm_v0_6_2.png"
        _plot_vapor_onset(
            onset,
            panel_snapshots,
            xv_threshold=cfg.vapor_visibility_xv_threshold,
            alpha_threshold=cfg.vapor_visibility_alpha_threshold,
        )
        figure_paths.append(onset)

    history_csv = out / "case_c_dvcm_comparison_history_v0_6_2.csv"
    fields_csv = out / "case_c_dvcm_comparison_xt_fields_v0_6_2.csv"
    summary_csv = out / "case_c_dvcm_comparison_summary_v0_6_2.csv"
    metrics_json = out / "case_c_dvcm_comparison_metrics_v0_6_2.json"
    write_csv(history_csv, all_history_rows)
    write_csv(fields_csv, all_field_rows)
    write_csv(summary_csv, summary_rows)

    data_paths = [history_csv, fields_csv, summary_csv, metrics_json]
    metrics: dict[str, object] = {
        "version": cfg.version,
        "config": asdict(cfg),
        "dvcm_config": asdict(dvcm_cfg),
        "base_params": asdict(base),
        "summary_rows": summary_rows,
        "dvcm_summary": dvcm_summary,
        "n_figures": len(figure_paths),
        "n_history_rows": len(all_history_rows),
        "n_field_rows": len(all_field_rows),
        "paths": {
            "report_md": str(out / "case_c_dvcm_legacy_comparison_report_v0_6_2.md"),
            "history_csv": str(history_csv),
            "fields_csv": str(fields_csv),
            "summary_csv": str(summary_csv),
            "metrics_json": str(metrics_json),
        },
    }
    write_json(metrics_json, metrics)
    _write_report(
        out / "case_c_dvcm_legacy_comparison_report_v0_6_2.md",
        cfg=cfg,
        dvcm_cfg=dvcm_cfg,
        base=base,
        summary_rows=summary_rows,
        figure_paths=figure_paths,
        data_paths=data_paths,
    )
    return metrics
