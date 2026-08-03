"""Gate 9 D4: event-align D1, D2, D3, and CFL-decision evidence.

This verification-only module observes the fixed CFL=0.10 pipeline case without
changing the production equations, numerical flux, sound-speed closure, phase
classifier, projection, boundary condition, thresholds, tolerances, or formal
stop path.

D4 increment 1 aligns the eight accepted steps before the immutable first
crossing and the candidate step itself.  The formal stop is honored; no
post-candidate continuation is manufactured.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

import numpy as np

from . import hem_pipeline_depressurization_first_crossing as pipeline_module
from .flux import observe_rusanov_flux
from .hem_acoustic_attempt_diagnostics import (
    Gate9AcousticAttemptEvent,
    observe_equilibrium_acoustic_attempts,
)
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
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
from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV

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
D4_SCHEMA_VERSION = "stage7_gate9_d4_event_alignment_increment1_v2"
D4_CFL_NO_NEW_TRIALS = "NO_NEW_SOUND_SPEED_ESTIMATOR_CALL_OBSERVED_DURING_COMPUTE_DT"
D4_CFL_TRIALS_OBSERVED = "SOUND_SPEED_ESTIMATOR_CALLS_OBSERVED_DURING_COMPUTE_DT"


class HEMGate9EventAlignmentError(RuntimeError):
    """Raised when the read-only D4 alignment contract cannot be preserved."""


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


@dataclass(frozen=True)
class _CflPrimitiveEvidence:
    velocity_m_s: np.ndarray
    sound_speed_m_s: np.ndarray


@dataclass
class _Trace:
    step: int | None = None
    time_before: float | None = None
    time_after: float | None = None
    dt: float | None = None
    pending_cfl_primitive: bool = False
    pending_pre_primitive: bool = False
    pending_final_primitive: bool = False
    cfl_primitive: _CflPrimitiveEvidence | None = None


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
    dt_s: float | None
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
class Gate9D4CflDecisionRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    dt_s: float
    dx_m: float
    maximum_characteristic_speed_m_s: float
    limiting_cell_index: int
    limiting_velocity_m_s: float
    limiting_sound_speed_m_s: float
    unconstrained_cfl_dt_s: float
    limited_by_t_end: bool
    measured_cfl: float
    focused_cell_indices: tuple[int, ...]
    focused_cell_velocities_m_s: tuple[float, ...]
    focused_cell_sound_speeds_m_s: tuple[float, ...]
    focused_cell_characteristic_speeds_m_s: tuple[float, ...]
    formula_identity_passed: bool
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
    cfl_observer: Callable[[Gate9D4CflDecisionRecord], None]
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
    array = np.ascontiguousarray(np.asarray(U, dtype="<f8"))
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _snapshot(runtime: _Runtime, trace: _Trace, stage: str, U: np.ndarray) -> None:
    if None in (trace.step, trace.time_before, trace.time_after, trace.dt):
        raise HEMGate9EventAlignmentError("incomplete step trace")
    when = trace.time_before if stage == "PRE_STEP_ACCEPTED" else trace.time_after
    state = np.array(U, dtype=float, copy=True)
    state.setflags(write=False)
    runtime.state_observer(
        Gate9D4StateSnapshot(
            case_id=runtime.case_id,
            cfl=runtime.cfl,
            absolute_step=int(trace.step),
            absolute_time_s=float(when),
            dt_s=float(trace.dt),
            stage=stage,
            state=state,
            state_sha256=_sha(state),
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


def _extended_mapping(
    rows: int,
    cells: int,
    ghosts: int,
    shift: int,
) -> tuple[int | None, ...]:
    out: list[int | None] = []
    for row in range(rows):
        extended = row + shift
        out.append(
            extended - ghosts if ghosts <= extended < ghosts + cells else None
        )
    return tuple(out)


class _EOSProxy:
    def __init__(
        self,
        base,
        runtime: _Runtime,
        trace: _Trace,
        left: Sequence[int | None],
        right: Sequence[int | None],
    ) -> None:
        self.base = base
        self.runtime = runtime
        self.trace = trace
        self.maps = (tuple(left), tuple(right))
        self.index = 0

    def __getattr__(self, name: str):
        return getattr(self.base, name)

    def primitive_from_conserved(self, U: np.ndarray):
        if self.index < 2:
            mapping = self.maps[self.index]
            name = ("FVM_FLUX_LEFT_STATE", "FVM_FLUX_RIGHT_STATE")[self.index]
            role = ("LEFT", "RIGHT")[self.index]
        else:
            mapping = tuple(None for _ in U)
            name = "FVM_FLUX_EXTRA_STATE"
            role = f"EXTRA_{self.index}"
        self.index += 1
        stage = _Stage(
            self.runtime.case_id,
            self.runtime.cfl,
            self.trace.step,
            self.trace.time_before,
            self.trace.dt,
            name,
            role,
        )
        with _stage(stage), _vector(stage, mapping):
            return self.base.primitive_from_conserved(U)


def _capture_cfl_primitive(
    trace: _Trace,
    primitive,
    expected_cells: int,
) -> None:
    velocity = np.asarray(primitive.u, dtype=float)
    sound = np.asarray(primitive.c, dtype=float)
    if (
        velocity.shape != (expected_cells,)
        or sound.shape != (expected_cells,)
        or not np.all(np.isfinite(velocity))
        or not np.all(np.isfinite(sound))
        or np.any(sound <= 0.0)
    ):
        raise HEMGate9EventAlignmentError(
            "compute_dt primitive must retain finite positive sound speeds"
        )
    velocity_copy = np.array(velocity, dtype=float, copy=True)
    sound_copy = np.array(sound, dtype=float, copy=True)
    velocity_copy.setflags(write=False)
    sound_copy.setflags(write=False)
    trace.cfl_primitive = _CflPrimitiveEvidence(
        velocity_m_s=velocity_copy,
        sound_speed_m_s=sound_copy,
    )


def _emit_cfl_decision(
    runtime: _Runtime,
    solver: FvmSolver,
    trace: _Trace,
    *,
    dt: float,
    t_end: float | None,
) -> None:
    if trace.step is None or trace.time_before is None:
        raise HEMGate9EventAlignmentError("compute_dt trace lacks step/time")
    evidence = trace.cfl_primitive
    if evidence is None:
        raise HEMGate9EventAlignmentError(
            "compute_dt did not expose the production primitive state"
        )
    wave = np.abs(evidence.velocity_m_s) + evidence.sound_speed_m_s
    max_speed = float(np.max(wave))
    limiting = int(np.argmax(wave))
    dx = float(solver.grid.dx)
    unconstrained = float(solver.cfl * dx / max_speed)
    expected = unconstrained
    limited = False
    if t_end is not None:
        remaining = max(float(t_end) - float(trace.time_before), 0.0)
        if remaining < expected:
            expected = remaining
            limited = True
    identity = float(dt).hex() == float(expected).hex()
    if not identity:
        raise HEMGate9EventAlignmentError(
            "captured CFL primitive does not reconstruct production compute_dt"
        )
    focus = tuple(int(cell) for cell in GATE9_FOCUS_CELLS)
    runtime.cfl_observer(
        Gate9D4CflDecisionRecord(
            case_id=runtime.case_id,
            cfl=runtime.cfl,
            absolute_step=int(trace.step),
            candidate_relative_step=0,
            absolute_time_s=float(trace.time_before),
            dt_s=float(dt),
            dx_m=dx,
            maximum_characteristic_speed_m_s=max_speed,
            limiting_cell_index=limiting,
            limiting_velocity_m_s=float(evidence.velocity_m_s[limiting]),
            limiting_sound_speed_m_s=float(evidence.sound_speed_m_s[limiting]),
            unconstrained_cfl_dt_s=unconstrained,
            limited_by_t_end=limited,
            measured_cfl=float(max_speed * dt / dx),
            focused_cell_indices=focus,
            focused_cell_velocities_m_s=tuple(
                float(evidence.velocity_m_s[cell]) for cell in focus
            ),
            focused_cell_sound_speeds_m_s=tuple(
                float(evidence.sound_speed_m_s[cell]) for cell in focus
            ),
            focused_cell_characteristic_speeds_m_s=tuple(
                float(wave[cell]) for cell in focus
            ),
            formula_identity_passed=True,
            capture_status="D4_EXACT_PRODUCTION_COMPUTE_DT_PRIMITIVE",
        )
    )
    trace.cfl_primitive = None


@contextmanager
def observe_gate9_d4_runtime(
    case_id: str,
    cfl: float,
    state_observer: Callable[[Gate9D4StateSnapshot], None],
    cfl_observer: Callable[[Gate9D4CflDecisionRecord], None],
) -> Iterator[None]:
    """Install temporary read-only wrappers for one D4 diagnostic-on run."""

    if _RUNTIME.get() is not None:
        raise HEMGate9EventAlignmentError("nested D4 contexts are prohibited")
    runtime = _Runtime(case_id, cfl, state_observer, cfl_observer)
    token = _RUNTIME.set(runtime)

    original_compute = FvmSolver.compute_dt
    original_primitive = FvmSolver.primitive
    original_step = FvmSolver.step
    original_project = pipeline_module.run_one_projected_fvm_case
    original_array = VerificationHEMLiquidOpenTwoPhaseEOS.primitive_from_conserved
    original_scalar = VerificationHEMLiquidOpenTwoPhaseEOS._evaluate_scalar

    def patched_compute(solver: FvmSolver, t_end=None):
        trace = runtime.trace(solver)
        trace.step = solver.step_count + 1
        trace.time_before = float(solver.t)
        trace.time_after = None
        trace.dt = None
        trace.pending_cfl_primitive = True
        trace.cfl_primitive = None
        try:
            dt = float(original_compute(solver, t_end))
        finally:
            trace.pending_cfl_primitive = False
        trace.dt = dt
        _emit_cfl_decision(runtime, solver, trace, dt=dt, t_end=t_end)
        trace.pending_pre_primitive = True
        return dt

    def patched_primitive(solver: FvmSolver):
        trace = runtime.trace(solver)
        if trace.pending_cfl_primitive:
            stage = _Stage(
                case_id,
                cfl,
                trace.step,
                trace.time_before,
                None,
                "CFL_DT_EVALUATION",
                "INTERNAL",
            )
        elif trace.pending_pre_primitive:
            trace.pending_pre_primitive = False
            stage = _Stage(
                case_id,
                cfl,
                trace.step,
                trace.time_before,
                trace.dt,
                "PRE_STEP_ACCEPTED",
                "INTERNAL",
            )
        elif trace.pending_final_primitive:
            trace.pending_final_primitive = False
            stage = _Stage(
                case_id,
                cfl,
                trace.step,
                trace.time_after,
                trace.dt,
                "FINAL_ACCEPTED",
                "INTERNAL",
            )
        else:
            return original_primitive(solver)

        with _stage(stage), _vector(stage, range(solver.grid.n_cells)):
            value = original_primitive(solver)
        if stage.name == "CFL_DT_EVALUATION":
            _capture_cfl_primitive(trace, value, solver.grid.n_cells)
        elif stage.name == "FINAL_ACCEPTED":
            _snapshot(runtime, trace, "FINAL_ACCEPTED", solver.U)
        return value

    def patched_step(solver: FvmSolver, dt=None):
        computed_here = dt is None
        actual = float(patched_compute(solver) if computed_here else dt)
        trace = runtime.trace(solver)
        if computed_here:
            trace.pending_pre_primitive = False
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
        stage = _Stage(
            case_id,
            cfl,
            trace.step,
            trace.time_after,
            trace.dt,
            "POST_FIRST_PROJECTION",
            "INTERNAL",
        )
        with _stage(stage):
            result = original_project(raw_case, config, **kwargs)
        if result.first_projection is not None:
            _snapshot(
                runtime,
                trace,
                "POST_FIRST_PROJECTION",
                result.first_projection.U_after,
            )
        if result.second_projection is not None:
            _snapshot(
                runtime,
                trace,
                "POST_SECOND_PROJECTION",
                result.second_projection.U_after,
            )
        trace.pending_final_primitive = result.outcome in {
            "ACCEPTED_CROSSING",
            "ACCEPTED_ALL_LIQUID_NOOP",
        }
        return result

    def patched_array(eos, U):
        if _VECTOR.get() is not None:
            return original_array(eos, U)
        stage = _STAGE.get()
        if stage is None:
            return original_array(eos, U)
        rows = int(np.asarray(U).shape[0])
        mapping = (
            tuple(range(rows))
            if rows == 32
            else tuple(None for _ in range(rows))
        )
        with _vector(stage, mapping):
            return original_array(eos, U)

    def patched_scalar(eos, rho, e):
        vector = _VECTOR.get()
        if vector is None:
            return original_scalar(eos, rho, e)
        position = vector.cursor
        vector.cursor += 1
        cell = vector.cells[position] if position < len(vector.cells) else None
        scalar_token = _SCALAR.set(_Scalar(vector.stage, cell))
        try:
            return original_scalar(eos, rho, e)
        finally:
            _SCALAR.reset(scalar_token)

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


def _align(
    event: Gate9AcousticAttemptEvent,
) -> Gate9D4AlignedAcousticRecord | None:
    scalar = _SCALAR.get()
    if scalar is None or scalar.cell is None:
        return None
    stage = scalar.stage
    if stage.step is None or stage.time_s is None:
        return None
    return Gate9D4AlignedAcousticRecord(
        case_id=stage.case_id,
        cfl=stage.cfl,
        absolute_step=int(stage.step),
        candidate_relative_step=0,
        absolute_time_s=float(stage.time_s),
        dt_s=None if stage.dt_s is None else float(stage.dt_s),
        cell_index=int(scalar.cell),
        stage=stage.name,
        vector_role=stage.role,
        evaluation_id=event.evaluation_id,
        event_kind=event.event_kind,
        axis=event.axis,
        center_rho_kg_m3=event.center_rho_kg_m3,
        center_e_j_kg=event.center_e_j_kg,
        center_phase_class=event.center_phase_class,
        base_density_increment=event.base_density_increment,
        base_energy_increment=event.base_energy_increment,
        halving_index=event.halving_index,
        trial_step=event.trial_step,
        trial_density_minus=event.trial_density_minus,
        trial_density_plus=event.trial_density_plus,
        trial_energy_minus=event.trial_energy_minus,
        trial_energy_plus=event.trial_energy_plus,
        minus_state_valid=event.minus_state_valid,
        plus_state_valid=event.plus_state_valid,
        minus_phase_or_scope_category=event.minus_phase_or_scope_category,
        plus_phase_or_scope_category=event.plus_phase_or_scope_category,
        computed_sound_speed_squared=event.computed_sound_speed_squared,
        accepted_or_refused=event.accepted_or_refused,
        refusal_category=event.refusal_category,
        backend_error_type=event.backend_error_type,
        capture_status="D4_ALIGNED_FROM_D3_SCALAR_CONTEXT",
    )


def _window_steps(result) -> tuple[tuple[int, ...], int, int, str]:
    if result.crossing_step is None:
        raise HEMGate9EventAlignmentError("candidate step is required")
    candidate = int(result.crossing_step)
    start = max(1, candidate - D4_PRE_STEPS)
    stop = min(int(result.step_count), candidate + D4_POST_STEPS)
    post = max(0, stop - candidate)
    status = (
        "AVAILABLE"
        if post == D4_POST_STEPS
        else D4_POST_STATUS_FORMAL_STOP
    )
    return tuple(range(start, stop + 1)), start, post, status


def _exact_cell_records(
    snapshots: Sequence[Gate9D4StateSnapshot],
    *,
    candidate_step: int,
    window_steps: set[int],
) -> tuple[Gate9D4ExactCellStageRecord, ...]:
    records: list[Gate9D4ExactCellStageRecord] = []
    for snapshot in snapshots:
        if snapshot.absolute_step not in window_steps:
            continue
        for cell in GATE9_FOCUS_CELLS:
            row = np.asarray(snapshot.state[cell], dtype=float)
            rho = float(row[IDX_RHO])
            rho_u = float(row[IDX_MOM])
            rho_E = float(row[IDX_RHOE])
            rho_q = float(row[IDX_RHO_XV])
            velocity = rho_u / rho
            internal = rho_E / rho - 0.5 * velocity * velocity
            records.append(
                Gate9D4ExactCellStageRecord(
                    case_id=snapshot.case_id,
                    cfl=snapshot.cfl,
                    absolute_step=snapshot.absolute_step,
                    candidate_relative_step=(
                        snapshot.absolute_step - candidate_step
                    ),
                    absolute_time_s=snapshot.absolute_time_s,
                    dt_s=snapshot.dt_s,
                    stage=snapshot.stage,
                    cell_index=int(cell),
                    rho=rho,
                    rho_u=rho_u,
                    rho_E=rho_E,
                    rho_q=rho_q,
                    velocity=velocity,
                    specific_internal_energy=internal,
                    specific_volume=1.0 / rho,
                    state_sha256=snapshot.state_sha256,
                    capture_status="D4_EXACT_SOLVER_OR_PROJECTION_STATE",
                )
            )
    return tuple(records)


def _require_identity(off: PipelineCaseResult, on: PipelineCaseResult) -> None:
    if solver_identity(off) != solver_identity(on):
        raise HEMGate9EventAlignmentError("D4 OFF/ON identity mismatch")
    for name in (
        "time_history_s",
        "pressure_history_pa",
        "accepted_state_history",
    ):
        if not np.array_equal(
            np.asarray(getattr(off, name)),
            np.asarray(getattr(on, name)),
        ):
            raise HEMGate9EventAlignmentError(f"D4 OFF/ON {name} mismatch")


_STAGE_ORDER = {
    "CFL_DT_EVALUATION": 0,
    "CFL_DT_DECISION": 0,
    "PRE_STEP_ACCEPTED": 1,
    "FVM_FLUX_LEFT_STATE": 2,
    "FVM_FLUX_RIGHT_STATE": 2,
    "FVM_FLUX_EXTRA_STATE": 2,
    "FVM_INTERFACE_FLUX": 2,
    "RAW_POST_FVM": 3,
    "POST_FIRST_PROJECTION": 4,
    "POST_SECOND_PROJECTION": 5,
    "FINAL_ACCEPTED": 6,
}
_ENTITY_ORDER = {"CFL": 0, "CELL": 1, "INTERFACE": 2, "ACOUSTIC": 3}


def _timeline(
    exact: Sequence[Gate9D4ExactCellStageRecord],
    interfaces: Sequence[Gate9InterfaceFluxRecord],
    acoustic: Sequence[Gate9D4AlignedAcousticRecord],
    cfl_decisions: Sequence[Gate9D4CflDecisionRecord],
    candidate_step: int,
) -> tuple[Gate9D4TimelineRecord, ...]:
    raw: list[
        tuple[tuple[object, ...], float, str, str, str, dict[str, object]]
    ] = []

    for record in cfl_decisions:
        detail = {
            "event_kind": "CFL_DT_DECISION",
            "dt_s": record.dt_s,
            "maximum_characteristic_speed_m_s": (
                record.maximum_characteristic_speed_m_s
            ),
            "limiting_cell_index": record.limiting_cell_index,
            "measured_cfl": record.measured_cfl,
            "formula_identity_passed": record.formula_identity_passed,
        }
        key = (
            record.absolute_step,
            _STAGE_ORDER["CFL_DT_DECISION"],
            _ENTITY_ORDER["CFL"],
            "GLOBAL",
            0,
        )
        raw.append(
            (
                key,
                record.absolute_time_s,
                "CFL_DT_DECISION",
                "CFL",
                "GLOBAL",
                detail,
            )
        )

    for record in exact:
        detail = {
            "event_kind": "STATE_SNAPSHOT",
            "state_sha256": record.state_sha256,
        }
        key = (
            record.absolute_step,
            _STAGE_ORDER.get(record.stage, 90),
            _ENTITY_ORDER["CELL"],
            str(record.cell_index),
            0,
        )
        raw.append(
            (
                key,
                record.absolute_time_s,
                record.stage,
                "CELL",
                str(record.cell_index),
                detail,
            )
        )

    for record in interfaces:
        detail = {
            "event_kind": "RUSANOV_FLUX",
            "a_max": record.a_max,
            "residual": record.normalized_reconstruction_residual,
        }
        key = (
            record.absolute_step,
            _STAGE_ORDER["FVM_INTERFACE_FLUX"],
            _ENTITY_ORDER["INTERFACE"],
            str(record.interface_id),
            0,
        )
        raw.append(
            (
                key,
                float(record.absolute_time_s),
                "FVM_INTERFACE_FLUX",
                "INTERFACE",
                str(record.interface_id),
                detail,
            )
        )

    for record in acoustic:
        detail = {
            "event_kind": record.event_kind,
            "halving_index": record.halving_index,
            "accepted_or_refused": record.accepted_or_refused,
            "refusal_category": record.refusal_category,
        }
        key = (
            record.absolute_step,
            _STAGE_ORDER.get(record.stage, 50),
            _ENTITY_ORDER["ACOUSTIC"],
            str(record.cell_index),
            record.evaluation_id,
            record.event_kind,
            record.axis,
            -1 if record.halving_index is None else record.halving_index,
        )
        raw.append(
            (
                key,
                record.absolute_time_s,
                record.stage,
                "ACOUSTIC",
                str(record.cell_index),
                detail,
            )
        )

    output: list[Gate9D4TimelineRecord] = []
    for index, item in enumerate(sorted(raw, key=lambda value: value[0])):
        key, time_s, stage, entity_type, entity_id, detail = item
        step = int(key[0])
        output.append(
            Gate9D4TimelineRecord(
                sequence_index=index,
                absolute_step=step,
                candidate_relative_step=step - candidate_step,
                absolute_time_s=float(time_s),
                stage=stage,
                entity_type=entity_type,
                entity_id=entity_id,
                event_kind=str(detail.get("event_kind", "STATE_OR_FLUX")),
                detail_json=json.dumps(detail, sort_keys=True),
            )
        )
    return tuple(output)


@dataclass(frozen=True)
class Gate9D4Result:
    exact_cell_stage_records: tuple[Gate9D4ExactCellStageRecord, ...]
    d1_cell_stage_records: tuple[Gate9CellStageRecord, ...]
    interface_flux_records: tuple[Gate9InterfaceFluxRecord, ...]
    acoustic_records: tuple[Gate9D4AlignedAcousticRecord, ...]
    cfl_decision_records: tuple[Gate9D4CflDecisionRecord, ...]
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
            "schema_version": D4_SCHEMA_VERSION,
            "scope": D4_SCOPE,
            "case_id": "pipeline_crossing_candidate_p5m5_to_p2m5",
            "cfl": 0.10,
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
            "candidate_step": self.candidate_step,
            "candidate_time_s": self.candidate_time_s,
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


def _finalize_acoustic(
    records: Sequence[Gate9D4AlignedAcousticRecord],
    *,
    candidate_step: int,
    dt_by_step: Mapping[int, float],
    window_steps: set[int],
) -> tuple[Gate9D4AlignedAcousticRecord, ...]:
    output: list[Gate9D4AlignedAcousticRecord] = []
    for record in records:
        if (
            record.absolute_step not in window_steps
            or record.cell_index not in GATE9_FOCUS_CELLS
        ):
            continue
        dt = (
            float(record.dt_s)
            if record.dt_s is not None
            else float(dt_by_step[record.absolute_step])
        )
        output.append(
            replace(
                record,
                candidate_relative_step=(
                    record.absolute_step - candidate_step
                ),
                dt_s=dt,
            )
        )
    return tuple(output)


def _finalize_cfl(
    records: Sequence[Gate9D4CflDecisionRecord],
    *,
    candidate_step: int,
    window_steps: set[int],
) -> tuple[Gate9D4CflDecisionRecord, ...]:
    return tuple(
        replace(
            record,
            candidate_relative_step=record.absolute_step - candidate_step,
        )
        for record in records
        if record.absolute_step in window_steps
    )


def run_gate9_d4_identity_pair(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig,
):
    """Run the immutable case OFF/ON and return event-aligned D4 evidence."""

    off = run_pipeline_depressurization_case(case, config)
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
            config.cfl,
            snapshots.append,
            cfl_raw.append,
        ),
        observe_rusanov_flux(rusanov),
        observe_equilibrium_acoustic_attempts(acoustic_observer),
    ):
        on = run_pipeline_depressurization_case(case, config)

    _require_identity(off, on)
    if (
        on.outcome != "ACCEPTED_FIRST_CROSSING"
        or on.crossing_step != 125
        or on.crossing_time_s != 7.999325695335248e-4
        or tuple(on.crossing_cell_indices) != (29,)
    ):
        raise HEMGate9EventAlignmentError(
            "D4 did not reproduce the fixed candidate"
        )

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
        raise HEMGate9EventAlignmentError(
            "no focused aligned acoustic evidence"
        )
    timeline = _timeline(
        exact,
        interfaces,
        acoustic,
        cfl_decisions,
        candidate,
    )
    result = Gate9D4Result(
        exact_cell_stage_records=exact,
        d1_cell_stage_records=d1,
        interface_flux_records=interfaces,
        acoustic_records=acoustic,
        cfl_decision_records=cfl_decisions,
        timeline_records=timeline,
        candidate_step=candidate,
        candidate_time_s=float(on.crossing_time_s),
        window_steps=steps,
        window_start_step=start,
        available_post_step_count=post_count,
        post_window_status=post_status,
        diagnostic_off_on_identity=True,
        solver_identity_off=solver_identity(off),
        solver_identity_on=solver_identity(on),
    )
    summary = result.summary()
    if summary["exact_cell_stage_record_count"] != len(steps) * 5 * 4:
        raise HEMGate9EventAlignmentError("incomplete exact stage window")
    if summary["d1_cell_stage_record_count"] != len(steps) * 3 * 4:
        raise HEMGate9EventAlignmentError("incomplete D1 window")
    if summary["interface_flux_record_count"] != len(steps) * 5:
        raise HEMGate9EventAlignmentError("incomplete interface window")
    if summary["cfl_decision_record_count"] != len(steps):
        raise HEMGate9EventAlignmentError("incomplete CFL decision window")
    if not summary["all_acoustic_records_have_step_cell_stage_dt"]:
        raise HEMGate9EventAlignmentError("incomplete acoustic alignment")
    if not summary["all_cfl_decisions_match_production_dt"]:
        raise HEMGate9EventAlignmentError("CFL decision identity failed")
    if not summary["all_timeline_records_have_source_time"]:
        raise HEMGate9EventAlignmentError(
            "timeline contains a synthetic or missing event time"
        )
    return off, on, result


def _flatten(value: object) -> object:
    return (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (tuple, list, dict))
        else value
    )


def _write(path: Path, record_type: type, rows: Sequence[object]) -> None:
    names = [item.name for item in fields(record_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow(
                {name: _flatten(payload[name]) for name in names}
            )


def write_gate9_d4_artifacts(
    output_dir: str | Path,
    result: Gate9D4Result,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
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
    paths["summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True) + "\n",
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
                "candidate_step": result.candidate_step,
                "candidate_time_s": result.candidate_time_s,
                "window_steps": list(result.window_steps),
                "post_window_status": result.post_window_status,
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
            (
                value
                for key, value in paths.items()
                if key != "digest"
            ),
            key=lambda path: path.name,
        )
    ]
    paths["digest"].write_text(
        "\n".join(digest_lines) + "\n",
        encoding="utf-8",
    )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    _, _, result = run_gate9_d4_identity_pair(
        FIXED_PIPELINE_DEPRESSURIZATION_CASES[0],
        HEMPipelineDepressurizationConfig(),
    )
    paths = write_gate9_d4_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
