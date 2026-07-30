"""Complete the locked Stage 7 Gate 8 post-crossing CFL sequence.

This verification-only orchestrator executes the fixed 32-cell sequence
CFL=0.10 / 0.05 / 0.025 without changing the production solver, Rusanov
flux, prescribed boundary, phase classifier, equilibrium sound-speed formula,
quality projection, threshold, or tolerance.  The authoritative Gate 6 identity
must pass before either refined column is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .hem_pipeline_phase_chatter_diagnosis import (
    PhaseChatterDiagnosisResult,
    run_phase_chatter_diagnosis,
)
from .hem_pipeline_post_crossing_cfl_sensitivity import (
    BASELINE_CASE_ID,
    CHATTER_CELL,
    GATE8_CFL_SEQUENCE,
    PHYSICAL_CHECKPOINTS_S,
    Gate8ColumnResult,
    HEMGate8CflSensitivityError,
    _gate6_identity_matches,
    _git_provenance,
    _run_gate6_column,
    _run_refined_column,
)

FULL_APPROVAL_BOUNDARY = {
    "Gate_8_execution_complete": True,
    "post_crossing_CFL_sensitivity_characterized": False,
    "CFL_independent_post_crossing_verified": False,
    "mesh_independent_post_crossing_verified": False,
    "post_crossing_propagation_approved": False,
    "phase_chatter_root_cause_approved": False,
    "chatter_mitigation_authorized": False,
    "near_saturation_acoustic_continuity_approved": False,
    "two_phase_acoustic_accuracy_band_approved": False,
    "Gate_P2_passed": False,
    "physical_validation": False,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}

PERMITTED_CLASSIFICATIONS = (
    "POST_CROSSING_FRONT_TREND_STABLE_ACROSS_CFL",
    "POST_CROSSING_FRONT_CFL_SENSITIVE",
    "CHATTER_PERSISTS_ACROSS_CFL",
    "CHATTER_FREQUENCY_CFL_SENSITIVE",
    "CFL_REFINEMENT_REDUCES_CHATTER",
    "CFL_REFINEMENT_AMPLIFIES_CHATTER",
    "CFL_SEQUENCE_NON_MONOTONE",
    "FIXED_HORIZON_OUTCOME_DIVERGENCE",
    "PROJECTION_BUDGET_STABLE_ACROSS_CFL",
    "POST_CROSSING_CFL_REVIEW_INCONCLUSIVE",
)


@dataclass(frozen=True)
class Gate8FullResult:
    columns: tuple[Gate8ColumnResult, ...]
    classifications: tuple[str, ...]
    classification_rationale: Mapping[str, str]
    gate7_reference: PhaseChatterDiagnosisResult
    provenance: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        order = tuple(column.cfl for column in self.columns)
        complete = order == GATE8_CFL_SEQUENCE
        accepted_complete = [
            column
            for column in self.columns
            if column.baseline.outcome == "ACCEPTED_FIRST_CROSSING"
            and column.continuation_outcome == "COMPLETED_FIXED_CHECKPOINTS"
            and all(row.reached for row in column.checkpoints)
        ]
        return {
            "schema_version": "stage7_gate8_full_cfl_sequence_v1",
            "scope": "verification_only",
            "case_id": BASELINE_CASE_ID,
            "mesh_cells": 32,
            "locked_full_cfl_sequence": list(GATE8_CFL_SEQUENCE),
            "implemented_cfl_columns": list(order),
            "pending_cfl_columns": [],
            "physical_checkpoints_s": dict(PHYSICAL_CHECKPOINTS_S),
            "gate6_identity_reproduced_exactly": bool(
                self.columns and _gate6_identity_matches(self.columns[0])
            ),
            "full_gate8_sequence_executed": complete,
            "formal_outcome_comparison_complete": complete,
            "cross_cfl_interpretation_authorized": complete,
            "post_crossing_comparison_available": len(accepted_complete) >= 2,
            "cross_cfl_classifications": list(self.classifications),
            "classification_rationale": dict(self.classification_rationale),
            "columns": [column.summary() for column in self.columns],
            "gate7_reference": {
                "cell30_toggle_count": self.gate7_reference.cell_toggle_counts[
                    CHATTER_CELL
                ],
                "transition_event_record_count": len(
                    self.gate7_reference.transition_events
                ),
                "classifications": list(self.gate7_reference.classifications),
                "correlation_metrics": dict(
                    self.gate7_reference.correlation_metrics
                ),
            },
            "provenance": dict(self.provenance),
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "boundary_changed": False,
            "phase_classifier_changed": False,
            "sound_speed_formula_changed": False,
            "quality_projection_changed": False,
            "threshold_or_tolerance_tuned": False,
            **FULL_APPROVAL_BOUNDARY,
        }


def _nonmonotone(values: Sequence[float | None]) -> bool:
    if len(values) != 3 or any(value is None or not np.isfinite(value) for value in values):
        return False
    differences = [float(right) - float(left) for left, right in zip(values, values[1:])]
    return differences[0] * differences[1] < 0.0


def _frequency(column: Gate8ColumnResult) -> float | None:
    if not column.steps or column.baseline.crossing_time_s is None:
        return None
    elapsed = column.steps[-1].time_after_s - column.baseline.crossing_time_s
    if elapsed <= 0.0:
        return None
    return column.region_toggle_counts[CHATTER_CELL] / elapsed


def _budgets_stable(column: Gate8ColumnResult) -> bool:
    if not column.steps:
        return False
    cfg = column.config
    return all(
        step.second_projection_noop
        and abs(step.boundary_mass_residual_kg)
        <= cfg.mass_budget_absolute_tolerance_kg
        + cfg.mass_budget_relative_tolerance * abs(step.mass_total_kg)
        and abs(step.boundary_momentum_residual_kg_m_s)
        <= cfg.momentum_budget_absolute_tolerance_kg_m_s
        + cfg.momentum_budget_relative_tolerance
        * abs(step.momentum_total_kg_m_s)
        and abs(step.boundary_energy_residual_J)
        <= cfg.energy_budget_absolute_tolerance_J
        + cfg.energy_budget_relative_tolerance * abs(step.energy_total_J)
        and abs(step.phase_vapor_residual_kg)
        <= cfg.vapor_budget_absolute_tolerance_kg
        for step in column.steps
    )


def _classify(columns: Sequence[Gate8ColumnResult]) -> tuple[tuple[str, ...], dict[str, str]]:
    if tuple(column.cfl for column in columns) != GATE8_CFL_SEQUENCE:
        raise HEMGate8CflSensitivityError("the locked full CFL sequence is incomplete")

    labels: list[str] = []
    rationale: dict[str, str] = {}
    outcomes = tuple(column.baseline.outcome for column in columns)
    if len(set(outcomes)) > 1:
        labels.append("FIXED_HORIZON_OUTCOME_DIVERGENCE")
        rationale["FIXED_HORIZON_OUTCOME_DIVERGENCE"] = (
            "The fixed 0.10/0.05/0.025 columns do not retain the same formal "
            "first-crossing outcome."
        )

    q_values = [column.baseline.maximum_crossing_quality for column in columns]
    if _nonmonotone(q_values):
        labels.append("CFL_SEQUENCE_NON_MONOTONE")
        rationale["CFL_SEQUENCE_NON_MONOTONE"] = (
            "Maximum candidate crossing quality changes direction across the fixed "
            "CFL sequence."
        )

    comparable = [
        column
        for column in columns
        if column.baseline.outcome == "ACCEPTED_FIRST_CROSSING"
        and column.continuation_outcome == "COMPLETED_FIXED_CHECKPOINTS"
        and all(row.reached for row in column.checkpoints)
    ]
    if len(comparable) == len(columns):
        positions = {
            name: [
                next(row for row in column.checkpoints if row.checkpoint == name)
                .furthest_upstream_distance_from_outlet_m
                for column in columns
            ]
            for name, _ in PHYSICAL_CHECKPOINTS_S
        }
        if all(len(set(values)) == 1 for values in positions.values()):
            labels.append("POST_CROSSING_FRONT_TREND_STABLE_ACROSS_CFL")
            rationale["POST_CROSSING_FRONT_TREND_STABLE_ACROSS_CFL"] = (
                "All fixed checkpoint front positions are identical across CFL."
            )
        else:
            labels.append("POST_CROSSING_FRONT_CFL_SENSITIVE")
            rationale["POST_CROSSING_FRONT_CFL_SENSITIVE"] = (
                "At least one fixed checkpoint front position differs across CFL."
            )

        frequencies = [_frequency(column) for column in columns]
        if all(value is not None and value > 0.0 for value in frequencies):
            labels.append("CHATTER_PERSISTS_ACROSS_CFL")
            rationale["CHATTER_PERSISTS_ACROSS_CFL"] = (
                "Cell 30 changes region in every completed CFL column."
            )
            if len({float(value) for value in frequencies if value is not None}) > 1:
                labels.append("CHATTER_FREQUENCY_CFL_SENSITIVE")
                rationale["CHATTER_FREQUENCY_CFL_SENSITIVE"] = (
                    "Cell-30 region-change frequency differs across CFL."
                )
            numeric = [float(value) for value in frequencies if value is not None]
            if numeric[0] > numeric[1] > numeric[2]:
                labels.append("CFL_REFINEMENT_REDUCES_CHATTER")
                rationale["CFL_REFINEMENT_REDUCES_CHATTER"] = (
                    "Region-change frequency decreases strictly with CFL refinement."
                )
            elif numeric[0] < numeric[1] < numeric[2]:
                labels.append("CFL_REFINEMENT_AMPLIFIES_CHATTER")
                rationale["CFL_REFINEMENT_AMPLIFIES_CHATTER"] = (
                    "Region-change frequency increases strictly with CFL refinement."
                )
            elif _nonmonotone(numeric):
                if "CFL_SEQUENCE_NON_MONOTONE" not in labels:
                    labels.append("CFL_SEQUENCE_NON_MONOTONE")
                rationale["CFL_SEQUENCE_NON_MONOTONE"] = (
                    "A reviewed metric changes direction across the fixed CFL sequence."
                )

        if all(_budgets_stable(column) for column in columns):
            labels.append("PROJECTION_BUDGET_STABLE_ACROSS_CFL")
            rationale["PROJECTION_BUDGET_STABLE_ACROSS_CFL"] = (
                "Every successful step in all three columns passes the fixed projection "
                "and conservative/vapor-budget guards."
            )
    else:
        labels.append("POST_CROSSING_CFL_REVIEW_INCONCLUSIVE")
        rationale["POST_CROSSING_CFL_REVIEW_INCONCLUSIVE"] = (
            "Fewer than three columns provide comparable accepted post-crossing "
            "histories through T1-T4; no post-crossing convergence claim is valid."
        )

    if not labels:
        labels.append("POST_CROSSING_CFL_REVIEW_INCONCLUSIVE")
        rationale["POST_CROSSING_CFL_REVIEW_INCONCLUSIVE"] = (
            "No stronger permitted classification is supported."
        )
    if any(label not in PERMITTED_CLASSIFICATIONS for label in labels):
        raise HEMGate8CflSensitivityError("an unpermitted classification was generated")
    return tuple(labels), rationale


def run_gate8_full_cfl_sequence() -> Gate8FullResult:
    gate6 = _run_gate6_column()
    if not _gate6_identity_matches(gate6):
        raise HEMGate8CflSensitivityError(
            "CFL 0.10 did not reproduce Gate 6; lower-CFL execution is prohibited"
        )
    cfl_0p05 = _run_refined_column(0.05)
    cfl_0p025 = _run_refined_column(0.025)
    columns = (gate6, cfl_0p05, cfl_0p025)
    classifications, rationale = _classify(columns)
    gate7_reference = run_phase_chatter_diagnosis()
    return Gate8FullResult(
        columns=columns,
        classifications=classifications,
        classification_rationale=rationale,
        gate7_reference=gate7_reference,
        provenance=_git_provenance(),
    )


def _flatten(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    if any(list(row) != fieldnames for row in rows):
        raise HEMGate8CflSensitivityError(f"inconsistent fields for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten(value) for key, value in row.items()})


def _case_rows(result: Gate8FullResult) -> list[dict[str, object]]:
    return [
        {
            "cfl": column.cfl,
            "implementation_status": "EXECUTED_FULL_SEQUENCE_COLUMN",
            "first_crossing_outcome": column.baseline.outcome,
            "first_crossing_step": column.baseline.crossing_step,
            "first_crossing_time_s": column.baseline.crossing_time_s,
            "first_crossing_cells": column.baseline.crossing_cell_indices,
            "first_crossing_distances_from_outlet_m": (
                column.baseline.crossing_distances_from_outlet_m
            ),
            "maximum_crossing_quality": column.baseline.maximum_crossing_quality,
            "continuation_outcome": column.continuation_outcome,
            "successful_post_crossing_step_count": len(column.steps),
            "reached_checkpoints": tuple(
                row.checkpoint for row in column.checkpoints if row.reached
            ),
            "cell30_region_changes": column.region_toggle_counts[CHATTER_CELL],
            "cell30_region_changes_per_s": _frequency(column),
            "last_valid_state_sha256": column.last_valid_state_sha256,
            "failure_category": column.failure_category,
            "failure_reason": column.failure_reason,
        }
        for column in result.columns
    ]


def _safe_ratio(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or reference == 0.0:
        return None
    return float(value / reference)


def _comparison_rows(result: Gate8FullResult) -> list[dict[str, object]]:
    reference = result.columns[0]
    ref_time = reference.baseline.crossing_time_s
    ref_distance = (
        reference.baseline.crossing_distances_from_outlet_m[0]
        if reference.baseline.crossing_distances_from_outlet_m
        else None
    )
    ref_quality = reference.baseline.maximum_crossing_quality
    rows: list[dict[str, object]] = []
    for column in result.columns:
        time = column.baseline.crossing_time_s
        distance = (
            column.baseline.crossing_distances_from_outlet_m[0]
            if column.baseline.crossing_distances_from_outlet_m
            else None
        )
        quality = column.baseline.maximum_crossing_quality
        rows.append(
            {
                "cfl": column.cfl,
                "formal_outcome": column.baseline.outcome,
                "crossing_time_s": time,
                "crossing_time_absolute_difference_from_0p10_s": (
                    None if time is None or ref_time is None else time - ref_time
                ),
                "crossing_time_ratio_to_0p10": _safe_ratio(time, ref_time),
                "crossing_distance_from_outlet_m": distance,
                "crossing_distance_absolute_difference_from_0p10_m": (
                    None
                    if distance is None or ref_distance is None
                    else distance - ref_distance
                ),
                "crossing_distance_ratio_to_0p10": _safe_ratio(distance, ref_distance),
                "maximum_crossing_quality": quality,
                "maximum_crossing_quality_absolute_difference_from_0p10": (
                    quality - ref_quality
                ),
                "maximum_crossing_quality_ratio_to_0p10": _safe_ratio(
                    quality, ref_quality
                ),
                "post_crossing_comparison_available": bool(
                    column.steps and all(row.reached for row in column.checkpoints)
                ),
            }
        )
    return rows


def _transition_rows(result: Gate8FullResult) -> list[dict[str, object]]:
    return [
        asdict(row)
        for column in result.columns
        for row in column.focused_cells
        if row.previous_region != row.post_region
    ]


def _figure_metadata(result: Gate8FullResult) -> dict[str, str]:
    return {
        "analysis_id": "stage7_gate8_full_cfl_sequence",
        "case": BASELINE_CASE_ID,
        "model": "HEM",
        "backend": "CoolProp",
        "version": str(result.provenance.get("property_backend_version", "")),
        "source_git_sha": str(result.provenance.get("source_git_sha", "")),
    }


def _write_figures(target: Path, result: Gate8FullResult) -> dict[str, Path]:
    import matplotlib.pyplot as plt

    metadata = _figure_metadata(result)
    paths: dict[str, Path] = {}

    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    for column in result.columns:
        if not column.steps or column.baseline.crossing_time_s is None:
            continue
        elapsed = [
            step.time_after_s - column.baseline.crossing_time_s
            for step in column.steps
        ]
        position = [
            np.nan
            if step.furthest_upstream_distance_from_outlet_m is None
            else step.furthest_upstream_distance_from_outlet_m
            for step in column.steps
        ]
        ax.plot(elapsed, position, marker=".", label=f"CFL {column.cfl:g}")
    ax.set_xlabel("elapsed time after accepted crossing [s]")
    ax.set_ylabel("furthest upstream two-phase distance from outlet [m]")
    ax.set_title("Gate 8 front position versus physical time")
    ax.grid(True, alpha=0.3)
    if ax.lines:
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No accepted post-crossing history", ha="center")
    fig.tight_layout()
    paths["front"] = target / "front_position_vs_time.png"
    fig.savefig(paths["front"], dpi=180, metadata=metadata)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    second = ax.twinx()
    for column in result.columns:
        if not column.steps or column.baseline.crossing_time_s is None:
            continue
        elapsed = [
            step.time_after_s - column.baseline.crossing_time_s
            for step in column.steps
        ]
        ax.plot(
            elapsed,
            [step.maximum_equilibrium_quality for step in column.steps],
            label=f"q max CFL {column.cfl:g}",
        )
        second.plot(
            elapsed,
            [step.maximum_void_fraction for step in column.steps],
            linestyle="--",
            label=f"alpha max CFL {column.cfl:g}",
        )
    ax.set_xlabel("elapsed time after accepted crossing [s]")
    ax.set_ylabel("maximum equilibrium quality")
    second.set_ylabel("maximum void fraction")
    ax.set_title("Quality and void fraction versus physical time")
    lines = ax.lines + second.lines
    if lines:
        ax.legend(lines, [line.get_label() for line in lines])
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    paths["quality"] = target / "quality_void_fraction_vs_time.png"
    fig.savefig(paths["quality"], dpi=180, metadata=metadata)
    plt.close(fig)

    rows = [
        row
        for row in result.gate7_reference.focused_cells
        if row.cell_index == CHATTER_CELL
        and row.state_stage == "post_projection_accepted"
    ]
    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    if rows:
        origin = rows[0].time_s
        x = np.asarray([row.time_s - origin for row in rows], dtype=float)
        phase = np.asarray(
            [1.0 if row.phase_class == "OPEN_TWO_PHASE" else 0.0 for row in rows]
        )
        de = np.asarray([row.delta_e_from_saturated_liquid_j_kg for row in rows])
        dv = np.asarray([row.delta_v_from_saturated_liquid_m3_kg for row in rows])
        de_scale = max(float(np.max(np.abs(de))), 1.0)
        dv_scale = max(float(np.max(np.abs(dv))), 1.0e-30)
        ax.step(x, phase, where="post", label="phase: 1=two-phase")
        ax.plot(x, de / de_scale, label="Delta e_sat normalized")
        ax.plot(x, dv / dv_scale, label="Delta v_sat normalized")
        second = ax.twinx()
        second.plot(
            x,
            [row.sound_speed_m_s for row in rows],
            linestyle="--",
            label="sound speed",
        )
        second.set_ylabel("sound speed [m/s]")
        lines = ax.lines + second.lines
        ax.legend(lines, [line.get_label() for line in lines])
    else:
        ax.text(0.5, 0.5, "No Gate 7 cell-30 reference history", ha="center")
    ax.axhline(0.0)
    ax.set_xlabel("elapsed time in Gate 7 reference [s]")
    ax.set_ylabel("phase / normalized saturation margins")
    ax.set_title("Cell 30 phase, acoustic branch, and saturation margins")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    paths["cell30"] = target / "cell30_phase_acoustic_margin.png"
    fig.savefig(paths["cell30"], dpi=180, metadata=metadata)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    frequencies = [_frequency(column) for column in result.columns]
    values = [np.nan if value is None else value * 1.0e-4 for value in frequencies]
    bars = ax.bar([str(column.cfl) for column in result.columns], values)
    for bar, column, value in zip(bars, result.columns, values):
        label = (
            column.baseline.outcome
            if np.isnan(value)
            else f"{value:.6g} changes / 1e-4 s"
        )
        ax.text(bar.get_x() + bar.get_width() / 2, 0 if np.isnan(value) else value, label,
                ha="center", va="bottom", rotation=15)
    ax.set_xlabel("CFL")
    ax.set_ylabel("cell-30 region changes per 1e-4 s")
    ax.set_title("Chatter-frequency comparison")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    paths["chatter"] = target / "chatter_frequency_comparison.png"
    fig.savefig(paths["chatter"], dpi=180, metadata=metadata)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    labels = ["mass", "momentum", "energy", "vapor"]
    x = np.arange(len(labels), dtype=float)
    width = 0.24
    for index, column in enumerate(result.columns):
        if column.steps:
            values = [
                max(abs(step.boundary_mass_residual_kg) for step in column.steps),
                max(
                    abs(step.boundary_momentum_residual_kg_m_s)
                    for step in column.steps
                ),
                max(abs(step.boundary_energy_residual_J) for step in column.steps),
                max(abs(step.phase_vapor_residual_kg) for step in column.steps),
            ]
        else:
            values = [np.nan] * 4
        ax.bar(x + (index - 1) * width, values, width, label=f"CFL {column.cfl:g}")
    ax.set_xticks(x, labels)
    ax.set_yscale("symlog", linthresh=1.0e-15)
    ax.set_ylabel("maximum absolute residual")
    ax.set_title("Budget-residual comparison")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    paths["budget"] = target / "budget_residual_comparison.png"
    fig.savefig(paths["budget"], dpi=180, metadata=metadata)
    plt.close(fig)
    return paths


def _report(result: Gate8FullResult) -> str:
    lines = [
        "# Stage 7 Gate 8 — Full CFL Sequence Execution",
        "",
        "```text",
        "scope:                              verification only",
        "mesh:                               32 cells",
        "executed sequence:                  0.10 / 0.05 / 0.025",
        "Gate 8 execution complete:          true",
        "post-crossing CFL characterization: false",
        "physical validation:                false",
        "design-use acceptance:              false",
        "```",
        "",
        "| CFL | first-crossing outcome | continuation | checkpoints | q max | cell 30 changes |",
        "|---:|---|---|---|---:|---:|",
    ]
    for column in result.columns:
        reached = ", ".join(
            row.checkpoint for row in column.checkpoints if row.reached
        ) or "none"
        lines.append(
            f"| {column.cfl:g} | {column.baseline.outcome} | "
            f"{column.continuation_outcome} | {reached} | "
            f"{column.baseline.maximum_crossing_quality:.17g} | "
            f"{column.region_toggle_counts[CHATTER_CELL]} |"
        )
    lines.extend(["", "## Evidence classifications", ""])
    for label in result.classifications:
        lines.append(f"- `{label}` — {result.classification_rationale[label]}")
    lines.extend(
        [
            "",
            "Gate 8 execution completion records the fixed formal outcomes. It does "
            "not approve propagation physics, root cause, physical accuracy, design "
            "use, or production activation.",
            "",
        ]
    )
    return "\n".join(lines)


def write_gate8_full_artifacts(
    output_dir: str | Path,
    result: Gate8FullResult | None = None,
) -> tuple[Gate8FullResult, dict[str, Path]]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    executed = result or run_gate8_full_cfl_sequence()
    summary = executed.summary()
    if summary["gate6_identity_reproduced_exactly"] is not True:
        raise HEMGate8CflSensitivityError("exact Gate 6 identity is required")
    if summary["full_gate8_sequence_executed"] is not True:
        raise HEMGate8CflSensitivityError("all three locked CFL columns are required")

    paths = {
        "summary": target / "summary.json",
        "cases": target / "cfl_cases.csv",
        "comparison": target / "cross_cfl_comparison.csv",
        "checkpoints": target / "physical_checkpoints.csv",
        "focus": target / "cell_29_30_31_history.csv",
        "transitions": target / "transition_events.csv",
        "inventory": target / "inventory_budget.csv",
        "report": target / "report.md",
        "digest": target / "artifact_sha256.txt",
    }
    paths.update(_write_figures(target, executed))
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_rows(paths["cases"], _case_rows(executed))
    _write_rows(paths["comparison"], _comparison_rows(executed))
    _write_rows(
        paths["checkpoints"],
        [asdict(row) for column in executed.columns for row in column.checkpoints],
    )
    _write_rows(
        paths["focus"],
        [asdict(row) for column in executed.columns for row in column.focused_cells],
    )
    _write_rows(paths["transitions"], _transition_rows(executed))
    _write_rows(
        paths["inventory"],
        [
            {"cfl": column.cfl, **asdict(step)}
            for column in executed.columns
            for step in column.steps
        ],
    )
    paths["report"].write_text(_report(executed), encoding="utf-8")
    digest_lines = []
    for path in sorted(
        (path for key, path in paths.items() if key != "digest"),
        key=lambda item: item.name,
    ):
        digest_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        )
    paths["digest"].write_text("\n".join(digest_lines) + "\n", encoding="utf-8")
    return executed, paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result, paths = write_gate8_full_artifacts(args.output_dir)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
