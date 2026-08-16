"""P2-A1R audit of transported-quality disequilibrium and front relations.

The P2-A1 solver is re-executed unchanged. This review classifies a closure
interaction that the first report generalized too broadly: finite relaxation
produces signed q_eq-q_transport disequilibrium, and the transported-q evidence
front can both lag and lead the HEM rho/e thermodynamic boundary.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .hne_pipeline_model_form_sensitivity import (
    P2_A1_TAU_CASES,
    analyze_hne_model_form_sensitivity,
)

SCHEMA = "stage7_p2_hne_model_form_sensitivity_a1r_v1"
SOURCE_A1_SHA = "18d78f65c39047bde3bf06ceb61ca90fb6551b36"
ZERO_TOL = 1.0e-18
OUTPUT_FILES = (
    "audit_summary.json",
    "case_disequilibrium.csv",
    "front_relation_history.csv",
    "signed_quality_lag_history.csv",
    "closure_limitations.csv",
    "signed_quality_lag_envelope.png",
    "front_relation_counts.png",
    "operator_report.md",
    "audit_manifest.json",
)
FORMAL_STATUS = {
    "implemented": True,
    "diagnostic_evidence_ready": True,
    "p2_model_form_vertical_slice": True,
    "physical_hne_vertical_slice": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}


class AuditError(RuntimeError):
    pass


def _sha(payload: object) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""
    return {
        "source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def front_relation(thermo: float | None, kinetic: float | None) -> str:
    if thermo is None and kinetic is None:
        return "BOTH_ABSENT"
    if thermo is not None and kinetic is None:
        return "KINETIC_ABSENT_WHILE_THERMODYNAMIC_PRESENT"
    if thermo is None and kinetic is not None:
        return "KINETIC_PRESENT_WHILE_THERMODYNAMIC_ABSENT"
    assert thermo is not None and kinetic is not None
    delta = kinetic - thermo
    if delta > 1.0e-15:
        return "KINETIC_AHEAD"
    if delta < -1.0e-15:
        return "KINETIC_BEHIND"
    return "COINCIDENT"


def behavior_classification(row: dict[str, object]) -> str:
    if bool(row["full_state_matches_hem"]) and float(
        row["maximum_absolute_signed_quality_lag"]
    ) <= ZERO_TOL:
        return "HEM_LIMIT"
    delayed = float(row["onset_delay_s"]) > 1.0e-15
    lagged = int(row["kinetic_absent_count"]) + int(row["kinetic_behind_count"]) > 0
    led = int(row["kinetic_only_count"]) + int(row["kinetic_ahead_count"]) > 0
    if delayed and lagged and led:
        return "RESOLVED_ONSET_DELAY_WITH_MIXED_FRONT_LAG_AND_LEAD"
    if delayed and lagged:
        return "RESOLVED_ONSET_DELAY_WITH_FRONT_LAG"
    if not delayed and led and not lagged:
        return "NO_RESOLVED_ONSET_DELAY_WITH_TRANSIENT_FRONT_LEAD"
    if lagged and led:
        return "MIXED_FRONT_LAG_AND_LEAD"
    if led:
        return "TRANSIENT_FRONT_LEAD"
    if lagged:
        return "TRANSIENT_FRONT_LAG"
    return "QUALITY_DISEQUILIBRIUM_WITH_COINCIDENT_EVIDENCE_FRONT"


def _front_rows(source: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for item in source["time_history"]:
        thermo = item["thermodynamic_phase_front_distance_from_outlet_m"]
        kinetic = item["kinetic_phase_front_distance_from_outlet_m"]
        thermo = None if thermo is None else float(thermo)
        kinetic = None if kinetic is None else float(kinetic)
        rows.append({
            "model_id": item["model_id"],
            "model_family": item["model_family"],
            "tau_s": item["tau_s"],
            "local_step": item["local_step"],
            "absolute_step": item["absolute_step"],
            "time_s": item["time_s"],
            "thermodynamic_front_m": thermo,
            "kinetic_front_m": kinetic,
            "relation": front_relation(thermo, kinetic),
            "thermodynamic_minus_kinetic_m": (
                None if thermo is None or kinetic is None else thermo - kinetic
            ),
            "kinetic_minus_thermodynamic_m": (
                None if thermo is None or kinetic is None else kinetic - thermo
            ),
        })
    return rows


def _lag_rows(source: dict[str, object]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[float]] = {}
    meta: dict[tuple[str, int], dict[str, object]] = {}
    for item in source["cell_history"]:
        key = (str(item["model_id"]), int(item["absolute_step"]))
        grouped.setdefault(key, []).append(float(item["signed_quality_lag"]))
        meta[key] = {
            "model_id": item["model_id"],
            "model_family": item["model_family"],
            "tau_s": item["tau_s"],
            "local_step": item["local_step"],
            "absolute_step": item["absolute_step"],
            "time_s": item["time_s"],
        }
    rows = []
    for key in sorted(grouped, key=lambda x: (x[0], x[1])):
        values = np.asarray(grouped[key], dtype=float)
        if not np.all(np.isfinite(values)):
            raise AuditError("nonfinite signed quality lag")
        positive = int(np.count_nonzero(values > ZERO_TOL))
        negative = int(np.count_nonzero(values < -ZERO_TOL))
        rows.append({
            **meta[key],
            "minimum_signed_quality_lag": float(np.min(values)),
            "maximum_signed_quality_lag": float(np.max(values)),
            "maximum_absolute_signed_quality_lag": float(np.max(np.abs(values))),
            "mean_signed_quality_lag": float(np.mean(values)),
            "positive_lag_cell_count": positive,
            "negative_lag_cell_count": negative,
            "near_zero_lag_cell_count": int(values.size - positive - negative),
        })
    return rows


def _case_rows(
    source: dict[str, object],
    fronts: Sequence[dict[str, object]],
    lags: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    source_cases = {str(r["model_id"]): r for r in source["case_comparison"]}
    hem = source_cases["HEM_EQUILIBRIUM"]
    output = []
    relations = (
        "BOTH_ABSENT",
        "KINETIC_ABSENT_WHILE_THERMODYNAMIC_PRESENT",
        "KINETIC_PRESENT_WHILE_THERMODYNAMIC_ABSENT",
        "KINETIC_BEHIND",
        "COINCIDENT",
        "KINETIC_AHEAD",
    )
    for model_id, case in source_cases.items():
        fr = [r for r in fronts if r["model_id"] == model_id]
        lr = [r for r in lags if r["model_id"] == model_id]
        counts = {name: sum(r["relation"] == name for r in fr) for name in relations}
        min_lag = min(float(r["minimum_signed_quality_lag"]) for r in lr)
        max_lag = max(float(r["maximum_signed_quality_lag"]) for r in lr)
        max_abs = max(float(r["maximum_absolute_signed_quality_lag"]) for r in lr)
        thermo_onset = float(case["first_thermodynamic_crossing_time_s"])
        kinetic_onset = float(case["first_kinetic_crossing_time_s"])
        paired_lag = [
            float(r["thermodynamic_minus_kinetic_m"])
            for r in fr if r["thermodynamic_minus_kinetic_m"] is not None
        ]
        paired_lead = [
            float(r["kinetic_minus_thermodynamic_m"])
            for r in fr if r["kinetic_minus_thermodynamic_m"] is not None
        ]
        row = {
            "model_id": model_id,
            "model_family": case["model_family"],
            "tau_s": case["tau_s"],
            "completed": case["completed"],
            "step_count": case["step_count"],
            "first_thermodynamic_crossing_time_s": thermo_onset,
            "first_kinetic_crossing_time_s": kinetic_onset,
            "onset_delay_s": kinetic_onset - thermo_onset,
            "minimum_signed_quality_lag": min_lag,
            "maximum_signed_quality_lag": max_lag,
            "maximum_absolute_signed_quality_lag": max_abs,
            "q_transport_below_q_eq_observed": max_lag > ZERO_TOL,
            "q_transport_above_q_eq_observed": min_lag < -ZERO_TOL,
            "both_absent_count": counts["BOTH_ABSENT"],
            "kinetic_absent_count": counts[
                "KINETIC_ABSENT_WHILE_THERMODYNAMIC_PRESENT"
            ],
            "kinetic_only_count": counts[
                "KINETIC_PRESENT_WHILE_THERMODYNAMIC_ABSENT"
            ],
            "kinetic_behind_count": counts["KINETIC_BEHIND"],
            "coincident_count": counts["COINCIDENT"],
            "kinetic_ahead_count": counts["KINETIC_AHEAD"],
            "maximum_observed_front_lag_m": max(paired_lag, default=0.0),
            "maximum_observed_front_lead_m": max(paired_lead, default=0.0),
            "final_thermodynamic_front_m": case[
                "final_thermodynamic_phase_front_m"
            ],
            "final_kinetic_front_m": case["final_kinetic_phase_front_m"],
            "final_quality_lag": case["final_quality_lag"],
            "final_vapor_mass_total_kg": case["final_vapor_mass_total_kg"],
            "full_state_matches_hem": case["final_full_state_sha256"]
            == hem["final_full_state_sha256"],
            "hydrodynamic_state_matches_hem": case[
                "final_hydrodynamic_state_sha256"
            ] == hem["final_hydrodynamic_state_sha256"],
        }
        row["behavior_classification"] = behavior_classification(row)
        output.append(row)
    return output


def _limitations() -> list[dict[str, object]]:
    entries = (
        (
            "INDEPENDENT_Q_TRANSPORT_CROSSES_HEM_THERMODYNAMIC_BOUNDARY",
            "Transported q may remain nonzero in HEM thermodynamic-liquid cells.",
        ),
        (
            "SIGNED_QUALITY_DISEQUILIBRIUM_IS_MIXED",
            "q_transport can be below or above q_eq; monotone delay is unsupported.",
        ),
        (
            "KINETIC_EVIDENCE_FRONT_CAN_LEAD_THERMODYNAMIC_FRONT",
            "The q-threshold front is not a validated physical phase front.",
        ),
        (
            "NO_NON_EQUILIBRIUM_HYDRODYNAMIC_FEEDBACK",
            "Pressure, temperature and acoustics remain HEM values by construction.",
        ),
        (
            "RELAXATION_TIME_NOT_VALIDATED",
            "Tested tau values are assumed sensitivity parameters.",
        ),
        (
            "NO_NUCLEATION_METASTABILITY_OR_SLIP_MODEL",
            "The scaffold is not a physical flashing-delay model.",
        ),
        (
            "P1_NUMERICAL_LIMITATIONS_RETAINED",
            "P1 mesh/CFL independence remains unverified.",
        ),
        (
            "NO_PHYSICAL_DISCHARGE_FEEDBACK_LOOP",
            "Prescribed depressurization is not the closed discharge-feedback loop.",
        ),
    )
    return [{"id": key, "closed": False, "implication": text} for key, text in entries]


def audit() -> dict[str, object]:
    source = analyze_hne_model_form_sensitivity()
    fronts = _front_rows(source)
    lags = _lag_rows(source)
    cases = _case_rows(source, fronts, lags)
    by_id = {str(r["model_id"]): r for r in cases}
    near = by_id["HNE_TAU_NEAR_ZERO"]
    medium = by_id["HNE_TAU_MEDIUM"]
    slow = by_id["HNE_TAU_SLOW"]
    expected = [
        "HEM_EQUILIBRIUM",
        "HNE_TAU_NEAR_ZERO",
        "HNE_TAU_MEDIUM",
        "HNE_TAU_SLOW",
    ]
    maturity_false = all(
        FORMAL_STATUS[key] is False
        for key in (
            "physical_hne_vertical_slice",
            "working_vertical_slice",
            "verified",
            "accepted",
            "physically_validated",
            "design_use_accepted",
            "production_approved",
        )
    )
    gates = [
        {
            "gate": "SOURCE_P2_A1_READY",
            "passed": source["model_form_slice_ready"] is True
            and source["execution_status"]
            == "WORKING_MODEL_FORM_SLICE_WITH_EXPLICIT_LIMITATIONS",
        },
        {
            "gate": "SOURCE_P2_A1_GATES_RETAINED",
            "passed": all(bool(v) for v in source["gate_results"].values()),
        },
        {"gate": "MODEL_MATRIX_RETAINED", "passed": list(by_id) == expected},
        {
            "gate": "TAU_ZERO_HEM_LIMIT_RETAINED",
            "passed": near["full_state_matches_hem"] is True
            and float(near["maximum_absolute_signed_quality_lag"]) <= ZERO_TOL,
        },
        {
            "gate": "FINITE_TAU_MIXED_SIGN_DISEQUILIBRIUM_RETAINED",
            "passed": all(
                r["q_transport_below_q_eq_observed"] is True
                and r["q_transport_above_q_eq_observed"] is True
                for r in (medium, slow)
            ),
        },
        {
            "gate": "MEDIUM_TAU_NO_RESOLVED_ONSET_DELAY",
            "passed": math.isclose(
                float(medium["onset_delay_s"]), 0.0, rel_tol=0.0, abs_tol=0.0
            ),
        },
        {
            "gate": "SLOW_TAU_ONSET_DELAY_RESOLVED",
            "passed": float(slow["onset_delay_s"]) > 0.0,
        },
        {
            "gate": "TRANSIENT_FRONT_LEAD_RETAINED",
            "passed": int(medium["kinetic_ahead_count"]) > 0
            and int(slow["kinetic_ahead_count"]) > 0,
        },
        {
            "gate": "SLOW_TAU_INITIAL_LAG_RETAINED",
            "passed": int(slow["kinetic_absent_count"])
            + int(slow["kinetic_behind_count"]) > 0,
        },
        {
            "gate": "HYDRODYNAMIC_INVARIANCE_IS_CONSTRUCTION_PROPERTY",
            "passed": all(r["hydrodynamic_state_matches_hem"] is True for r in cases),
        },
        {"gate": "PHYSICAL_HNE_CLAIM_PROHIBITED", "passed": True},
        {"gate": "MATURITY_NOT_PROMOTED", "passed": maturity_false},
    ]
    ready = all(bool(g["passed"]) for g in gates)
    payload = {
        "schema_version": SCHEMA,
        "scope": "p2_a1_transported_quality_disequilibrium_audit",
        "source_p2_a1_branch_sha": SOURCE_A1_SHA,
        "source_p2_a1_model_form_sha256": source["model_form_sha256"],
        "source_p2_a1_execution_status": source["execution_status"],
        "tau_cases": [
            {"model_id": model_id, "tau_s": tau_s}
            for model_id, tau_s in P2_A1_TAU_CASES
        ],
        "case_disequilibrium": cases,
        "front_relation_history": fronts,
        "signed_quality_lag_history": lags,
        "closure_limitations": _limitations(),
        "interpretation": {
            "tau_to_zero_limit": "BITWISE_HEM_LIMIT_RETAINED",
            "finite_tau_quality_behavior": (
                "MIXED_SIGN_TRANSPORTED_EQUILIBRIUM_DISEQUILIBRIUM"
            ),
            "onset_delay_at_tested_resolution": "RESOLVED_FOR_SLOW_TAU_ONLY",
            "kinetic_front_behavior": (
                "MIXED_LAG_AND_LEAD_UNDER_INDEPENDENT_QUALITY_TRANSPORT"
            ),
            "closure_finding": (
                "TRANSPORTED_Q_CAN_CROSS_HEM_THERMODYNAMIC_BOUNDARY"
            ),
            "hydrodynamic_feedback": "ABSENT_BY_CONSTRUCTION",
            "physical_hne_interpretation": "NOT_AUTHORIZED",
            "physical_tau_validation": "NOT_ESTABLISHED",
            "superseded_generalization": (
                "FINITE_TAU_DOES_NOT_IMPLY_MONOTONE_KINETIC_FRONT_DELAY"
            ),
        },
        "key_metrics": {
            "medium_tau_onset_delay_s": medium["onset_delay_s"],
            "slow_tau_onset_delay_s": slow["onset_delay_s"],
            "medium_tau_ahead_snapshot_count": medium["kinetic_ahead_count"],
            "slow_tau_ahead_snapshot_count": slow["kinetic_ahead_count"],
            "slow_tau_lag_or_absent_snapshot_count": (
                int(slow["kinetic_behind_count"])
                + int(slow["kinetic_absent_count"])
            ),
        },
        "gates": gates,
        "gate_results": {str(g["gate"]): bool(g["passed"]) for g in gates},
        "audit_ready": ready,
        "execution_status": (
            "A1R_AUDIT_READY_WITH_CLOSURE_LIMITATION" if ready else "FAIL_CLOSED"
        ),
        "physical_hne_claim_allowed": False,
        "next_phase_decision": (
            "PROCEED_TO_P2_A2_THERMODYNAMIC_CLOSURE_REFINEMENT_BEFORE_BROAD_TAU_SWEEP"
            if ready else "STOP_AND_DIAGNOSE_P2_A1R"
        ),
        "warnings": [
            "P2_A1_SOFTWARE_SLICE_RETAINED_BUT_FRONT_DELAY_INTERPRETATION_NARROWED",
            "KINETIC_Q_THRESHOLD_FRONT_IS_NOT_A_VALIDATED_PHYSICAL_PHASE_FRONT",
            "TRANSPORTED_Q_CAN_EXCEED_LOCAL_HEM_EQUILIBRIUM_Q",
            "TRANSPORTED_Q_CAN_REMAIN_NONZERO_IN_HEM_LIQUID_CELLS",
            "PRESSURE_TEMPERATURE_AND_SOUND_SPEED_REMAIN_HEM_BY_CONSTRUCTION",
            "TAU_VALUES_REMAIN_UNVALIDATED_SENSITIVITY_PARAMETERS",
            "P1_MESH_CFL_LIMITATIONS_REMAIN_ACTIVE",
        ],
        "provenance": _provenance(),
        "formal_status": dict(FORMAL_STATUS),
    }
    payload["audit_sha256"] = _sha(payload)
    return payload


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise AuditError(f"cannot write empty CSV: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _plot_lag(path: Path, summary: dict[str, object]) -> None:
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    origin = min(float(r["time_s"]) for r in summary["signed_quality_lag_history"])
    for case in summary["case_disequilibrium"]:
        model = str(case["model_id"])
        rows = [r for r in summary["signed_quality_lag_history"] if r["model_id"] == model]
        t = 1.0e6 * np.asarray([float(r["time_s"]) - origin for r in rows])
        ax.plot(t, [float(r["maximum_signed_quality_lag"]) for r in rows], label=f"{model} max")
        ax.plot(t, [float(r["minimum_signed_quality_lag"]) for r in rows], linestyle="--", label=f"{model} min")
    ax.axhline(0.0, linewidth=1.0)
    ax.set_xlabel("Time from audit start [microseconds]")
    ax.set_ylabel("q_eq - q_transport [-]")
    ax.set_title("P2-A1R signed quality disequilibrium")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_front_counts(path: Path, summary: dict[str, object]) -> None:
    cases = summary["case_disequilibrium"]
    labels = [str(r["model_id"]) for r in cases]
    keys = (
        ("kinetic_absent_count", "absent"),
        ("kinetic_behind_count", "behind"),
        ("coincident_count", "coincident"),
        ("kinetic_ahead_count", "ahead"),
        ("kinetic_only_count", "kinetic-only"),
    )
    x = np.arange(len(labels), dtype=float)
    width = 0.15
    fig, ax = plt.subplots(figsize=(10.0, 5.2))
    for index, (key, label) in enumerate(keys):
        ax.bar(x + (index - 2) * width, [int(r[key]) for r in cases], width, label=label)
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("Snapshots")
    ax.set_title("P2-A1R kinetic/thermodynamic front relation counts")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _report(summary: dict[str, object]) -> str:
    lines = [
        "# P2-A1R Transported-Quality Disequilibrium Audit",
        "",
        f"- status: `{summary['execution_status']}`",
        "- physical HNE claim allowed: `false`",
        "",
        "The near-zero tau case remains bitwise HEM. Finite tau creates mixed-sign",
        "q_eq-q_transport disequilibrium. At the tested resolution tau=1e-5 s has",
        "no onset delay and transient front lead; tau=1e-4 s has initial delay and",
        "then both lag and lead. The q-threshold front is not a physical phase front.",
        "",
        "| model | tau [s] | onset delay [us] | min lag | max lag | absent | behind | equal | ahead | classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["case_disequilibrium"]:
        lines.append(
            "| {model} | {tau} | {delay:.6f} | {minimum:.8g} | {maximum:.8g} | {absent} | {behind} | {equal} | {ahead} | {classification} |".format(
                model=row["model_id"],
                tau="HEM" if row["tau_s"] is None else f"{float(row['tau_s']):.6g}",
                delay=1.0e6 * float(row["onset_delay_s"]),
                minimum=float(row["minimum_signed_quality_lag"]),
                maximum=float(row["maximum_signed_quality_lag"]),
                absent=row["kinetic_absent_count"],
                behind=row["kinetic_behind_count"],
                equal=row["coincident_count"],
                ahead=row["kinetic_ahead_count"],
                classification=row["behavior_classification"],
            )
        )
    lines.extend([
        "",
        "## Decision",
        "",
        "Retain P2-A1 as a working software/model-form scaffold. Refine the",
        "thermodynamic closure before a broad tau sweep or any physical HNE claim.",
        "",
        "## Maturity",
        "",
        "- IMPLEMENTED: true",
        "- DIAGNOSTIC EVIDENCE READY: true",
        "- P2 MODEL-FORM VERTICAL SLICE: true",
        "- PHYSICAL HNE VERTICAL SLICE: false",
        "- PROJECT WORKING VERTICAL SLICE: false",
        "- VERIFIED / ACCEPTED / PHYSICALLY VALIDATED: false",
        "- DESIGN-USE ACCEPTED / PRODUCTION APPROVED: false",
        "",
    ])
    return "\n".join(lines)


def write_artifacts(output_dir: str | Path, summary: dict[str, object]) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    if {p.name for p in target.iterdir() if p.is_file()} - expected:
        raise AuditError("unexpected files in output directory")
    paths = {
        "summary": target / "audit_summary.json",
        "cases": target / "case_disequilibrium.csv",
        "fronts": target / "front_relation_history.csv",
        "lags": target / "signed_quality_lag_history.csv",
        "limitations": target / "closure_limitations.csv",
        "lag_plot": target / "signed_quality_lag_envelope.png",
        "front_plot": target / "front_relation_counts.png",
        "report": target / "operator_report.md",
        "manifest": target / "audit_manifest.json",
    }
    paths["summary"].write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    _write_csv(paths["cases"], summary["case_disequilibrium"])
    _write_csv(paths["fronts"], summary["front_relation_history"])
    _write_csv(paths["lags"], summary["signed_quality_lag_history"])
    _write_csv(paths["limitations"], summary["closure_limitations"])
    _plot_lag(paths["lag_plot"], summary)
    _plot_front_counts(paths["front_plot"], summary)
    paths["report"].write_text(_report(summary), encoding="utf-8")
    payload_files = {
        path.name: {"sha256": _file_sha(path), "size_bytes": path.stat().st_size}
        for key, path in paths.items() if key != "manifest"
    }
    manifest = {
        "schema_version": SCHEMA,
        "artifact_contract": "stage7_p2_hne_model_form_a1r_exactly_9_files",
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "execution_status": summary["execution_status"],
        "audit_ready": summary["audit_ready"],
        "audit_sha256": summary["audit_sha256"],
        "source_p2_a1_branch_sha": SOURCE_A1_SHA,
        "physical_hne_claim_allowed": False,
        "payload_files": payload_files,
        "formal_status": dict(FORMAL_STATUS),
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    actual = {p.name for p in target.iterdir() if p.is_file()}
    if actual != expected:
        raise AuditError(f"output contract mismatch: {sorted(actual)}")
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    summary = audit()
    paths = write_artifacts(output_dir, summary)
    return {**summary, "artifact_paths": {k: str(v) for k, v in paths.items()}}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["audit_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
