"""Gate 9 D4: event-align D1, D2 and D3 evidence for CFL=0.10."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

import numpy as np

from . import hem_pipeline_depressurization_first_crossing as pipeline_module
from .flux import observe_rusanov_flux
from .hem_acoustic_attempt_diagnostics import (
    Gate9AcousticAttemptEvent,
    observe_equilibrium_acoustic_attempts,
)
from .hem_mixed_liquid_open_two_phase_eos import VerificationHEMLiquidOpenTwoPhaseEOS
from .hem_pipeline_crossing_depth_diagnosis import (
    GATE9_FOCUS_CELLS,
    Gate9CellStageRecord,
    Gate9InterfaceFluxRecord,
    instrument_pipeline_case_result,
    solver_identity,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    run_pipeline_depressurization_case,
)
from .hem_rusanov_diagnostic_decomposition import (
    Gate9RusanovEvaluationCollector,
    RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE,
    build_gate9_interface_flux_records,
)
from .solver import FvmSolver
from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, N_VARS

D4_CAPTURED_STAGES = (
    "PRE_STEP_ACCEPTED",
    "RAW_POST_FVM",
    "POST_FIRST_PROJECTION",
    "POST_SECOND_PROJECTION",
    "FINAL_ACCEPTED",
)
D4_PRE_STEPS = 8
D4_POST_STEPS = 8
D4_POST_STATUS_FORMAL_STOP = "NOT_AVAILABLE_DUE_TO_FORMAL_STOP"
D4_SCOPE = "verification_only_event_aligned_d1_d2_d3_integration"
PROPERTY_BACKEND_NAME = "coolprop_co2"
PROPERTY_BACKEND_DESIGN_STATUS = "VERIFICATION_ONLY_NOT_APPROVED_FOR_DESIGN_USE"


class HEMGate9EventAlignmentError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Stage:
    case_id: str
    cfl: float
    step: int | None
    time_s: float | None
    dt_s: float | None
    name: str
    role: str = ""


@dataclass
class _Vector:
    stage: _Stage
    cells: tuple[int | None, ...]
    cursor: int = 0


@dataclass(frozen=True)
class _Scalar:
    stage: _Stage
    cell: int | None


@dataclass
class _Trace:
    step: int | None = None
    time_before: float | None = None
    time_after: float | None = None
    dt: float | None = None
    pending_pre_primitive: bool = False
    pending_final_primitive: bool = False


@dataclass(frozen=True)
class Gate9D4StateSnapshot:
    case_id: str
    cfl: float
    absolute_step: int
    absolute_time_s: float
    dt_s: float
    stage: str
    state: np.ndarray
    state_sha256: str


@dataclass(frozen=True)
class Gate9D4ExactCellStageRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    dt_s: float
    stage: str
    cell_index: int
    rho: float
    rho_u: float
    rho_E: float
    rho_q: float
    velocity: float
    specific_internal_energy: float
    specific_volume: float
    state_sha256: str
    capture_status: str


@dataclass(frozen=True)
class Gate9D4AlignedAcousticRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    dt_s: float
    cell_index: int
    stage: str
    vector_role: str
    evaluation_id: int
    event_kind: str
    axis: str
    center_rho_kg_m3: float
    center_e_j_kg: float
    center_phase_class: str
    base_density_increment: float | None
    base_energy_increment: float | None
    halving_index: int | None
    trial_step: float | None
    trial_density_minus: float | None
    trial_density_plus: float | None
    trial_energy_minus: float | None
    trial_energy_plus: float | None
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
class Gate9D4TimelineRecord:
    sequence_index: int
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    stage: str
    entity_type: str
    entity_id: str
    event_kind: str
    detail_json: str


@dataclass
class _Runtime:
    case_id: str
    cfl: float
    state_observer: Callable[[Gate9D4StateSnapshot], None]
    traces: dict[int, _Trace] = field(default_factory=dict)
    last_solver: int | None = None

    def trace(self, solver: FvmSolver) -> _Trace:
        key = id(solver)
        self.last_solver = key
        return self.traces.setdefault(key, _Trace())

    def current(self) -> _Trace:
        if self.last_solver is None:
            raise HEMGate9EventAlignmentError("no active solver trace")
        return self.traces[self.last_solver]


_STAGE: ContextVar[_Stage | None] = ContextVar("gate9_d4_stage", default=None)
_VECTOR: ContextVar[_Vector | None] = ContextVar("gate9_d4_vector", default=None)
_SCALAR: ContextVar[_Scalar | None] = ContextVar("gate9_d4_scalar", default=None)
_RUNTIME: ContextVar[_Runtime | None] = ContextVar("gate9_d4_runtime", default=None)


def _sha(U: np.ndarray) -> str:
    a = np.ascontiguousarray(np.asarray(U, dtype="<f8"))
    return hashlib.sha256(a.tobytes(order="C")).hexdigest()


def _snapshot(runtime: _Runtime, trace: _Trace, stage: str, U: np.ndarray) -> None:
    if None in (trace.step, trace.time_before, trace.time_after, trace.dt):
        raise HEMGate9EventAlignmentError("incomplete step trace")
    when = trace.time_before if stage == "PRE_STEP_ACCEPTED" else trace.time_after
    state = np.array(U, dtype=float, copy=True)
    state.setflags(write=False)
    runtime.state_observer(
        Gate9D4StateSnapshot(
            runtime.case_id,
            runtime.cfl,
            int(trace.step),
            float(when),
            float(trace.dt),
            stage,
            state,
            _sha(state),
        )
    )


@contextmanager
def _stage(stage: _Stage) -> Iterator[None]:
    token = _STAGE.set(stage)
    try:
        yield
    finally:
        _STAGE.reset(token)


@contextmanager
def _vector(stage: _Stage, cells: Sequence[int | None]) -> Iterator[None]:
    token = _VECTOR.set(_Vector(stage, tuple(cells)))
    try:
        yield
    finally:
        _VECTOR.reset(token)


def _extended_mapping(rows: int, cells: int, ghosts: int, shift: int) -> tuple[int | None, ...]:
    out: list[int | None] = []
    for row in range(rows):
        extended = row + shift
        out.append(extended - ghosts if ghosts <= extended < ghosts + cells else None)
    return tuple(out)


class _EOSProxy:
    def __init__(self, base, runtime: _Runtime, trace: _Trace, left, right) -> None:
        self.base = base
        self.runtime = runtime
        self.trace = trace
        self.maps = (left, right)
        self.index = 0

    def __getattr__(self, name: str):
        return getattr(self.base, name)

    def primitive_from_conserved(self, U: np.ndarray):
        mapping = self.maps[self.index] if self.index < 2 else tuple(None for _ in U)
        name = ("FVM_FLUX_LEFT_STATE", "FVM_FLUX_RIGHT_STATE")[self.index] if self.index < 2 else "FVM_FLUX_EXTRA_STATE"
        role = ("LEFT", "RIGHT")[self.index] if self.index < 2 else f"EXTRA_{self.index}"
        self.index += 1
        s = _Stage(self.runtime.case_id, self.runtime.cfl, self.trace.step, self.trace.time_before, self.trace.dt, name, role)
        with _stage(s), _vector(s, mapping):
            return self.base.primitive_from_conserved(U)


@contextmanager
def observe_gate9_d4_runtime(case_id: str, cfl: float, state_observer) -> Iterator[None]:
    if _RUNTIME.get() is not None:
        raise HEMGate9EventAlignmentError("nested D4 contexts are prohibited")
    runtime = _Runtime(case_id, cfl, state_observer)
    token = _RUNTIME.set(runtime)

    original_compute = FvmSolver.compute_dt
    original_primitive = FvmSolver.primitive
    original_step = FvmSolver.step
    original_project = pipeline_module.run_one_projected_fvm_case
    original_array = VerificationHEMLiquidOpenTwoPhaseEOS.primitive_from_conserved
    original_scalar = VerificationHEMLiquidOpenTwoPhaseEOS._evaluate_scalar

    def patched_compute(solver: FvmSolver, t_end=None):
        dt = original_compute(solver, t_end)
        trace = runtime.trace(solver)
        trace.step = solver.step_count + 1
        trace.time_before = float(solver.t)
        trace.dt = float(dt)
        trace.pending_pre_primitive = True
        return dt

    def patched_primitive(solver: FvmSolver):
        trace = runtime.trace(solver)
        if trace.pending_pre_primitive:
            trace.pending_pre_primitive = False
            s = _Stage(case_id, cfl, trace.step, trace.time_before, trace.dt, "PRE_STEP_ACCEPTED", "INTERNAL")
        elif trace.pending_final_primitive:
            trace.pending_final_primitive = False
            s = _Stage(case_id, cfl, trace.step, trace.time_after, trace.dt, "FINAL_ACCEPTED", "INTERNAL")
        else:
            return original_primitive(solver)
        with _stage(s), _vector(s, range(solver.grid.n_cells)):
            value = original_primitive(solver)
        if s.name == "FINAL_ACCEPTED":
            _snapshot(runtime, trace, "FINAL_ACCEPTED", solver.U)
        return value

    def patched_step(solver: FvmSolver, dt=None):
        trace = runtime.trace(solver)
        actual = float(dt if dt is not None else original_compute(solver))
        trace.step = solver.step_count + 1
        trace.time_before = float(solver.t)
        trace.dt = actual
        trace.time_after = trace.time_before + actual
        _snapshot(runtime, trace, "PRE_STEP_ACCEPTED", solver.U)
        rows = solver.grid.n_cells + 2 * solver.n_ghost - 1
        left = _extended_mapping(rows, solver.grid.n_cells, solver.n_ghost, 0)
        right = _extended_mapping(rows, solver.grid.n_cells, solver.n_ghost, 1)
        base = solver.eos
        solver.eos = _EOSProxy(base, runtime, trace, left, right)
        try:
            used = original_step(solver, actual)
        finally:
            solver.eos = base
        trace.time_after = float(solver.t)
        _snapshot(runtime, trace, "RAW_POST_FVM", solver.U)
        return used

    def patched_project(raw_case, config, **kwargs):
        trace = runtime.current()
        s = _Stage(case_id, cfl, trace.step, trace.time_after, trace.dt, "POST_FIRST_PROJECTION", "INTERNAL")
        with _stage(s):
            result = original_project(raw_case, config, **kwargs)
        if result.first_projection is not None:
            _snapshot(runtime, trace, "POST_FIRST_PROJECTION", result.first_projection.U_after)
        if result.second_projection is not None:
            _snapshot(runtime, trace, "POST_SECOND_PROJECTION", result.second_projection.U_after)
        trace.pending_final_primitive = result.outcome in {"ACCEPTED_CROSSING", "ACCEPTED_ALL_LIQUID_NOOP"}
        return result

    def patched_array(eos, U):
        if _VECTOR.get() is not None:
            return original_array(eos, U)
        s = _STAGE.get()
        if s is None:
            return original_array(eos, U)
        rows = int(np.asarray(U).shape[0])
        mapping = tuple(range(rows)) if rows == 32 else tuple(None for _ in range(rows))
        with _vector(s, mapping):
            return original_array(eos, U)

    def patched_scalar(eos, rho, e):
        vector = _VECTOR.get()
        if vector is None:
            return original_scalar(eos, rho, e)
        position = vector.cursor
        vector.cursor += 1
        cell = vector.cells[position] if position < len(vector.cells) else None
        token_scalar = _SCALAR.set(_Scalar(vector.stage, cell))
        try:
            return original_scalar(eos, rho, e)
        finally:
            _SCALAR.reset(token_scalar)

    FvmSolver.compute_dt = patched_compute
    FvmSolver.primitive = patched_primitive
    FvmSolver.step = patched_step
    pipeline_module.run_one_projected_fvm_case = patched_project
    VerificationHEMLiquidOpenTwoPhaseEOS.primitive_from_conserved = patched_array
    VerificationHEMLiquidOpenTwoPhaseEOS._evaluate_scalar = patched_scalar
    try:
        yield
    finally:
        VerificationHEMLiquidOpenTwoPhaseEOS._evaluate_scalar = original_scalar
        VerificationHEMLiquidOpenTwoPhaseEOS.primitive_from_conserved = original_array
        pipeline_module.run_one_projected_fvm_case = original_project
        FvmSolver.step = original_step
        FvmSolver.primitive = original_primitive
        FvmSolver.compute_dt = original_compute
        _RUNTIME.reset(token)


def _align(event: Gate9AcousticAttemptEvent) -> Gate9D4AlignedAcousticRecord | None:
    scalar = _SCALAR.get()
    if scalar is None or scalar.cell is None:
        return None
    s = scalar.stage
    if None in (s.step, s.time_s, s.dt_s):
        return None
    return Gate9D4AlignedAcousticRecord(
        s.case_id, s.cfl, int(s.step), 0, float(s.time_s), float(s.dt_s), int(scalar.cell), s.name, s.role,
        event.evaluation_id, event.event_kind, event.axis, event.center_rho_kg_m3, event.center_e_j_kg,
        event.center_phase_class, event.base_density_increment, event.base_energy_increment,
        event.halving_index, event.trial_step, event.trial_density_minus, event.trial_density_plus,
        event.trial_energy_minus, event.trial_energy_plus, event.minus_state_valid, event.plus_state_valid,
        event.minus_phase_or_scope_category, event.plus_phase_or_scope_category,
        event.computed_sound_speed_squared, event.accepted_or_refused, event.refusal_category,
        event.backend_error_type, "D4_ALIGNED_FROM_D3_SCALAR_CONTEXT",
    )


def _window_steps(result) -> tuple[tuple[int, ...], int, int, str]:
    if result.crossing_step is None:
        raise HEMGate9EventAlignmentError("candidate step is required")
    candidate = int(result.crossing_step)
    start = max(1, candidate - D4_PRE_STEPS)
    stop = min(int(result.step_count), candidate + D4_POST_STEPS)
    post = max(0, stop - candidate)
    status = "AVAILABLE" if post == D4_POST_STEPS else D4_POST_STATUS_FORMAL_STOP
    return tuple(range(start, stop + 1)), start, post, status


def _exact_cell_records(snapshots, *, candidate_step: int, window_steps: set[int]):
    records = []
    for snap in snapshots:
        if snap.absolute_step not in window_steps:
            continue
        for cell in GATE9_FOCUS_CELLS:
            row = np.asarray(snap.state[cell], dtype=float)
            rho = float(row[IDX_RHO])
            rho_u = float(row[IDX_MOM])
            rho_E = float(row[IDX_RHOE])
            rho_q = float(row[IDX_RHO_XV])
            u = rho_u / rho
            e = rho_E / rho - 0.5 * u * u
            records.append(Gate9D4ExactCellStageRecord(
                snap.case_id, snap.cfl, snap.absolute_step, snap.absolute_step - candidate_step,
                snap.absolute_time_s, snap.dt_s, snap.stage, int(cell), rho, rho_u, rho_E, rho_q,
                u, e, 1.0 / rho, snap.state_sha256, "D4_EXACT_SOLVER_OR_PROJECTION_STATE",
            ))
    return tuple(records)


def _require_identity(off: PipelineCaseResult, on: PipelineCaseResult) -> None:
    if solver_identity(off) != solver_identity(on):
        raise HEMGate9EventAlignmentError("D4 OFF/ON identity mismatch")
    for name in ("time_history_s", "pressure_history_pa", "accepted_state_history"):
        if not np.array_equal(np.asarray(getattr(off, name)), np.asarray(getattr(on, name))):
            raise HEMGate9EventAlignmentError(f"D4 OFF/ON {name} mismatch")


def _timeline(exact, interfaces, acoustic, candidate_step: int):
    stage_order = {name: i for i, name in enumerate(D4_CAPTURED_STAGES)}
    raw: list[tuple[tuple, str, str, str, dict]] = []
    for r in exact:
        raw.append(((r.absolute_step, stage_order.get(r.stage, 90), 0, str(r.cell_index), 0), r.stage, "CELL", str(r.cell_index), {"state_sha256": r.state_sha256}))
    for r in interfaces:
        raw.append(((r.absolute_step, 1, 1, str(r.interface_id), 0), "FVM_INTERFACE_FLUX", "INTERFACE", r.interface_id, {"a_max": r.a_max, "residual": r.normalized_reconstruction_residual}))
    for r in acoustic:
        raw.append(((r.absolute_step, stage_order.get(r.stage, 50), 2, str(r.cell_index), r.evaluation_id), r.stage, "ACOUSTIC", str(r.cell_index), {"event_kind": r.event_kind, "halving_index": r.halving_index, "accepted_or_refused": r.accepted_or_refused, "refusal_category": r.refusal_category}))
    out = []
    for index, item in enumerate(sorted(raw, key=lambda value: value[0])):
        key, stage, entity_type, entity_id, detail = item
        step = int(key[0])
        time_candidates = [r.absolute_time_s for r in exact if r.absolute_step == step and r.stage == stage]
        time_s = float(time_candidates[0]) if time_candidates else 0.0
        out.append(Gate9D4TimelineRecord(index, step, step - candidate_step, time_s, stage, entity_type, entity_id, detail.get("event_kind", "STATE_OR_FLUX"), json.dumps(detail, sort_keys=True)))
    return tuple(out)


@dataclass(frozen=True)
class Gate9D4Result:
    exact_cell_stage_records: tuple[Gate9D4ExactCellStageRecord, ...]
    d1_cell_stage_records: tuple[Gate9CellStageRecord, ...]
    interface_flux_records: tuple[Gate9InterfaceFluxRecord, ...]
    acoustic_records: tuple[Gate9D4AlignedAcousticRecord, ...]
    timeline_records: tuple[Gate9D4TimelineRecord, ...]
    candidate_step: int
    candidate_time_s: float
    window_steps: tuple[int, ...]
    window_start_step: int
    available_post_step_count: int
    post_window_status: str
    diagnostic_off_on_identity: bool
    solver_identity_off: Mapping[str, object]
    solver_identity_on: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "stage7_gate9_d4_event_alignment_increment1_v1",
            "scope": D4_SCOPE,
            "case_id": "pipeline_crossing_candidate_p5m5_to_p2m5",
            "cfl": 0.10,
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
            "candidate_step": self.candidate_step,
            "candidate_time_s": self.candidate_time_s,
            "window_steps": list(self.window_steps),
            "window_start_step": self.window_start_step,
            "available_pre_step_count": self.candidate_step - self.window_start_step,
            "available_post_step_count": self.available_post_step_count,
            "post_window_status": self.post_window_status,
            "focused_cells": list(GATE9_FOCUS_CELLS),
            "captured_exact_stages": list(D4_CAPTURED_STAGES),
            "exact_cell_stage_record_count": len(self.exact_cell_stage_records),
            "d1_cell_stage_record_count": len(self.d1_cell_stage_records),
            "interface_flux_record_count": len(self.interface_flux_records),
            "aligned_acoustic_record_count": len(self.acoustic_records),
            "timeline_record_count": len(self.timeline_records),
            "all_acoustic_records_have_step_cell_stage": all(r.absolute_step in self.window_steps and r.cell_index in GATE9_FOCUS_CELLS and bool(r.stage) for r in self.acoustic_records),
            "rusanov_reconstruction_guard_passed": all(r.normalized_reconstruction_residual is not None and r.normalized_reconstruction_residual <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE for r in self.interface_flux_records),
            "diagnostic_off_on_identity": self.diagnostic_off_on_identity,
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


def run_gate9_d4_identity_pair(case: PipelineDepressurizationCaseSpec, config: HEMPipelineDepressurizationConfig):
    off = run_pipeline_depressurization_case(case, config)
    snapshots: list[Gate9D4StateSnapshot] = []
    acoustic_raw: list[Gate9D4AlignedAcousticRecord] = []
    rusanov = Gate9RusanovEvaluationCollector()

    def acoustic_observer(event: Gate9AcousticAttemptEvent) -> None:
        aligned = _align(event)
        if aligned is not None:
            acoustic_raw.append(aligned)

    with observe_gate9_d4_runtime(case.case_id, config.cfl, snapshots.append), observe_rusanov_flux(rusanov), observe_equilibrium_acoustic_attempts(acoustic_observer):
        on = run_pipeline_depressurization_case(case, config)
    _require_identity(off, on)
    if on.outcome != "ACCEPTED_FIRST_CROSSING" or on.crossing_step != 125 or on.crossing_time_s != 7.999325695335248e-4 or tuple(on.crossing_cell_indices) != (29,):
        raise HEMGate9EventAlignmentError("D4 did not reproduce the fixed candidate")

    steps, start, post_count, post_status = _window_steps(on)
    step_set = set(steps)
    candidate = int(on.crossing_step)
    exact = _exact_cell_records(snapshots, candidate_step=candidate, window_steps=step_set)
    d1 = tuple(r for r in instrument_pipeline_case_result(on).cell_stage_records if r.absolute_step in step_set)
    interfaces = tuple(r for r in build_gate9_interface_flux_records(on, rusanov.evaluations) if r.absolute_step in step_set)
    acoustic = tuple(Gate9D4AlignedAcousticRecord(**{**asdict(r), "candidate_relative_step": r.absolute_step - candidate}) for r in acoustic_raw if r.absolute_step in step_set and r.cell_index in GATE9_FOCUS_CELLS)
    if not acoustic:
        raise HEMGate9EventAlignmentError("no focused aligned acoustic evidence")
    timeline = _timeline(exact, interfaces, acoustic, candidate)
    result = Gate9D4Result(exact, d1, interfaces, acoustic, timeline, candidate, float(on.crossing_time_s), steps, start, post_count, post_status, True, solver_identity(off), solver_identity(on))
    summary = result.summary()
    if summary["exact_cell_stage_record_count"] != len(steps) * 5 * 4:
        raise HEMGate9EventAlignmentError("incomplete exact stage window")
    if summary["d1_cell_stage_record_count"] != len(steps) * 3 * 4:
        raise HEMGate9EventAlignmentError("incomplete D1 window")
    if summary["interface_flux_record_count"] != len(steps) * 5:
        raise HEMGate9EventAlignmentError("incomplete interface window")
    if not summary["all_acoustic_records_have_step_cell_stage"]:
        raise HEMGate9EventAlignmentError("incomplete acoustic alignment")
    return off, on, result


def _flatten(value: object) -> object:
    return json.dumps(value, sort_keys=True) if isinstance(value, (tuple, list, dict)) else value


def _write(path: Path, record_type: type, rows: Sequence[object]) -> None:
    names = [f.name for f in fields(record_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow({name: _flatten(payload[name]) for name in names})


def write_gate9_d4_artifacts(output_dir: str | Path, result: Gate9D4Result) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": target / "summary.json",
        "exact_cells": target / "event_aligned_exact_cell_stage_history.csv",
        "d1_cells": target / "event_aligned_d1_cell_stage_history.csv",
        "interfaces": target / "event_aligned_interface_flux_history.csv",
        "acoustic": target / "event_aligned_acoustic_history.csv",
        "timeline": target / "candidate_event_timeline.csv",
        "candidate": target / "candidate_summary.json",
        "digest": target / "artifact_sha256.txt",
    }
    paths["summary"].write_text(json.dumps(result.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write(paths["exact_cells"], Gate9D4ExactCellStageRecord, result.exact_cell_stage_records)
    _write(paths["d1_cells"], Gate9CellStageRecord, result.d1_cell_stage_records)
    _write(paths["interfaces"], Gate9InterfaceFluxRecord, result.interface_flux_records)
    _write(paths["acoustic"], Gate9D4AlignedAcousticRecord, result.acoustic_records)
    _write(paths["timeline"], Gate9D4TimelineRecord, result.timeline_records)
    paths["candidate"].write_text(json.dumps({"candidate_step": result.candidate_step, "candidate_time_s": result.candidate_time_s, "window_steps": list(result.window_steps), "post_window_status": result.post_window_status}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in sorted((p for k, p in paths.items() if k != "digest"), key=lambda p: p.name)]
    paths["digest"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    _, _, result = run_gate9_d4_identity_pair(FIXED_PIPELINE_DEPRESSURIZATION_CASES[0], HEMPipelineDepressurizationConfig())
    paths = write_gate9_d4_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
