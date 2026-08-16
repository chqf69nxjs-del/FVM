"""Stage 7 P1 numerical sensitivity closeout.

This evidence-only closeout integrates P1-A2, P1-A3, P1-A3F, and P1-A3G
without changing the solver, EOS, threshold, Guard, tolerance, boundary model,
or production numerics. The closeout is READY only when the limited robust
finding and the unresolved numerical sensitivities are both retained explicitly.

CLOSEOUT_READY_WITH_LIMITATIONS is not VERIFIED, ACCEPTED, PHYSICALLY
VALIDATED, DESIGN-USE ACCEPTED, or PRODUCTION APPROVED.
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
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .hem_pipeline_crossing_event_alignment import analyze_crossing_event_alignment
from .hem_pipeline_mesh_cfl_sensitivity import analyze_mesh_cfl_sensitivity
from .hem_pipeline_post_crossing_analysis import analyze_post_crossing_propagation
from .hem_pipeline_post_crossing_propagation import run_post_crossing_propagation_review
from .hem_pipeline_pressure_phase_relationship import analyze_pressure_phase_relationship
from .hem_pipeline_subthreshold_crossing_forensics import analyze_subthreshold_crossing_forensics
from .hem_pipeline_threshold_sensitivity import analyze_threshold_sensitivity

P1_CLOSEOUT_SCHEMA_VERSION = "stage7_p1_numerical_sensitivity_closeout_v1"
P1_CLOSEOUT_MODEL_ID = "HEM_EQUILIBRIUM"
P1_CLOSEOUT_FIXED_EVIDENCE_FLOOR = 1.0e-6
P1_CLOSEOUT_SUBTHRESHOLD_CASE_IDS = ("mesh_64_cfl_0p10", "cfl_32_0p05")
P1_CLOSEOUT_AUTHORITY = {
    "main": {"branch": "main", "sha": "aa108961762c9ae70ee9940405024eb5188064b8"},
    "p1_a2": {"branch": "agent/stage7-p1-threshold-sensitivity-a2", "sha": "247148c8ee7ac119fb030f07240ca0e5b05e8ff4"},
    "p1_a3": {"branch": "agent/stage7-p1-mesh-cfl-sensitivity-a3", "sha": "b9e36507370c6c7e8136e1635bb9c4382c6a292a"},
    "p1_a3f": {"branch": "agent/stage7-p1-a3-subthreshold-crossing-forensics", "sha": "994124c38828459e866f0d4f874ecf05bd15299a"},
    "p1_a3g": {"branch": "agent/stage7-p1-a3-crossing-event-alignment", "sha": "5d58291e0debe103092c4b7ebd6ad751eb5ea9bd"},
}
P1_CLOSEOUT_OUTPUT_FILES = (
    "closeout_summary.json",
    "evidence_authorities.csv",
    "threshold_synthesis.csv",
    "mesh_cfl_event_synthesis.csv",
    "limitations.csv",
    "numerical_sensitivity_overview.png",
    "operator_report.md",
    "closeout_manifest.json",
)
P1_CLOSEOUT_FORMAL_STATUS = {
    "implemented": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "mesh_independent_crossing_verified": False,
    "cfl_independent_crossing_verified": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}
_A3_FROZEN_VERDICT = {
    "sensitivity_execution_status": "FAIL_CLOSED",
    "ordering_verdict": "INCONCLUSIVE",
    "numerical_verdict": "INCONCLUSIVE",
}
_MATURITY_FALSE_KEYS = (
    "working_vertical_slice",
    "verified",
    "accepted",
    "physically_validated",
    "design_use_accepted",
    "production_approved",
)


class P1NumericalSensitivityCloseoutError(RuntimeError):
    """Raised when the P1 closeout evidence contract cannot complete safely."""


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""
    return {
        "source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run("git", "status", "--porcelain=v1", "--untracked-files=all"),
    }


def _source_maturity_not_promoted(summary: Mapping[str, object]) -> bool:
    status = summary.get("formal_status")
    return isinstance(status, Mapping) and all(status.get(key) is False for key in _MATURITY_FALSE_KEYS)


def _finite(value: object) -> bool:
    return value is not None and math.isfinite(float(value))


def _case_by_id(a3g: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    rows = a3g.get("case_alignment")
    if not isinstance(rows, Sequence):
        raise P1NumericalSensitivityCloseoutError("A3G case_alignment is unavailable")
    output: dict[str, Mapping[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise P1NumericalSensitivityCloseoutError("A3G case row is invalid")
        output[str(row["case_id"])] = row
    return output


def _threshold_rows(a2: Mapping[str, object]) -> list[dict[str, object]]:
    rows = a2.get("threshold_comparisons")
    if not isinstance(rows, Sequence):
        raise P1NumericalSensitivityCloseoutError("A2 threshold_comparisons are unavailable")
    output: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise P1NumericalSensitivityCloseoutError("A2 threshold row is invalid")
        output.append({
            "threshold_multiplier": float(row["threshold_multiplier"]),
            "pressure_drop_threshold_relative": float(row["pressure_drop_threshold_relative"]),
            "phase_bearing_snapshot_count": int(row["phase_bearing_snapshot_count"]),
            "pressure_strictly_ahead_snapshot_count": int(row["pressure_strictly_ahead_snapshot_count"]),
            "pressure_strictly_ahead_all_phase_bearing_snapshots": bool(row["pressure_strictly_ahead_all_phase_bearing_snapshots"]),
            "final_pressure_front_distance_from_outlet_m": float(row["final_pressure_front_distance_from_outlet_m"]),
            "final_phase_front_distance_from_outlet_m": float(row["final_phase_front_distance_from_outlet_m"]),
            "final_pressure_phase_separation_m": float(row["final_pressure_phase_separation_m"]),
        })
    return output


def _event_rows(a3g: Mapping[str, object]) -> list[dict[str, object]]:
    by_id = _case_by_id(a3g)
    ordered = ("mesh_16_cfl_0p10", "baseline_32_cfl_0p10", "mesh_64_cfl_0p10", "cfl_32_0p05", "cfl_32_0p20")
    output: list[dict[str, object]] = []
    for case_id in ordered:
        row = by_id[case_id]
        output.append({
            "case_id": case_id,
            "n_cells": int(row["n_cells"]),
            "cfl": float(row["cfl"]),
            "authoritative_outcome": str(row["authoritative_outcome"]),
            "event_a_time_s": float(row["event_a_time_s"]),
            "event_a_quality": float(row["event_a_quality"]),
            "event_b_time_s": float(row["event_b_time_s"]),
            "event_b_quality": float(row["event_b_quality"]),
            "delta_t_a_to_b_s": float(row["delta_t_a_to_b_s"]),
            "delta_step_a_to_b": int(row["delta_step_a_to_b"]),
            "delta_x_front_a_to_b_m": float(row["delta_x_front_a_to_b_m"]),
            "shadow_continuation_used": bool(row["shadow_continuation_used"]),
        })
    return output


def _sensitivity_metrics(a3g: Mapping[str, object]) -> dict[str, float]:
    by_id = _case_by_id(a3g)
    mesh_ids = ("mesh_16_cfl_0p10", "baseline_32_cfl_0p10", "mesh_64_cfl_0p10")
    cfl_ids = ("cfl_32_0p05", "baseline_32_cfl_0p10", "cfl_32_0p20")
    mesh_times = [float(by_id[case_id]["event_a_time_s"]) for case_id in mesh_ids]
    cfl_times = [float(by_id[case_id]["event_a_time_s"]) for case_id in cfl_ids]
    baseline = float(by_id["baseline_32_cfl_0p10"]["event_a_time_s"])
    fine_ab = float(by_id["mesh_64_cfl_0p10"]["delta_t_a_to_b_s"])
    low_ab = float(by_id["cfl_32_0p05"]["delta_t_a_to_b_s"])
    ab_mean = 0.5 * (fine_ab + low_ab)
    return {
        "mesh_event_a_time_min_s": min(mesh_times),
        "mesh_event_a_time_max_s": max(mesh_times),
        "mesh_event_a_time_span_s": max(mesh_times) - min(mesh_times),
        "mesh_event_a_time_span_relative_to_baseline": (max(mesh_times) - min(mesh_times)) / baseline,
        "cfl_event_a_time_min_s": min(cfl_times),
        "cfl_event_a_time_max_s": max(cfl_times),
        "cfl_event_a_time_span_s": max(cfl_times) - min(cfl_times),
        "cfl_event_a_time_span_relative_to_baseline": (max(cfl_times) - min(cfl_times)) / baseline,
        "fine_mesh_a_to_b_s": fine_ab,
        "low_cfl_a_to_b_s": low_ab,
        "subthreshold_a_to_b_relative_difference": abs(fine_ab - low_ab) / ab_mean if ab_mean > 0.0 else 0.0,
    }


def _limitations() -> list[dict[str, object]]:
    return [
        {"id": "MESH_INDEPENDENCE_NOT_VERIFIED", "closed": False, "design_implication": "Absolute first-crossing time must not be treated as mesh-independent."},
        {"id": "CFL_INDEPENDENCE_NOT_VERIFIED", "closed": False, "design_implication": "Absolute first-crossing time and crossing depth retain CFL sensitivity."},
        {"id": "DISCRETE_PRESSURE_FRONT_SPEED_NOT_PHYSICALLY_UNIQUE", "closed": False, "design_implication": "Threshold-derived arrival slope is diagnostic, not a validated wave speed."},
        {"id": "HEM_HAS_NO_PHYSICAL_NUCLEATION_DELAY", "closed": False, "design_implication": "Event A-to-B time is not a physical flashing or nucleation delay."},
        {"id": "PRESCRIBED_DEPRESSURIZATION_NOT_FULL_DISCHARGE_FEEDBACK", "closed": False, "design_implication": "P1 does not close the physical-discharge/two-phase feedback loop."},
    ]


def _evaluate_sources(a2: Mapping[str, object], a3: Mapping[str, object], a3f: Mapping[str, object], a3g: Mapping[str, object]) -> tuple[list[dict[str, object]], bool]:
    a3g_authority = a3g.get("authoritative_a3_verdict")
    a3f_subthreshold = tuple(str(x) for x in a3f.get("subthreshold_case_ids", []))
    a3g_subthreshold = tuple(str(x) for x in a3g.get("subthreshold_case_ids", []))
    gates = [
        {"gate": "A2_THRESHOLD_ORDERING_ROBUST", "passed": a2.get("sensitivity_execution_status") == "SENSITIVITY_READY" and a2.get("sensitivity_verdict") == "ROBUST" and bool(a2.get("sensitivity_ready"))},
        {"gate": "A3_FAIL_CLOSED_AUTHORITY_PRESERVED", "passed": a3.get("sensitivity_execution_status") == "FAIL_CLOSED" and a3.get("ordering_verdict") == "INCONCLUSIVE" and a3.get("numerical_verdict") == "INCONCLUSIVE" and a3g_authority == _A3_FROZEN_VERDICT},
        {"gate": "A3F_DIRECT_FAILURE_MECHANISM_CONFIRMED", "passed": a3f.get("forensic_execution_status") == "FORENSICS_READY" and bool(a3f.get("forensics_ready")) and a3f.get("direct_failure_mechanism") == "CONFIRMED" and a3f.get("unrelated_failure_case_ids") == []},
        {"gate": "A3G_EVENT_ALIGNMENT_READY", "passed": a3g.get("alignment_execution_status") == "ALIGNMENT_READY" and bool(a3g.get("alignment_ready")) and a3g.get("event_definition_interpretation") == "STRONGLY_SUPPORTS_DISCRETE_EVENT_ALIASING" and a3g.get("event_b_unreached_case_ids") == []},
        {"gate": "SUBTHRESHOLD_CASE_IDENTITY_PRESERVED", "passed": a3f_subthreshold == P1_CLOSEOUT_SUBTHRESHOLD_CASE_IDS and a3g_subthreshold == P1_CLOSEOUT_SUBTHRESHOLD_CASE_IDS},
        {"gate": "FIXED_EVIDENCE_FLOOR_PRESERVED", "passed": float(a3f.get("fixed_crossing_evidence_floor", math.nan)) == P1_CLOSEOUT_FIXED_EVIDENCE_FLOOR and float(a3g.get("fixed_crossing_evidence_floor", math.nan)) == P1_CLOSEOUT_FIXED_EVIDENCE_FLOOR and a3f.get("threshold_or_tolerance_changed") is False and a3g.get("threshold_or_tolerance_changed") is False},
        {"gate": "SOLVER_AND_PHYSICS_UNCHANGED", "passed": a3f.get("solver_or_physics_changed") is False and a3g.get("solver_or_physics_changed") is False and a2.get("physics_or_numerics_changed") is False and a3.get("physics_or_production_numerics_changed") is False and a3.get("locked_gate6_contract_changed") is False},
        {"gate": "SOURCE_MATURITY_NOT_PROMOTED", "passed": all(_source_maturity_not_promoted(summary) for summary in (a2, a3, a3f, a3g))},
        {"gate": "CLOSEOUT_MATURITY_NOT_PROMOTED", "passed": all(P1_CLOSEOUT_FORMAL_STATUS[key] is False for key in _MATURITY_FALSE_KEYS)},
        {"gate": "MESH_AND_CFL_INDEPENDENCE_RETAINED_AS_UNVERIFIED", "passed": P1_CLOSEOUT_FORMAL_STATUS["mesh_independent_crossing_verified"] is False and P1_CLOSEOUT_FORMAL_STATUS["cfl_independent_crossing_verified"] is False and "MESH_INDEPENDENCE_NOT_VERIFIED" in a3.get("warnings", []) and "CFL_INDEPENDENCE_NOT_VERIFIED" in a3.get("warnings", [])},
    ]
    return gates, all(bool(gate["passed"]) for gate in gates)


def synthesize_closeout(a2: Mapping[str, object], a3: Mapping[str, object], a3f: Mapping[str, object], a3g: Mapping[str, object], *, source_digests: Mapping[str, str] | None = None, provenance: Mapping[str, str] | None = None) -> dict[str, object]:
    gates, ready = _evaluate_sources(a2, a3, a3f, a3g)
    threshold_rows = _threshold_rows(a2)
    event_rows = _event_rows(a3g)
    metrics = _sensitivity_metrics(a3g)
    finite_events = all(_finite(row["event_a_time_s"]) and _finite(row["event_a_quality"]) and _finite(row["event_b_time_s"]) and _finite(row["event_b_quality"]) for row in event_rows)
    gates.append({"gate": "CLOSEOUT_EVENT_SCALARS_FINITE", "passed": finite_events})
    ready = ready and finite_events
    payload = {
        "schema_version": P1_CLOSEOUT_SCHEMA_VERSION,
        "scope": "p1_hem_numerical_sensitivity_closeout_with_explicit_limitations",
        "model_id": P1_CLOSEOUT_MODEL_ID,
        "closeout_execution_status": "CLOSEOUT_READY_WITH_LIMITATIONS" if ready else "FAIL_CLOSED",
        "closeout_ready": ready,
        "authority": P1_CLOSEOUT_AUTHORITY,
        "source_evidence_digests": dict(source_digests or {}),
        "source_status": {
            "p1_a2": {"execution_status": a2.get("sensitivity_execution_status"), "verdict": a2.get("sensitivity_verdict")},
            "p1_a3": {"execution_status": a3.get("sensitivity_execution_status"), "ordering_verdict": a3.get("ordering_verdict"), "numerical_verdict": a3.get("numerical_verdict")},
            "p1_a3f": {"execution_status": a3f.get("forensic_execution_status"), "direct_failure_mechanism": a3f.get("direct_failure_mechanism")},
            "p1_a3g": {"execution_status": a3g.get("alignment_execution_status"), "event_definition_interpretation": a3g.get("event_definition_interpretation")},
        },
        "threshold_synthesis": threshold_rows,
        "mesh_cfl_event_synthesis": event_rows,
        "sensitivity_metrics": metrics,
        "limitations": _limitations(),
        "engineering_interpretation": {
            "pressure_phase_ordering": "ROBUST_WITHIN_PREDECLARED_PRESSURE_THRESHOLD_ENVELOPE",
            "a3_guard_failure": "SUBTHRESHOLD_THERMODYNAMIC_CROSSING_WITH_DISCRETE_EVENT_ALIASING",
            "absolute_crossing_time": "NUMERICALLY_SENSITIVE_ESPECIALLY_TO_MESH",
            "mesh_independence": "NOT_VERIFIED",
            "cfl_independence": "NOT_VERIFIED",
            "physical_nucleation_delay": "NOT_MODELLED_BY_HEM",
        },
        "p1_closeout_statement": "The pressure-front-before-accepted-equilibrium-phase-front ordering is retained over the predeclared pressure-front threshold envelope. The A3 guard failures are explained by positive but subthreshold thermodynamic crossings followed by one-step evidence-floor crossings in the fine-mesh and low-CFL cases. Absolute first-crossing timing remains numerically sensitive, especially to mesh; mesh/CFL independence is not verified.",
        "next_phase_decision": "PROCEED_TO_P2_HNE_MODEL_FORM_SENSITIVITY_WITH_P1_LIMITATIONS_RETAINED" if ready else "DO_NOT_PROCEED_FROM_THIS_CLOSEOUT",
        "gates": gates,
        "gate_results": {str(gate["gate"]): bool(gate["passed"]) for gate in gates},
        "provenance": dict(provenance or {}),
        "formal_status": dict(P1_CLOSEOUT_FORMAL_STATUS),
        "warnings": [
            "CLOSEOUT_READY_IS_NOT_VERIFIED_OR_ACCEPTED",
            "MESH_INDEPENDENCE_NOT_VERIFIED",
            "CFL_INDEPENDENCE_NOT_VERIFIED",
            "EVENT_A_TO_B_IS_NOT_PHYSICAL_FLASHING_DELAY",
            "PRESSURE_FRONT_SPEED_REMAINS_THRESHOLD_DEFINED_DIAGNOSTIC",
            "P1_PRESCRIBED_DEPRESSURIZATION_IS_NOT_FULL_DISCHARGE_FEEDBACK",
        ],
    }
    digest_payload = dict(payload)
    payload["closeout_sha256"] = _canonical_json_sha256(digest_payload)
    return payload


def analyze_numerical_sensitivity_closeout() -> dict[str, object]:
    source = run_post_crossing_propagation_review()
    a0 = analyze_post_crossing_propagation(source)
    a1 = analyze_pressure_phase_relationship(source, a0)
    a2_result = analyze_threshold_sensitivity(source, a0, a1)
    a2 = a2_result.summary()
    a2["sensitivity_sha256"] = a2_result.sensitivity_sha256
    a3_result = analyze_mesh_cfl_sensitivity()
    a3 = a3_result.summary()
    a3f = analyze_subthreshold_crossing_forensics()
    a3g = analyze_crossing_event_alignment()
    return synthesize_closeout(a2, a3, a3f, a3g, source_digests={
        "p1_a2_sensitivity_sha256": a2_result.sensitivity_sha256,
        "p1_a3_sensitivity_sha256": a3_result.sensitivity_sha256,
        "p1_a3f_forensic_sha256": str(a3f["forensic_sha256"]),
        "p1_a3g_event_alignment_sha256": str(a3g["event_alignment_sha256"]),
    }, provenance=_git_provenance())


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise P1NumericalSensitivityCloseoutError(f"cannot write empty closeout CSV: {path.name}")
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _authority_rows() -> list[dict[str, object]]:
    return [{"authority": key, **value} for key, value in P1_CLOSEOUT_AUTHORITY.items()]


def _plot_overview(path: Path, event_rows: Sequence[Mapping[str, object]]) -> None:
    by_id = {str(row["case_id"]): row for row in event_rows}
    labels = ["mesh16/CFL.10", "mesh32/CFL.10", "mesh64/CFL.10", "mesh32/CFL.05", "mesh32/CFL.20"]
    ids = ["mesh_16_cfl_0p10", "baseline_32_cfl_0p10", "mesh_64_cfl_0p10", "cfl_32_0p05", "cfl_32_0p20"]
    event_a_ms = np.asarray([1000.0 * float(by_id[case_id]["event_a_time_s"]) for case_id in ids])
    event_b_ms = np.asarray([1000.0 * float(by_id[case_id]["event_b_time_s"]) for case_id in ids])
    x = np.arange(len(ids), dtype=float)
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.plot(x, event_a_ms, marker="o", label="Event A")
    ax.plot(x, event_b_ms, marker="x", label="Event B")
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("Crossing time [ms]")
    ax.set_title("P1 closeout: Event A / Event B timing across mesh and CFL")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _operator_report(summary: Mapping[str, object]) -> str:
    metrics = summary["sensitivity_metrics"]
    lines = [
        "# P1 Numerical Sensitivity Closeout", "",
        f"- status: `{summary['closeout_execution_status']}`",
        f"- model: `{summary['model_id']}`",
        "- A3 authority remains: `FAIL_CLOSED / INCONCLUSIVE / INCONCLUSIVE`",
        "- mesh-independent verified: `false`",
        "- CFL-independent verified: `false`", "",
        "## Consolidated conclusion", "", str(summary["p1_closeout_statement"]), "",
        "## Quantitative bounds", "",
        f"- mesh Event-A time span: `{1.0e6 * float(metrics['mesh_event_a_time_span_s']):.6f} us` (`{100.0 * float(metrics['mesh_event_a_time_span_relative_to_baseline']):.3f}%` of baseline Event-A time)",
        f"- CFL Event-A time span: `{1.0e6 * float(metrics['cfl_event_a_time_span_s']):.6f} us` (`{100.0 * float(metrics['cfl_event_a_time_span_relative_to_baseline']):.3f}%` of baseline Event-A time)",
        f"- fine-mesh A->B: `{1.0e6 * float(metrics['fine_mesh_a_to_b_s']):.6f} us`",
        f"- low-CFL A->B: `{1.0e6 * float(metrics['low_cfl_a_to_b_s']):.6f} us`", "",
        "## What is closed", "",
        "- Pressure-front-first ordering is robust within the predeclared threshold envelope.",
        "- A3 subthreshold Guard failure mechanism is identified and reproduced.",
        "- Event A / Event B separation is quantified without changing the evidence floor.", "",
        "## What remains open", "",
    ]
    for row in summary["limitations"]:
        lines.append(f"- `{row['id']}`: {row['design_implication']}")
    lines.extend(["", "## Next step", "", f"`{summary['next_phase_decision']}`", "", "## Formal maturity", "", "- IMPLEMENTED: true", "- WORKING VERTICAL SLICE: false", "- VERIFIED: false", "- ACCEPTED: false", "- PHYSICALLY VALIDATED: false", "- DESIGN-USE ACCEPTED: false", "- PRODUCTION APPROVED: false", ""])
    return "\n".join(lines)


def write_closeout_artifacts(output_dir: str | Path, summary: Mapping[str, object]) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_CLOSEOUT_OUTPUT_FILES)
    existing = {path.name for path in target.iterdir() if path.is_file()}
    unexpected = existing - expected
    if unexpected:
        raise P1NumericalSensitivityCloseoutError(f"output directory contains unexpected files: {sorted(unexpected)}")
    paths = {
        "summary": target / "closeout_summary.json",
        "authorities": target / "evidence_authorities.csv",
        "threshold": target / "threshold_synthesis.csv",
        "mesh_cfl": target / "mesh_cfl_event_synthesis.csv",
        "limitations": target / "limitations.csv",
        "plot": target / "numerical_sensitivity_overview.png",
        "operator_report": target / "operator_report.md",
        "manifest": target / "closeout_manifest.json",
    }
    paths["summary"].write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    _write_csv(paths["authorities"], _authority_rows())
    _write_csv(paths["threshold"], summary["threshold_synthesis"])
    _write_csv(paths["mesh_cfl"], summary["mesh_cfl_event_synthesis"])
    _write_csv(paths["limitations"], summary["limitations"])
    _plot_overview(paths["plot"], summary["mesh_cfl_event_synthesis"])
    paths["operator_report"].write_text(_operator_report(summary), encoding="utf-8")
    payload_files: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if key == "manifest":
            continue
        payload_files[path.name] = {"sha256": _file_sha256(path), "size_bytes": path.stat().st_size}
    manifest = {
        "schema_version": P1_CLOSEOUT_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_numerical_sensitivity_closeout_exactly_8_files",
        "declared_file_count": len(P1_CLOSEOUT_OUTPUT_FILES),
        "declared_file_names": list(P1_CLOSEOUT_OUTPUT_FILES),
        "closeout_execution_status": summary["closeout_execution_status"],
        "closeout_ready": summary["closeout_ready"],
        "closeout_sha256": summary["closeout_sha256"],
        "authority": P1_CLOSEOUT_AUTHORITY,
        "payload_files": payload_files,
        "formal_status": dict(P1_CLOSEOUT_FORMAL_STATUS),
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1NumericalSensitivityCloseoutError(f"closeout output contract mismatch: expected={sorted(expected)}, actual={sorted(actual)}")
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    summary = analyze_numerical_sensitivity_closeout()
    paths = write_closeout_artifacts(output_dir, summary)
    output = dict(summary)
    output["artifact_paths"] = {key: str(path) for key, path in paths.items()}
    return output


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrate P1-A2/A3/A3F/A3G into a fail-closed numerical sensitivity closeout without promoting maturity or changing physics/numerics.")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["closeout_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
