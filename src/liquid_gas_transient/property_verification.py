"""Property-backend verification tables for Ver.0.5.1.

This module is deliberately solver-light.  It probes a property backend through
only the public ``RealFluidPropertyBackend`` protocol and produces repeatable
CSV/JSON/PNG/Markdown artifacts.  The goal is not to certify a fluid package; it
is to make backend substitution auditable before the FVM solver is allowed to
use the backend for design-style calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

import numpy as np

from .properties import (
    CoolPropCO2Backend,
    RealFluidPropertyBackend,
    SaturationState,
    SurrogateLCO2PropertyBackend,
    coolprop_available,
)


@dataclass(frozen=True)
class PropertyBackendVerificationConfig:
    """Configuration for property-backend verification tables.

    The default pressure range is intentionally modest and representative of a
    low-temperature dense-transfer toy/surrogate setting.  A true LCO2 design
    table should later be replaced by project-specific validated reference
    points from CoolProp, REFPROP, or certified plant data.
    """

    version: str = "0.5.1"
    pressures_pa: tuple[float, ...] = (1.2e6, 1.5e6, 1.9e6, 2.3e6, 2.8e6)
    quality_points: tuple[float, ...] = (0.0, 0.01, 0.05, 0.1, 0.5, 0.9, 0.99, 1.0)
    mixture_pressures_pa: tuple[float, ...] = (1.9e6,)
    pT_temperature_offsets_K: tuple[float, ...] = (-8.0, -2.0, 0.0, 2.0, 8.0)
    include_optional_coolprop: bool = True
    make_figures: bool = True
    pressure_consistency_abs_tol_pa: float = 1.0e-6
    quality_abs_tol: float = 1.0e-10
    alpha_monotonic_tol: float = 1.0e-12


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if len(rows) == 0:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _to_float(x: object, default: float = math.nan) -> float:
    try:
        y = float(x)  # type: ignore[arg-type]
    except Exception:
        return default
    return y if math.isfinite(y) else default


def _sat_scalar(sat: SaturationState, i: int) -> dict[str, float]:
    return {
        "p_pa": float(np.ravel(sat.p)[i]),
        "T_sat_K": float(np.ravel(sat.T_sat)[i]),
        "rho_l_kg_m3": float(np.ravel(sat.rho_l)[i]),
        "rho_v_kg_m3": float(np.ravel(sat.rho_v)[i]),
        "e_l_j_kg": float(np.ravel(sat.e_l)[i]),
        "e_v_j_kg": float(np.ravel(sat.e_v)[i]),
        "h_lv_j_kg": float(np.ravel(sat.h_lv)[i]),
    }


def saturation_table(backend: RealFluidPropertyBackend, pressures_pa: Sequence[float]) -> list[dict[str, float | str]]:
    """Return a saturation table evaluated through ``backend``."""

    p = np.asarray(pressures_pa, dtype=float)
    sat = backend.saturation_state(p)
    rows: list[dict[str, float | str]] = []
    for i in range(p.size):
        row = _sat_scalar(sat, i)
        row.update(
            {
                "backend": backend.name,
                "rho_l_over_rho_v": row["rho_l_kg_m3"] / row["rho_v_kg_m3"],
                "specific_volume_ratio_v_over_l": row["rho_l_kg_m3"] / row["rho_v_kg_m3"],
            }
        )
        rows.append(row)
    return rows


def mixture_reconstruction_table(
    backend: RealFluidPropertyBackend,
    pressures_pa: Sequence[float],
    quality_points: Sequence[float],
) -> list[dict[str, float | str]]:
    """Check saturated-mixture quality reconstruction from ``rho`` and ``e``.

    For each saturation pressure and target quality ``q``, construct the mixture
    using the homogeneous relations

    ``1/rho = (1-q)/rho_l + q/rho_v`` and ``e = (1-q)e_l + q e_v``.

    The backend is then asked to recover ``quality``, ``alpha``, ``p`` and
    ``sound speed`` from ``rho,e``.  This is the core HEM/HNE thermodynamic
    consistency check used before coupling a backend to Case C.
    """

    rows: list[dict[str, float | str]] = []
    sat = backend.saturation_state(np.asarray(pressures_pa, dtype=float))
    for i in range(np.asarray(pressures_pa).size):
        s = _sat_scalar(sat, i)
        rho_l = s["rho_l_kg_m3"]
        rho_v = s["rho_v_kg_m3"]
        e_l = s["e_l_j_kg"]
        e_v = s["e_v_j_kg"]
        for q_target in quality_points:
            q = float(q_target)
            rho_mix = 1.0 / ((1.0 - q) / rho_l + q / rho_v)
            e_mix = (1.0 - q) * e_l + q * e_v
            state = backend.state_from_rho_e(np.array([rho_mix]), np.array([e_mix]))
            q_eval = float(state.quality[0])
            alpha_eval = float(state.alpha[0])
            p_eval = float(state.p[0])
            rows.append(
                {
                    "backend": backend.name,
                    "p_sat_pa": s["p_pa"],
                    "T_sat_K": s["T_sat_K"],
                    "quality_target": q,
                    "rho_constructed_kg_m3": rho_mix,
                    "e_constructed_j_kg": e_mix,
                    "quality_evaluated": q_eval,
                    "quality_abs_error": abs(q_eval - q),
                    "alpha_evaluated": alpha_eval,
                    "p_evaluated_pa": p_eval,
                    "p_abs_error_pa": abs(p_eval - s["p_pa"]),
                    "c_m_s": float(state.c[0]),
                }
            )
    return rows


def density_pT_table(
    backend: RealFluidPropertyBackend,
    pressures_pa: Sequence[float],
    temperature_offsets_K: Sequence[float],
) -> list[dict[str, float | str]]:
    """Return density from p,T around saturation temperatures."""

    rows: list[dict[str, float | str]] = []
    sat = backend.saturation_state(np.asarray(pressures_pa, dtype=float))
    for i in range(np.asarray(pressures_pa).size):
        s = _sat_scalar(sat, i)
        for dT in temperature_offsets_K:
            T = s["T_sat_K"] + float(dT)
            rho = backend.density_from_pT(np.array([s["p_pa"]]), np.array([T]))
            rows.append(
                {
                    "backend": backend.name,
                    "p_pa": s["p_pa"],
                    "T_sat_K": s["T_sat_K"],
                    "T_K": T,
                    "T_minus_Tsat_K": float(dT),
                    "rho_from_pT_kg_m3": float(rho[0]),
                }
            )
    return rows


def _alpha_monotonic_violation(mixture_rows: Sequence[Mapping[str, object]]) -> float:
    groups: dict[float, list[tuple[float, float]]] = {}
    for row in mixture_rows:
        p = _to_float(row.get("p_sat_pa"))
        q = _to_float(row.get("quality_target"))
        a = _to_float(row.get("alpha_evaluated"))
        groups.setdefault(p, []).append((q, a))
    violation = 0.0
    for pairs in groups.values():
        pairs.sort()
        alphas = np.asarray([a for _, a in pairs], dtype=float)
        if alphas.size > 1:
            violation = max(violation, float(np.max(np.maximum(0.0, -np.diff(alphas)))))
    return violation


def summarize_property_verification(
    backend: RealFluidPropertyBackend,
    sat_rows: Sequence[Mapping[str, object]],
    mixture_rows: Sequence[Mapping[str, object]],
    pT_rows: Sequence[Mapping[str, object]],
    config: PropertyBackendVerificationConfig,
) -> dict[str, float | str | bool]:
    """Return scalar pass/fail metrics for one backend."""

    rho_l_minus_v = [
        _to_float(row.get("rho_l_kg_m3")) - _to_float(row.get("rho_v_kg_m3")) for row in sat_rows
    ]
    h_lv = [_to_float(row.get("h_lv_j_kg")) for row in sat_rows]
    T_sat = np.asarray([_to_float(row.get("T_sat_K")) for row in sat_rows], dtype=float)
    q_err = [_to_float(row.get("quality_abs_error")) for row in mixture_rows]
    p_err = [_to_float(row.get("p_abs_error_pa")) for row in mixture_rows]
    c_vals = [_to_float(row.get("c_m_s")) for row in mixture_rows]
    rho_pT = [_to_float(row.get("rho_from_pT_kg_m3")) for row in pT_rows]
    alpha_violation = _alpha_monotonic_violation(mixture_rows)

    metrics: dict[str, float | str | bool] = {
        "backend": backend.name,
        "n_saturation_points": float(len(sat_rows)),
        "n_mixture_points": float(len(mixture_rows)),
        "n_pT_points": float(len(pT_rows)),
        "rho_l_minus_rho_v_min_kg_m3": float(np.nanmin(rho_l_minus_v)),
        "latent_heat_min_j_kg": float(np.nanmin(h_lv)),
        "T_sat_monotonic_min_diff_K": float(np.nanmin(np.diff(T_sat))) if T_sat.size > 1 else math.inf,
        "quality_reconstruction_max_abs_error": float(np.nanmax(q_err)),
        "mixture_pressure_max_abs_error_pa": float(np.nanmax(p_err)),
        "sound_speed_min_m_s": float(np.nanmin(c_vals)),
        "density_from_pT_min_kg_m3": float(np.nanmin(rho_pT)),
        "alpha_monotonic_max_violation": float(alpha_violation),
    }
    metrics["density_order_pass"] = metrics["rho_l_minus_rho_v_min_kg_m3"] > 0.0
    metrics["latent_heat_positive_pass"] = metrics["latent_heat_min_j_kg"] > 0.0
    metrics["T_sat_monotonic_pass"] = metrics["T_sat_monotonic_min_diff_K"] > 0.0
    metrics["quality_reconstruction_pass"] = (
        metrics["quality_reconstruction_max_abs_error"] <= config.quality_abs_tol
    )
    metrics["mixture_pressure_consistency_pass"] = (
        metrics["mixture_pressure_max_abs_error_pa"] <= config.pressure_consistency_abs_tol_pa
    )
    metrics["sound_speed_positive_pass"] = metrics["sound_speed_min_m_s"] > 0.0
    metrics["density_from_pT_positive_pass"] = metrics["density_from_pT_min_kg_m3"] > 0.0
    metrics["alpha_monotonic_pass"] = metrics["alpha_monotonic_max_violation"] <= config.alpha_monotonic_tol
    pass_keys = [k for k in metrics if k.endswith("_pass")]
    metrics["overall_pass"] = all(bool(metrics[k]) for k in pass_keys)
    return metrics


def _plot_backend_tables(
    out_dir: Path,
    backend_name: str,
    sat_rows: Sequence[Mapping[str, object]],
    mixture_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    import matplotlib.pyplot as plt

    paths: list[str] = []
    p_mpa = np.asarray([_to_float(row.get("p_pa")) / 1.0e6 for row in sat_rows], dtype=float)
    T = np.asarray([_to_float(row.get("T_sat_K")) for row in sat_rows], dtype=float)
    rho_l = np.asarray([_to_float(row.get("rho_l_kg_m3")) for row in sat_rows], dtype=float)
    rho_v = np.asarray([_to_float(row.get("rho_v_kg_m3")) for row in sat_rows], dtype=float)
    h_lv = np.asarray([_to_float(row.get("h_lv_j_kg")) for row in sat_rows], dtype=float)

    fig, ax = plt.subplots()
    ax.plot(p_mpa, T, marker="o")
    ax.set_xlabel("Saturation pressure [MPa]")
    ax.set_ylabel("Saturation temperature [K]")
    ax.set_title(f"{backend_name}: saturation temperature")
    path = out_dir / f"{backend_name}_saturation_temperature_v0_5_1.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(str(path))

    fig, ax = plt.subplots()
    ax.plot(p_mpa, rho_l, marker="o", label="liquid")
    ax.plot(p_mpa, rho_v, marker="s", label="vapor")
    ax.set_xlabel("Saturation pressure [MPa]")
    ax.set_ylabel("Density [kg/m3]")
    ax.set_title(f"{backend_name}: saturation densities")
    ax.legend()
    path = out_dir / f"{backend_name}_saturation_densities_v0_5_1.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(str(path))

    fig, ax = plt.subplots()
    ax.plot(p_mpa, h_lv, marker="o")
    ax.set_xlabel("Saturation pressure [MPa]")
    ax.set_ylabel("Latent heat placeholder / backend value [J/kg]")
    ax.set_title(f"{backend_name}: latent heat")
    path = out_dir / f"{backend_name}_latent_heat_v0_5_1.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(str(path))

    # Quality reconstruction across all pressures.
    q_target = np.asarray([_to_float(row.get("quality_target")) for row in mixture_rows], dtype=float)
    q_eval = np.asarray([_to_float(row.get("quality_evaluated")) for row in mixture_rows], dtype=float)
    alpha = np.asarray([_to_float(row.get("alpha_evaluated")) for row in mixture_rows], dtype=float)
    c = np.asarray([_to_float(row.get("c_m_s")) for row in mixture_rows], dtype=float)

    fig, ax = plt.subplots()
    ax.plot(q_target, q_eval, ".")
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.set_xlabel("Target quality [-]")
    ax.set_ylabel("Evaluated quality [-]")
    ax.set_title(f"{backend_name}: quality reconstruction")
    path = out_dir / f"{backend_name}_quality_reconstruction_v0_5_1.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(str(path))

    fig, ax = plt.subplots()
    ax.plot(q_target, alpha, ".")
    ax.set_xlabel("Target quality [-]")
    ax.set_ylabel("Void fraction alpha [-]")
    ax.set_title(f"{backend_name}: quality to void fraction")
    path = out_dir / f"{backend_name}_quality_alpha_v0_5_1.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(str(path))

    fig, ax = plt.subplots()
    ax.plot(q_target, c, ".")
    ax.set_xlabel("Target quality [-]")
    ax.set_ylabel("Sound speed [m/s]")
    ax.set_title(f"{backend_name}: sound speed over mixture states")
    path = out_dir / f"{backend_name}_quality_sound_speed_v0_5_1.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(str(path))
    return paths


def _backend_section_markdown(metrics: Mapping[str, object]) -> str:
    status = "PASS" if bool(metrics.get("overall_pass")) else "FAIL"
    return "\n".join(
        [
            f"### {metrics.get('backend')} — {status}",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| saturation points | {int(_to_float(metrics.get('n_saturation_points'), 0.0))} |",
            f"| mixture points | {int(_to_float(metrics.get('n_mixture_points'), 0.0))} |",
            f"| pT points | {int(_to_float(metrics.get('n_pT_points'), 0.0))} |",
            f"| min(rho_l - rho_v) [kg/m3] | {_to_float(metrics.get('rho_l_minus_rho_v_min_kg_m3')):.6e} |",
            f"| min(latent heat) [J/kg] | {_to_float(metrics.get('latent_heat_min_j_kg')):.6e} |",
            f"| min(dT_sat/dp sample diff) [K] | {_to_float(metrics.get('T_sat_monotonic_min_diff_K')):.6e} |",
            f"| max quality abs error | {_to_float(metrics.get('quality_reconstruction_max_abs_error')):.6e} |",
            f"| max mixture pressure abs error [Pa] | {_to_float(metrics.get('mixture_pressure_max_abs_error_pa')):.6e} |",
            f"| min sound speed [m/s] | {_to_float(metrics.get('sound_speed_min_m_s')):.6e} |",
            f"| min density_from_pT [kg/m3] | {_to_float(metrics.get('density_from_pT_min_kg_m3')):.6e} |",
            f"| alpha monotonic max violation | {_to_float(metrics.get('alpha_monotonic_max_violation')):.6e} |",
            "",
        ]
    )


def generate_property_backend_verification(
    output_dir: str | Path,
    *,
    config: PropertyBackendVerificationConfig | None = None,
    backends: Sequence[RealFluidPropertyBackend] | None = None,
) -> dict[str, object]:
    """Generate property-backend verification artifacts.

    Returns a dictionary containing paths and scalar metrics.  The default run
    always verifies the dependency-free surrogate backend.  If CoolProp is
    installed and ``include_optional_coolprop`` is true, the optional CoolProp
    adapter is also probed and reported separately.
    """

    cfg = config or PropertyBackendVerificationConfig()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected: list[RealFluidPropertyBackend]
    if backends is None:
        selected = [SurrogateLCO2PropertyBackend()]
        if cfg.include_optional_coolprop and coolprop_available():
            selected.append(CoolPropCO2Backend())
    else:
        selected = list(backends)

    all_sat: list[dict[str, object]] = []
    all_mix: list[dict[str, object]] = []
    all_pT: list[dict[str, object]] = []
    metrics_by_backend: list[dict[str, object]] = []
    figures: list[str] = []

    for backend in selected:
        sat_rows = saturation_table(backend, cfg.pressures_pa)
        mix_rows = mixture_reconstruction_table(backend, cfg.mixture_pressures_pa, cfg.quality_points)
        pT_rows = density_pT_table(backend, cfg.pressures_pa, cfg.pT_temperature_offsets_K)
        metrics = summarize_property_verification(backend, sat_rows, mix_rows, pT_rows, cfg)
        metrics_by_backend.append(metrics)
        all_sat.extend(sat_rows)
        all_mix.extend(mix_rows)
        all_pT.extend(pT_rows)
        if cfg.make_figures:
            figures.extend(_plot_backend_tables(out_dir, backend.name, sat_rows, mix_rows))

    paths: dict[str, str | list[str]] = {
        "saturation_table_csv": str(out_dir / "property_saturation_table_v0_5_1.csv"),
        "mixture_reconstruction_csv": str(out_dir / "property_mixture_reconstruction_v0_5_1.csv"),
        "density_pT_table_csv": str(out_dir / "property_density_pT_table_v0_5_1.csv"),
        "metrics_json": str(out_dir / "property_backend_verification_metrics_v0_5_1.json"),
        "report_md": str(out_dir / "property_backend_verification_report_v0_5_1.md"),
        "figures": figures,
    }

    _write_csv(Path(paths["saturation_table_csv"]), all_sat)  # type: ignore[arg-type]
    _write_csv(Path(paths["mixture_reconstruction_csv"]), all_mix)  # type: ignore[arg-type]
    _write_csv(Path(paths["density_pT_table_csv"]), all_pT)  # type: ignore[arg-type]

    overall_pass = all(bool(m.get("overall_pass")) for m in metrics_by_backend)
    metrics_payload: dict[str, object] = {
        "version": cfg.version,
        "config": asdict(cfg),
        "coolprop_available": coolprop_available(),
        "backend_count": len(metrics_by_backend),
        "overall_pass": overall_pass,
        "metrics_by_backend": metrics_by_backend,
        "paths": paths,
    }
    _write_json(Path(paths["metrics_json"]), metrics_payload)  # type: ignore[arg-type]

    report_lines = [
        "# Property backend verification report Ver.0.5.1",
        "",
        f"overall_pass: `{str(overall_pass).lower()}`",
        "",
        "## Scope",
        "",
        "This report verifies the property-backend adapter pathway before real-fluid data are used for design-style Case-C runs.",
        "It checks saturation-property ordering, mixture quality reconstruction at configured mixture reference pressures, pressure consistency, pT density positivity, sound-speed positivity, and void-fraction monotonicity.",
        "",
        "The dependency-free surrogate backend is verified by default. Optional CoolProp verification is included only when the package is installed in the execution environment.",
        "",
        "## Backend metrics",
        "",
    ]
    for metrics in metrics_by_backend:
        report_lines.append(_backend_section_markdown(metrics))
    report_lines.extend(
        [
            "## Generated data",
            "",
            f"- Saturation table: `{Path(paths['saturation_table_csv']).name}`",
            f"- Mixture reconstruction table: `{Path(paths['mixture_reconstruction_csv']).name}`",
            f"- Density pT table: `{Path(paths['density_pT_table_csv']).name}`",
            f"- Metrics JSON: `{Path(paths['metrics_json']).name}`",
            "",
            "## Interpretation guardrails",
            "",
            "- A PASS here means that the backend adapter is internally consistent over the sampled table.",
            "- It does not mean that surrogate values are certified LCO2 properties.",
            "- Before design use, the same table should be regenerated with CoolProp/REFPROP or a validated tabular backend and archived as a reference artifact.",
            "",
        ]
    )
    Path(paths["report_md"]).write_text("\n".join(report_lines), encoding="utf-8")  # type: ignore[arg-type]

    return metrics_payload
