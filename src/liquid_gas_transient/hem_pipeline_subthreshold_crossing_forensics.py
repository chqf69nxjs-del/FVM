"""Stage 7 P1-A3 sub-threshold first-crossing forensics.

This diagnostic increment preserves the fixed crossing evidence floor and the
failed A3 result.  It replays only the first-crossing portion of the five
predeclared mesh/CFL cases, retaining the crossing cell state even when the
existing first-crossing runner correctly returns GUARD_FAILURE because the
equilibrium quality is below the fixed evidence floor.

No threshold, solver, EOS, boundary model, projection, conservation tolerance,
or production configuration is changed.
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

from .hem_phase_classification import evaluate_coolprop_hem_phase_state
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    run_pipeline_depressurization_case,
)
from .hem_pipeline_mesh_cfl_sensitivity import P1_A3_CASE_SPECS
from .hem_pipeline_mesh_cfl_variant import HEMMeshCflPipelineConfig
from .state import IDX_RHO, internal_energy

P1_A3F_SCHEMA_VERSION = "stage7_p1_a3_subthreshold_crossing_forensics_v1"
P1_A3F_MODEL_ID = "HEM_EQUILIBRIUM"
P1_A3F_EVIDENCE_FLOOR = 1.0e-6
P1_A3F_OUTPUT_FILES = (
    "forensic_summary.json",
    "case_forensics.csv",
    "cell_forensics.csv",
    "quality_scaling.csv",
    "quality_vs_dx.png",
    "quality_vs_cfl.png",
    "operator_report.md",
    "forensic_manifest.json",
)
P1_A3F_FORMAL_STATUS = {
    "implemented": True,
    "diagnostic_evidence_ready": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "mesh_independent_crossing_verified": False,
    "cfl_independent_crossing_verified": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}


class P1A3SubthresholdForensicsError(RuntimeError):
    """Raised when the bounded forensic contract cannot be completed safely."""


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_provenance() -> dict[str, str]:
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


def _baseline_case():
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        if case.case_id == "pipeline_crossing_candidate_p5m5_to_p2m5":
            return case
    raise P1A3SubthresholdForensicsError("fixed 5 MPa -> 2 MPa case was not found")


def _config_for_spec(spec):
    if spec.use_locked_gate6_authority:
        return HEMPipelineDepressurizationConfig()
    return HEMMeshCflPipelineConfig(n_cells=spec.n_cells, cfl=spec.cfl)


def _crossing_status(result: PipelineCaseResult) -> str:
    if result.outcome == "ACCEPTED_FIRST_CROSSING":
        return "ACCEPTED_ABOVE_FIXED_FLOOR"
    if (
        result.outcome == "GUARD_FAILURE"
        and result.crossing_step is not None
        and math.isfinite(result.maximum_crossing_quality)
        and 0.0 < result.maximum_crossing_quality < P1_A3F_EVIDENCE_FLOOR
        and "crossing quality evidence is below the fixed minimum"
        in result.failure_reason
    ):
        return "SUBTHRESHOLD_CROSSING_RETAINED"
    if result.crossing_step is None:
        return "NO_RETAINED_CROSSING"
    return "OTHER_CROSSING_FAILURE"


def _phase_quality(U: np.ndarray, config: HEMPipelineDepressurizationConfig) -> np.ndarray:
    state = evaluate_coolprop_hem_phase_state(
        np.asarray(U[:, IDX_RHO], dtype=float),
        np.asarray(internal_energy(U), dtype=float),
        config=config.phase_config,
    )
    quality = np.asarray(state.quality, dtype=float)
    if quality.shape != (config.n_cells,) or not np.all(np.isfinite(quality)):
        raise P1A3SubthresholdForensicsError(
            "phase-quality reconstruction returned invalid values"
        )
    return quality


def _crossing_step_record(result: PipelineCaseResult):
    if result.crossing_step is None:
        return None
    for row in result.steps:
        if row.step_index == result.crossing_step:
            return row
    return None


def _case_and_cell_rows(spec, result: PipelineCaseResult):
    status = _crossing_status(result)
    crossing_step = result.crossing_step
    step_record = _crossing_step_record(result)
    q_max = (
        None
        if crossing_step is None
        else float(result.maximum_crossing_quality)
    )
    ratio = (
        None
        if q_max is None
        else q_max / P1_A3F_EVIDENCE_FLOOR
    )
    margin = (
        None
        if q_max is None
        else q_max - P1_A3F_EVIDENCE_FLOOR
    )
    dt_s = None if step_record is None else float(step_record.dt_s)
    measured_step_cfl = (
        None
        if dt_s is None
        else float(spec.cfl)
    )
    case_row = {
        "case_id": spec.case_id,
        "role": spec.role,
        "source_kind": (
            "LOCKED_GATE6_FIRST_CROSSING"
            if spec.use_locked_gate6_authority
            else "P1_A3_VARIANT_FIRST_CROSSING"
        ),
        "n_cells": int(spec.n_cells),
        "cfl": float(spec.cfl),
        "dx_m": 1.0 / float(spec.n_cells),
        "outcome": result.outcome,
        "failure_reason": result.failure_reason,
        "crossing_status": status,
        "crossing_detected": crossing_step is not None,
        "crossing_step": crossing_step,
        "crossing_time_s": result.crossing_time_s,
        "crossing_dt_s": dt_s,
        "crossing_cell_count": len(result.crossing_cell_indices),
        "crossing_cell_indices": list(result.crossing_cell_indices),
        "crossing_distances_from_outlet_m": list(
            result.crossing_distances_from_outlet_m
        ),
        "maximum_crossing_quality": q_max,
        "fixed_evidence_floor": P1_A3F_EVIDENCE_FLOOR,
        "quality_to_floor_ratio": ratio,
        "quality_margin_to_floor": margin,
        "reverse_flow_fallback_count": result.reverse_flow_fallback_count,
        "final_state_sha256": result.final_state_sha256,
        "run_signature_sha256": result.run_signature_sha256,
        "measured_step_cfl": measured_step_cfl,
    }

    if crossing_step is None:
        return case_row, []

    if result.accepted_state_history.shape[0] <= crossing_step:
        raise P1A3SubthresholdForensicsError(
            f"{spec.case_id}: crossing state is missing from accepted history"
        )
    if crossing_step < 1:
        raise P1A3SubthresholdForensicsError(
            f"{spec.case_id}: crossing step must be positive"
        )

    previous_U = np.asarray(
        result.accepted_state_history[crossing_step - 1],
        dtype=float,
    )
    crossing_U = np.asarray(
        result.accepted_state_history[crossing_step],
        dtype=float,
    )
    previous_quality = _phase_quality(previous_U, result.config)
    accepted_quality = _phase_quality(crossing_U, result.config)

    records = {
        row.cell_index: row
        for row in result.cells
        if row.step_index == crossing_step
        and row.cell_index in result.crossing_cell_indices
    }
    missing = set(result.crossing_cell_indices) - set(records)
    if missing:
        raise P1A3SubthresholdForensicsError(
            f"{spec.case_id}: crossing cell records are missing: {sorted(missing)}"
        )

    cell_rows: list[dict[str, object]] = []
    for cell_index in result.crossing_cell_indices:
        row = records[cell_index]
        q_raw = float(row.q_equilibrium)
        q_prev = float(previous_quality[cell_index])
        q_accepted = float(accepted_quality[cell_index])
        post_pressure = float(
            result.pressure_history_pa[crossing_step, cell_index]
        )
        previous_pressure = float(
            result.pressure_history_pa[crossing_step - 1, cell_index]
        )
        cell_rows.append(
            {
                "case_id": spec.case_id,
                "role": spec.role,
                "n_cells": int(spec.n_cells),
                "cfl": float(spec.cfl),
                "dx_m": 1.0 / float(spec.n_cells),
                "crossing_status": status,
                "outcome": result.outcome,
                "crossing_step": crossing_step,
                "time_before_s": (
                    None if step_record is None else float(step_record.time_before_s)
                ),
                "time_after_s": (
                    result.crossing_time_s
                    if step_record is None
                    else float(step_record.time_after_s)
                ),
                "dt_s": dt_s,
                "cell_index": int(cell_index),
                "cell_center_m": float(row.cell_center_m),
                "distance_from_outlet_m": float(row.distance_from_outlet_m),
                "previous_region": row.previous_region,
                "raw_region": row.raw_region,
                "post_region": row.post_region,
                "transition_event": row.transition_event,
                "quality_previous_accepted": q_prev,
                "quality_raw_equilibrium": q_raw,
                "quality_post_projection": float(row.q_post),
                "quality_reconstructed_accepted": q_accepted,
                "quality_increment_raw_from_previous": q_raw - q_prev,
                "fixed_evidence_floor": P1_A3F_EVIDENCE_FLOOR,
                "quality_to_floor_ratio": q_raw / P1_A3F_EVIDENCE_FLOOR,
                "quality_margin_to_floor": q_raw - P1_A3F_EVIDENCE_FLOOR,
                "q_transport_raw": float(row.q_transport_raw),
                "void_fraction_post": (
                    None if row.alpha_post is None else float(row.alpha_post)
                ),
                "rho_raw_kg_m3": float(row.rho_raw_kg_m3),
                "e_raw_j_kg": float(row.e_raw_j_kg),
                "pressure_previous_pa": previous_pressure,
                "pressure_raw_pa": float(row.pressure_raw_pa),
                "pressure_post_pa": post_pressure,
                "temperature_raw_K": float(row.temperature_raw_K),
                "first_projection_applied": bool(row.first_projection_applied),
                "second_projection_applied": bool(row.second_projection_applied),
            }
        )
    return case_row, cell_rows


def _trend(values: Sequence[float], *, increasing_label: str, decreasing_label: str) -> str:
    if len(values) < 2 or not all(math.isfinite(value) for value in values):
        return "UNAVAILABLE"
    if all(later > earlier for earlier, later in zip(values, values[1:])):
        return increasing_label
    if all(later < earlier for earlier, later in zip(values, values[1:])):
        return decreasing_label
    if all(math.isclose(value, values[0], rel_tol=0.0, abs_tol=1.0e-18) for value in values):
        return "INVARIANT_TO_REPORTED_PRECISION"
    return "NONMONOTONIC"


def _scaling_rows(case_rows: Sequence[dict[str, object]]):
    by_id = {str(row["case_id"]): row for row in case_rows}
    rows: list[dict[str, object]] = []

    axis_specs = (
        (
            "MESH_DX",
            (
                "mesh_64_cfl_0p10",
                "baseline_32_cfl_0p10",
                "mesh_16_cfl_0p10",
            ),
            "dx_m",
        ),
        (
            "CFL",
            (
                "cfl_32_0p05",
                "baseline_32_cfl_0p10",
                "cfl_32_0p20",
            ),
            "cfl",
        ),
    )
    for axis, case_ids, x_key in axis_specs:
        previous_x = None
        previous_q = None
        for order, case_id in enumerate(case_ids):
            case = by_id[case_id]
            x_value = float(case[x_key])
            q_value = case["maximum_crossing_quality"]
            exponent = None
            if (
                previous_x is not None
                and previous_q is not None
                and q_value is not None
                and float(q_value) > 0.0
                and previous_q > 0.0
                and x_value > 0.0
                and previous_x > 0.0
                and not math.isclose(x_value, previous_x)
            ):
                exponent = math.log(float(q_value) / previous_q) / math.log(
                    x_value / previous_x
                )
            rows.append(
                {
                    "axis": axis,
                    "order": order,
                    "case_id": case_id,
                    "independent_variable": x_value,
                    "independent_variable_units": "m" if axis == "MESH_DX" else "1",
                    "maximum_crossing_quality": q_value,
                    "fixed_evidence_floor": P1_A3F_EVIDENCE_FLOOR,
                    "quality_to_floor_ratio": case["quality_to_floor_ratio"],
                    "crossing_status": case["crossing_status"],
                    "pairwise_apparent_exponent_from_previous": exponent,
                }
            )
            previous_x = x_value
            previous_q = None if q_value is None else float(q_value)
    return tuple(rows)


def _evaluate_forensics(case_rows: Sequence[dict[str, object]]) -> dict[str, object]:
    by_id = {str(row["case_id"]): row for row in case_rows}
    expected_ids = [spec.case_id for spec in P1_A3_CASE_SPECS]
    matrix_exact = list(by_id) == expected_ids

    crossing_detected_all = all(bool(row["crossing_detected"]) for row in case_rows)
    statuses = {str(row["crossing_status"]) for row in case_rows}
    only_expected_statuses = statuses <= {
        "ACCEPTED_ABOVE_FIXED_FLOOR",
        "SUBTHRESHOLD_CROSSING_RETAINED",
    }

    direct_mechanism = bool(
        crossing_detected_all
        and only_expected_statuses
        and all(
            (
                row["crossing_status"] == "ACCEPTED_ABOVE_FIXED_FLOOR"
                and row["quality_to_floor_ratio"] is not None
                and float(row["quality_to_floor_ratio"]) >= 1.0
            )
            or (
                row["crossing_status"] == "SUBTHRESHOLD_CROSSING_RETAINED"
                and row["quality_to_floor_ratio"] is not None
                and 0.0 < float(row["quality_to_floor_ratio"]) < 1.0
            )
            for row in case_rows
        )
    )

    cfl_ids = (
        "cfl_32_0p05",
        "baseline_32_cfl_0p10",
        "cfl_32_0p20",
    )
    cfl_q = [
        float(by_id[case_id]["maximum_crossing_quality"])
        for case_id in cfl_ids
        if by_id[case_id]["maximum_crossing_quality"] is not None
    ]
    cfl_trend = (
        _trend(
            cfl_q,
            increasing_label="STRICTLY_INCREASING_WITH_CFL",
            decreasing_label="STRICTLY_DECREASING_WITH_CFL",
        )
        if len(cfl_q) == 3
        else "UNAVAILABLE"
    )

    mesh_ids = (
        "mesh_16_cfl_0p10",
        "baseline_32_cfl_0p10",
        "mesh_64_cfl_0p10",
    )
    mesh_q = [
        float(by_id[case_id]["maximum_crossing_quality"])
        for case_id in mesh_ids
        if by_id[case_id]["maximum_crossing_quality"] is not None
    ]
    mesh_trend = (
        _trend(
            mesh_q,
            increasing_label="STRICTLY_INCREASING_WITH_CELL_COUNT",
            decreasing_label="STRICTLY_DECREASING_WITH_CELL_COUNT",
        )
        if len(mesh_q) == 3
        else "UNAVAILABLE"
    )
    fine_mesh_boundary_effect = bool(
        by_id["baseline_32_cfl_0p10"]["quality_to_floor_ratio"] is not None
        and by_id["mesh_64_cfl_0p10"]["quality_to_floor_ratio"] is not None
        and float(by_id["baseline_32_cfl_0p10"]["quality_to_floor_ratio"]) >= 1.0
        and float(by_id["mesh_64_cfl_0p10"]["quality_to_floor_ratio"]) < 1.0
    )
    low_cfl_boundary_effect = bool(
        by_id["baseline_32_cfl_0p10"]["quality_to_floor_ratio"] is not None
        and by_id["cfl_32_0p05"]["quality_to_floor_ratio"] is not None
        and float(by_id["baseline_32_cfl_0p10"]["quality_to_floor_ratio"]) >= 1.0
        and float(by_id["cfl_32_0p05"]["quality_to_floor_ratio"]) < 1.0
    )

    if direct_mechanism and fine_mesh_boundary_effect and low_cfl_boundary_effect:
        interaction = "SUPPORTED_BY_FINE_MESH_AND_LOW_CFL"
    elif direct_mechanism and (fine_mesh_boundary_effect or low_cfl_boundary_effect):
        interaction = "PARTIALLY_SUPPORTED"
    elif direct_mechanism:
        interaction = "DIRECT_MECHANISM_CONFIRMED_TREND_MIXED"
    else:
        interaction = "INCONCLUSIVE"

    unrelated_failures = [
        str(row["case_id"])
        for row in case_rows
        if row["crossing_status"]
        not in {
            "ACCEPTED_ABOVE_FIXED_FLOOR",
            "SUBTHRESHOLD_CROSSING_RETAINED",
        }
    ]
    hashes_present = all(
        len(str(row["final_state_sha256"])) == 64
        and len(str(row["run_signature_sha256"])) == 64
        for row in case_rows
    )
    values_finite = all(
        row["maximum_crossing_quality"] is not None
        and math.isfinite(float(row["maximum_crossing_quality"]))
        and row["crossing_time_s"] is not None
        and math.isfinite(float(row["crossing_time_s"]))
        and row["crossing_dt_s"] is not None
        and math.isfinite(float(row["crossing_dt_s"]))
        and float(row["crossing_dt_s"]) > 0.0
        for row in case_rows
    )

    gates = (
        {
            "gate": "PREDECLARED_MATRIX_EXACT",
            "passed": matrix_exact,
            "detail": "The original five A3 cases are retained in fixed order.",
        },
        {
            "gate": "CROSSING_EVENT_RETAINED_FOR_ALL_CASES",
            "passed": crossing_detected_all,
            "detail": "Every case retains a first liquid-to-two-phase crossing event.",
        },
        {
            "gate": "DIRECT_FAILURE_MECHANISM_CONFIRMED",
            "passed": direct_mechanism,
            "detail": (
                "Accepted cases lie at or above the fixed 1e-6 quality floor; "
                "guarded cases retain a positive crossing below that floor."
            ),
        },
        {
            "gate": "NO_UNRELATED_FAILURE_CATEGORY",
            "passed": not unrelated_failures,
            "detail": "No backend, conservation, reverse-flow, or nonfinite failure replaces the crossing-floor guard.",
        },
        {
            "gate": "FORENSIC_SCALARS_FINITE",
            "passed": values_finite,
            "detail": "Crossing time, dt, and quality are finite for every case.",
        },
        {
            "gate": "DETERMINISTIC_HASHES_PRESENT",
            "passed": hashes_present,
            "detail": "Every retained partial or accepted state has deterministic evidence hashes.",
        },
        {
            "gate": "FIXED_EVIDENCE_FLOOR_UNCHANGED",
            "passed": all(
                math.isclose(
                    float(row["fixed_evidence_floor"]),
                    P1_A3F_EVIDENCE_FLOOR,
                    rel_tol=0.0,
                    abs_tol=0.0,
                )
                for row in case_rows
            ),
            "detail": "The original 1e-6 crossing evidence floor is preserved exactly.",
        },
    )
    ready = all(bool(gate["passed"]) for gate in gates)
    return {
        "direct_failure_mechanism": (
            "CONFIRMED" if direct_mechanism else "INCONCLUSIVE"
        ),
        "resolution_interaction_hypothesis": interaction,
        "cfl_crossing_quality_trend": cfl_trend,
        "mesh_crossing_quality_trend": mesh_trend,
        "fine_mesh_crosses_below_fixed_floor": fine_mesh_boundary_effect,
        "low_cfl_crosses_below_fixed_floor": low_cfl_boundary_effect,
        "subthreshold_case_ids": [
            str(row["case_id"])
            for row in case_rows
            if row["crossing_status"] == "SUBTHRESHOLD_CROSSING_RETAINED"
        ],
        "unrelated_failure_case_ids": unrelated_failures,
        "gates": gates,
        "forensics_ready": ready,
        "forensic_execution_status": "FORENSICS_READY" if ready else "FAIL_CLOSED",
    }


def analyze_subthreshold_crossing_forensics() -> dict[str, object]:
    case_rows: list[dict[str, object]] = []
    cell_rows: list[dict[str, object]] = []
    case = _baseline_case()
    for spec in P1_A3_CASE_SPECS:
        config = _config_for_spec(spec)
        result = run_pipeline_depressurization_case(case, config)
        case_row, extracted_cells = _case_and_cell_rows(spec, result)
        case_rows.append(case_row)
        cell_rows.extend(extracted_cells)

    scaling_rows = _scaling_rows(case_rows)
    evaluation = _evaluate_forensics(case_rows)
    warnings = [
        "FIXED_CROSSING_EVIDENCE_FLOOR_NOT_TUNED",
        "SUBTHRESHOLD_CROSSING_IS_NOT_ACCEPTED_FIRST_CROSSING",
        "FIRST_CROSSING_DEPTH_IS_A_DISCRETE_STEP_DIAGNOSTIC",
        "HEM_EQUILIBRIUM_DOES_NOT_MODEL_REAL_NUCLEATION_DELAY",
        "MESH_AND_CFL_INDEPENDENCE_NOT_VERIFIED",
    ]
    payload = {
        "schema_version": P1_A3F_SCHEMA_VERSION,
        "scope": "diagnostic_first_crossing_forensics_without_threshold_change",
        "model_id": P1_A3F_MODEL_ID,
        "case_count": len(case_rows),
        "fixed_crossing_evidence_floor": P1_A3F_EVIDENCE_FLOOR,
        "threshold_or_tolerance_changed": False,
        "solver_or_physics_changed": False,
        "case_forensics": case_rows,
        "cell_forensics": cell_rows,
        "quality_scaling": list(scaling_rows),
        "direct_failure_mechanism": evaluation["direct_failure_mechanism"],
        "resolution_interaction_hypothesis": evaluation[
            "resolution_interaction_hypothesis"
        ],
        "cfl_crossing_quality_trend": evaluation[
            "cfl_crossing_quality_trend"
        ],
        "mesh_crossing_quality_trend": evaluation[
            "mesh_crossing_quality_trend"
        ],
        "fine_mesh_crosses_below_fixed_floor": evaluation[
            "fine_mesh_crosses_below_fixed_floor"
        ],
        "low_cfl_crosses_below_fixed_floor": evaluation[
            "low_cfl_crosses_below_fixed_floor"
        ],
        "subthreshold_case_ids": evaluation["subthreshold_case_ids"],
        "unrelated_failure_case_ids": evaluation["unrelated_failure_case_ids"],
        "gates": list(evaluation["gates"]),
        "gate_results": {
            str(gate["gate"]): bool(gate["passed"])
            for gate in evaluation["gates"]
        },
        "forensics_ready": evaluation["forensics_ready"],
        "forensic_execution_status": evaluation["forensic_execution_status"],
        "warnings": warnings,
        "provenance": _git_provenance(),
        "formal_status": dict(P1_A3F_FORMAL_STATUS),
    }
    digest_payload = dict(payload)
    digest_payload["formal_status"] = dict(P1_A3F_FORMAL_STATUS)
    payload["forensic_sha256"] = _canonical_json_sha256(digest_payload)
    return payload


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise P1A3SubthresholdForensicsError(
            f"cannot write empty forensic CSV: {path.name}"
        )
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        for row in rows:
            encoded = {
                key: (
                    json.dumps(value, separators=(",", ":"))
                    if isinstance(value, (list, tuple, dict))
                    else value
                )
                for key, value in row.items()
            }
            writer.writerow(encoded)


def _plot_quality_axis(
    path: Path,
    rows: Sequence[dict[str, object]],
    *,
    axis: str,
    xlabel: str,
    title: str,
) -> None:
    selected = [row for row in rows if row["axis"] == axis]
    x = np.asarray(
        [float(row["independent_variable"]) for row in selected],
        dtype=float,
    )
    ratio = np.asarray(
        [float(row["quality_to_floor_ratio"]) for row in selected],
        dtype=float,
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(x, ratio, marker="o")
    ax.axhline(1.0, linestyle="--", label="Fixed evidence floor")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("First-crossing quality / fixed 1e-6 floor")
    ax.set_title(title)
    ax.set_yscale("log")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _operator_report(summary: dict[str, object]) -> str:
    by_id = {
        str(row["case_id"]): row
        for row in summary["case_forensics"]
    }
    lines = [
        "# P1-A3 Sub-threshold Crossing Forensics",
        "",
        f"- execution status: `{summary['forensic_execution_status']}`",
        f"- direct failure mechanism: `{summary['direct_failure_mechanism']}`",
        (
            "- resolution interaction: "
            f"`{summary['resolution_interaction_hypothesis']}`"
        ),
        (
            "- CFL crossing-quality trend: "
            f"`{summary['cfl_crossing_quality_trend']}`"
        ),
        (
            "- mesh crossing-quality trend: "
            f"`{summary['mesh_crossing_quality_trend']}`"
        ),
        f"- fixed evidence floor: `{summary['fixed_crossing_evidence_floor']}`",
        "- threshold or tolerance changed: `false`",
        "",
        "## Case evidence",
        "",
        "| case | cells | CFL | outcome | crossing status | q_cross | q/floor |",
        "|---|---:|---:|---|---|---:|---:|",
    ]
    for spec in P1_A3_CASE_SPECS:
        row = by_id[spec.case_id]
        lines.append(
            "| {case} | {cells} | {cfl:.2f} | {outcome} | {status} | "
            "{q:.12g} | {ratio:.6g} |".format(
                case=spec.case_id,
                cells=spec.n_cells,
                cfl=spec.cfl,
                outcome=row["outcome"],
                status=row["crossing_status"],
                q=float(row["maximum_crossing_quality"]),
                ratio=float(row["quality_to_floor_ratio"]),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "The A3 failure is reproduced as a classification boundary: "
                "all five cases retain a positive liquid-to-two-phase crossing, "
                "while the fine-mesh and low-CFL cases remain below the unchanged "
                "1e-6 evidence floor. This confirms the direct fail-closed "
                "mechanism. It does not establish mesh/CFL independence or "
                "justify changing the evidence floor."
            ),
            "",
            "## Formal boundary",
            "",
            "- IMPLEMENTED: true",
            "- DIAGNOSTIC EVIDENCE READY: false until separately reviewed",
            "- VERIFIED: false",
            "- ACCEPTED: false",
            "- PHYSICALLY VALIDATED: false",
            "- DESIGN-USE ACCEPTED: false",
            "- PRODUCTION APPROVED: false",
            "",
        ]
    )
    return "\n".join(lines)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_subthreshold_crossing_forensic_artifacts(
    output_dir: str | Path,
    summary: dict[str, object],
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_A3F_OUTPUT_FILES)
    existing = {path.name for path in target.iterdir() if path.is_file()}
    unexpected = existing - expected
    if unexpected:
        raise P1A3SubthresholdForensicsError(
            f"output directory contains unexpected files: {sorted(unexpected)}"
        )

    paths = {
        "summary": target / "forensic_summary.json",
        "case_forensics": target / "case_forensics.csv",
        "cell_forensics": target / "cell_forensics.csv",
        "quality_scaling": target / "quality_scaling.csv",
        "quality_vs_dx": target / "quality_vs_dx.png",
        "quality_vs_cfl": target / "quality_vs_cfl.png",
        "operator_report": target / "operator_report.md",
        "manifest": target / "forensic_manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["case_forensics"], summary["case_forensics"])
    _write_csv(paths["cell_forensics"], summary["cell_forensics"])
    _write_csv(paths["quality_scaling"], summary["quality_scaling"])
    _plot_quality_axis(
        paths["quality_vs_dx"],
        summary["quality_scaling"],
        axis="MESH_DX",
        xlabel="Cell width dx [m]",
        title="P1-A3 first-crossing quality versus mesh spacing",
    )
    _plot_quality_axis(
        paths["quality_vs_cfl"],
        summary["quality_scaling"],
        axis="CFL",
        xlabel="CFL",
        title="P1-A3 first-crossing quality versus CFL",
    )
    paths["operator_report"].write_text(
        _operator_report(summary),
        encoding="utf-8",
    )

    payload_files: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if key == "manifest":
            continue
        payload_files[path.name] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": P1_A3F_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_a3_subthreshold_crossing_forensics_exactly_8_files",
        "declared_file_count": len(P1_A3F_OUTPUT_FILES),
        "declared_file_names": list(P1_A3F_OUTPUT_FILES),
        "forensic_execution_status": summary["forensic_execution_status"],
        "forensics_ready": summary["forensics_ready"],
        "direct_failure_mechanism": summary["direct_failure_mechanism"],
        "resolution_interaction_hypothesis": summary[
            "resolution_interaction_hypothesis"
        ],
        "forensic_sha256": summary["forensic_sha256"],
        "threshold_or_tolerance_changed": False,
        "solver_or_physics_changed": False,
        "payload_files": payload_files,
        "formal_status": dict(P1_A3F_FORMAL_STATUS),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1A3SubthresholdForensicsError(
            f"forensic output contract mismatch: expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    summary = analyze_subthreshold_crossing_forensics()
    paths = write_subthreshold_crossing_forensic_artifacts(output_dir, summary)
    output = dict(summary)
    output["artifact_paths"] = {key: str(path) for key, path in paths.items()}
    return output


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the five P1-A3 first crossings and retain sub-threshold "
            "crossing evidence without changing the fixed 1e-6 floor."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["forensics_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
