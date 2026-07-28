"""Verification-only 0-D near-saturation acoustic-continuity diagnostic.

This module intentionally does not import or execute FVM transport, boundaries,
Rusanov fluxes, source terms, or CFL logic.  It exercises the existing guarded
pure-CO2 equilibrium acoustic closure without changing its formula or settings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from .hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedError,
    estimate_coolprop_equilibrium_sound_speed,
)
from .hem_phase_classification import evaluate_coolprop_hem_phase_state

PRESSURES_PA = (2.0e6, 3.0e6, 4.0e6)
SUBCOOLING_K = (5.0, 1.0, 0.1, 0.01)
QUALITIES = (0.0, 1.0e-12, 1.0e-10, 1.0e-8, 1.0e-6, 1.0e-4, 1.0e-2)
PERTURBATIONS = (0.0, -1.0e-10, 1.0e-10, -1.0e-8, 1.0e-8, -1.0e-6, 1.0e-6)
PR79_REFERENCE = {
    "accepted_liquid_c_eq_m_s": 461.25669095385655,
    "raw_micro_quality_c_eq_m_s": 43.22308393386989,
    "raw_pressure_pa": 4273927.110515705,
    "raw_q_eq": 9.672588429198319e-9,
}
APPROVAL_BOUNDARY = {
    "Gate_5_execution_complete": False,
    "near_saturation_acoustic_continuity_approved": False,
    "two_phase_acoustic_accuracy_band_approved": False,
    "post_crossing_propagation_approved": False,
    "Gate_P2_passed": False,
    "physical_validation": False,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}


@dataclass(frozen=True)
class StateRecord:
    pressure_pa: float
    saturation_temperature_K: float
    source_state_definition: str
    source_coordinate: float
    rho_kg_m3: float
    e_j_kg: float
    h_j_kg: float
    s_j_kg_K: float
    temperature_K: float
    raw_phase: str
    normalized_phase: str
    scope_status: str
    quality: float | None
    void_fraction: float | None
    acoustic_status: str
    acoustic_failure_category: str
    acoustic_failure_reason: str
    c_eq_m_s: float | None
    c_eq_squared_m2_s2: float | None
    dp_drho_at_e: float | None
    dp_de_at_rho: float | None
    density_term_m2_s2: float | None
    energy_term_m2_s2: float | None
    density_step_kg_m3: float | None
    energy_step_j_kg: float | None
    density_step_halvings: int | None
    energy_step_halvings: int | None
    nearest_liquid_reference_c_eq_m_s: float | None
    sound_speed_ratio_to_nearest_liquid: float | None
    saturation_side_coordinate: str
    saturation_margin_K: float | None
    coolprop_call_status: str


@dataclass(frozen=True)
class PerturbationRecord:
    pressure_pa: float
    base_source_state_definition: str
    base_source_coordinate: float
    delta_rho_relative: float
    delta_e_relative: float
    rho_kg_m3: float
    e_j_kg: float
    phase_status: str
    normalized_phase: str
    scope_status: str
    quality: float | None
    void_fraction: float | None
    acoustic_status: str
    acoustic_failure_category: str
    acoustic_failure_reason: str
    c_eq_m_s: float | None
    c_eq_relative_change: float | None
    base_classification_changed: bool


def _props_si():
    from CoolProp.CoolProp import PropsSI  # type: ignore
    return PropsSI


def _coolprop_version() -> str:
    import CoolProp  # type: ignore
    return str(CoolProp.__version__)


def _scalar(value: object) -> float:
    result = float(np.asarray(value, dtype=float).reshape(-1)[0])
    if not np.isfinite(result):
        raise ValueError("non-finite property value")
    return result


def _phase_metadata(rho: float, e: float) -> dict[str, object]:
    state = evaluate_coolprop_hem_phase_state(
        np.asarray([rho], dtype=float), np.asarray([e], dtype=float)
    )
    def optional(name: str) -> float | None:
        values = np.asarray(getattr(state, name), dtype=float)
        value = float(values[0])
        return value if np.isfinite(value) else None
    raw = getattr(state, "raw_phase", np.asarray([""]))
    return {
        "pressure_pa": float(np.asarray(state.p, dtype=float)[0]),
        "temperature_K": float(np.asarray(state.T, dtype=float)[0]),
        "raw_phase": str(np.asarray(raw).astype(str)[0]),
        "normalized_phase": str(np.asarray(state.phase_class).astype(str)[0]),
        "scope_status": str(np.asarray(state.scope_status).astype(str)[0]),
        "quality": optional("quality"),
        "void_fraction": optional("alpha"),
    }


def _failure_category(reason: str) -> str:
    text = reason.lower()
    if "no valid central" in text or "phase" in text:
        return "PHASE_PRESERVING_STENCIL_REFUSED"
    if "outside the supported" in text or "scope" in text:
        return "OUTSIDE_SUPPORTED_SCOPE"
    if "non-positive" in text or "not finite" in text:
        return "NONPHYSICAL_ACOUSTIC_RESULT"
    return "PROPERTY_OR_ACOUSTIC_EVALUATION_FAILURE"


def _state_from_pt(pressure: float, temperature: float) -> tuple[float, float, float, float]:
    props = _props_si()
    return tuple(
        _scalar(props(name, "P", pressure, "T", temperature, "CO2"))
        for name in ("Dmass", "Umass", "Hmass", "Smass")
    )


def _state_from_pq(pressure: float, quality: float) -> tuple[float, float, float, float, float]:
    props = _props_si()
    tsat = _scalar(props("T", "P", pressure, "Q", 0.0, "CO2"))
    values = tuple(
        _scalar(props(name, "P", pressure, "Q", quality, "CO2"))
        for name in ("Dmass", "Umass", "Hmass", "Smass")
    )
    return (tsat, *values)


def _evaluate_state(
    pressure: float,
    source: str,
    coordinate: float,
    rho: float,
    e: float,
    h: float,
    s: float,
    temperature: float,
    tsat: float,
    nearest_liquid: float | None,
) -> StateRecord:
    meta: dict[str, object] = {}
    try:
        meta = _phase_metadata(rho, e)
        coolprop_status = "SUCCESS"
    except Exception as exc:
        return StateRecord(
            pressure, tsat, source, coordinate, rho, e, h, s, temperature,
            "", "", "", None, None, "FAILURE", "PROPERTY_FAILURE",
            f"{type(exc).__name__}: {exc}", None, None, None, None, None, None,
            None, None, None, None, nearest_liquid, None,
            "LIQUID_SIDE" if source == "PT_SUBCOOLED" else "SATURATION_OR_TWO_PHASE",
            tsat - temperature if source == "PT_SUBCOOLED" else 0.0,
            "FAILURE",
        )
    try:
        estimate = estimate_coolprop_equilibrium_sound_speed(rho, e)
        acoustic_status = "SUCCESS"
        failure_category = ""
        failure_reason = ""
        values = (
            estimate.sound_speed_m_s,
            estimate.sound_speed_squared_m2_s2,
            estimate.dp_drho_at_e,
            estimate.dp_de_at_rho,
            estimate.density_term_m2_s2,
            estimate.energy_term_m2_s2,
            estimate.density_step_kg_m3,
            estimate.energy_step_j_kg,
            estimate.density_step_halvings,
            estimate.energy_step_halvings,
        )
    except HEMEquilibriumSoundSpeedError as exc:
        acoustic_status = "REFUSED" if coordinate == 0.0 and source == "PQ" else "FAILURE"
        failure_reason = f"{type(exc).__name__}: {exc}"
        failure_category = _failure_category(failure_reason)
        values = (None,) * 10
    c_eq = values[0]
    ratio = None if c_eq is None or nearest_liquid is None else c_eq / nearest_liquid
    return StateRecord(
        pressure, tsat, source, coordinate, rho, e, h, s, temperature,
        str(meta["raw_phase"]), str(meta["normalized_phase"]), str(meta["scope_status"]),
        meta["quality"], meta["void_fraction"], acoustic_status,
        failure_category, failure_reason, *values, nearest_liquid, ratio,
        "LIQUID_SIDE" if source == "PT_SUBCOOLED" else "SATURATION_OR_TWO_PHASE",
        tsat - temperature if source == "PT_SUBCOOLED" else 0.0,
        coolprop_status,
    )


def build_state_records() -> list[StateRecord]:
    records: list[StateRecord] = []
    for pressure in PRESSURES_PA:
        tsat, *_ = _state_from_pq(pressure, 0.0)
        liquid_rows: list[StateRecord] = []
        for subcooling in SUBCOOLING_K:
            temperature = tsat - subcooling
            rho, e, h, s = _state_from_pt(pressure, temperature)
            row = _evaluate_state(
                pressure, "PT_SUBCOOLED", subcooling, rho, e, h, s,
                temperature, tsat, None,
            )
            liquid_rows.append(row)
        nearest = next(
            (row.c_eq_m_s for row in reversed(liquid_rows) if row.c_eq_m_s is not None),
            None,
        )
        records.extend(
            StateRecord(**{**asdict(row), "nearest_liquid_reference_c_eq_m_s": nearest,
                           "sound_speed_ratio_to_nearest_liquid":
                           None if row.c_eq_m_s is None or nearest is None else row.c_eq_m_s / nearest})
            for row in liquid_rows
        )
        for quality in QUALITIES:
            tsat, rho, e, h, s = _state_from_pq(pressure, quality)
            records.append(_evaluate_state(
                pressure, "PQ", quality, rho, e, h, s, tsat, tsat, nearest
            ))
    return records


def build_perturbation_records(states: Iterable[StateRecord]) -> list[PerturbationRecord]:
    selected = [
        row for row in states
        if (row.source_state_definition == "PT_SUBCOOLED" and row.source_coordinate == 0.01)
        or (row.source_state_definition == "PQ" and row.source_coordinate in (1.0e-10, 1.0e-8, 1.0e-6))
    ]
    output: list[PerturbationRecord] = []
    for base in selected:
        for drho in PERTURBATIONS:
            for de in PERTURBATIONS:
                rho = base.rho_kg_m3 * (1.0 + drho)
                e = base.e_j_kg * (1.0 + de)
                try:
                    meta = _phase_metadata(rho, e)
                    phase_status = "SUCCESS"
                    normalized = str(meta["normalized_phase"])
                    scope = str(meta["scope_status"])
                    quality = meta["quality"]
                    alpha = meta["void_fraction"]
                except Exception as exc:
                    phase_status = f"FAILURE: {type(exc).__name__}: {exc}"
                    normalized, scope, quality, alpha = "", "", None, None
                try:
                    estimate = estimate_coolprop_equilibrium_sound_speed(rho, e)
                    acoustic_status = "SUCCESS"
                    category = reason = ""
                    c_eq = estimate.sound_speed_m_s
                    rel = None if base.c_eq_m_s is None else c_eq / base.c_eq_m_s - 1.0
                except Exception as exc:
                    acoustic_status = "FAILURE"
                    reason = f"{type(exc).__name__}: {exc}"
                    category = _failure_category(reason)
                    c_eq = rel = None
                output.append(PerturbationRecord(
                    base.pressure_pa, base.source_state_definition,
                    base.source_coordinate, drho, de, rho, e, phase_status,
                    normalized, scope, quality, alpha, acoustic_status,
                    category, reason, c_eq, rel,
                    bool(normalized and normalized != base.normalized_phase),
                ))
    return output


def _git_provenance() -> dict[str, object]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""
    return {
        "source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run("git", "status", "--porcelain=v1", "--untracked-files=all"),
        "property_backend_version": _coolprop_version(),
        "python_version": os.sys.version,
    }


def _classify(states: list[StateRecord], perturbations: list[PerturbationRecord]) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    rationale: list[str] = []
    two_phase = [r for r in states if r.source_state_definition == "PQ" and r.source_coordinate > 0 and r.c_eq_m_s]
    endpoint_refused = all(
        r.acoustic_status == "REFUSED" for r in states
        if r.source_state_definition == "PQ" and r.source_coordinate == 0.0
    )
    changed = [r for r in perturbations if r.base_classification_changed]
    failed = [r for r in perturbations if r.acoustic_status != "SUCCESS"]
    if endpoint_refused and two_phase:
        labels.append("FINITE_JUMP_MODEL_CONSISTENT")
        rationale.append("The exact q=0 endpoint is retained and refused by the unchanged phase-preserving central stencil, while open-two-phase states can be evaluated.")
    ratios = [r.sound_speed_ratio_to_nearest_liquid for r in two_phase if r.sound_speed_ratio_to_nearest_liquid is not None]
    if ratios and min(ratios) < 0.5:
        labels.append("NEAR_SATURATION_PROPERTY_SENSITIVE")
        rationale.append("Open-two-phase sound speed differs materially from the nearest 0.01 K subcooled-liquid reference.")
    if changed:
        labels.append("PHASE_CLASSIFIER_SENSITIVE")
        rationale.append(f"{len(changed)} fixed perturbations changed the normalized phase classification.")
    if failed:
        labels.append("ACOUSTIC_REVIEW_INCONCLUSIVE")
        rationale.append(f"{len(failed)} perturbations did not yield a successful guarded acoustic estimate and remain retained as evidence.")
    if not labels:
        labels.append("ACOUSTIC_REVIEW_INCONCLUSIVE")
        rationale.append("The fixed grid did not support a stronger permitted initial classification.")
    return labels, rationale


def _write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def _make_figures(output_dir: Path, states: list[StateRecord], perturbations: list[PerturbationRecord]) -> list[str]:
    import matplotlib.pyplot as plt
    figures: list[str] = []
    for name, x_key, subset in (
        ("sound_speed_vs_quality.png", "source_coordinate", [r for r in states if r.source_state_definition == "PQ" and r.source_coordinate > 0]),
        ("sound_speed_vs_saturation_approach.png", "source_coordinate", [r for r in states if r.source_state_definition == "PT_SUBCOOLED"]),
    ):
        fig, ax = plt.subplots()
        for pressure in PRESSURES_PA:
            rows = [r for r in subset if r.pressure_pa == pressure and r.c_eq_m_s is not None]
            ax.plot([getattr(r, x_key) for r in rows], [r.c_eq_m_s for r in rows], marker="o", label=f"{pressure/1e6:g} MPa")
        ax.set_xscale("log")
        ax.set_xlabel("quality" if "quality" in name else "subcooling [K]")
        ax.set_ylabel("c_eq [m/s]")
        ax.grid(True)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / name, dpi=160)
        plt.close(fig)
        figures.append(name)
    fig, ax = plt.subplots()
    rows = [r for r in perturbations if r.c_eq_relative_change is not None]
    ax.scatter([r.delta_rho_relative for r in rows], [r.c_eq_relative_change for r in rows], s=10)
    ax.set_xlabel("relative density perturbation")
    ax.set_ylabel("relative c_eq change")
    ax.grid(True)
    fig.tight_layout()
    name = "perturbation_sensitivity.png"
    fig.savefig(output_dir / name, dpi=160)
    plt.close(fig)
    figures.append(name)
    return figures


def execute(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    states = build_state_records()
    perturbations = build_perturbation_records(states)
    figures = _make_figures(output_dir, states, perturbations)
    labels, rationale = _classify(states, perturbations)
    summary = {
        "schema_version": "stage7_gate5_near_saturation_acoustic_continuity_v1",
        "scope": "verification_only_0d",
        "immutable_contract": {
            "fluid": "CO2", "backend": "CoolProp", "version": "8.0.0",
            "pressures_pa": list(PRESSURES_PA), "subcooling_K": list(SUBCOOLING_K),
            "qualities": list(QUALITIES), "perturbations": list(PERTURBATIONS),
            "fvm_used": False, "boundary_used": False, "rusanov_used": False,
            "cfl_used": False, "sound_speed_formula_changed": False,
        },
        "state_record_count": len(states),
        "perturbation_record_count": len(perturbations),
        "successful_acoustic_record_count": sum(r.acoustic_status == "SUCCESS" for r in states),
        "failed_or_refused_acoustic_record_count": sum(r.acoustic_status != "SUCCESS" for r in states),
        "initial_evidence_labels": labels,
        "initial_disposition_rationale": rationale,
        "pr79_forensic_comparison": {
            **PR79_REFERENCE,
            "baseline_reclassified": False,
            "diagnostic_only": True,
        },
        "generated_figures": figures,
        "provenance": _git_provenance(),
        **APPROVAL_BOUNDARY,
    }
    _write_csv(output_dir / "state_points.csv", states)
    _write_csv(output_dir / "perturbations.csv", perturbations)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Stage 7 Gate 5 near-saturation acoustic-continuity review",
        "", "## Scope", "",
        "Independent 0-D diagnostic using the unchanged guarded phase-preserving central-difference closure.",
        "FVM, boundaries, Rusanov flux, source terms, CFL, threshold tuning, and production changes are excluded.",
        "", "## Initial disposition", "",
        *(f"- `{label}`" for label in labels), "",
        *(f"- {item}" for item in rationale), "",
        "## PR #79 retained comparison", "",
        f"- accepted liquid c_eq: {PR79_REFERENCE['accepted_liquid_c_eq_m_s']} m/s",
        f"- raw micro-quality c_eq: {PR79_REFERENCE['raw_micro_quality_c_eq_m_s']} m/s",
        f"- raw pressure: {PR79_REFERENCE['raw_pressure_pa']} Pa",
        f"- raw q_eq: {PR79_REFERENCE['raw_q_eq']}",
        "- The PR #79 case is not rerun or reclassified.", "",
        "## Approval boundary", "",
        *(f"- `{key} = false`" for key in APPROVAL_BOUNDARY), "",
    ]
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    digest = hashlib.sha256()
    for path in sorted(output_dir.iterdir()):
        if path.name != "artifact_sha256.txt" and path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    (output_dir / "artifact_sha256.txt").write_text(digest.hexdigest() + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
