"""Stage 7 Gate 9 D1 read-only instrumentation scaffold.

D1 does not modify the finite-volume solver or replay a different numerical path.
It consumes the retained :class:`PipelineCaseResult` evidence after the solver has
returned and reconstructs focused cell-stage records from immutable copies.

The Rusanov decomposition and acoustic-attempt histories are represented by fixed
record types but deliberately remain empty until D2 and D3. Missing quantities
are recorded as ``None`` or an explicit category; they are never inferred by
clipping, fallback, or extra property calls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    _state_sha256,
    run_pipeline_depressurization_case,
)
from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, N_VARS

GATE9_FOCUS_CELLS: tuple[int, ...] = (28, 29, 30, 31)
GATE9_FOCUS_INTERFACES: tuple[str, ...] = (
    "27|28",
    "28|29",
    "29|30",
    "30|31",
    "RIGHT_BOUNDARY",
)
GATE9_D1_CAPTURED_STAGES: tuple[str, ...] = (
    "PRE_STEP_ACCEPTED",
    "RAW_POST_FVM",
    "FINAL_ACCEPTED_IF_AVAILABLE",
)
GATE9_PENDING_STAGES: tuple[str, ...] = (
    "POST_FIRST_PROJECTION_IF_AVAILABLE",
    "POST_SECOND_PROJECTION_IF_AVAILABLE",
)


class HEMGate9InstrumentationError(RuntimeError):
    """Raised when retained evidence is internally inconsistent."""


@dataclass(frozen=True)
class Gate9CellStageRecord:
    case_id: str
    cfl: float
    absolute_step: int
    absolute_time_s: float
    dt_s: float
    measured_cfl: float | None
    stage: str
    cell_index: int
    rho: float
    rho_u: float
    rho_E: float
    rho_q: float
    velocity: float
    specific_internal_energy: float
    pressure: float | None
    temperature: float | None
    specific_volume: float
    q_internal_energy_coordinate: float | None
    q_specific_volume_coordinate: float | None
    q_equilibrium: float | None
    void_fraction: float | None
    delta_e_from_saturated_liquid: float | None
    delta_v_from_saturated_liquid: float | None
    raw_region: str
    post_region: str
    transition_event: str
    sound_speed: float | None
    sound_speed_squared: float | None
    sound_speed_branch: str
    first_projection_applied: bool | None
    first_projection_delta_rho_q: float | None
    second_projection_applied: bool | None
    second_projection_exact_noop: bool | None
    state_sha256: str
    capture_status: str


@dataclass(frozen=True)
class Gate9InterfaceFluxRecord:
    case_id: str
    cfl: float
    absolute_step: int
    absolute_time_s: float
    dt_s: float
    interface_id: str
    left_cell: int | None
    right_cell: int | None
    left_conserved_state: tuple[float, ...] | None
    right_conserved_state: tuple[float, ...] | None
    left_physical_flux: tuple[float, ...] | None
    right_physical_flux: tuple[float, ...] | None
    a_max: float | None
    central_component: tuple[float, ...] | None
    dissipative_component: tuple[float, ...] | None
    reconstructed_rusanov_flux: tuple[float, ...] | None
    production_rusanov_flux: tuple[float, ...] | None
    normalized_reconstruction_residual: float | None
    left_cell_increment_over_dt_dx: tuple[float, ...] | None
    right_cell_increment_over_dt_dx: tuple[float, ...] | None
    capture_status: str


@dataclass(frozen=True)
class Gate9AcousticAttemptRecord:
    case_id: str
    cfl: float
    absolute_step: int
    absolute_time_s: float
    cell_index: int
    stage: str
    base_density_increment: float | None
    halving_index: int | None
    trial_density_minus: float | None
    trial_density_plus: float | None
    minus_state_valid: bool | None
    plus_state_valid: bool | None
    minus_phase_or_scope_category: str
    plus_phase_or_scope_category: str
    computed_sound_speed_squared: float | None
    accepted_or_refused: str
    refusal_category: str
    backend_error_type: str
    capture_status: str


@dataclass(frozen=True)
class Gate9CandidateSummary:
    case_id: str
    cfl: float
    candidate_step: int | None
    candidate_time_s: float | None
    candidate_cells: tuple[int, ...]
    candidate_distances_from_outlet_m: tuple[float, ...]
    maximum_candidate_q_equilibrium: float
    formal_outcome: str
    formal_failure_reason: str
    final_state_sha256: str
    run_signature_sha256: str
    capture_status: str


@dataclass(frozen=True)
class Gate9RunResult:
    schema_version: str
    case_id: str
    cfl: float
    focused_cells: tuple[int, ...]
    focused_interfaces: tuple[str, ...]
    captured_stages: tuple[str, ...]
    pending_stages: tuple[str, ...]
    cell_stage_records: tuple[Gate9CellStageRecord, ...]
    interface_flux_records: tuple[Gate9InterfaceFluxRecord, ...]
    acoustic_attempt_records: tuple[Gate9AcousticAttemptRecord, ...]
    candidate_summary: Gate9CandidateSummary
    diagnostic_status: str
    cell_capture_status: str
    interface_capture_status: str
    acoustic_capture_status: str
    diagnostic_failures: tuple[str, ...]
    solver_identity: Mapping[str, object]
    retained_history_sha256_before: str
    retained_history_sha256_after: str

    @property
    def solver_state_preserved(self) -> bool:
        return self.retained_history_sha256_before == self.retained_history_sha256_after

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scope": "verification_only_read_only_instrumentation_scaffold",
            "case_id": self.case_id,
            "cfl": self.cfl,
            "focused_cells": list(self.focused_cells),
            "focused_interfaces": list(self.focused_interfaces),
            "captured_stages": list(self.captured_stages),
            "pending_stages": list(self.pending_stages),
            "cell_stage_record_count": len(self.cell_stage_records),
            "interface_flux_record_count": len(self.interface_flux_records),
            "acoustic_attempt_record_count": len(self.acoustic_attempt_records),
            "candidate_summary": asdict(self.candidate_summary),
            "diagnostic_status": self.diagnostic_status,
            "cell_capture_status": self.cell_capture_status,
            "interface_capture_status": self.interface_capture_status,
            "acoustic_capture_status": self.acoustic_capture_status,
            "diagnostic_failures": list(self.diagnostic_failures),
            "solver_identity": dict(self.solver_identity),
            "retained_history_sha256_before": self.retained_history_sha256_before,
            "retained_history_sha256_after": self.retained_history_sha256_after,
            "solver_state_preserved": self.solver_state_preserved,
            "diagnostics_may_change_solver_state": False,
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "sound_speed_formula_changed": False,
            "phase_classifier_changed": False,
            "quality_projection_changed": False,
            "crossing_threshold_changed": False,
            "boundary_changed": False,
            "Gate_9_execution_complete": False,
            "crossing_depth_CFL_sensitivity_characterized": False,
            "crossing_depth_root_cause_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


Gate9CaseRunner = Callable[
    [PipelineDepressurizationCaseSpec, HEMPipelineDepressurizationConfig],
    PipelineCaseResult,
]


def solver_identity(result: PipelineCaseResult) -> dict[str, object]:
    """Return the exact fields that diagnostics must not change."""

    return {
        "outcome": result.outcome,
        "failure_reason": result.failure_reason,
        "step_count": int(result.step_count),
        "final_time_s_hex": float(result.final_time_s).hex(),
        "crossing_step": result.crossing_step,
        "crossing_time_s_hex": (
            None
            if result.crossing_time_s is None
            else float(result.crossing_time_s).hex()
        ),
        "crossing_cell_indices": tuple(int(v) for v in result.crossing_cell_indices),
        "maximum_crossing_quality_hex": float(
            result.maximum_crossing_quality
        ).hex(),
        "final_state_sha256": result.final_state_sha256,
        "run_signature_sha256": result.run_signature_sha256,
    }


def _history_sha256(result: PipelineCaseResult) -> str:
    digest = hashlib.sha256()
    for array in (
        result.time_history_s,
        result.pressure_history_pa,
        result.accepted_state_history,
    ):
        little = np.ascontiguousarray(np.asarray(array, dtype="<f8"))
        digest.update(str(little.shape).encode("ascii"))
        digest.update(little.tobytes(order="C"))
    digest.update(
        json.dumps(
            solver_identity(result),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _primitive_from_conserved(row: np.ndarray) -> tuple[float, float, float, float, float, float]:
    values = np.asarray(row, dtype=float)
    if values.shape != (N_VARS,) or not np.all(np.isfinite(values)):
        raise HEMGate9InstrumentationError("conserved cell state must be finite N_VARS")
    rho = float(values[IDX_RHO])
    if rho <= 0.0:
        raise HEMGate9InstrumentationError("density must remain positive")
    rho_u = float(values[IDX_MOM])
    rho_E = float(values[IDX_RHOE])
    rho_q = float(values[IDX_RHO_XV])
    velocity = rho_u / rho
    internal = rho_E / rho - 0.5 * velocity * velocity
    return rho, rho_u, rho_E, rho_q, velocity, internal


def _raw_state_from_cells(cells: Sequence[object], n_cells: int) -> np.ndarray:
    raw = np.empty((n_cells, N_VARS), dtype=float)
    seen: set[int] = set()
    for cell in cells:
        index = int(cell.cell_index)
        if index < 0 or index >= n_cells or index in seen:
            raise HEMGate9InstrumentationError(
                f"invalid or duplicate raw cell index: {index}"
            )
        rho = float(cell.rho_raw_kg_m3)
        velocity = float(cell.velocity_raw_m_s)
        internal = float(cell.e_raw_j_kg)
        quality = float(cell.q_transport_raw)
        values = (rho, velocity, internal, quality)
        if rho <= 0.0 or not all(np.isfinite(value) for value in values):
            raise HEMGate9InstrumentationError(
                f"non-finite raw retained evidence at cell {index}"
            )
        raw[index, IDX_RHO] = rho
        raw[index, IDX_MOM] = rho * velocity
        raw[index, IDX_RHOE] = rho * (internal + 0.5 * velocity * velocity)
        raw[index, IDX_RHO_XV] = rho * quality
        seen.add(index)
    if len(seen) != n_cells:
        raise HEMGate9InstrumentationError(
            f"raw retained evidence covers {len(seen)} of {n_cells} cells"
        )
    return raw


def _cell_stage_record(
    *,
    result: PipelineCaseResult,
    step: object,
    cell: object,
    stage: str,
    state: np.ndarray,
    state_sha256: str,
    pressure: float | None,
) -> Gate9CellStageRecord:
    index = int(cell.cell_index)
    rho, rho_u, rho_E, rho_q, velocity, internal = _primitive_from_conserved(
        state[index]
    )
    if stage == "PRE_STEP_ACCEPTED":
        absolute_time = float(step.time_before_s)
        raw_region = "NOT_APPLICABLE_PRE_STEP"
        post_region = str(cell.previous_region)
        transition_event = "NOT_APPLICABLE_PRE_STEP"
        q_equilibrium = None
        void_fraction = None
        sound_speed = None
        first_applied = None
        first_delta = None
        second_applied = None
        status = "D1_FROM_RETAINED_PRE_STEP_ACCEPTED_HISTORY"
    elif stage == "RAW_POST_FVM":
        absolute_time = float(step.time_after_s)
        raw_region = str(cell.raw_region)
        post_region = "NOT_AVAILABLE_BEFORE_PROJECTION"
        transition_event = str(cell.transition_event)
        q_equilibrium = float(cell.q_equilibrium)
        void_fraction = None
        sound_speed = None
        first_applied = None
        first_delta = None
        second_applied = None
        status = "D1_RECONSTRUCTED_FROM_RETAINED_RAW_CELL_EVIDENCE"
    elif stage == "FINAL_ACCEPTED_IF_AVAILABLE":
        absolute_time = float(step.time_after_s)
        raw_region = str(cell.raw_region)
        post_region = str(cell.post_region)
        transition_event = str(cell.transition_event)
        q_equilibrium = float(cell.q_equilibrium)
        void_fraction = float(cell.alpha_post)
        sound_speed = float(cell.sound_speed_post_m_s)
        first_applied = bool(cell.first_projection_applied)
        first_delta = rho_q - float(cell.rho_raw_kg_m3) * float(
            cell.q_transport_raw
        )
        second_applied = bool(cell.second_projection_applied)
        status = "D1_FROM_RETAINED_FINAL_ACCEPTED_HISTORY"
    else:
        raise HEMGate9InstrumentationError(f"unsupported D1 stage: {stage}")

    return Gate9CellStageRecord(
        case_id=result.case.case_id,
        cfl=float(result.config.cfl),
        absolute_step=int(step.step_index),
        absolute_time_s=absolute_time,
        dt_s=float(step.dt_s),
        measured_cfl=None,
        stage=stage,
        cell_index=index,
        rho=rho,
        rho_u=rho_u,
        rho_E=rho_E,
        rho_q=rho_q,
        velocity=velocity,
        specific_internal_energy=internal,
        pressure=pressure,
        temperature=(
            float(cell.temperature_raw_K) if stage == "RAW_POST_FVM" else None
        ),
        specific_volume=1.0 / rho,
        q_internal_energy_coordinate=None,
        q_specific_volume_coordinate=None,
        q_equilibrium=q_equilibrium,
        void_fraction=void_fraction,
        delta_e_from_saturated_liquid=None,
        delta_v_from_saturated_liquid=None,
        raw_region=raw_region,
        post_region=post_region,
        transition_event=transition_event,
        sound_speed=sound_speed,
        sound_speed_squared=(
            None if sound_speed is None else sound_speed * sound_speed
        ),
        sound_speed_branch="NOT_CAPTURED_D1_PENDING_D3",
        first_projection_applied=first_applied,
        first_projection_delta_rho_q=first_delta,
        second_projection_applied=second_applied,
        second_projection_exact_noop=None,
        state_sha256=state_sha256,
        capture_status=status,
    )


def instrument_pipeline_case_result(result: PipelineCaseResult) -> Gate9RunResult:
    """Create Gate 9 D1 records without mutating ``result`` or calling the EOS."""

    before = _history_sha256(result)
    failures: list[str] = []
    records: list[Gate9CellStageRecord] = []
    n_cells = int(result.config.n_cells)

    if tuple(GATE9_FOCUS_CELLS) != (28, 29, 30, 31) or n_cells != 32:
        raise HEMGate9InstrumentationError(
            "Gate 9 D1 is fixed to cells 28/29/30/31 on the 32-cell case"
        )

    cells_by_step: dict[int, list[object]] = {}
    for cell in result.cells:
        cells_by_step.setdefault(int(cell.step_index), []).append(cell)

    accepted = np.asarray(result.accepted_state_history, dtype=float)
    pressures = np.asarray(result.pressure_history_pa, dtype=float)
    if accepted.ndim != 3 or accepted.shape[1:] != (n_cells, N_VARS):
        raise HEMGate9InstrumentationError(
            "accepted state history has an incompatible shape"
        )
    if pressures.shape != accepted.shape[:2]:
        raise HEMGate9InstrumentationError(
            "pressure and accepted histories are not aligned"
        )

    for position, step in enumerate(result.steps):
        step_index = int(step.step_index)
        step_cells = cells_by_step.get(step_index, [])
        if len(step_cells) != n_cells:
            failures.append(
                f"step {step_index}: retained raw cell count {len(step_cells)} != {n_cells}"
            )
            continue
        if position + 1 >= accepted.shape[0]:
            failures.append(f"step {step_index}: accepted history is unavailable")
            continue
        by_index = {int(cell.cell_index): cell for cell in step_cells}
        try:
            raw_state = _raw_state_from_cells(step_cells, n_cells)
            pre_state = np.array(accepted[position], dtype=float, copy=True)
            final_state = np.array(accepted[position + 1], dtype=float, copy=True)
            raw_hash = _state_sha256(raw_state)
            pre_hash = _state_sha256(pre_state)
            final_hash = _state_sha256(final_state)
            if final_hash != step.state_sha256:
                raise HEMGate9InstrumentationError(
                    f"step {step_index}: retained final SHA mismatch"
                )
            for index in GATE9_FOCUS_CELLS:
                cell = by_index[index]
                records.append(
                    _cell_stage_record(
                        result=result,
                        step=step,
                        cell=cell,
                        stage="PRE_STEP_ACCEPTED",
                        state=pre_state,
                        state_sha256=pre_hash,
                        pressure=float(pressures[position, index]),
                    )
                )
                records.append(
                    _cell_stage_record(
                        result=result,
                        step=step,
                        cell=cell,
                        stage="RAW_POST_FVM",
                        state=raw_state,
                        state_sha256=raw_hash,
                        pressure=float(cell.pressure_raw_pa),
                    )
                )
                records.append(
                    _cell_stage_record(
                        result=result,
                        step=step,
                        cell=cell,
                        stage="FINAL_ACCEPTED_IF_AVAILABLE",
                        state=final_state,
                        state_sha256=final_hash,
                        pressure=float(pressures[position + 1, index]),
                    )
                )
        except Exception as exc:
            failures.append(f"step {step_index}: {type(exc).__name__}: {exc}")

    after = _history_sha256(result)
    if before != after:
        raise HEMGate9InstrumentationError(
            "read-only instrumentation changed retained solver evidence"
        )

    candidate = Gate9CandidateSummary(
        case_id=result.case.case_id,
        cfl=float(result.config.cfl),
        candidate_step=result.crossing_step,
        candidate_time_s=result.crossing_time_s,
        candidate_cells=tuple(int(v) for v in result.crossing_cell_indices),
        candidate_distances_from_outlet_m=tuple(
            float(v) for v in result.crossing_distances_from_outlet_m
        ),
        maximum_candidate_q_equilibrium=float(result.maximum_crossing_quality),
        formal_outcome=str(result.outcome),
        formal_failure_reason=str(result.failure_reason),
        final_state_sha256=str(result.final_state_sha256),
        run_signature_sha256=str(result.run_signature_sha256),
        capture_status=(
            "D1_CANDIDATE_METADATA_FROM_RETAINED_RESULT"
            if result.crossing_step is not None
            else "D1_NO_RETAINED_CANDIDATE"
        ),
    )
    return Gate9RunResult(
        schema_version="stage7_gate9_d1_instrumentation_scaffold_v1",
        case_id=result.case.case_id,
        cfl=float(result.config.cfl),
        focused_cells=GATE9_FOCUS_CELLS,
        focused_interfaces=GATE9_FOCUS_INTERFACES,
        captured_stages=GATE9_D1_CAPTURED_STAGES,
        pending_stages=GATE9_PENDING_STAGES,
        cell_stage_records=tuple(records),
        interface_flux_records=(),
        acoustic_attempt_records=(),
        candidate_summary=candidate,
        diagnostic_status=(
            "D1_CAPTURE_COMPLETE" if not failures else "D1_PARTIAL_CAPTURE"
        ),
        cell_capture_status="D1_RETAINED_HISTORY_ADAPTER_ACTIVE",
        interface_capture_status="PENDING_D2_RUSANOV_DECOMPOSITION",
        acoustic_capture_status="PENDING_D3_ACOUSTIC_ATTEMPT_HOOKS",
        diagnostic_failures=tuple(failures),
        solver_identity=solver_identity(result),
        retained_history_sha256_before=before,
        retained_history_sha256_after=after,
    )


def run_gate9_d1_instrumented_case(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig,
    *,
    case_runner: Gate9CaseRunner = run_pipeline_depressurization_case,
) -> tuple[PipelineCaseResult, Gate9RunResult]:
    """Run the unchanged case, then attach D1 diagnostics after solver return."""

    solver_result = case_runner(case, config)
    diagnostics = instrument_pipeline_case_result(solver_result)
    if dict(diagnostics.solver_identity) != solver_identity(solver_result):
        raise HEMGate9InstrumentationError("diagnostic identity does not match solver result")
    if not diagnostics.solver_state_preserved:
        raise HEMGate9InstrumentationError("diagnostics changed retained solver state")
    return solver_result, diagnostics


def run_gate9_d1_identity_pair(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig,
    *,
    case_runner: Gate9CaseRunner = run_pipeline_depressurization_case,
) -> tuple[PipelineCaseResult, PipelineCaseResult, Gate9RunResult]:
    """Execute diagnostic-off/on paths and require exact solver identity."""

    diagnostic_off = case_runner(case, config)
    diagnostic_on, diagnostics = run_gate9_d1_instrumented_case(
        case,
        config,
        case_runner=case_runner,
    )
    if solver_identity(diagnostic_off) != solver_identity(diagnostic_on):
        raise HEMGate9InstrumentationError(
            "diagnostic off/on solver identity mismatch"
        )
    for name in (
        "time_history_s",
        "pressure_history_pa",
        "accepted_state_history",
    ):
        if not np.array_equal(
            np.asarray(getattr(diagnostic_off, name)),
            np.asarray(getattr(diagnostic_on, name)),
        ):
            raise HEMGate9InstrumentationError(
                f"diagnostic off/on {name} mismatch"
            )
    return diagnostic_off, diagnostic_on, diagnostics


def _flatten(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_dataclass_rows(path: Path, record_type: type, rows: Sequence[object]) -> None:
    fieldnames = [field.name for field in fields(record_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow({key: _flatten(payload[key]) for key in fieldnames})


def write_gate9_d1_scaffold_artifacts(
    output_dir: str | Path,
    diagnostics: Gate9RunResult,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": target / "summary.json",
        "cells": target / "focused_cell_stage_history.csv",
        "interfaces": target / "focused_interface_flux_decomposition.csv",
        "acoustic": target / "acoustic_attempt_history.csv",
        "candidate": target / "candidate_summary.json",
        "digest": target / "artifact_sha256.txt",
    }
    paths["summary"].write_text(
        json.dumps(diagnostics.summary(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_dataclass_rows(
        paths["cells"],
        Gate9CellStageRecord,
        diagnostics.cell_stage_records,
    )
    _write_dataclass_rows(
        paths["interfaces"],
        Gate9InterfaceFluxRecord,
        diagnostics.interface_flux_records,
    )
    _write_dataclass_rows(
        paths["acoustic"],
        Gate9AcousticAttemptRecord,
        diagnostics.acoustic_attempt_records,
    )
    paths["candidate"].write_text(
        json.dumps(asdict(diagnostics.candidate_summary), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = []
    for path in sorted(
        (value for key, value in paths.items() if key != "digest"),
        key=lambda item: item.name,
    ):
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    paths["digest"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    _, _, diagnostics = run_gate9_d1_identity_pair(
        case,
        HEMPipelineDepressurizationConfig(),
    )
    paths = write_gate9_d1_scaffold_artifacts(args.output_dir, diagnostics)
    print(json.dumps(diagnostics.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
