"""Gate 9 D4-B: event-align the fixed CFL 0.05 and 0.025 columns.

This verification-only increment reuses the read-only D4 observation context from
``hem_gate9_event_alignment``.  It executes the immutable 32-cell first-crossing
case independently at CFL 0.05 and 0.025, reproduces the retained Gate 8 formal
identities, and captures the same predeclared step/cell/stage evidence window.

No production equation, Rusanov flux, sound-speed formula, property evaluation
order, phase classifier, quality projection, crossing threshold, tolerance, or
boundary condition is changed.  A formal guard or first-crossing stop is never
bypassed to manufacture post-event states.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Mapping, Sequence

from .flux import observe_rusanov_flux
from .hem_acoustic_attempt_diagnostics import (
    Gate9AcousticAttemptEvent,
    observe_equilibrium_acoustic_attempts,
)
from .hem_gate9_event_alignment import (
    D4_CAPTURED_STAGES,
    D4_CFL_NO_NEW_TRIALS,
    D4_CFL_TRIALS_OBSERVED,
    D4_POST_STATUS_FORMAL_STOP,
    PROPERTY_BACKEND_DESIGN_STATUS,
    PROPERTY_BACKEND_NAME,
    Gate9D4AlignedAcousticRecord,
    Gate9D4CflDecisionRecord,
    Gate9D4ExactCellStageRecord,
    Gate9D4StateSnapshot,
    Gate9D4TimelineRecord,
    _align,
    _exact_cell_records,
    _finalize_acoustic,
    _finalize_cfl,
    _require_identity,
    _timeline,
    _window_steps,
    _write,
    observe_gate9_d4_runtime,
)
from .hem_pipeline_crossing_depth_diagnosis import (
    GATE9_FOCUS_CELLS,
    Gate9CellStageRecord,
    Gate9InterfaceFluxRecord,
    instrument_pipeline_case_result,
    solver_identity,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    PipelineCaseResult,
    run_pipeline_depressurization_case,
)
from .hem_pipeline_post_crossing_cfl_sensitivity import HEMGate8PipelineConfig
from .hem_rusanov_diagnostic_decomposition import (
    Gate9RusanovEvaluationCollector,
    RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE,
    build_gate9_interface_flux_records,
)

REFINED_D4_SCHEMA_VERSION = "stage7_gate9_d4_refined_columns_v1"
REFINED_D4_COLUMN_SCHEMA_VERSION = "stage7_gate9_d4_event_alignment_column_v1"
REFINED_D4_SCOPE = "verification_only_event_aligned_refined_cfl_columns"
REFINED_D4_CFL_SEQUENCE: tuple[float, ...] = (0.05, 0.025)


class HEMGate9RefinedEventAlignmentError(RuntimeError):
    """Raised when a locked refined-CFL D4 contract cannot be preserved."""


@dataclass(frozen=True)
class Gate9D4RefinedColumnContract:
    cfl: float
    expected_outcome: str
    expected_failure_reason: str
    expected_step_count: int
    expected_candidate_time_s: float
    expected_candidate_cells: tuple[int, ...]
    expected_maximum_candidate_quality: float
    expected_final_state_sha256: str
    expected_run_signature_sha256: str

    def expected_solver_identity(self) -> dict[str, object]:
        return {
            "outcome": self.expected_outcome,
            "failure_reason": self.expected_failure_reason,
            "step_count": self.expected_step_count,
            "final_time_s_hex": float(self.expected_candidate_time_s).hex(),
            "crossing_step": self.expected_step_count,
            "crossing_time_s_hex": float(self.expected_candidate_time_s).hex(),
            "crossing_cell_indices": self.expected_candidate_cells,
            "maximum_crossing_quality_hex": float(
                self.expected_maximum_candidate_quality
            ).hex(),
            "final_state_sha256": self.expected_final_state_sha256,
            "run_signature_sha256": self.expected_run_signature_sha256,
        }


REFINED_D4_CONTRACTS: tuple[Gate9D4RefinedColumnContract, ...] = (
    Gate9D4RefinedColumnContract(
        cfl=0.05,
        expected_outcome="GUARD_FAILURE",
        expected_failure_reason=(
            "HEMPipelineDepressurizationError: crossing quality evidence is "
            "below the fixed minimum"
        ),
        expected_step_count=249,
        expected_candidate_time_s=7.967173062790038e-4,
        expected_candidate_cells=(29,),
        expected_maximum_candidate_quality=1.1006096906989802e-7,
        expected_final_state_sha256=(
            "d18e4bdf1477c29f1183b2f3276c84e086f6cfef80c336a7f6f13616769c5a29"
        ),
        expected_run_signature_sha256=(
            "1292331d53eddd7ec700d8a76bc3900a501c40f4671c758b0ae4bd5c9487cfde"
        ),
    ),
    Gate9D4RefinedColumnContract(
        cfl=0.025,
        expected_outcome="ACCEPTED_FIRST_CROSSING",
        expected_failure_reason="",
        expected_step_count=499,
        expected_candidate_time_s=7.981201399992095e-4,
        expected_candidate_cells=(29,),
        expected_maximum_candidate_quality=1.3949366092287805e-6,
        expected_final_state_sha256=(
            "cb2d5859775d1b1c736e936af798c36cd8d20c73d926de9ed47bcc0aadb1f688"
        ),
        expected_run_signature_sha256=(
            "5af1d089f4139b209a7bfc192a4fc5d6afda9da4031a60a1d13f0ddf683e6dd7"
        ),
    ),
)


@dataclass(frozen=True)
class Gate9D4RefinedColumnResult:
    contract: Gate9D4RefinedColumnContract
    exact_cell_stage_records: tuple[Gate9D4ExactCellStageRecord, ...]
    d1_cell_stage_records: tuple[Gate9CellStageRecord, ...]
    interface_flux_records: tuple[Gate9InterfaceFluxRecord, ...]
    acoustic_records: tuple[Gate9D4AlignedAcousticRecord, ...]
    cfl_decision_records: tuple[Gate9D4CflDecisionRecord, ...]
    timeline_records: tuple[Gate9D4TimelineRecord, ...]
    candidate_step: int
    candidate_time_s: float
    candidate_cells: tuple[int, ...]
    maximum_candidate_quality: float
    window_steps: tuple[int, ...]
    window_start_step: int
    available_post_step_count: int
    post_window_status: str
    solver_identity_off: Mapping[str, object]
    solver_identity_on: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        cfl_acoustic = sum(
            record.stage == "CFL_DT_EVALUATION"
            for record in self.acoustic_records
        )
        cfl_status = (
            D4_CFL_TRIALS_OBSERVED
            if cfl_acoustic
            else D4_CFL_NO_NEW_TRIALS
        )
        return {
            "schema_version": REFINED_D4_COLUMN_SCHEMA_VERSION,
            "scope": REFINED_D4_SCOPE,
            "case_id": FIXED_PIPELINE_DEPRESSURIZATION_CASES[0].case_id,
            "cfl": self.contract.cfl,
            "formal_outcome": self.solver_identity_on["outcome"],
            "formal_failure_reason": self.solver_identity_on["failure_reason"],
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
            "gate8_identity_reproduced_exactly": (
                dict(self.solver_identity_on)
                == self.contract.expected_solver_identity()
            ),
            "candidate_step": self.candidate_step,
            "candidate_time_s": self.candidate_time_s,
            "candidate_cells": list(self.candidate_cells),
            "maximum_candidate_quality": self.maximum_candidate_quality,
            "window_steps": list(self.window_steps),
            "window_start_step": self.window_start_step,
            "available_pre_step_count": (
                self.candidate_step - self.window_start_step
            ),
            "available_post_step_count": self.available_post_step_count,
            "post_window_status": self.post_window_status,
            "focused_cells": list(GATE9_FOCUS_CELLS),
            "captured_exact_stages": list(D4_CAPTURED_STAGES),
            "exact_cell_stage_record_count": len(
                self.exact_cell_stage_records
            ),
            "d1_cell_stage_record_count": len(self.d1_cell_stage_records),
            "interface_flux_record_count": len(
                self.interface_flux_records
            ),
            "aligned_acoustic_record_count": len(self.acoustic_records),
            "cfl_decision_record_count": len(self.cfl_decision_records),
            "cfl_dt_acoustic_trial_record_count": cfl_acoustic,
            "cfl_dt_acoustic_trial_capture_status": cfl_status,
            "timeline_record_count": len(self.timeline_records),
            "all_acoustic_records_have_step_cell_stage_dt": all(
                record.absolute_step in self.window_steps
                and record.cell_index in GATE9_FOCUS_CELLS
                and bool(record.stage)
                and record.dt_s is not None
                and record.dt_s > 0.0
                for record in self.acoustic_records
            ),
            "all_cfl_decisions_match_production_dt": all(
                record.formula_identity_passed
                for record in self.cfl_decision_records
            ),
            "all_timeline_records_have_source_time": all(
                record.absolute_time_s > 0.0
                for record in self.timeline_records
            ),
            "rusanov_reconstruction_guard_passed": all(
                record.normalized_reconstruction_residual is not None
                and record.normalized_reconstruction_residual
                <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
                for record in self.interface_flux_records
            ),
            "diagnostic_off_on_identity": (
                dict(self.solver_identity_off)
                == dict(self.solver_identity_on)
            ),
            "solver_identity_off": dict(self.solver_identity_off),
            "solver_identity_on": dict(self.solver_identity_on),
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "sound_speed_formula_changed": False,
            "phase_classifier_changed": False,
            "quality_projection_changed": False,
            "crossing_threshold_changed": False,
            "boundary_changed": False,
            "forced_post_guard_continuation": False,
            "Gate_9_execution_complete": False,
            "crossing_depth_CFL_sensitivity_characterized": False,
            "crossing_depth_root_cause_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


@dataclass(frozen=True)
class Gate9D4RefinedResult:
    columns: tuple[Gate9D4RefinedColumnResult, ...]

    def summary(self) -> dict[str, object]:
        column_summaries = [column.summary() for column in self.columns]
        return {
            "schema_version": REFINED_D4_SCHEMA_VERSION,
            "scope": REFINED_D4_SCOPE,
            "case_id": FIXED_PIPELINE_DEPRESSURIZATION_CASES[0].case_id,
            "locked_cfl_columns": list(REFINED_D4_CFL_SEQUENCE),
            "column_count": len(self.columns),
            "columns": column_summaries,
            "all_gate8_identities_reproduced_exactly": all(
                summary["gate8_identity_reproduced_exactly"]
                for summary in column_summaries
            ),
            "all_diagnostic_off_on_identities_passed": all(
                summary["diagnostic_off_on_identity"]
                for summary in column_summaries
            ),
            "all_rusanov_reconstruction_guards_passed": all(
                summary["rusanov_reconstruction_guard_passed"]
                for summary in column_summaries
            ),
            "all_cfl_decisions_match_production_dt": all(
                summary["all_cfl_decisions_match_production_dt"]
                for summary in column_summaries
            ),
            "all_timeline_records_have_source_time": all(
                summary["all_timeline_records_have_source_time"]
                for summary in column_summaries
            ),
            "all_formal_stops_honored_without_continuation": all(
                summary["post_window_status"] == D4_POST_STATUS_FORMAL_STOP
                and summary["forced_post_guard_continuation"] is False
                for summary in column_summaries
            ),
            "refined_event_alignment_complete": (
                tuple(column.contract.cfl for column in self.columns)
                == REFINED_D4_CFL_SEQUENCE
            ),
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "sound_speed_formula_changed": False,
            "phase_classifier_changed": False,
            "quality_projection_changed": False,
            "crossing_threshold_changed": False,
            "boundary_changed": False,
            "forced_post_guard_continuation": False,
            "Gate_9_execution_complete": False,
            "crossing_depth_CFL_sensitivity_characterized": False,
            "crossing_depth_root_cause_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


def _require_locked_contract(
    result: PipelineCaseResult,
    contract: Gate9D4RefinedColumnContract,
) -> None:
    if float(result.config.cfl) != contract.cfl:
        raise HEMGate9RefinedEventAlignmentError(
            f"unexpected CFL: {result.config.cfl}"
        )
    actual = solver_identity(result)
    expected = contract.expected_solver_identity()
    if actual != expected:
        raise HEMGate9RefinedEventAlignmentError(
            "refined column did not reproduce the retained Gate 8 identity: "
            + json.dumps(
                {"expected": expected, "actual": actual},
                sort_keys=True,
                default=list,
            )
        )


def _validate_column(result: Gate9D4RefinedColumnResult) -> None:
    summary = result.summary()
    step_count = len(result.window_steps)
    expected_exact = step_count * len(D4_CAPTURED_STAGES) * len(
        GATE9_FOCUS_CELLS
    )
    expected_d1 = step_count * 3 * len(GATE9_FOCUS_CELLS)
    expected_interfaces = step_count * 5
    if summary["exact_cell_stage_record_count"] != expected_exact:
        raise HEMGate9RefinedEventAlignmentError(
            "incomplete exact stage window"
        )
    if summary["d1_cell_stage_record_count"] != expected_d1:
        raise HEMGate9RefinedEventAlignmentError("incomplete D1 window")
    if summary["interface_flux_record_count"] != expected_interfaces:
        raise HEMGate9RefinedEventAlignmentError(
            "incomplete interface window"
        )
    if summary["cfl_decision_record_count"] != step_count:
        raise HEMGate9RefinedEventAlignmentError(
            "incomplete CFL decision window"
        )
    for key in (
        "gate8_identity_reproduced_exactly",
        "diagnostic_off_on_identity",
        "all_acoustic_records_have_step_cell_stage_dt",
        "all_cfl_decisions_match_production_dt",
        "all_timeline_records_have_source_time",
        "rusanov_reconstruction_guard_passed",
    ):
        if summary[key] is not True:
            raise HEMGate9RefinedEventAlignmentError(
                f"refined D4 contract failed: {key}"
            )
    stage_pairs = {
        (record.absolute_step, record.stage)
        for record in result.exact_cell_stage_records
    }
    expected_pairs = {
        (step, stage)
        for step in result.window_steps
        for stage in D4_CAPTURED_STAGES
    }
    if stage_pairs != expected_pairs:
        raise HEMGate9RefinedEventAlignmentError(
            "exact stage coverage is incomplete"
        )


def run_gate9_d4_refined_column(
    contract: Gate9D4RefinedColumnContract,
) -> Gate9D4RefinedColumnResult:
    """Run one immutable refined-CFL column with D4 diagnostics OFF and ON."""

    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    config = HEMGate8PipelineConfig.for_cfl(contract.cfl)
    off = run_pipeline_depressurization_case(case, config)
    _require_locked_contract(off, contract)

    snapshots: list[Gate9D4StateSnapshot] = []
    acoustic_raw: list[Gate9D4AlignedAcousticRecord] = []
    cfl_raw: list[Gate9D4CflDecisionRecord] = []
    rusanov = Gate9RusanovEvaluationCollector()

    def acoustic_observer(event: Gate9AcousticAttemptEvent) -> None:
        aligned = _align(event)
        if aligned is not None:
            acoustic_raw.append(aligned)

    with (
        observe_gate9_d4_runtime(
            case.case_id,
            contract.cfl,
            snapshots.append,
            cfl_raw.append,
        ),
        observe_rusanov_flux(rusanov),
        observe_equilibrium_acoustic_attempts(acoustic_observer),
    ):
        on = run_pipeline_depressurization_case(case, config)

    _require_identity(off, on)
    _require_locked_contract(on, contract)
    steps, start, post_count, post_status = _window_steps(on)
    step_set = set(steps)
    candidate = int(on.crossing_step)
    dt_by_step = {
        int(step.step_index): float(step.dt_s) for step in on.steps
    }

    exact = _exact_cell_records(
        snapshots,
        candidate_step=candidate,
        window_steps=step_set,
    )
    d1 = tuple(
        record
        for record in instrument_pipeline_case_result(on).cell_stage_records
        if record.absolute_step in step_set
    )
    interfaces = tuple(
        record
        for record in build_gate9_interface_flux_records(
            on,
            rusanov.evaluations,
        )
        if record.absolute_step in step_set
    )
    acoustic = _finalize_acoustic(
        acoustic_raw,
        candidate_step=candidate,
        dt_by_step=dt_by_step,
        window_steps=step_set,
    )
    cfl_decisions = _finalize_cfl(
        cfl_raw,
        candidate_step=candidate,
        window_steps=step_set,
    )
    if not acoustic:
        raise HEMGate9RefinedEventAlignmentError(
            "no focused aligned acoustic evidence"
        )
    timeline = _timeline(
        exact,
        interfaces,
        acoustic,
        cfl_decisions,
        candidate,
    )
    result = Gate9D4RefinedColumnResult(
        contract=contract,
        exact_cell_stage_records=exact,
        d1_cell_stage_records=d1,
        interface_flux_records=interfaces,
        acoustic_records=acoustic,
        cfl_decision_records=cfl_decisions,
        timeline_records=timeline,
        candidate_step=candidate,
        candidate_time_s=float(on.crossing_time_s),
        candidate_cells=tuple(int(value) for value in on.crossing_cell_indices),
        maximum_candidate_quality=float(on.maximum_crossing_quality),
        window_steps=steps,
        window_start_step=start,
        available_post_step_count=post_count,
        post_window_status=post_status,
        solver_identity_off=solver_identity(off),
        solver_identity_on=solver_identity(on),
    )
    _validate_column(result)
    return result


def run_gate9_d4_refined_columns() -> Gate9D4RefinedResult:
    """Run the locked CFL 0.05 and 0.025 columns in fixed order."""

    columns = tuple(
        run_gate9_d4_refined_column(contract)
        for contract in REFINED_D4_CONTRACTS
    )
    result = Gate9D4RefinedResult(columns=columns)
    summary = result.summary()
    for key in (
        "all_gate8_identities_reproduced_exactly",
        "all_diagnostic_off_on_identities_passed",
        "all_rusanov_reconstruction_guards_passed",
        "all_cfl_decisions_match_production_dt",
        "all_timeline_records_have_source_time",
        "all_formal_stops_honored_without_continuation",
        "refined_event_alignment_complete",
    ):
        if summary[key] is not True:
            raise HEMGate9RefinedEventAlignmentError(
                f"refined D4 aggregate contract failed: {key}"
            )
    return result


def _cfl_token(cfl: float) -> str:
    return f"{cfl:.3f}".replace(".", "p")


def _flatten(value: object) -> object:
    return (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (tuple, list, dict))
        else value
    )


def _column_paths(target: Path) -> dict[str, Path]:
    return {
        "summary": target / "summary.json",
        "exact_cells": target / "event_aligned_exact_cell_stage_history.csv",
        "d1_cells": target / "event_aligned_d1_cell_stage_history.csv",
        "interfaces": target / "event_aligned_interface_flux_history.csv",
        "acoustic": target / "event_aligned_acoustic_history.csv",
        "cfl": target / "event_aligned_cfl_decision_history.csv",
        "timeline": target / "candidate_event_timeline.csv",
        "candidate": target / "candidate_summary.json",
        "digest": target / "artifact_sha256.txt",
    }


def write_gate9_d4_refined_column_artifacts(
    output_dir: str | Path,
    result: Gate9D4RefinedColumnResult,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = _column_paths(target)
    summary = result.summary()
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write(
        paths["exact_cells"],
        Gate9D4ExactCellStageRecord,
        result.exact_cell_stage_records,
    )
    _write(
        paths["d1_cells"],
        Gate9CellStageRecord,
        result.d1_cell_stage_records,
    )
    _write(
        paths["interfaces"],
        Gate9InterfaceFluxRecord,
        result.interface_flux_records,
    )
    _write(
        paths["acoustic"],
        Gate9D4AlignedAcousticRecord,
        result.acoustic_records,
    )
    _write(
        paths["cfl"],
        Gate9D4CflDecisionRecord,
        result.cfl_decision_records,
    )
    _write(
        paths["timeline"],
        Gate9D4TimelineRecord,
        result.timeline_records,
    )
    paths["candidate"].write_text(
        json.dumps(
            {
                "case_id": FIXED_PIPELINE_DEPRESSURIZATION_CASES[0].case_id,
                "cfl": result.contract.cfl,
                "formal_outcome": summary["formal_outcome"],
                "formal_failure_reason": summary["formal_failure_reason"],
                "candidate_step": result.candidate_step,
                "candidate_time_s": result.candidate_time_s,
                "candidate_cells": list(result.candidate_cells),
                "maximum_candidate_quality": result.maximum_candidate_quality,
                "window_steps": list(result.window_steps),
                "post_window_status": result.post_window_status,
                "final_state_sha256": summary["solver_identity_on"][
                    "final_state_sha256"
                ],
                "run_signature_sha256": summary["solver_identity_on"][
                    "run_signature_sha256"
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    digest_lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(
            (value for key, value in paths.items() if key != "digest"),
            key=lambda path: path.name,
        )
    ]
    paths["digest"].write_text(
        "\n".join(digest_lines) + "\n",
        encoding="utf-8",
    )
    return paths


def _write_candidate_metrics(
    path: Path,
    columns: Sequence[Gate9D4RefinedColumnResult],
) -> None:
    rows = []
    for column in columns:
        summary = column.summary()
        identity = summary["solver_identity_on"]
        rows.append(
            {
                "cfl": column.contract.cfl,
                "formal_outcome": summary["formal_outcome"],
                "formal_failure_reason": summary["formal_failure_reason"],
                "candidate_step": column.candidate_step,
                "candidate_time_s": column.candidate_time_s,
                "candidate_cells": list(column.candidate_cells),
                "maximum_candidate_quality": column.maximum_candidate_quality,
                "window_start_step": column.window_start_step,
                "window_end_step": column.window_steps[-1],
                "post_window_status": column.post_window_status,
                "exact_cell_stage_record_count": len(
                    column.exact_cell_stage_records
                ),
                "interface_flux_record_count": len(
                    column.interface_flux_records
                ),
                "aligned_acoustic_record_count": len(column.acoustic_records),
                "cfl_decision_record_count": len(
                    column.cfl_decision_records
                ),
                "final_state_sha256": identity["final_state_sha256"],
                "run_signature_sha256": identity["run_signature_sha256"],
            }
        )
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: _flatten(value) for key, value in row.items()}
            )


def write_gate9_d4_refined_artifacts(
    output_dir: str | Path,
    result: Gate9D4RefinedResult,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "summary": target / "summary.json",
        "candidate_metrics": target / "per_cfl_candidate_metrics.csv",
        "digest": target / "artifact_sha256.txt",
    }
    column_dirs: list[Path] = []
    for column in result.columns:
        column_dir = target / f"cfl_{_cfl_token(column.contract.cfl)}"
        write_gate9_d4_refined_column_artifacts(column_dir, column)
        column_dirs.append(column_dir)
    summary = result.summary()
    summary["column_artifact_directories"] = [
        path.name for path in column_dirs
    ]
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_candidate_metrics(paths["candidate_metrics"], result.columns)
    digest_sources = sorted(
        (
            path
            for path in target.rglob("*")
            if path.is_file() and path != paths["digest"]
        ),
        key=lambda path: str(path.relative_to(target)),
    )
    paths["digest"].write_text(
        "\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
            f"{path.relative_to(target).as_posix()}"
            for path in digest_sources
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    result = run_gate9_d4_refined_columns()
    paths = write_gate9_d4_refined_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
