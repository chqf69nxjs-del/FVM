"""DVCM legacy comparison helpers for Case C Ver.0.6.2.

This module deliberately implements DVCM as a *legacy comparison / diagnostic*
path, not as the primary physical model for liquefied-gas two-phase transients.

The conservative FVM + HEM/HNE branches carry vapor mass fraction as a state-like
quantity.  Classical DVCM instead represents vapor as discrete cavity volume at
computational nodes once local pressure reaches vapor pressure.  To compare the
old and new viewpoints on the same plots, this module maps a sampled single-phase
Case C field to a DVCM-like cavity-volume proxy:

* pressure is clipped at vapor pressure,
* cavity volume fraction is estimated from saturated-liquid density deficit,
* equivalent vapor mass fraction is reported only as a visualization proxy.

This is enough for review plots and legacy comparison.  It is not a replacement
for a full MOC-DVCM solver with characteristic compatibility equations and nodal
cavity continuity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

import numpy as np

from .visualization import FieldSnapshotSet


@dataclass(frozen=True)
class DVCMLegacyConfig:
    """Configuration for the Ver.0.6.2 legacy DVCM proxy."""

    version: str = "0.6.2"
    vapor_pressure_pa: float = 1.90e6
    saturated_liquid_density_kg_m3: float = 930.0
    saturated_vapor_density_kg_m3: float = 40.0
    pressure_activation_margin_pa: float = 1.0e3
    alpha_visibility_threshold: float = 1.0e-6
    max_alpha_cap: float = 0.20
    cavity_sound_speed_proxy_m_s: float = 750.0
    pipe_area_m2: float = math.pi * 0.30**2 / 4.0


@dataclass(frozen=True)
class DVCMLegacySummary:
    """Summary of a DVCM legacy proxy field."""

    variant: str
    label: str
    p_min_overall_pa: float
    p_max_overall_pa: float
    alpha_max_overall: float
    xv_equiv_max_overall: float
    c_min_overall_m_s: float
    cavity_volume_proxy_max_m3: float
    cavity_volume_proxy_final_m3: float
    cavity_length_max_m: float
    cavity_length_final_m: float
    cavity_present: bool
    first_cavity_time_s: float | None


def _dx_from_snapshot(snapshot: FieldSnapshotSet) -> float:
    if len(snapshot.x_m) < 2:
        return 1.0
    return float(np.nanmedian(np.diff(snapshot.x_m)))


def _equivalent_xv_from_alpha(alpha: np.ndarray, rho_l: float, rho_v: float) -> np.ndarray:
    """Convert cavity volume fraction to a mass-quality proxy.

    Classical DVCM cavity volume is not the same quantity as HEM/HNE vapor mass
    fraction.  This conversion is only for placing DVCM on the existing xv plot.
    """

    denom = alpha * rho_v + (1.0 - alpha) * rho_l
    with np.errstate(divide="ignore", invalid="ignore"):
        xv = np.where(denom > 0.0, alpha * rho_v / denom, 0.0)
    return np.clip(xv, 0.0, 1.0)


def build_dvcm_legacy_snapshot(
    liquid_snapshot: FieldSnapshotSet,
    *,
    config: DVCMLegacyConfig | None = None,
    variant: str = "dvcm_legacy",
    label: str = "DVCM legacy cavity-volume proxy",
) -> FieldSnapshotSet:
    """Build a DVCM-like snapshot from a sampled liquid/FVM field.

    Parameters
    ----------
    liquid_snapshot:
        Usually the single-phase Case C snapshot.  It supplies pressure and
        density histories on the same x--t grid as HEM/HNE.
    config:
        DVCM proxy parameters.

    Returns
    -------
    FieldSnapshotSet
        A field set compatible with the visualization/postprocessor module.
    """

    cfg = config or DVCMLegacyConfig()
    p = np.maximum(liquid_snapshot.pressure_pa, cfg.vapor_pressure_pa)
    pressure_active = liquid_snapshot.pressure_pa <= cfg.vapor_pressure_pa + cfg.pressure_activation_margin_pa
    density_deficit = (cfg.saturated_liquid_density_kg_m3 - liquid_snapshot.rho_kg_m3) / cfg.saturated_liquid_density_kg_m3
    alpha = np.where(pressure_active, density_deficit, 0.0)
    alpha = np.clip(alpha, 0.0, cfg.max_alpha_cap)
    xv_equiv = _equivalent_xv_from_alpha(alpha, cfg.saturated_liquid_density_kg_m3, cfg.saturated_vapor_density_kg_m3)

    # DVCM represents discrete cavities rather than a smooth homogeneous mixture
    # sound-speed field.  Keep the liquid acoustic speed as a proxy so plots do
    # not imply the same continuous two-phase acoustic model as HEM/HNE.
    c_proxy = np.where(alpha > cfg.alpha_visibility_threshold, cfg.cavity_sound_speed_proxy_m_s, liquid_snapshot.c_m_s)

    return FieldSnapshotSet(
        variant=variant,
        label=label,
        phase_change_model="dvcm_legacy",
        x_m=liquid_snapshot.x_m.copy(),
        elevation_m=liquid_snapshot.elevation_m.copy(),
        segment=tuple(liquid_snapshot.segment),
        time_s=liquid_snapshot.time_s.copy(),
        pressure_pa=p,
        velocity_m_s=liquid_snapshot.velocity_m_s.copy(),
        xv=xv_equiv,
        alpha=alpha,
        c_m_s=c_proxy,
        rho_kg_m3=liquid_snapshot.rho_kg_m3.copy(),
    )


def summarize_dvcm_legacy(snapshot: FieldSnapshotSet, *, config: DVCMLegacyConfig | None = None) -> DVCMLegacySummary:
    """Summarize the DVCM legacy proxy snapshot."""

    cfg = config or DVCMLegacyConfig()
    dx = _dx_from_snapshot(snapshot)
    active = snapshot.alpha > cfg.alpha_visibility_threshold
    cavity_volume_t = np.sum(snapshot.alpha, axis=1) * dx * cfg.pipe_area_m2
    cavity_length_t = np.sum(active, axis=1) * dx
    active_any = np.any(active)
    if active_any:
        first_idx = int(np.where(np.any(active, axis=1))[0][0])
        first_time = float(snapshot.time_s[first_idx])
    else:
        first_time = None
    return DVCMLegacySummary(
        variant=snapshot.variant,
        label=snapshot.label,
        p_min_overall_pa=float(np.nanmin(snapshot.pressure_pa)),
        p_max_overall_pa=float(np.nanmax(snapshot.pressure_pa)),
        alpha_max_overall=float(np.nanmax(snapshot.alpha)),
        xv_equiv_max_overall=float(np.nanmax(snapshot.xv)),
        c_min_overall_m_s=float(np.nanmin(snapshot.c_m_s)),
        cavity_volume_proxy_max_m3=float(np.nanmax(cavity_volume_t)),
        cavity_volume_proxy_final_m3=float(cavity_volume_t[-1]),
        cavity_length_max_m=float(np.nanmax(cavity_length_t)),
        cavity_length_final_m=float(cavity_length_t[-1]),
        cavity_present=bool(active_any),
        first_cavity_time_s=first_time,
    )


def dvcm_history_rows(snapshot: FieldSnapshotSet, *, config: DVCMLegacyConfig | None = None) -> list[dict[str, object]]:
    """Return time-history rows for the DVCM proxy."""

    cfg = config or DVCMLegacyConfig()
    dx = _dx_from_snapshot(snapshot)
    rows: list[dict[str, object]] = []
    for it, t in enumerate(snapshot.time_s):
        active = snapshot.alpha[it] > cfg.alpha_visibility_threshold
        cavity_volume = float(np.sum(snapshot.alpha[it]) * dx * cfg.pipe_area_m2)
        rows.append(
            {
                "variant": snapshot.variant,
                "time_s": float(t),
                "p_min_pa": float(np.nanmin(snapshot.pressure_pa[it])),
                "p_max_pa": float(np.nanmax(snapshot.pressure_pa[it])),
                "alpha_max": float(np.nanmax(snapshot.alpha[it])),
                "xv_equiv_max": float(np.nanmax(snapshot.xv[it])),
                "c_min_m_s": float(np.nanmin(snapshot.c_m_s[it])),
                "cavity_volume_proxy_m3": cavity_volume,
                "cavity_length_m": float(np.sum(active) * dx),
                "cavity_cell_count": int(np.sum(active)),
            }
        )
    return rows


def dvcm_field_rows(snapshot: FieldSnapshotSet) -> list[dict[str, object]]:
    """Return long-form x--t field rows for the DVCM proxy."""

    rows: list[dict[str, object]] = []
    for it, t in enumerate(snapshot.time_s):
        for ix, x in enumerate(snapshot.x_m):
            rows.append(
                {
                    "variant": snapshot.variant,
                    "phase_change_model": snapshot.phase_change_model,
                    "time_s": float(t),
                    "cell": ix,
                    "x_m": float(x),
                    "segment": snapshot.segment[ix],
                    "elevation_m": float(snapshot.elevation_m[ix]),
                    "p_pa": float(snapshot.pressure_pa[it, ix]),
                    "u_m_s": float(snapshot.velocity_m_s[it, ix]),
                    "xv_equiv": float(snapshot.xv[it, ix]),
                    "alpha_cavity": float(snapshot.alpha[it, ix]),
                    "c_m_s_proxy": float(snapshot.c_m_s[it, ix]),
                    "rho_kg_m3": float(snapshot.rho_kg_m3[it, ix]),
                }
            )
    return rows


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
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
        writer.writerows(rows)


def write_json(path: Path, obj: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def summary_asdict(summary: DVCMLegacySummary) -> dict[str, object]:
    return asdict(summary)
