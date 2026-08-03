"""Gate 9 D6: classify temporal ordering and cross-CFL correlations.

This verification-only module consumes the immutable Gate 9 D5 artifact produced
by workflow run 30805641241. It does not execute the production solver, alter
any numerical/model setting, or approve a root cause or mitigation.

D6 answers a narrower question: which recorded measures preserve the observed
non-monotone crossing-depth ordering, and which candidate mechanisms do not?
Every permitted Issue #110 label is emitted with an explicit numerator,
denominator, criterion, temporal-order statement, and limitation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
import subprocess
import sys
from typing import Mapping, Sequence


D6_SCHEMA_VERSION = "stage7_gate9_d6_temporal_correlation_classification_v1"
D6_SCOPE = "verification_only_temporal_order_and_correlation_classification"

D5_SCHEMA_VERSION = "stage7_gate9_d5_three_cfl_integration_v1"
D5_WORKFLOW_RUN_ID = 30805641241
D5_ARTIFACT_ID = 8855725551
D5_ARTIFACT_ZIP_SHA256 = (
    "6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850"
)
D5_SOURCE_HEAD_SHA = "45894a3fbe8c176c8435517c6204d94359dccccc"
D5_MERGE_SHA = "ede646078f5d9cc094f0efa430b87ef4bc5e232a"

D6_CFL_SEQUENCE: tuple[float, ...] = (0.10, 0.05, 0.025)
D6_CROSSING_THRESHOLD = 1.0e-6
D6_TIME_STABILITY_MAX_COARSE_STEP_MULTIPLE = 1.0
D6_MATERIAL_PAIR_RATIO = 2.0

D6_PERMITTED_LABELS: tuple[str, ...] = (
    "CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL",
    "CROSSING_DEPTH_CFL_SENSITIVE",
    "CROSSING_DEPTH_SEQUENCE_NON_MONOTONE",
    "CANDIDATE_STEP_OVERSHOOT_CORRELATED",
    "RUSANOV_DISSIPATION_CORRELATED",
    "BOUNDARY_FLUX_IMBALANCE_CORRELATED",
    "SATURATION_MARGIN_DISPLACEMENT_CORRELATED",
    "ACOUSTIC_BRANCH_SELECTION_CORRELATED",
    "PROJECTION_ACTIVITY_POSTDATES_RAW_CROSSING",
    "THRESHOLD_CLASSIFICATION_DISCONTINUITY_OBSERVED",
    "MULTI_FACTOR_CROSSING_DEPTH",
    "CROSSING_DEPTH_REVIEW_INCONCLUSIVE",
)

D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS: tuple[str, ...] = (
    "CANDIDATE_STEP_OVERSHOOT_CORRELATED",
    "RUSANOV_DISSIPATION_CORRELATED",
    "BOUNDARY_FLUX_IMBALANCE_CORRELATED",
    "ACOUSTIC_BRANCH_SELECTION_CORRELATED",
)

D5_REQUIRED_FILES: frozenset[str] = frozenset(
    {
        "summary.json",
        "per_cfl_candidate_metrics.csv",
        "focused_cell_stage_history.csv",
        "focused_interface_flux_decomposition.csv",
        "candidate_event_comparison.csv",
        "saturation_margin_history.csv",
        "projection_history.csv",
        "budget_history.csv",
        "acoustic_attempt_history.csv",
        "cfl_decision_history.csv",
        "candidate_event_timeline.csv",
        "report.md",
        "candidate_quality_vs_physical_time.png",
        "saturation_margins_vs_physical_time.png",
        "candidate_step_flux_decomposition.png",
        "acoustic_branch_vs_margin.png",
        "cross_cfl_depth_comparison.png",
        "artifact_sha256.txt",
    }
)

D6_OUTPUT_FILES: frozenset[str] = frozenset(
    {
        "summary.json",
        "label_evidence.csv",
        "temporal_order_evidence.csv",
        "mechanism_rank_comparison.csv",
        "threshold_classification_evidence.csv",
        "report.md",
        "artifact_sha256.txt",
    }
)


class HEMGate9D6ClassificationError(RuntimeError):
    """Raised when immutable D5 evidence or the D6 contract is violated."""


@dataclass(frozen=True)
class Gate9D6CandidateMetric:
    cfl: float
    formal_outcome: str
    candidate_step: int
    candidate_time_s: float
    candidate_cell: int
    distance_from_outlet_m: float
    maximum_candidate_q_eq: float
    threshold_distance_q: float
    candidate_dt_s: float
    q_internal_energy_coordinate: float
    q_specific_volume_coordinate: float
    delta_e_from_saturated_liquid_J_kg: float
    delta_v_from_saturated_liquid_m3_kg: float
    first_projection_delta_rho_q: float
    second_projection_exact_noop: bool
    final_sound_speed_m_s: float
    final_sound_speed_branch: str
    cell29_dissipative_mass_increment: float
    cell29_dissipative_momentum_increment: float
    cell29_dissipative_energy_increment: float
    cell31_central_mass_increment: float
    cell31_central_momentum_increment: float
    cell31_central_energy_increment: float
    cell31_dissipative_mass_increment: float
    cell31_dissipative_momentum_increment: float
    cell31_dissipative_energy_increment: float


@dataclass(frozen=True)
class Gate9D6ProjectionEvidence:
    cfl: float
    candidate_step: int
    raw_rho_q: float
    post_first_rho_q: float
    post_second_rho_q: float
    final_rho_q: float
    first_projection_delta_rho_q: float
    second_projection_delta_rho_q: float
    second_projection_exact_noop: bool
    final_equals_second_projection: bool


@dataclass(frozen=True)
class Gate9D6TemporalOrderEvidence:
    cfl: float
    candidate_step: int
    raw_sequence_index: int
    first_projection_sequence_index: int
    raw_precedes_first_projection: bool
    raw_candidate_q_eq: float
    raw_rho_q: float
    post_first_rho_q: float
    first_projection_delta_rho_q: float
    second_projection_delta_rho_q: float
    second_projection_exact_noop: bool
    raw_crossing_precedes_projection_activity: bool


@dataclass(frozen=True)
class Gate9D6MechanismRankComparison:
    family: str
    measure: str
    values_by_cfl_json: str
    pairwise_concordant: int
    pairwise_total: int
    full_order_match: bool
    candidate_stage: str
    interpretation: str


@dataclass(frozen=True)
class Gate9D6ThresholdEvidence:
    cfl: float
    candidate_q_eq: float
    threshold: float
    threshold_distance_q: float
    continuous_side: str
    formal_outcome: str
    expected_formal_outcome: str
    classification_matches_threshold_side: bool


@dataclass(frozen=True)
class Gate9D6LabelEvidence:
    label: str
    assigned: bool
    numerator: int
    denominator: int
    criterion: str
    evidence: str
    temporal_order: str
    limitation: str


@dataclass(frozen=True)
class Gate9D6InputEvidence:
    d5_summary: Mapping[str, object]
    candidate_metrics: tuple[Gate9D6CandidateMetric, ...]
    projections: tuple[Gate9D6ProjectionEvidence, ...]
    timeline_sequence: Mapping[tuple[float, str], int]
    internal_digest_verified: bool


@dataclass(frozen=True)
class Gate9D6Result:
    input_evidence: Gate9D6InputEvidence
    label_evidence: tuple[Gate9D6LabelEvidence, ...]
    temporal_order_evidence: tuple[Gate9D6TemporalOrderEvidence, ...]
    mechanism_comparisons: tuple[Gate9D6MechanismRankComparison, ...]
    threshold_evidence: tuple[Gate9D6ThresholdEvidence, ...]
    provenance: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        labels = {row.label: row for row in self.label_evidence}
        assigned = [name for name in D6_PERMITTED_LABELS if labels[name].assigned]
        not_assigned = [
            name for name in D6_PERMITTED_LABELS if not labels[name].assigned
        ]
        candidate_times = [
            row.candidate_time_s for row in self.input_evidence.candidate_metrics
        ]
        candidate_dt = [
            row.candidate_dt_s for row in self.input_evidence.candidate_metrics
        ]
        candidate_q = [
            row.maximum_candidate_q_eq
            for row in self.input_evidence.candidate_metrics
        ]
        time_spread = max(candidate_times) - min(candidate_times)
        max_dt = max(candidate_dt)
        complete = bool(
            self.input_evidence.internal_digest_verified
            and tuple(row.label for row in self.label_evidence)
            == D6_PERMITTED_LABELS
            and len(self.temporal_order_evidence) == len(D6_CFL_SEQUENCE)
            and len(self.threshold_evidence) == len(D6_CFL_SEQUENCE)
            and all(
                row.denominator > 0 and 0 <= row.numerator <= row.denominator
                for row in self.label_evidence
            )
        )
        sensitivity_characterized = bool(
            complete
            and labels["CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL"].assigned
            and labels["CROSSING_DEPTH_CFL_SENSITIVE"].assigned
            and labels["CROSSING_DEPTH_SEQUENCE_NON_MONOTONE"].assigned
        )
        return {
            "schema_version": D6_SCHEMA_VERSION,
            "scope": D6_SCOPE,
            "input_d5_schema_version": D5_SCHEMA_VERSION,
            "input_d5_workflow_run_id": D5_WORKFLOW_RUN_ID,
            "input_d5_artifact_id": D5_ARTIFACT_ID,
            "input_d5_artifact_zip_sha256": D5_ARTIFACT_ZIP_SHA256,
            "input_d5_source_head_sha": D5_SOURCE_HEAD_SHA,
            "input_d5_merge_sha": D5_MERGE_SHA,
            "input_d5_internal_digest_verified": (
                self.input_evidence.internal_digest_verified
            ),
            "locked_cfl_sequence": list(D6_CFL_SEQUENCE),
            "crossing_threshold": D6_CROSSING_THRESHOLD,
            "candidate_time_spread_s": time_spread,
            "maximum_candidate_dt_s": max_dt,
            "candidate_time_spread_over_max_candidate_dt": (
                time_spread / max_dt
            ),
            "candidate_depth_max_to_min_ratio": max(candidate_q) / min(candidate_q),
            "candidate_depth_sequence_status": _sequence_status(candidate_q),
            "label_count": len(self.label_evidence),
            "assigned_label_count": len(assigned),
            "not_assigned_label_count": len(not_assigned),
            "assigned_labels": assigned,
            "not_assigned_labels": not_assigned,
            "temporal_order_record_count": len(self.temporal_order_evidence),
            "mechanism_comparison_record_count": len(
                self.mechanism_comparisons
            ),
            "threshold_evidence_record_count": len(self.threshold_evidence),
            "D6_temporal_correlation_classification_complete": complete,
            "Gate_9_execution_complete": complete,
            "crossing_depth_CFL_sensitivity_characterized": (
                sensitivity_characterized
            ),
            "crossing_depth_root_cause_approved": False,
            "threshold_change_authorized": False,
            "flux_change_authorized": False,
            "sound_speed_change_authorized": False,
            "projection_change_authorized": False,
            "post_crossing_propagation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "cfl_calculation_changed": False,
            "sound_speed_formula_changed": False,
            "phase_classifier_changed": False,
            "quality_projection_changed": False,
            "crossing_threshold_changed": False,
            "boundary_changed": False,
            "forced_post_guard_continuation": False,
            "provenance": dict(self.provenance),
        }


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise HEMGate9D6ClassificationError(f"invalid boolean value: {value!r}")


def _as_float(row: Mapping[str, str], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise HEMGate9D6ClassificationError(
            f"missing or invalid float field: {key}"
        ) from exc
    if not math.isfinite(value):
        raise HEMGate9D6ClassificationError(f"non-finite field: {key}")
    return value


def _as_int(row: Mapping[str, str], key: str) -> int:
    try:
        return int(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise HEMGate9D6ClassificationError(
            f"missing or invalid integer field: {key}"
        ) from exc


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_internal_digest(target: Path) -> bool:
    actual_files = {path.name for path in target.iterdir() if path.is_file()}
    if actual_files != D5_REQUIRED_FILES:
        missing = sorted(D5_REQUIRED_FILES - actual_files)
        extra = sorted(actual_files - D5_REQUIRED_FILES)
        raise HEMGate9D6ClassificationError(
            f"D5 artifact file set mismatch; missing={missing}, extra={extra}"
        )
    digest_path = target / "artifact_sha256.txt"
    entries: dict[str, str] = {}
    for line in digest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split("  ", 1)
        except ValueError as exc:
            raise HEMGate9D6ClassificationError(
                "invalid D5 artifact digest line"
            ) from exc
        if "/" in name or "\\" in name or name == "artifact_sha256.txt":
            raise HEMGate9D6ClassificationError(
                f"invalid D5 digest member: {name}"
            )
        entries[name] = digest
    expected_members = D5_REQUIRED_FILES - {"artifact_sha256.txt"}
    if set(entries) != expected_members:
        raise HEMGate9D6ClassificationError(
            "D5 internal digest does not enumerate the locked file set"
        )
    for name, expected in entries.items():
        actual = _sha256(target / name)
        if actual != expected:
            raise HEMGate9D6ClassificationError(
                f"D5 internal digest mismatch for {name}"
            )
    return True


def _validate_d5_summary(summary: Mapping[str, object]) -> None:
    exact = {
        "schema_version": D5_SCHEMA_VERSION,
        "scope": "verification_only_same_schema_three_cfl_integration",
        "locked_cfl_sequence": list(D6_CFL_SEQUENCE),
        "column_count": 3,
        "focused_cell_stage_record_count": 540,
        "focused_interface_flux_record_count": 135,
        "projection_record_count": 108,
        "budget_record_count": 27,
        "cfl_decision_record_count": 27,
        "candidate_metric_count": 3,
        "candidate_comparison_count": 3,
        "candidate_depth_sequence_status": "NON_MONOTONE",
        "D5_three_cfl_integration_complete": True,
        "D6_temporal_correlation_classification_complete": False,
        "Gate_9_execution_complete": False,
        "all_gate8_formal_identities_reproduced": True,
        "all_rusanov_reconstruction_guards_passed": True,
        "all_cfl_decisions_match_production_dt": True,
        "all_timeline_records_have_source_time": True,
        "all_second_projections_exact_noop": True,
        "budgets_traceable": True,
    }
    for key, expected in exact.items():
        if summary.get(key) != expected:
            raise HEMGate9D6ClassificationError(
                f"D5 summary contract mismatch for {key}: "
                f"{summary.get(key)!r} != {expected!r}"
            )
    provenance = summary.get("provenance")
    if not isinstance(provenance, Mapping):
        raise HEMGate9D6ClassificationError("D5 provenance is unavailable")
    if provenance.get("source_git_sha") != D5_SOURCE_HEAD_SHA:
        raise HEMGate9D6ClassificationError(
            "D5 source head does not match the selected authoritative artifact"
        )


def _load_candidate_metrics(target: Path) -> tuple[Gate9D6CandidateMetric, ...]:
    rows = _read_csv(target / "per_cfl_candidate_metrics.csv")
    required = {
        "cfl",
        "formal_outcome",
        "candidate_step",
        "candidate_time_s",
        "candidate_cell",
        "distance_from_outlet_m",
        "maximum_candidate_q_eq",
        "threshold_distance_q",
        "candidate_dt_s",
        "q_internal_energy_coordinate",
        "q_specific_volume_coordinate",
        "delta_e_from_saturated_liquid_J_kg",
        "delta_v_from_saturated_liquid_m3_kg",
        "first_projection_delta_rho_q",
        "second_projection_exact_noop",
        "final_sound_speed_m_s",
        "final_sound_speed_branch",
        "cell29_dissipative_mass_increment",
        "cell29_dissipative_momentum_increment",
        "cell29_dissipative_energy_increment",
        "cell31_central_mass_increment",
        "cell31_central_momentum_increment",
        "cell31_central_energy_increment",
        "cell31_dissipative_mass_increment",
        "cell31_dissipative_momentum_increment",
        "cell31_dissipative_energy_increment",
    }
    if len(rows) != 3 or not required <= set(rows[0]):
        raise HEMGate9D6ClassificationError(
            "D5 candidate metric schema/count mismatch"
        )
    output: list[Gate9D6CandidateMetric] = []
    for row in rows:
        output.append(
            Gate9D6CandidateMetric(
                cfl=_as_float(row, "cfl"),
                formal_outcome=row["formal_outcome"],
                candidate_step=_as_int(row, "candidate_step"),
                candidate_time_s=_as_float(row, "candidate_time_s"),
                candidate_cell=_as_int(row, "candidate_cell"),
                distance_from_outlet_m=_as_float(
                    row, "distance_from_outlet_m"
                ),
                maximum_candidate_q_eq=_as_float(
                    row, "maximum_candidate_q_eq"
                ),
                threshold_distance_q=_as_float(row, "threshold_distance_q"),
                candidate_dt_s=_as_float(row, "candidate_dt_s"),
                q_internal_energy_coordinate=_as_float(
                    row, "q_internal_energy_coordinate"
                ),
                q_specific_volume_coordinate=_as_float(
                    row, "q_specific_volume_coordinate"
                ),
                delta_e_from_saturated_liquid_J_kg=_as_float(
                    row, "delta_e_from_saturated_liquid_J_kg"
                ),
                delta_v_from_saturated_liquid_m3_kg=_as_float(
                    row, "delta_v_from_saturated_liquid_m3_kg"
                ),
                first_projection_delta_rho_q=_as_float(
                    row, "first_projection_delta_rho_q"
                ),
                second_projection_exact_noop=_as_bool(
                    row["second_projection_exact_noop"]
                ),
                final_sound_speed_m_s=_as_float(row, "final_sound_speed_m_s"),
                final_sound_speed_branch=row["final_sound_speed_branch"],
                cell29_dissipative_mass_increment=_as_float(
                    row, "cell29_dissipative_mass_increment"
                ),
                cell29_dissipative_momentum_increment=_as_float(
                    row, "cell29_dissipative_momentum_increment"
                ),
                cell29_dissipative_energy_increment=_as_float(
                    row, "cell29_dissipative_energy_increment"
                ),
                cell31_central_mass_increment=_as_float(
                    row, "cell31_central_mass_increment"
                ),
                cell31_central_momentum_increment=_as_float(
                    row, "cell31_central_momentum_increment"
                ),
                cell31_central_energy_increment=_as_float(
                    row, "cell31_central_energy_increment"
                ),
                cell31_dissipative_mass_increment=_as_float(
                    row, "cell31_dissipative_mass_increment"
                ),
                cell31_dissipative_momentum_increment=_as_float(
                    row, "cell31_dissipative_momentum_increment"
                ),
                cell31_dissipative_energy_increment=_as_float(
                    row, "cell31_dissipative_energy_increment"
                ),
            )
        )
    metrics = tuple(output)
    if tuple(row.cfl for row in metrics) != D6_CFL_SEQUENCE:
        raise HEMGate9D6ClassificationError(
            "D5 candidate metrics do not retain the locked CFL order"
        )
    expected = {
        0.10: (
            "ACCEPTED_FIRST_CROSSING",
            125,
            7.999325695335248e-4,
            29,
            3.773646403587342e-6,
        ),
        0.05: (
            "GUARD_FAILURE",
            249,
            7.967173062790038e-4,
            29,
            1.1006096906989802e-7,
        ),
        0.025: (
            "ACCEPTED_FIRST_CROSSING",
            499,
            7.981201399992095e-4,
            29,
            1.3949366092287805e-6,
        ),
    }
    for row in metrics:
        outcome, step, time_s, cell, quality = expected[row.cfl]
        if (
            row.formal_outcome != outcome
            or row.candidate_step != step
            or row.candidate_time_s != time_s
            or row.candidate_cell != cell
            or row.maximum_candidate_q_eq != quality
        ):
            raise HEMGate9D6ClassificationError(
                f"D5 immutable identity mismatch for CFL={row.cfl}"
            )
    return metrics


def _load_projection_evidence(
    target: Path,
) -> tuple[Gate9D6ProjectionEvidence, ...]:
    rows = _read_csv(target / "projection_history.csv")
    selected = [
        row
        for row in rows
        if _as_int(row, "candidate_relative_step") == 0
        and _as_int(row, "cell_index") == 29
    ]
    if len(selected) != 3:
        raise HEMGate9D6ClassificationError(
            "D5 candidate projection evidence must contain three rows"
        )
    output = tuple(
        Gate9D6ProjectionEvidence(
            cfl=_as_float(row, "cfl"),
            candidate_step=_as_int(row, "absolute_step"),
            raw_rho_q=_as_float(row, "raw_rho_q"),
            post_first_rho_q=_as_float(row, "post_first_rho_q"),
            post_second_rho_q=_as_float(row, "post_second_rho_q"),
            final_rho_q=_as_float(row, "final_rho_q"),
            first_projection_delta_rho_q=_as_float(
                row, "first_projection_delta_rho_q"
            ),
            second_projection_delta_rho_q=_as_float(
                row, "second_projection_delta_rho_q"
            ),
            second_projection_exact_noop=_as_bool(
                row["second_projection_exact_noop"]
            ),
            final_equals_second_projection=_as_bool(
                row["final_equals_second_projection"]
            ),
        )
        for row in selected
    )
    if tuple(row.cfl for row in output) != D6_CFL_SEQUENCE:
        raise HEMGate9D6ClassificationError(
            "D5 projection evidence does not retain the locked CFL order"
        )
    return output


def _load_timeline_sequence(
    target: Path,
) -> dict[tuple[float, str], int]:
    rows = _read_csv(target / "candidate_event_timeline.csv")
    output: dict[tuple[float, str], int] = {}
    for row in rows:
        if (
            _as_int(row, "candidate_relative_step") != 0
            or row["entity_type"] != "CELL"
            or str(row["entity_id"]) != "29"
            or row["stage"] not in {"RAW_POST_FVM", "POST_FIRST_PROJECTION"}
        ):
            continue
        key = (_as_float(row, "cfl"), row["stage"])
        index = _as_int(row, "column_sequence_index")
        previous = output.get(key)
        if previous is None or index < previous:
            output[key] = index
    expected = {
        (cfl, stage)
        for cfl in D6_CFL_SEQUENCE
        for stage in ("RAW_POST_FVM", "POST_FIRST_PROJECTION")
    }
    if set(output) != expected:
        raise HEMGate9D6ClassificationError(
            "D5 timeline is missing candidate raw/projection ordering"
        )
    return output


def load_gate9_d5_artifact(
    artifact_dir: str | Path,
) -> Gate9D6InputEvidence:
    """Load and verify the immutable D5 evidence directory."""

    target = Path(artifact_dir)
    if not target.is_dir():
        raise HEMGate9D6ClassificationError(
            f"D5 artifact directory not found: {target}"
        )
    digest_verified = _verify_internal_digest(target)
    summary = json.loads(
        (target / "summary.json").read_text(encoding="utf-8")
    )
    if not isinstance(summary, Mapping):
        raise HEMGate9D6ClassificationError("D5 summary must be an object")
    _validate_d5_summary(summary)
    metrics = _load_candidate_metrics(target)
    projections = _load_projection_evidence(target)
    timeline = _load_timeline_sequence(target)
    return Gate9D6InputEvidence(
        d5_summary=summary,
        candidate_metrics=metrics,
        projections=projections,
        timeline_sequence=timeline,
        internal_digest_verified=digest_verified,
    )


def _sequence_status(values: Sequence[float]) -> str:
    if len(values) < 2 or any(not math.isfinite(value) for value in values):
        return "INCOMPLETE"
    differences = [
        right - left for left, right in zip(values[:-1], values[1:])
    ]
    if all(value == 0.0 for value in differences):
        return "CONSTANT"
    if all(value >= 0.0 for value in differences):
        return "MONOTONE_NONDECREASING"
    if all(value <= 0.0 for value in differences):
        return "MONOTONE_NONINCREASING"
    return "NON_MONOTONE"


def _pairwise_concordance(
    depth: Sequence[float],
    measure: Sequence[float],
) -> tuple[int, int]:
    if len(depth) != len(measure):
        raise HEMGate9D6ClassificationError(
            "pairwise comparison length mismatch"
        )
    concordant = 0
    total = 0
    for left in range(len(depth)):
        for right in range(left + 1, len(depth)):
            depth_delta = depth[left] - depth[right]
            measure_delta = measure[left] - measure[right]
            if depth_delta == 0.0:
                continue
            total += 1
            if measure_delta != 0.0 and (
                (depth_delta > 0.0) == (measure_delta > 0.0)
            ):
                concordant += 1
    return concordant, total


def _values_json(
    metrics: Sequence[Gate9D6CandidateMetric],
    values: Sequence[float | str],
) -> str:
    return json.dumps(
        [
            {"cfl": metric.cfl, "value": value}
            for metric, value in zip(metrics, values)
        ],
        sort_keys=True,
    )


def _comparison(
    metrics: Sequence[Gate9D6CandidateMetric],
    *,
    family: str,
    measure: str,
    values: Sequence[float],
    candidate_stage: str,
    interpretation: str,
) -> Gate9D6MechanismRankComparison:
    depth = [row.maximum_candidate_q_eq for row in metrics]
    concordant, total = _pairwise_concordance(depth, values)
    return Gate9D6MechanismRankComparison(
        family=family,
        measure=measure,
        values_by_cfl_json=_values_json(metrics, values),
        pairwise_concordant=concordant,
        pairwise_total=total,
        full_order_match=bool(total > 0 and concordant == total),
        candidate_stage=candidate_stage,
        interpretation=interpretation,
    )


def _build_mechanism_comparisons(
    metrics: Sequence[Gate9D6CandidateMetric],
) -> tuple[Gate9D6MechanismRankComparison, ...]:
    output: list[Gate9D6MechanismRankComparison] = []
    output.append(
        _comparison(
            metrics,
            family="CANDIDATE_STEP_OVERSHOOT",
            measure="candidate_dt_s",
            values=[row.candidate_dt_s for row in metrics],
            candidate_stage="CFL_DT_DECISION_BEFORE_RAW_POST_FVM",
            interpretation=(
                "A full 3/3 pair ordering is required; partial agreement cannot "
                "explain the non-monotone depth sequence."
            ),
        )
    )

    rusanov_fields = (
        ("cell29_abs_dissipative_mass_increment", "cell29_dissipative_mass_increment"),
        (
            "cell29_abs_dissipative_momentum_increment",
            "cell29_dissipative_momentum_increment",
        ),
        (
            "cell29_abs_dissipative_energy_increment",
            "cell29_dissipative_energy_increment",
        ),
        ("cell31_abs_dissipative_mass_increment", "cell31_dissipative_mass_increment"),
        (
            "cell31_abs_dissipative_momentum_increment",
            "cell31_dissipative_momentum_increment",
        ),
        (
            "cell31_abs_dissipative_energy_increment",
            "cell31_dissipative_energy_increment",
        ),
    )
    for measure, attribute in rusanov_fields:
        output.append(
            _comparison(
                metrics,
                family="RUSANOV_DISSIPATION",
                measure=measure,
                values=[abs(getattr(row, attribute)) for row in metrics],
                candidate_stage="FVM_INTERFACE_FLUX_BEFORE_RAW_POST_FVM",
                interpretation=(
                    "Absolute candidate-step dissipative increments are compared "
                    "componentwise; vapor components are excluded because all are zero."
                ),
            )
        )

    boundary_components = (
        ("cell31_abs_net_mass_increment", "mass"),
        ("cell31_abs_net_momentum_increment", "momentum"),
        ("cell31_abs_net_energy_increment", "energy"),
    )
    for measure, component in boundary_components:
        central = f"cell31_central_{component}_increment"
        dissipative = f"cell31_dissipative_{component}_increment"
        output.append(
            _comparison(
                metrics,
                family="BOUNDARY_FLUX_IMBALANCE",
                measure=measure,
                values=[
                    abs(getattr(row, central) + getattr(row, dissipative))
                    for row in metrics
                ],
                candidate_stage="FVM_INTERFACE_FLUX_BEFORE_RAW_POST_FVM",
                interpretation=(
                    "The net candidate-step update of boundary-adjacent cell 31 "
                    "is used as the boundary-flux imbalance measure."
                ),
            )
        )

    saturation_fields = (
        ("q_internal_energy_coordinate", "q_internal_energy_coordinate"),
        ("q_specific_volume_coordinate", "q_specific_volume_coordinate"),
        (
            "abs_delta_e_from_saturated_liquid_J_kg",
            "delta_e_from_saturated_liquid_J_kg",
        ),
        (
            "abs_delta_v_from_saturated_liquid_m3_kg",
            "delta_v_from_saturated_liquid_m3_kg",
        ),
    )
    for measure, attribute in saturation_fields:
        output.append(
            _comparison(
                metrics,
                family="SATURATION_MARGIN_DISPLACEMENT",
                measure=measure,
                values=[abs(getattr(row, attribute)) for row in metrics],
                candidate_stage="RAW_POST_FVM",
                interpretation=(
                    "These are continuous thermodynamic coordinates of the same raw "
                    "candidate state; ordering agreement is descriptive, not causal."
                ),
            )
        )

    output.append(
        _comparison(
            metrics,
            family="ACOUSTIC_BRANCH_SELECTION",
            measure="final_sound_speed_m_s",
            values=[row.final_sound_speed_m_s for row in metrics],
            candidate_stage="FINAL_ACCEPTED_AFTER_PROJECTION",
            interpretation=(
                "Sound-speed ordering is secondary; the categorical branch must also "
                "vary before branch selection can be called correlated."
            ),
        )
    )
    return tuple(output)


def _family_counts(
    comparisons: Sequence[Gate9D6MechanismRankComparison],
    family: str,
) -> tuple[int, int]:
    rows = [row for row in comparisons if row.family == family]
    if not rows:
        raise HEMGate9D6ClassificationError(
            f"missing mechanism comparison family: {family}"
        )
    return (
        sum(row.pairwise_concordant for row in rows),
        sum(row.pairwise_total for row in rows),
    )


def _build_temporal_order_evidence(
    input_evidence: Gate9D6InputEvidence,
) -> tuple[Gate9D6TemporalOrderEvidence, ...]:
    projection_by_cfl = {
        row.cfl: row for row in input_evidence.projections
    }
    output: list[Gate9D6TemporalOrderEvidence] = []
    for metric in input_evidence.candidate_metrics:
        projection = projection_by_cfl[metric.cfl]
        raw_index = input_evidence.timeline_sequence[
            (metric.cfl, "RAW_POST_FVM")
        ]
        first_index = input_evidence.timeline_sequence[
            (metric.cfl, "POST_FIRST_PROJECTION")
        ]
        raw_precedes = raw_index < first_index
        raw_crossing_precedes = bool(
            raw_precedes
            and metric.maximum_candidate_q_eq > 0.0
            and projection.raw_rho_q == 0.0
            and projection.first_projection_delta_rho_q > 0.0
            and projection.second_projection_exact_noop
            and projection.final_equals_second_projection
        )
        output.append(
            Gate9D6TemporalOrderEvidence(
                cfl=metric.cfl,
                candidate_step=metric.candidate_step,
                raw_sequence_index=raw_index,
                first_projection_sequence_index=first_index,
                raw_precedes_first_projection=raw_precedes,
                raw_candidate_q_eq=metric.maximum_candidate_q_eq,
                raw_rho_q=projection.raw_rho_q,
                post_first_rho_q=projection.post_first_rho_q,
                first_projection_delta_rho_q=(
                    projection.first_projection_delta_rho_q
                ),
                second_projection_delta_rho_q=(
                    projection.second_projection_delta_rho_q
                ),
                second_projection_exact_noop=(
                    projection.second_projection_exact_noop
                ),
                raw_crossing_precedes_projection_activity=(
                    raw_crossing_precedes
                ),
            )
        )
    return tuple(output)


def _build_threshold_evidence(
    metrics: Sequence[Gate9D6CandidateMetric],
) -> tuple[Gate9D6ThresholdEvidence, ...]:
    output: list[Gate9D6ThresholdEvidence] = []
    for row in metrics:
        above = row.maximum_candidate_q_eq >= D6_CROSSING_THRESHOLD
        expected = "ACCEPTED_FIRST_CROSSING" if above else "GUARD_FAILURE"
        output.append(
            Gate9D6ThresholdEvidence(
                cfl=row.cfl,
                candidate_q_eq=row.maximum_candidate_q_eq,
                threshold=D6_CROSSING_THRESHOLD,
                threshold_distance_q=(
                    row.maximum_candidate_q_eq - D6_CROSSING_THRESHOLD
                ),
                continuous_side=(
                    "ABOVE_OR_EQUAL_THRESHOLD"
                    if above
                    else "BELOW_THRESHOLD"
                ),
                formal_outcome=row.formal_outcome,
                expected_formal_outcome=expected,
                classification_matches_threshold_side=(
                    row.formal_outcome == expected
                ),
            )
        )
    return tuple(output)


def _label(
    name: str,
    assigned: bool,
    numerator: int,
    denominator: int,
    criterion: str,
    evidence: str,
    temporal_order: str,
    limitation: str,
) -> Gate9D6LabelEvidence:
    if name not in D6_PERMITTED_LABELS:
        raise HEMGate9D6ClassificationError(f"unpermitted D6 label: {name}")
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise HEMGate9D6ClassificationError(
            f"invalid evidence denominator for {name}"
        )
    return Gate9D6LabelEvidence(
        label=name,
        assigned=assigned,
        numerator=numerator,
        denominator=denominator,
        criterion=criterion,
        evidence=evidence,
        temporal_order=temporal_order,
        limitation=limitation,
    )


def classify_gate9_d6_evidence(
    input_evidence: Gate9D6InputEvidence,
    *,
    provenance: Mapping[str, object] | None = None,
) -> Gate9D6Result:
    """Classify the fixed D5 evidence without rerunning or changing the solver."""

    metrics = input_evidence.candidate_metrics
    depth = [row.maximum_candidate_q_eq for row in metrics]
    dt = [row.candidate_dt_s for row in metrics]
    comparisons = _build_mechanism_comparisons(metrics)
    temporal = _build_temporal_order_evidence(input_evidence)
    threshold = _build_threshold_evidence(metrics)

    reference = metrics[0]
    max_dt = max(dt)
    stable_columns = sum(
        metric.candidate_cell == reference.candidate_cell
        and metric.distance_from_outlet_m == reference.distance_from_outlet_m
        and abs(metric.candidate_time_s - reference.candidate_time_s)
        <= D6_TIME_STABILITY_MAX_COARSE_STEP_MULTIPLE * max_dt
        for metric in metrics
    )

    material_depth_pairs = 0
    total_depth_pairs = 0
    for left in range(len(depth)):
        for right in range(left + 1, len(depth)):
            total_depth_pairs += 1
            ratio = max(depth[left], depth[right]) / min(
                depth[left], depth[right]
            )
            if ratio >= D6_MATERIAL_PAIR_RATIO:
                material_depth_pairs += 1

    overshoot_counts = _family_counts(
        comparisons, "CANDIDATE_STEP_OVERSHOOT"
    )
    rusanov_counts = _family_counts(comparisons, "RUSANOV_DISSIPATION")
    boundary_counts = _family_counts(
        comparisons, "BOUNDARY_FLUX_IMBALANCE"
    )
    saturation_counts = _family_counts(
        comparisons, "SATURATION_MARGIN_DISPLACEMENT"
    )
    acoustic_counts = _family_counts(
        comparisons, "ACOUSTIC_BRANCH_SELECTION"
    )
    branch_pair_changes = sum(
        metrics[left].final_sound_speed_branch
        != metrics[right].final_sound_speed_branch
        for left in range(len(metrics))
        for right in range(left + 1, len(metrics))
    )
    branch_pair_total = 3

    projection_passes = sum(
        row.raw_crossing_precedes_projection_activity for row in temporal
    )
    threshold_passes = sum(
        row.classification_matches_threshold_side for row in threshold
    )
    both_threshold_sides = len(
        {row.continuous_side for row in threshold}
    ) == 2

    preliminary: dict[str, bool] = {
        "CANDIDATE_STEP_OVERSHOOT_CORRELATED": (
            overshoot_counts[0] == overshoot_counts[1]
        ),
        "RUSANOV_DISSIPATION_CORRELATED": (
            rusanov_counts[0] == rusanov_counts[1]
        ),
        "BOUNDARY_FLUX_IMBALANCE_CORRELATED": (
            boundary_counts[0] == boundary_counts[1]
        ),
        "ACOUSTIC_BRANCH_SELECTION_CORRELATED": bool(
            branch_pair_changes > 0
            and acoustic_counts[0] == acoustic_counts[1]
        ),
    }
    independent_assigned = sum(
        preliminary[name]
        for name in D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS
    )
    independent_unassigned = (
        len(D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS)
        - independent_assigned
    )

    label_rows = (
        _label(
            "CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL",
            stable_columns == len(metrics),
            stable_columns,
            len(metrics),
            (
                "All columns must retain the same candidate cell/outlet distance, "
                "and candidate time must remain within one maximum coarse-column "
                "candidate dt of the CFL 0.10 reference."
            ),
            (
                f"stable columns={stable_columns}/{len(metrics)}; "
                f"time spread={max(row.candidate_time_s for row in metrics) - min(row.candidate_time_s for row in metrics):.17g} s; "
                f"max candidate dt={max_dt:.17g} s"
            ),
            "Candidate locations and times are selected before formal threshold interpretation.",
            "This establishes event alignment, not physical front-speed accuracy.",
        ),
        _label(
            "CROSSING_DEPTH_CFL_SENSITIVE",
            material_depth_pairs == total_depth_pairs,
            material_depth_pairs,
            total_depth_pairs,
            (
                f"Every cross-CFL candidate-depth pair must differ by a factor "
                f"of at least {D6_MATERIAL_PAIR_RATIO:g}."
            ),
            (
                f"pairwise material depth differences="
                f"{material_depth_pairs}/{total_depth_pairs}; "
                f"max/min={max(depth) / min(depth):.17g}"
            ),
            "Depth is measured from RAW_POST_FVM thermodynamic evidence.",
            "Sensitivity does not identify a causal numerical or physical mechanism.",
        ),
        _label(
            "CROSSING_DEPTH_SEQUENCE_NON_MONOTONE",
            _sequence_status(depth) == "NON_MONOTONE",
            int(_sequence_status(depth) == "NON_MONOTONE"),
            1,
            "The locked CFL-ordered continuous q_eq sequence must be NON_MONOTONE.",
            f"sequence status={_sequence_status(depth)}; values={depth!r}",
            "The continuous sequence is evaluated before accepted/guard binarization.",
            "No convergence order may be inferred from three non-monotone points.",
        ),
        _label(
            "CANDIDATE_STEP_OVERSHOOT_CORRELATED",
            preliminary["CANDIDATE_STEP_OVERSHOOT_CORRELATED"],
            overshoot_counts[0],
            overshoot_counts[1],
            "Candidate dt must reproduce the q_eq ordering for all three CFL pairs.",
            (
                f"pairwise ordering agreement="
                f"{overshoot_counts[0]}/{overshoot_counts[1]}"
            ),
            "Candidate dt is fixed before RAW_POST_FVM.",
            "Partial 2/3 agreement is insufficient for the non-monotone sequence.",
        ),
        _label(
            "RUSANOV_DISSIPATION_CORRELATED",
            preliminary["RUSANOV_DISSIPATION_CORRELATED"],
            rusanov_counts[0],
            rusanov_counts[1],
            (
                "All nonzero mass/momentum/energy dissipative increments at cells "
                "29 and 31 must reproduce the q_eq ordering for all CFL pairs."
            ),
            (
                f"component-pair ordering agreement="
                f"{rusanov_counts[0]}/{rusanov_counts[1]}"
            ),
            "Rusanov interface contributions are formed before RAW_POST_FVM.",
            "A failed full-order test does not prove dissipation is irrelevant.",
        ),
        _label(
            "BOUNDARY_FLUX_IMBALANCE_CORRELATED",
            preliminary["BOUNDARY_FLUX_IMBALANCE_CORRELATED"],
            boundary_counts[0],
            boundary_counts[1],
            (
                "The absolute net mass/momentum/energy update of boundary-adjacent "
                "cell 31 must reproduce the q_eq ordering for all CFL pairs."
            ),
            (
                f"component-pair ordering agreement="
                f"{boundary_counts[0]}/{boundary_counts[1]}"
            ),
            "The focused boundary/interface fluxes are formed before RAW_POST_FVM.",
            "This fixed candidate-step test does not exclude accumulated boundary influence.",
        ),
        _label(
            "SATURATION_MARGIN_DISPLACEMENT_CORRELATED",
            saturation_counts[0] == saturation_counts[1],
            saturation_counts[0],
            saturation_counts[1],
            (
                "q_u, q_v, |Delta e_sat|, and |Delta v_sat| must each reproduce "
                "the q_eq ordering for all CFL pairs."
            ),
            (
                f"coordinate-pair ordering agreement="
                f"{saturation_counts[0]}/{saturation_counts[1]}"
            ),
            "All four measures describe the RAW_POST_FVM candidate state.",
            (
                "These coordinates are thermodynamically coupled to q_eq and are "
                "not an independent root-cause proof."
            ),
        ),
        _label(
            "ACOUSTIC_BRANCH_SELECTION_CORRELATED",
            preliminary["ACOUSTIC_BRANCH_SELECTION_CORRELATED"],
            branch_pair_changes,
            branch_pair_total,
            (
                "At least one cross-CFL branch pair must differ, and accepted "
                "sound-speed ordering must match q_eq for all pairs."
            ),
            (
                f"branch differences={branch_pair_changes}/{branch_pair_total}; "
                f"sound-speed ordering agreement="
                f"{acoustic_counts[0]}/{acoustic_counts[1]}; "
                f"branches={[row.final_sound_speed_branch for row in metrics]!r}"
            ),
            "The retained candidate sound speed is FINAL_ACCEPTED after projection.",
            "A constant branch cannot explain the cross-CFL depth ordering.",
        ),
        _label(
            "PROJECTION_ACTIVITY_POSTDATES_RAW_CROSSING",
            projection_passes == len(temporal),
            projection_passes,
            len(temporal),
            (
                "For every CFL, positive raw q_eq and RAW_POST_FVM timeline evidence "
                "must precede positive first-projection rho*q insertion; the second "
                "projection must be an exact no-op."
            ),
            f"temporally ordered columns={projection_passes}/{len(temporal)}",
            "RAW_POST_FVM precedes POST_FIRST_PROJECTION by captured sequence index.",
            "Projection can stabilize accepted state but did not create the raw thermodynamic crossing.",
        ),
        _label(
            "THRESHOLD_CLASSIFICATION_DISCONTINUITY_OBSERVED",
            threshold_passes == len(threshold) and both_threshold_sides,
            threshold_passes,
            len(threshold),
            (
                "Every formal outcome must match the sign of q_eq - 1e-6, and "
                "the fixed columns must occupy both sides of the threshold."
            ),
            (
                f"outcome/threshold matches={threshold_passes}/{len(threshold)}; "
                f"both threshold sides represented={both_threshold_sides}"
            ),
            "Threshold interpretation follows continuous raw q_eq evaluation.",
            "The label records a discrete evidence classification, not a thermodynamic discontinuity.",
        ),
        _label(
            "MULTI_FACTOR_CROSSING_DEPTH",
            independent_assigned >= 2,
            independent_assigned,
            len(D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS),
            (
                "At least two independent pre-raw candidate-mechanism labels must "
                "satisfy their full-order tests."
            ),
            (
                f"independent fully correlated mechanisms="
                f"{independent_assigned}/"
                f"{len(D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS)}"
            ),
            "Only candidate measures available no later than RAW_POST_FVM count.",
            "Saturation coordinates and threshold/projection labels are excluded as non-independent or downstream.",
        ),
        _label(
            "CROSSING_DEPTH_REVIEW_INCONCLUSIVE",
            independent_unassigned
            == len(D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS),
            independent_unassigned,
            len(D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS),
            (
                "Assign when none of the independent candidate-mechanism labels "
                "passes the full-order criterion and no root cause is approved."
            ),
            (
                f"independent mechanisms without full correlation="
                f"{independent_unassigned}/"
                f"{len(D6_INDEPENDENT_PRE_RAW_MECHANISM_LABELS)}"
            ),
            "The review retains temporal ordering but does not elevate correlation to causation.",
            "Further controlled intervention or additional resolution points are required.",
        ),
    )
    if tuple(row.label for row in label_rows) != D6_PERMITTED_LABELS:
        raise HEMGate9D6ClassificationError(
            "D6 label order does not match the locked contract"
        )
    result = Gate9D6Result(
        input_evidence=input_evidence,
        label_evidence=label_rows,
        temporal_order_evidence=temporal,
        mechanism_comparisons=comparisons,
        threshold_evidence=threshold,
        provenance=dict(provenance or _runtime_provenance()),
    )
    summary = result.summary()
    for key in (
        "D6_temporal_correlation_classification_complete",
        "Gate_9_execution_complete",
        "crossing_depth_CFL_sensitivity_characterized",
    ):
        if summary[key] is not True:
            raise HEMGate9D6ClassificationError(
                f"D6 completion contract failed: {key}"
            )
    if summary["crossing_depth_root_cause_approved"] is not False:
        raise HEMGate9D6ClassificationError(
            "D6 must not approve a crossing-depth root cause"
        )
    return result


def run_gate9_d6_temporal_correlation_classification(
    d5_artifact_dir: str | Path,
) -> Gate9D6Result:
    """Load the authoritative D5 artifact and execute the D6 classifier."""

    return classify_gate9_d6_evidence(
        load_gate9_d5_artifact(d5_artifact_dir)
    )


def _git_command(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def _runtime_provenance() -> dict[str, object]:
    source_sha = os.environ.get("ANALYSIS_SOURCE_GIT_SHA") or _git_command(
        "rev-parse", "HEAD"
    )
    checkout_sha = _git_command("rev-parse", "HEAD")
    git_status = _git_command(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if git_status == "UNAVAILABLE":
        git_status = ""
    return {
        "source_git_sha": source_sha,
        "checkout_git_sha": checkout_sha,
        "git_status_porcelain_tracked": git_status,
        "python_version": sys.version,
    }


def _flatten(value: object) -> object:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_dataclass_rows(
    path: Path,
    record_type: type,
    rows: Sequence[object],
) -> None:
    names = [item.name for item in fields(record_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow(
                {name: _flatten(payload[name]) for name in names}
            )


def _write_report(path: Path, result: Gate9D6Result) -> None:
    summary = result.summary()
    lines = [
        "# Stage 7 Gate 9 D6 — Temporal/correlation classification",
        "",
        "`VERIFICATION ONLY; CORRELATION IS NOT ROOT-CAUSE APPROVAL`",
        "",
        "## Authoritative input",
        "",
        "```text",
        f"D5 workflow run:      {D5_WORKFLOW_RUN_ID}",
        f"D5 artifact ID:       {D5_ARTIFACT_ID}",
        f"D5 source head:       {D5_SOURCE_HEAD_SHA}",
        f"D5 merge SHA:         {D5_MERGE_SHA}",
        f"D5 ZIP SHA256:        {D5_ARTIFACT_ZIP_SHA256}",
        "internal digest:       verified",
        "```",
        "",
        "## Label disposition",
        "",
        "| label | assigned | evidence |",
        "|---|---:|---:|",
    ]
    for row in result.label_evidence:
        lines.append(
            f"| `{row.label}` | `{str(row.assigned).lower()}` | "
            f"{row.numerator}/{row.denominator} |"
        )
    lines.extend(
        [
            "",
            "## Controlled interpretation",
            "",
            "- Candidate time and position remain event-aligned across the three CFLs.",
            "- Crossing depth is strongly CFL-sensitive and non-monotone.",
            "- Continuous saturation coordinates reproduce the depth ordering.",
            "- Candidate dt, Rusanov dissipation, boundary-adjacent net flux, and "
            "accepted acoustic branch do not satisfy the locked full-order test.",
            "- Raw thermodynamic crossing evidence precedes quality projection.",
            "- The fixed `1e-6` threshold converts continuous depth into the "
            "accepted/guard outcome sequence.",
            "- No unique or multi-factor root cause is approved.",
            "",
            "## Completion and approval boundary",
            "",
            "```text",
            f"D6 classification complete: {summary['D6_temporal_correlation_classification_complete']}",
            f"Gate 9 execution complete:   {summary['Gate_9_execution_complete']}",
            f"CFL sensitivity characterized: {summary['crossing_depth_CFL_sensitivity_characterized']}",
            "crossing-depth root cause approved: false",
            "threshold / flux / sound-speed / projection changes authorized: false",
            "physical validation / design use / production activation: false",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_gate9_d6_artifacts(
    output_dir: str | Path,
    result: Gate9D6Result,
) -> dict[str, Path]:
    """Write the fixed D6 evidence bundle and an internal SHA256 manifest."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": target / "summary.json",
        "labels": target / "label_evidence.csv",
        "temporal": target / "temporal_order_evidence.csv",
        "mechanisms": target / "mechanism_rank_comparison.csv",
        "threshold": target / "threshold_classification_evidence.csv",
        "report": target / "report.md",
        "digest": target / "artifact_sha256.txt",
    }
    paths["summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_dataclass_rows(
        paths["labels"], Gate9D6LabelEvidence, result.label_evidence
    )
    _write_dataclass_rows(
        paths["temporal"],
        Gate9D6TemporalOrderEvidence,
        result.temporal_order_evidence,
    )
    _write_dataclass_rows(
        paths["mechanisms"],
        Gate9D6MechanismRankComparison,
        result.mechanism_comparisons,
    )
    _write_dataclass_rows(
        paths["threshold"],
        Gate9D6ThresholdEvidence,
        result.threshold_evidence,
    )
    _write_report(paths["report"], result)

    digest_sources = sorted(
        (
            path
            for path in target.iterdir()
            if path.is_file() and path != paths["digest"]
        ),
        key=lambda item: item.name,
    )
    paths["digest"].write_text(
        "\n".join(
            f"{_sha256(path)}  {path.name}" for path in digest_sources
        )
        + "\n",
        encoding="utf-8",
    )
    if {path.name for path in target.iterdir() if path.is_file()} != D6_OUTPUT_FILES:
        raise HEMGate9D6ClassificationError(
            "D6 writer did not emit the locked output file set"
        )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d5-artifact-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    result = run_gate9_d6_temporal_correlation_classification(
        args.d5_artifact_dir
    )
    paths = write_gate9_d6_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
