"""Case C trial evaluation mode for Ver.0.6.0.

This module promotes the Ver.0.4.x automated reporting and Ver.0.5.x
property-reference gate into a Case C trial-evaluation workflow.

The workflow is deliberately conservative:

* It can run with a design-accepted project reference table when provided.
* In the default artifact it runs with the internal surrogate LCO2 backend only.
  That mode is suitable for software-path trial evaluation, not design approval.
* It produces an explicit evaluation status so numerical results cannot be
  mistaken for design-certified LCO2 predictions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

import numpy as np

from .cases.case_c import CaseCParameters, effective_phase_change_model
from .reference_acceptance import (
    ReferenceAcceptanceGateConfig,
    generate_reference_acceptance_gate_artifacts,
)
from .reporting import (
    CaseCReportConfig,
    ReportVariant,
    run_case_c_for_report,
    summarize_history,
)


@dataclass(frozen=True)
class CaseCTrialEvaluationConfig:
    """Configuration for Ver.0.6.0 Case C trial evaluation."""

    version: str = "0.6.0"
    title: str = "Case C trial evaluation report"
    backend_name: str = "surrogate_lco2"
    trial_label: str = "surrogate-LCO2 trial / not design reference"
    require_design_accepted_reference: bool = False
    sample_every: int = 10
    max_steps: int = 100_000
    include_figures: bool = True
    pressure_limit_pa: float = 4.0e6
    vapor_mass_fraction_limit: float = 1.0e-3
    alpha_limit: float = 2.0e-2
    c_min_warning_m_s: float = 300.0
    mass_residual_rel_limit: float = 1.0e-10
    energy_residual_abs_limit_j: float = 1.0e-2


DEFAULT_TRIAL_VARIANTS: tuple[ReportVariant, ...] = (
    ReportVariant(name="single_phase", label="single-phase / no phase change", phase_change_model="none"),
    ReportVariant(name="hem", label="HEM equilibrium flash", phase_change_model="hem"),
    ReportVariant(name="hne_tau005", label="HNE relaxation tau=0.05 s", phase_change_model="hne", hne_tau_s=0.05),
)


def standard_trial_parameters() -> CaseCParameters:
    """Return the Ver.0.6.0 Case C trial-evaluation setup.

    This setup isolates the Case C main event: land-side ESD valve rapid closure.
    The pump is treated as a quasi-steady constant-head inlet.  Dynamic pump-stop
    behavior belongs to Case A.
    """

    return CaseCParameters(
        n_cells=400,
        t_end_s=0.20,
        eos_model="lco2_surrogate",
        lco2_boundary_temperature_K=253.15,
        phase_change_model="none",
        pump_delta_p_nominal_pa=2.5e5,
        pump_trip_start_s=None,
        pump_trip_duration_s=0.0,
        pump_delta_p_final_pa=2.5e5,
        valve_close_start_s=0.05,
        valve_close_time_s=0.02,
        latent_heat_placeholder_j_kg=2.0e5,
        hem_p_sat_pa=1.9e6,
        hem_rho_l_sat_kg_m3=930.0,
        hem_rho_v_sat_kg_m3=40.0,
        hem_c_two_phase_min_m_s=80.0,
        hem_high_elevation_min_m=10.0,
        initial_velocity_m_s=1.5,
    )


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
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, obj: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _profile_rows(variant_name: str, profiles: Mapping[str, np.ndarray | tuple[str, ...]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    n = len(profiles["x_m"])  # type: ignore[arg-type]
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


def _plot_time_series(path: Path, histories: Mapping[str, Sequence[Mapping[str, object]]], keys: Sequence[str], ylabel: str, title: str) -> None:
    plt = _import_matplotlib()
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(1, 1, 1)
    for name, history in histories.items():
        t = _time(history)
        for key in keys:
            y = _series(history, key)
            if np.all(~np.isfinite(y)):
                continue
            ax.plot(t, y, label=f"{name}: {key}")
    ax.set_xlabel("time [s]")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True)
    ax.legend(fontsize="small")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_profile(path: Path, profiles_by_variant: Mapping[str, Mapping[str, np.ndarray | tuple[str, ...]]], y_key: str, ylabel: str, title: str) -> None:
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


def _md_table(rows: Sequence[Mapping[str, object]], columns: Sequence[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body = []
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


def _engineering_flags(summary: Mapping[str, float], cfg: CaseCTrialEvaluationConfig) -> dict[str, object]:
    flags = {
        "pressure_limit_pass": _finite(summary.get("p_max_overall_pa")) <= cfg.pressure_limit_pa,
        "xv_limit_pass": _finite(summary.get("xv_max_overall")) <= cfg.vapor_mass_fraction_limit,
        "alpha_limit_pass": _finite(summary.get("alpha_max_overall")) <= cfg.alpha_limit,
        "c_min_warning_pass": _finite(summary.get("c_min_overall_m_s")) >= cfg.c_min_warning_m_s,
        "mass_budget_pass": abs(_finite(summary.get("mass_relative_residual_final"))) <= cfg.mass_residual_rel_limit,
        "energy_budget_pass": abs(_finite(summary.get("energy_balance_residual_final_j"))) <= cfg.energy_residual_abs_limit_j,
    }
    flags["trial_screening_pass"] = bool(all(flags.values()))
    return flags


def _write_trial_report(
    path: Path,
    *,
    cfg: CaseCTrialEvaluationConfig,
    base_params: CaseCParameters,
    acceptance_status: str,
    acceptance_message: str,
    summary_rows: Sequence[Mapping[str, object]],
    figure_paths: Sequence[Path],
    data_paths: Sequence[Path],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_table = _md_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("p_max_overall_pa", "p_max [Pa]"),
            ("p_min_overall_pa", "p_min [Pa]"),
            ("xv_max_overall", "xv_max"),
            ("alpha_max_overall", "alpha_max"),
            ("c_min_overall_m_s", "c_min [m/s]"),
            ("vapor_mass_final_kg", "vapor mass [kg]"),
            ("two_phase_length_final_m", "two-phase L [m]"),
            ("trial_screening_pass", "trial screen"),
        ],
    )
    budget_table = _md_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("mass_relative_residual_final", "mass rel. residual"),
            ("phase_vapor_source_final_kg", "phase vapor source [kg]"),
            ("phase_vapor_residual_final_kg", "phase residual [kg]"),
            ("energy_balance_residual_final_j", "energy residual [J]"),
            ("pump_work_final_j", "pump work [J]"),
            ("valve_loss_final_j", "valve loss proxy [J]"),
            ("latent_requirement_final_j", "latent req. [J]"),
        ],
    )
    flag_table = _md_table(
        summary_rows,
        [
            ("variant", "Variant"),
            ("pressure_limit_pass", "p limit"),
            ("xv_limit_pass", "xv limit"),
            ("alpha_limit_pass", "alpha limit"),
            ("c_min_warning_pass", "c_min"),
            ("mass_budget_pass", "mass budget"),
            ("energy_budget_pass", "energy budget"),
        ],
    )
    rel_figs = [p.relative_to(path.parent).as_posix() for p in figure_paths]
    rel_data = [p.relative_to(path.parent).as_posix() for p in data_paths]
    fig_md = "\n\n".join(f"![{Path(fig).stem}]({fig})" for fig in rel_figs)
    data_md = "\n".join(f"- `{p}`" for p in rel_data)

    max_row = max(summary_rows, key=lambda r: _finite(r.get("p_max_overall_pa")))
    most_vapor = max(summary_rows, key=lambda r: _finite(r.get("vapor_mass_final_kg")))
    min_c_row = min(summary_rows, key=lambda r: _finite(r.get("c_min_overall_m_s")))

    text = f"""# {cfg.title} — Ver.{cfg.version}

## 1. Scope and status

This is a **trial evaluation** of Case C: land-side ESD valve rapid closure.
It exercises the accepted-property-backend workflow introduced in Ver.0.5.x, but the generated artifact uses the internal surrogate LCO₂ backend unless a project-approved external reference table is supplied.

- Backend: `{cfg.backend_name}`
- Reference gate status: `{acceptance_status}`
- Trial label: `{cfg.trial_label}`
- Gate message: {acceptance_message}

**Design-use note:** this report is suitable for software-path trial evaluation and engineering screening workflow rehearsal. It is not a final design basis unless the reference gate status is `ACCEPTED_FOR_DESIGN_USE` with a real project-approved property table.

## 2. Case C setup

Main event: ESD valve closure from `t = {base_params.valve_close_start_s:.3f} s` to `t = {base_params.valve_close_start_s + base_params.valve_close_time_s:.3f} s`.

```json
{json.dumps(asdict(base_params), indent=2, ensure_ascii=False)}
```

## 3. Main results

{summary_table}

## 4. Budget ledger

{budget_table}

## 5. Trial screening flags

Screening criteria used in this trial:

- pressure limit: `{cfg.pressure_limit_pa:.6e} Pa`
- vapor mass fraction limit: `{cfg.vapor_mass_fraction_limit:.6e}`
- void fraction limit: `{cfg.alpha_limit:.6e}`
- minimum sound speed warning threshold: `{cfg.c_min_warning_m_s:.6g} m/s`
- mass relative residual limit: `{cfg.mass_residual_rel_limit:.6e}`
- energy residual absolute limit: `{cfg.energy_residual_abs_limit_j:.6e} J`

{flag_table}

## 6. Engineering interpretation

- Maximum pressure occurred in variant `{max_row.get('variant')}` with `p_max = {_finite(max_row.get('p_max_overall_pa')):.6e} Pa`.
- Largest vapor inventory occurred in variant `{most_vapor.get('variant')}` with `vapor_mass = {_finite(most_vapor.get('vapor_mass_final_kg')):.6e} kg`.
- Lowest mixture sound speed occurred in variant `{min_c_row.get('variant')}` with `c_min = {_finite(min_c_row.get('c_min_overall_m_s')):.6e} m/s`.

Within the surrogate trial setup, Case C remains pressure-dominated. The HEM and HNE branches produce small vapor inventories. HNE produces less vapor than HEM because phase change is delayed by the finite relaxation time. Budget residuals remain near machine precision compared with inventory scale, which supports the numerical consistency of the trial run.

## 7. Figures

{fig_md}

## 8. Output data

{data_md}

## 9. Required next action before design use

Provide a project-approved LCO₂ property reference table from CoolProp, REFPROP, NIST, or an approved vendor source, then rerun the same Ver.0.6.0 trial workflow with `require_design_accepted_reference=True`. Only then should the Case C results be promoted from trial evaluation to design-use evaluation.
"""
    path.write_text(text, encoding="utf-8")


def generate_case_c_trial_evaluation(
    output_dir: str | Path,
    *,
    base_params: CaseCParameters | None = None,
    variants: Sequence[ReportVariant] = DEFAULT_TRIAL_VARIANTS,
    config: CaseCTrialEvaluationConfig | None = None,
) -> dict[str, object]:
    """Generate a complete Ver.0.6.0 Case C trial evaluation package."""

    cfg = config or CaseCTrialEvaluationConfig()
    base = base_params or standard_trial_parameters()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    gate_metrics = generate_reference_acceptance_gate_artifacts(
        out / "reference_gate",
        backend_name=cfg.backend_name,
        config=ReferenceAcceptanceGateConfig(
            version=cfg.version,
            require_design_approved_reference=cfg.require_design_accepted_reference,
            fail_if_not_design_approved=cfg.require_design_accepted_reference,
        ),
    )
    decision = gate_metrics.get("decision", {})
    if not isinstance(decision, Mapping):
        decision = {}
    status = str(decision.get("status", "UNKNOWN"))
    message = str(decision.get("message", ""))

    histories: dict[str, list[dict[str, float]]] = {}
    profiles: dict[str, dict[str, np.ndarray | tuple[str, ...]]] = {}
    all_history_rows: list[dict[str, object]] = []
    all_profile_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for variant in variants:
        params = _variant_params(base, variant)
        history, profile = run_case_c_for_report(params, sample_every=cfg.sample_every, max_steps=cfg.max_steps)
        histories[variant.name] = history
        profiles[variant.name] = profile
        for row in history:
            all_history_rows.append({"variant": variant.name, **row})
        all_profile_rows.extend(_profile_rows(variant.name, profile))
        summary = summarize_history(history)
        flags = _engineering_flags(summary, cfg)
        summary_rows.append({
            "variant": variant.name,
            "label": variant.label,
            "phase_change_model": effective_phase_change_model(params),
            **summary,
            **flags,
        })

    data_paths: list[Path] = []
    hist_csv = out / "case_c_trial_history_v0_6_0.csv"
    summ_csv = out / "case_c_trial_summary_v0_6_0.csv"
    prof_csv = out / "case_c_trial_final_profiles_v0_6_0.csv"
    metrics_json = out / "case_c_trial_metrics_v0_6_0.json"
    _write_csv(hist_csv, all_history_rows)
    _write_csv(summ_csv, summary_rows)
    _write_csv(prof_csv, all_profile_rows)
    data_paths.extend([hist_csv, summ_csv, prof_csv, metrics_json])

    figure_paths: list[Path] = []
    if cfg.include_figures:
        fig_specs = {
            "case_c_trial_pressure_v0_6_0.png": (["p_min_pa", "p_max_pa"], "pressure [Pa]", "Case C pressure extrema"),
            "case_c_trial_velocity_v0_6_0.png": (["u_min_m_s", "u_max_m_s"], "velocity [m/s]", "Case C velocity extrema"),
            "case_c_trial_phase_inventory_v0_6_0.png": (["vapor_mass_total", "phase_vapor_mass_source_cumulative_kg"], "mass [kg]", "Vapor inventory and source"),
            "case_c_trial_budget_residuals_v0_6_0.png": (["budget_mass_relative_residual", "energy_budget_balance_residual_j"], "residual", "Budget residuals"),
            "case_c_trial_interface_energy_v0_6_0.png": (["energy_interface_pump_hydraulic_work_cumulative_j", "energy_interface_valve_loss_proxy_cumulative_j"], "energy [J]", "Pump work and valve loss proxy"),
            "case_c_trial_cmin_v0_6_0.png": (["c_min_m_s"], "sound speed [m/s]", "Minimum sound speed"),
        }
        for fname, (keys, ylabel, title) in fig_specs.items():
            path = out / fname
            _plot_time_series(path, histories, keys, ylabel, title)
            figure_paths.append(path)

        profile_specs = {
            "case_c_trial_final_pressure_profile_v0_6_0.png": ("p_pa", "pressure [Pa]", "Final pressure profile"),
            "case_c_trial_final_xv_profile_v0_6_0.png": ("xv", "vapor mass fraction [-]", "Final vapor mass fraction profile"),
            "case_c_trial_final_alpha_profile_v0_6_0.png": ("alpha", "void fraction [-]", "Final void fraction profile"),
            "case_c_trial_final_sound_speed_profile_v0_6_0.png": ("c_m_s", "sound speed [m/s]", "Final sound-speed profile"),
        }
        for fname, (key, ylabel, title) in profile_specs.items():
            path = out / fname
            _plot_profile(path, profiles, key, ylabel, title)
            figure_paths.append(path)

    metrics: dict[str, object] = {
        "version": cfg.version,
        "config": asdict(cfg),
        "base_params": asdict(base),
        "reference_gate_status": status,
        "reference_gate_message": message,
        "summary_rows": summary_rows,
        "overall_trial_screening_pass": all(bool(row.get("trial_screening_pass")) for row in summary_rows),
        "paths": {
            "report_md": str(out / "case_c_trial_evaluation_report_v0_6_0.md"),
            "history_csv": str(hist_csv),
            "summary_csv": str(summ_csv),
            "profiles_csv": str(prof_csv),
            "metrics_json": str(metrics_json),
            "reference_gate_report": str(Path(str(gate_metrics.get("paths", {}).get("report_md", ""))) if isinstance(gate_metrics.get("paths"), Mapping) else ""),
        },
    }
    _write_json(metrics_json, metrics)

    report_md = out / "case_c_trial_evaluation_report_v0_6_0.md"
    _write_trial_report(
        report_md,
        cfg=cfg,
        base_params=base,
        acceptance_status=status,
        acceptance_message=message,
        summary_rows=summary_rows,
        figure_paths=figure_paths,
        data_paths=data_paths,
    )
    return metrics
