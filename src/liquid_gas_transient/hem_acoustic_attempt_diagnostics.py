"""Gate 9 D3 read-only acoustic trial and halving diagnostics.

This verification-only module temporarily wraps the dispatch point used by the
existing equilibrium sound-speed estimator.  The original estimator, central
stencil loop, property evaluator, formulas, guards, return values, and exceptions
remain unchanged.  A transparent evaluator proxy records the exact production
``rho/e`` calls, then reconstructs the already-executed halving sequence from
those calls for evidence only.

D3 increment 1 deliberately leaves step/cell/stage alignment to D4.  It records
production acoustic evaluations for the immutable CFL=0.10 identity column and
proves diagnostic OFF/ON equality without assigning a root cause.
"""

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

from . import hem_equilibrium_sound_speed as acoustic_module
from .hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedConfig,
    HEMEquilibriumSoundSpeedEstimate,
    PressurePhaseEvaluator,
    PressurePhaseSample,
)
from .hem_pipeline_crossing_depth_diagnosis import solver_identity
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    run_pipeline_depressurization_case,
)

PROPERTY_BACKEND_NAME = "coolprop_co2"
PROPERTY_BACKEND_DESIGN_STATUS = "VERIFICATION_ONLY_NOT_APPROVED_FOR_DESIGN_USE"
D3_MAX_EXISTING_HALVINGS = 12
D3_CAPTURE_STATUS = "D3_EXACT_EXISTING_EVALUATOR_CALL_SEQUENCE"
D3_ALIGNMENT_STATUS = "PENDING_D4_EVENT_ALIGNED_STEP_CELL_STAGE_MAPPING"


class HEMGate9AcousticDiagnosticError(RuntimeError):
    """Raised when the D3 observer cannot preserve or parse the fixed path."""


@dataclass(frozen=True)
class Gate9AcousticAttemptEvent:
    """One raw acoustic center, stencil-attempt, or final-result event."""

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
    capture_status: str = D3_CAPTURE_STATUS


AcousticAttemptObserver = Callable[[Gate9AcousticAttemptEvent], None]


@dataclass(frozen=True)
class _EvaluatorCall:
    rho_kg_m3: float
    e_j_kg: float
    returned: bool
    pressure_pa: float | None
    phase_class: str
    scope_status: str
    error_type: str

    @property
    def guarded_valid(self) -> bool:
        return bool(
            self.returned
            and self.pressure_pa is not None
            and np.isfinite(self.pressure_pa)
            and self.pressure_pa > 0.0
            and self.scope_status == "supported_candidate"
            and self.phase_class
        )

    @property
    def phase_scope_category(self) -> str:
        if not self.returned:
            return "EVALUATION_FAILED"
        return f"{self.phase_class}|{self.scope_status}"


@dataclass
class _ObserverState:
    observer: AcousticAttemptObserver
    next_evaluation_id: int = 0


_OBSERVER_STATE: ContextVar[_ObserverState | None] = ContextVar(
    "liquid_gas_transient_gate9_acoustic_observer",
    default=None,
)


@dataclass
class Gate9AcousticAttemptCollector:
    """Collect immutable D3 events in production evaluation order."""

    events: list[Gate9AcousticAttemptEvent] = field(default_factory=list)

    def __call__(self, event: Gate9AcousticAttemptEvent) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class Gate9D3Result:
    events: tuple[Gate9AcousticAttemptEvent, ...]
    diagnostic_off_on_identity: bool
    solver_identity_off: Mapping[str, object]
    solver_identity_on: Mapping[str, object]
    candidate_step: int | None
    candidate_time_s: float | None
    candidate_cells: tuple[int, ...]
    maximum_candidate_q_equilibrium: float
    formal_outcome: str
    final_state_sha256: str
    run_signature_sha256: str

    def summary(self) -> dict[str, object]:
        attempts = [event for event in self.events if event.event_kind == "STENCIL_ATTEMPT"]
        density_attempts = [event for event in attempts if event.axis == "rho"]
        energy_attempts = [event for event in attempts if event.axis == "e"]
        final_events = [event for event in self.events if event.event_kind == "EVALUATION_RESULT"]
        accepted_attempts = [
            event for event in attempts if event.accepted_or_refused == "ACCEPTED"
        ]
        refused_attempts = [
            event for event in attempts if event.accepted_or_refused == "REFUSED"
        ]
        halving_values = [
            int(event.halving_index)
            for event in attempts
            if event.halving_index is not None
        ]
        evaluation_ids = {event.evaluation_id for event in self.events}
        result_ids = {event.evaluation_id for event in final_events}
        return {
            "schema_version": "stage7_gate9_d3_acoustic_attempts_increment1_v1",
            "scope": "verification_only_transparent_acoustic_evaluator_proxy",
            "case_id": "pipeline_crossing_candidate_p5m5_to_p2m5",
            "cfl": 0.10,
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
            "production_acoustic_evaluation_count": len(evaluation_ids),
            "evaluation_result_record_count": len(final_events),
            "all_evaluations_have_final_record": evaluation_ids == result_ids,
            "acoustic_event_record_count": len(self.events),
            "stencil_attempt_record_count": len(attempts),
            "density_attempt_record_count": len(density_attempts),
            "energy_attempt_record_count": len(energy_attempts),
            "accepted_attempt_record_count": len(accepted_attempts),
            "refused_attempt_record_count": len(refused_attempts),
            "maximum_observed_halving_index": max(halving_values, default=-1),
            "existing_max_step_halvings": D3_MAX_EXISTING_HALVINGS,
            "halving_limit_preserved": all(
                0 <= value <= D3_MAX_EXISTING_HALVINGS for value in halving_values
            ),
            "diagnostic_off_on_identity": self.diagnostic_off_on_identity,
            "solver_identity_off": dict(self.solver_identity_off),
            "solver_identity_on": dict(self.solver_identity_on),
            "candidate_summary": {
                "candidate_step": self.candidate_step,
                "candidate_time_s": self.candidate_time_s,
                "candidate_cells": list(self.candidate_cells),
                "maximum_candidate_q_equilibrium": (
                    self.maximum_candidate_q_equilibrium
                ),
                "formal_outcome": self.formal_outcome,
                "final_state_sha256": self.final_state_sha256,
                "run_signature_sha256": self.run_signature_sha256,
            },
            "event_alignment_status": D3_ALIGNMENT_STATUS,
            "production_sound_speed_formula_changed": False,
            "central_stencil_loop_changed": False,
            "maximum_halving_count_changed": False,
            "one_sided_fallback_added": False,
            "trial_state_clipping_added": False,
            "property_evaluation_order_changed": False,
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


def _root_error_type(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    current: BaseException = exc
    while current.__cause__ is not None:
        current = current.__cause__
    return type(current).__name__


def _call_category(call: _EvaluatorCall | None) -> str:
    return "NOT_EVALUATED" if call is None else call.phase_scope_category


def _consume_call(
    calls: Sequence[_EvaluatorCall],
    cursor: int,
    *,
    expected_rho: float,
    expected_e: float,
) -> tuple[_EvaluatorCall, int]:
    if cursor >= len(calls):
        raise HEMGate9AcousticDiagnosticError(
            "acoustic evaluator call history ended before the stencil trace"
        )
    call = calls[cursor]
    if call.rho_kg_m3 != float(expected_rho) or call.e_j_kg != float(expected_e):
        raise HEMGate9AcousticDiagnosticError(
            "acoustic evaluator call order differs from the unchanged central stencil: "
            f"expected ({float(expected_rho).hex()}, {float(expected_e).hex()}), "
            f"received ({call.rho_kg_m3.hex()}, {call.e_j_kg.hex()})"
        )
    return call, cursor + 1


def _attempt_event(
    *,
    evaluation_id: int,
    axis: str,
    rho: float,
    e: float,
    center_phase: str,
    density_step_0: float,
    energy_step_0: float,
    halving_index: int,
    step: float,
    minus_rho: float,
    plus_rho: float,
    minus_e: float,
    plus_e: float,
    minus: _EvaluatorCall | None,
    plus: _EvaluatorCall | None,
    accepted: bool,
    refusal_category: str,
    error_type: str,
) -> Gate9AcousticAttemptEvent:
    return Gate9AcousticAttemptEvent(
        evaluation_id=evaluation_id,
        event_kind="STENCIL_ATTEMPT",
        axis=axis,
        center_rho_kg_m3=rho,
        center_e_j_kg=e,
        center_phase_class=center_phase,
        base_density_increment=density_step_0,
        base_energy_increment=energy_step_0,
        halving_index=halving_index,
        trial_step=step,
        trial_density_minus=minus_rho,
        trial_density_plus=plus_rho,
        trial_energy_minus=minus_e,
        trial_energy_plus=plus_e,
        minus_state_valid=(None if minus is None else minus.guarded_valid),
        plus_state_valid=(None if plus is None else plus.guarded_valid),
        minus_phase_or_scope_category=_call_category(minus),
        plus_phase_or_scope_category=_call_category(plus),
        computed_sound_speed_squared=None,
        accepted_or_refused="ACCEPTED" if accepted else "REFUSED",
        refusal_category="" if accepted else refusal_category,
        backend_error_type=error_type,
    )


def _final_event(
    *,
    evaluation_id: int,
    rho: float,
    e: float,
    center_phase: str,
    density_step_0: float,
    energy_step_0: float,
    result: HEMEquilibriumSoundSpeedEstimate | None,
    error: BaseException | None,
    refusal_category: str,
) -> Gate9AcousticAttemptEvent:
    return Gate9AcousticAttemptEvent(
        evaluation_id=evaluation_id,
        event_kind="EVALUATION_RESULT",
        axis="combined",
        center_rho_kg_m3=rho,
        center_e_j_kg=e,
        center_phase_class=center_phase,
        base_density_increment=density_step_0,
        base_energy_increment=energy_step_0,
        halving_index=None,
        trial_step=None,
        trial_density_minus=None,
        trial_density_plus=None,
        trial_energy_minus=None,
        trial_energy_plus=None,
        minus_state_valid=None,
        plus_state_valid=None,
        minus_phase_or_scope_category="NOT_APPLICABLE",
        plus_phase_or_scope_category="NOT_APPLICABLE",
        computed_sound_speed_squared=(
            None if result is None else float(result.sound_speed_squared_m2_s2)
        ),
        accepted_or_refused="ACCEPTED" if result is not None else "REFUSED",
        refusal_category="" if result is not None else refusal_category,
        backend_error_type=_root_error_type(error),
    )


def _reconstruct_attempt_events(
    *,
    evaluation_id: int,
    rho: float,
    e: float,
    config: HEMEquilibriumSoundSpeedConfig,
    calls: Sequence[_EvaluatorCall],
    result: HEMEquilibriumSoundSpeedEstimate | None,
    error: BaseException | None,
) -> tuple[Gate9AcousticAttemptEvent, ...]:
    density_step_0 = max(
        config.relative_density_step * abs(rho),
        config.minimum_density_step_kg_m3,
    )
    energy_step_0 = max(
        config.relative_energy_step * max(abs(e), 1.0),
        config.minimum_energy_step_j_kg,
    )
    if not calls:
        return (
            _final_event(
                evaluation_id=evaluation_id,
                rho=rho,
                e=e,
                center_phase="",
                density_step_0=density_step_0,
                energy_step_0=energy_step_0,
                result=result,
                error=error,
                refusal_category="CENTER_INPUT_REJECTED_BEFORE_PROPERTY_EVALUATION",
            ),
        )

    center = calls[0]
    center_phase = center.phase_class if center.guarded_valid else ""
    if not center.guarded_valid:
        if len(calls) != 1:
            raise HEMGate9AcousticDiagnosticError(
                "invalid center state unexpectedly produced stencil evaluator calls"
            )
        return (
            _final_event(
                evaluation_id=evaluation_id,
                rho=rho,
                e=e,
                center_phase=center_phase,
                density_step_0=density_step_0,
                energy_step_0=energy_step_0,
                result=result,
                error=error,
                refusal_category="CENTER_STATE_REJECTED",
            ),
        )

    cursor = 1
    events: list[Gate9AcousticAttemptEvent] = []
    accepted_axes: set[str] = set()
    for axis, initial_step in (("rho", density_step_0), ("e", energy_step_0)):
        for halvings in range(config.max_step_halvings + 1):
            step = initial_step / (2.0**halvings)
            if axis == "rho":
                minus_rho, plus_rho = rho - step, rho + step
                minus_e = plus_e = e
                if minus_rho <= 0.0:
                    events.append(
                        _attempt_event(
                            evaluation_id=evaluation_id,
                            axis=axis,
                            rho=rho,
                            e=e,
                            center_phase=center_phase,
                            density_step_0=density_step_0,
                            energy_step_0=energy_step_0,
                            halving_index=halvings,
                            step=step,
                            minus_rho=minus_rho,
                            plus_rho=plus_rho,
                            minus_e=minus_e,
                            plus_e=plus_e,
                            minus=None,
                            plus=None,
                            accepted=False,
                            refusal_category="NONPOSITIVE_MINUS_DENSITY",
                            error_type="",
                        )
                    )
                    continue
            else:
                minus_rho = plus_rho = rho
                minus_e, plus_e = e - step, e + step

            minus, cursor = _consume_call(
                calls,
                cursor,
                expected_rho=minus_rho,
                expected_e=minus_e,
            )
            if not minus.guarded_valid:
                events.append(
                    _attempt_event(
                        evaluation_id=evaluation_id,
                        axis=axis,
                        rho=rho,
                        e=e,
                        center_phase=center_phase,
                        density_step_0=density_step_0,
                        energy_step_0=energy_step_0,
                        halving_index=halvings,
                        step=step,
                        minus_rho=minus_rho,
                        plus_rho=plus_rho,
                        minus_e=minus_e,
                        plus_e=plus_e,
                        minus=minus,
                        plus=None,
                        accepted=False,
                        refusal_category="MINUS_STATE_REJECTED",
                        error_type=(
                            minus.error_type or "HEMEquilibriumSoundSpeedError"
                        ),
                    )
                )
                continue

            plus, cursor = _consume_call(
                calls,
                cursor,
                expected_rho=plus_rho,
                expected_e=plus_e,
            )
            if not plus.guarded_valid:
                events.append(
                    _attempt_event(
                        evaluation_id=evaluation_id,
                        axis=axis,
                        rho=rho,
                        e=e,
                        center_phase=center_phase,
                        density_step_0=density_step_0,
                        energy_step_0=energy_step_0,
                        halving_index=halvings,
                        step=step,
                        minus_rho=minus_rho,
                        plus_rho=plus_rho,
                        minus_e=minus_e,
                        plus_e=plus_e,
                        minus=minus,
                        plus=plus,
                        accepted=False,
                        refusal_category="PLUS_STATE_REJECTED",
                        error_type=(
                            plus.error_type or "HEMEquilibriumSoundSpeedError"
                        ),
                    )
                )
                continue

            phase_mismatch = bool(
                config.require_same_phase_class
                and (
                    minus.phase_class != center_phase
                    or plus.phase_class != center_phase
                )
            )
            events.append(
                _attempt_event(
                    evaluation_id=evaluation_id,
                    axis=axis,
                    rho=rho,
                    e=e,
                    center_phase=center_phase,
                    density_step_0=density_step_0,
                    energy_step_0=energy_step_0,
                    halving_index=halvings,
                    step=step,
                    minus_rho=minus_rho,
                    plus_rho=plus_rho,
                    minus_e=minus_e,
                    plus_e=plus_e,
                    minus=minus,
                    plus=plus,
                    accepted=not phase_mismatch,
                    refusal_category="PHASE_CLASS_MISMATCH" if phase_mismatch else "",
                    error_type="",
                )
            )
            if not phase_mismatch:
                accepted_axes.add(axis)
                break
        if axis not in accepted_axes:
            break

    if cursor != len(calls):
        raise HEMGate9AcousticDiagnosticError(
            "unconsumed acoustic evaluator calls remain after parsing: "
            f"{len(calls) - cursor}"
        )

    if result is not None:
        refusal = ""
    elif "rho" not in accepted_axes:
        refusal = "NO_VALID_CENTRAL_RHO_STENCIL_AFTER_MAX_HALVINGS"
    elif "e" not in accepted_axes:
        refusal = "NO_VALID_CENTRAL_E_STENCIL_AFTER_MAX_HALVINGS"
    else:
        refusal = "FINAL_SOUND_SPEED_SQUARED_REJECTED"
    events.append(
        _final_event(
            evaluation_id=evaluation_id,
            rho=rho,
            e=e,
            center_phase=center_phase,
            density_step_0=density_step_0,
            energy_step_0=energy_step_0,
            result=result,
            error=error,
            refusal_category=refusal,
        )
    )
    return tuple(events)


def _instrumented_estimate(
    original_estimator: Callable[..., HEMEquilibriumSoundSpeedEstimate],
    state: _ObserverState,
    rho_kg_m3: float,
    e_j_kg: float,
    evaluator: PressurePhaseEvaluator,
    *,
    config: HEMEquilibriumSoundSpeedConfig | None = None,
) -> HEMEquilibriumSoundSpeedEstimate:
    evaluation_id = state.next_evaluation_id
    state.next_evaluation_id += 1
    cfg = config or HEMEquilibriumSoundSpeedConfig()
    rho = float(rho_kg_m3)
    e = float(e_j_kg)
    calls: list[_EvaluatorCall] = []

    def proxy(rho_value: float, e_value: float) -> PressurePhaseSample:
        rho_call = float(rho_value)
        e_call = float(e_value)
        try:
            sample = evaluator(rho_call, e_call)
        except Exception as exc:
            calls.append(
                _EvaluatorCall(
                    rho_kg_m3=rho_call,
                    e_j_kg=e_call,
                    returned=False,
                    pressure_pa=None,
                    phase_class="",
                    scope_status="",
                    error_type=_root_error_type(exc),
                )
            )
            raise
        calls.append(
            _EvaluatorCall(
                rho_kg_m3=rho_call,
                e_j_kg=e_call,
                returned=True,
                pressure_pa=float(sample.pressure_pa),
                phase_class=str(sample.phase_class),
                scope_status=str(sample.scope_status),
                error_type="",
            )
        )
        return sample

    result: HEMEquilibriumSoundSpeedEstimate | None = None
    error: BaseException | None = None
    try:
        result = original_estimator(rho, e, proxy, config=cfg)
    except Exception as exc:
        error = exc
    events = _reconstruct_attempt_events(
        evaluation_id=evaluation_id,
        rho=rho,
        e=e,
        config=cfg,
        calls=calls,
        result=result,
        error=error,
    )
    for event in events:
        state.observer(event)
    if error is not None:
        raise error
    if result is None:  # pragma: no cover - defensive contract
        raise HEMGate9AcousticDiagnosticError(
            "acoustic estimator returned neither a result nor an exception"
        )
    return result


@contextmanager
def observe_equilibrium_acoustic_attempts(
    observer: AcousticAttemptObserver,
) -> Iterator[None]:
    """Temporarily observe the unchanged production acoustic evaluator path.

    The context replaces only the module dispatch reference with a transparent
    wrapper and restores it on exit.  The original estimator executes exactly
    once with a proxy around the already supplied property evaluator.  The proxy
    returns the same samples or re-raises the same exceptions and never changes
    trial coordinates, halving order, formulas, or guards.

    The temporary dispatch wrapper is intended for this single-threaded
    verification runner; nested D3 observer contexts are rejected explicitly.
    """

    if not callable(observer):
        raise TypeError("acoustic attempt observer must be callable")
    if _OBSERVER_STATE.get() is not None:
        raise HEMGate9AcousticDiagnosticError(
            "nested acoustic-attempt observer contexts are not supported"
        )

    original_estimator = acoustic_module.estimate_equilibrium_sound_speed
    state = _ObserverState(observer=observer)
    token = _OBSERVER_STATE.set(state)

    def wrapped_estimator(
        rho_kg_m3: float,
        e_j_kg: float,
        evaluator: PressurePhaseEvaluator,
        *,
        config: HEMEquilibriumSoundSpeedConfig | None = None,
    ) -> HEMEquilibriumSoundSpeedEstimate:
        return _instrumented_estimate(
            original_estimator,
            state,
            rho_kg_m3,
            e_j_kg,
            evaluator,
            config=config,
        )

    acoustic_module.estimate_equilibrium_sound_speed = wrapped_estimator
    try:
        yield
    finally:
        acoustic_module.estimate_equilibrium_sound_speed = original_estimator
        _OBSERVER_STATE.reset(token)


def _require_exact_off_on_identity(
    diagnostic_off: PipelineCaseResult,
    diagnostic_on: PipelineCaseResult,
) -> None:
    if solver_identity(diagnostic_off) != solver_identity(diagnostic_on):
        raise HEMGate9AcousticDiagnosticError(
            "D3 diagnostic OFF/ON solver identity mismatch"
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
            raise HEMGate9AcousticDiagnosticError(
                f"D3 diagnostic OFF/ON {name} mismatch"
            )


def _require_gate8_cfl_0p10_reference(result: PipelineCaseResult) -> None:
    if (
        float(result.config.cfl) != 0.10
        or result.outcome != "ACCEPTED_FIRST_CROSSING"
        or int(result.step_count) != 125
        or result.crossing_step != 125
        or result.crossing_time_s != 7.999325695335248e-4
        or tuple(result.crossing_cell_indices) != (29,)
        or result.maximum_crossing_quality != 3.773646403587342e-6
    ):
        raise HEMGate9AcousticDiagnosticError(
            "D3 CFL 0.10 run did not reproduce the immutable Gate 8 candidate"
        )


def run_gate9_d3_identity_pair(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig,
) -> tuple[PipelineCaseResult, PipelineCaseResult, Gate9D3Result]:
    """Run the fixed CFL=0.10 case OFF/ON and retain acoustic attempts."""

    if config.sound_speed_config.max_step_halvings != D3_MAX_EXISTING_HALVINGS:
        raise HEMGate9AcousticDiagnosticError(
            "D3 must retain the existing maximum of 12 step halvings"
        )
    diagnostic_off = run_pipeline_depressurization_case(case, config)
    collector = Gate9AcousticAttemptCollector()
    with observe_equilibrium_acoustic_attempts(collector):
        diagnostic_on = run_pipeline_depressurization_case(case, config)

    _require_exact_off_on_identity(diagnostic_off, diagnostic_on)
    _require_gate8_cfl_0p10_reference(diagnostic_on)
    events = tuple(collector.events)
    if not events:
        raise HEMGate9AcousticDiagnosticError(
            "D3 observer produced no production acoustic events"
        )
    attempts = [event for event in events if event.event_kind == "STENCIL_ATTEMPT"]
    if not attempts or any(
        event.halving_index is None
        or not 0 <= event.halving_index <= D3_MAX_EXISTING_HALVINGS
        for event in attempts
    ):
        raise HEMGate9AcousticDiagnosticError(
            "D3 attempt history is empty or exceeds the existing halving contract"
        )
    result = Gate9D3Result(
        events=events,
        diagnostic_off_on_identity=True,
        solver_identity_off=solver_identity(diagnostic_off),
        solver_identity_on=solver_identity(diagnostic_on),
        candidate_step=diagnostic_on.crossing_step,
        candidate_time_s=diagnostic_on.crossing_time_s,
        candidate_cells=tuple(diagnostic_on.crossing_cell_indices),
        maximum_candidate_q_equilibrium=float(
            diagnostic_on.maximum_crossing_quality
        ),
        formal_outcome=str(diagnostic_on.outcome),
        final_state_sha256=str(diagnostic_on.final_state_sha256),
        run_signature_sha256=str(diagnostic_on.run_signature_sha256),
    )
    summary = result.summary()
    if (
        not summary["all_evaluations_have_final_record"]
        or not summary["halving_limit_preserved"]
    ):
        raise HEMGate9AcousticDiagnosticError(
            "D3 event sequence failed its completeness or halving guard"
        )
    return diagnostic_off, diagnostic_on, result


def _flatten(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_dataclass_rows(path: Path, rows: Sequence[object]) -> None:
    names = [item.name for item in fields(Gate9AcousticAttemptEvent)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow({name: _flatten(payload[name]) for name in names})


def write_gate9_d3_artifacts(
    output_dir: str | Path,
    result: Gate9D3Result,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": target / "summary.json",
        "acoustic": target / "acoustic_attempt_history.csv",
        "candidate": target / "candidate_summary.json",
        "digest": target / "artifact_sha256.txt",
    }
    summary = result.summary()
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_dataclass_rows(paths["acoustic"], result.events)
    paths["candidate"].write_text(
        json.dumps(summary["candidate_summary"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest_lines = []
    for path in sorted(
        (value for key, value in paths.items() if key != "digest"),
        key=lambda value: value.name,
    ):
        digest_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        )
    paths["digest"].write_text(
        "\n".join(digest_lines) + "\n",
        encoding="utf-8",
    )
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    _, _, result = run_gate9_d3_identity_pair(
        case,
        HEMPipelineDepressurizationConfig(),
    )
    paths = write_gate9_d3_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
