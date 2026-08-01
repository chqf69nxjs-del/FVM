"""Gate 9 D3 read-only acoustic trial and halving diagnostics.

The existing equilibrium sound-speed estimator is executed exactly once.  A
transparent proxy records the already requested ``rho/e`` property calls and
reconstructs the executed central-stencil attempt sequence.  No trial point,
formula, guard, return value, exception, or maximum-halving setting is changed.

D3 increment 1 records the immutable CFL=0.10 production path.  Step/cell/stage
alignment remains explicitly deferred to D4.
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
    """Raised when the fixed D3 observation contract cannot be preserved."""


@dataclass(frozen=True)
class Gate9AcousticAttemptEvent:
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
    rho: float
    e: float
    returned: bool
    pressure: float | None
    phase: str
    scope: str
    error_type: str

    @property
    def valid(self) -> bool:
        return bool(
            self.returned
            and self.pressure is not None
            and np.isfinite(self.pressure)
            and self.pressure > 0.0
            and self.scope == "supported_candidate"
            and self.phase
        )

    @property
    def category(self) -> str:
        if not self.returned:
            return "EVALUATION_FAILED"
        return f"{self.phase}|{self.scope}"


@dataclass
class _ObserverState:
    observer: AcousticAttemptObserver
    next_id: int = 0


_STATE: ContextVar[_ObserverState | None] = ContextVar(
    "gate9_d3_acoustic_observer_state",
    default=None,
)


@dataclass
class Gate9AcousticAttemptCollector:
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
        attempts = tuple(
            event for event in self.events if event.event_kind == "STENCIL_ATTEMPT"
        )
        final = tuple(
            event for event in self.events if event.event_kind == "EVALUATION_RESULT"
        )
        ids = {event.evaluation_id for event in self.events}
        final_ids = {event.evaluation_id for event in final}
        indices = tuple(
            int(event.halving_index)
            for event in attempts
            if event.halving_index is not None
        )
        return {
            "schema_version": "stage7_gate9_d3_acoustic_attempts_increment1_v1",
            "scope": "verification_only_transparent_acoustic_evaluator_proxy",
            "case_id": "pipeline_crossing_candidate_p5m5_to_p2m5",
            "cfl": 0.10,
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
            "production_acoustic_evaluation_count": len(ids),
            "evaluation_result_record_count": len(final),
            "all_evaluations_have_final_record": ids == final_ids,
            "acoustic_event_record_count": len(self.events),
            "stencil_attempt_record_count": len(attempts),
            "density_attempt_record_count": sum(e.axis == "rho" for e in attempts),
            "energy_attempt_record_count": sum(e.axis == "e" for e in attempts),
            "accepted_attempt_record_count": sum(
                e.accepted_or_refused == "ACCEPTED" for e in attempts
            ),
            "refused_attempt_record_count": sum(
                e.accepted_or_refused == "REFUSED" for e in attempts
            ),
            "maximum_observed_halving_index": max(indices, default=-1),
            "existing_max_step_halvings": D3_MAX_EXISTING_HALVINGS,
            "halving_limit_preserved": all(
                0 <= value <= D3_MAX_EXISTING_HALVINGS for value in indices
            ),
            "diagnostic_off_on_identity": self.diagnostic_off_on_identity,
            "solver_identity_off": dict(self.solver_identity_off),
            "solver_identity_on": dict(self.solver_identity_on),
            "candidate_summary": {
                "candidate_step": self.candidate_step,
                "candidate_time_s": self.candidate_time_s,
                "candidate_cells": list(self.candidate_cells),
                "maximum_candidate_q_equilibrium": self.maximum_candidate_q_equilibrium,
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
    root = exc
    while root.__cause__ is not None:
        root = root.__cause__
    return type(root).__name__


def _consume(
    calls: Sequence[_EvaluatorCall],
    cursor: int,
    rho: float,
    e: float,
) -> tuple[_EvaluatorCall, int]:
    if cursor >= len(calls):
        raise HEMGate9AcousticDiagnosticError(
            "evaluator call history ended before the unchanged stencil trace"
        )
    call = calls[cursor]
    if call.rho != float(rho) or call.e != float(e):
        raise HEMGate9AcousticDiagnosticError(
            "evaluator call order differs from the unchanged central stencil"
        )
    return call, cursor + 1


def _attempt(
    *,
    evaluation_id: int,
    axis: str,
    rho: float,
    e: float,
    center_phase: str,
    drho0: float,
    de0: float,
    halving: int,
    step: float,
    minus_rho: float,
    plus_rho: float,
    minus_e: float,
    plus_e: float,
    minus: _EvaluatorCall | None,
    plus: _EvaluatorCall | None,
    accepted: bool,
    refusal: str,
    error_type: str = "",
) -> Gate9AcousticAttemptEvent:
    return Gate9AcousticAttemptEvent(
        evaluation_id=evaluation_id,
        event_kind="STENCIL_ATTEMPT",
        axis=axis,
        center_rho_kg_m3=rho,
        center_e_j_kg=e,
        center_phase_class=center_phase,
        base_density_increment=drho0,
        base_energy_increment=de0,
        halving_index=halving,
        trial_step=step,
        trial_density_minus=minus_rho,
        trial_density_plus=plus_rho,
        trial_energy_minus=minus_e,
        trial_energy_plus=plus_e,
        minus_state_valid=None if minus is None else minus.valid,
        plus_state_valid=None if plus is None else plus.valid,
        minus_phase_or_scope_category=(
            "NOT_EVALUATED" if minus is None else minus.category
        ),
        plus_phase_or_scope_category=(
            "NOT_EVALUATED" if plus is None else plus.category
        ),
        computed_sound_speed_squared=None,
        accepted_or_refused="ACCEPTED" if accepted else "REFUSED",
        refusal_category="" if accepted else refusal,
        backend_error_type=error_type,
    )


def _final(
    *,
    evaluation_id: int,
    rho: float,
    e: float,
    center_phase: str,
    drho0: float,
    de0: float,
    result: HEMEquilibriumSoundSpeedEstimate | None,
    error: BaseException | None,
    refusal: str,
) -> Gate9AcousticAttemptEvent:
    return Gate9AcousticAttemptEvent(
        evaluation_id=evaluation_id,
        event_kind="EVALUATION_RESULT",
        axis="combined",
        center_rho_kg_m3=rho,
        center_e_j_kg=e,
        center_phase_class=center_phase,
        base_density_increment=drho0,
        base_energy_increment=de0,
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
        refusal_category="" if result is not None else refusal,
        backend_error_type=_root_error_type(error),
    )


def _parse_events(
    *,
    evaluation_id: int,
    rho: float,
    e: float,
    config: HEMEquilibriumSoundSpeedConfig,
    calls: Sequence[_EvaluatorCall],
    result: HEMEquilibriumSoundSpeedEstimate | None,
    error: BaseException | None,
) -> tuple[Gate9AcousticAttemptEvent, ...]:
    drho0 = max(
        config.relative_density_step * abs(rho),
        config.minimum_density_step_kg_m3,
    )
    de0 = max(
        config.relative_energy_step * max(abs(e), 1.0),
        config.minimum_energy_step_j_kg,
    )
    if not calls:
        return (
            _final(
                evaluation_id=evaluation_id,
                rho=rho,
                e=e,
                center_phase="",
                drho0=drho0,
                de0=de0,
                result=result,
                error=error,
                refusal="CENTER_INPUT_REJECTED_BEFORE_PROPERTY_EVALUATION",
            ),
        )

    center = calls[0]
    center_phase = center.phase if center.valid else ""
    if not center.valid:
        if len(calls) != 1:
            raise HEMGate9AcousticDiagnosticError(
                "invalid center unexpectedly produced stencil calls"
            )
        return (
            _final(
                evaluation_id=evaluation_id,
                rho=rho,
                e=e,
                center_phase=center_phase,
                drho0=drho0,
                de0=de0,
                result=result,
                error=error,
                refusal="CENTER_STATE_REJECTED",
            ),
        )

    cursor = 1
    events: list[Gate9AcousticAttemptEvent] = []
    accepted_axes: set[str] = set()
    for axis, initial in (("rho", drho0), ("e", de0)):
        for halving in range(config.max_step_halvings + 1):
            step = initial / (2.0**halving)
            if axis == "rho":
                rm, rp, em, ep = rho - step, rho + step, e, e
                if rm <= 0.0:
                    events.append(
                        _attempt(
                            evaluation_id=evaluation_id,
                            axis=axis,
                            rho=rho,
                            e=e,
                            center_phase=center_phase,
                            drho0=drho0,
                            de0=de0,
                            halving=halving,
                            step=step,
                            minus_rho=rm,
                            plus_rho=rp,
                            minus_e=em,
                            plus_e=ep,
                            minus=None,
                            plus=None,
                            accepted=False,
                            refusal="NONPOSITIVE_MINUS_DENSITY",
                        )
                    )
                    continue
            else:
                rm, rp, em, ep = rho, rho, e - step, e + step

            minus, cursor = _consume(calls, cursor, rm, em)
            if not minus.valid:
                events.append(
                    _attempt(
                        evaluation_id=evaluation_id,
                        axis=axis,
                        rho=rho,
                        e=e,
                        center_phase=center_phase,
                        drho0=drho0,
                        de0=de0,
                        halving=halving,
                        step=step,
                        minus_rho=rm,
                        plus_rho=rp,
                        minus_e=em,
                        plus_e=ep,
                        minus=minus,
                        plus=None,
                        accepted=False,
                        refusal="MINUS_STATE_REJECTED",
                        error_type=(
                            minus.error_type or "HEMEquilibriumSoundSpeedError"
                        ),
                    )
                )
                continue

            plus, cursor = _consume(calls, cursor, rp, ep)
            if not plus.valid:
                events.append(
                    _attempt(
                        evaluation_id=evaluation_id,
                        axis=axis,
                        rho=rho,
                        e=e,
                        center_phase=center_phase,
                        drho0=drho0,
                        de0=de0,
                        halving=halving,
                        step=step,
                        minus_rho=rm,
                        plus_rho=rp,
                        minus_e=em,
                        plus_e=ep,
                        minus=minus,
                        plus=plus,
                        accepted=False,
                        refusal="PLUS_STATE_REJECTED",
                        error_type=(
                            plus.error_type or "HEMEquilibriumSoundSpeedError"
                        ),
                    )
                )
                continue

            mismatch = bool(
                config.require_same_phase_class
                and (minus.phase != center_phase or plus.phase != center_phase)
            )
            events.append(
                _attempt(
                    evaluation_id=evaluation_id,
                    axis=axis,
                    rho=rho,
                    e=e,
                    center_phase=center_phase,
                    drho0=drho0,
                    de0=de0,
                    halving=halving,
                    step=step,
                    minus_rho=rm,
                    plus_rho=rp,
                    minus_e=em,
                    plus_e=ep,
                    minus=minus,
                    plus=plus,
                    accepted=not mismatch,
                    refusal="PHASE_CLASS_MISMATCH" if mismatch else "",
                )
            )
            if not mismatch:
                accepted_axes.add(axis)
                break
        if axis not in accepted_axes:
            break

    if cursor != len(calls):
        raise HEMGate9AcousticDiagnosticError(
            f"{len(calls) - cursor} unconsumed evaluator calls remain"
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
        _final(
            evaluation_id=evaluation_id,
            rho=rho,
            e=e,
            center_phase=center_phase,
            drho0=drho0,
            de0=de0,
            result=result,
            error=error,
            refusal=refusal,
        )
    )
    return tuple(events)


def _instrumented_estimate(
    original: Callable[..., HEMEquilibriumSoundSpeedEstimate],
    state: _ObserverState,
    rho_kg_m3: float,
    e_j_kg: float,
    evaluator: PressurePhaseEvaluator,
    *,
    config: HEMEquilibriumSoundSpeedConfig | None = None,
) -> HEMEquilibriumSoundSpeedEstimate:
    evaluation_id = state.next_id
    state.next_id += 1
    cfg = config or HEMEquilibriumSoundSpeedConfig()
    rho, e = float(rho_kg_m3), float(e_j_kg)
    calls: list[_EvaluatorCall] = []

    def proxy(rho_value: float, e_value: float) -> PressurePhaseSample:
        r, u = float(rho_value), float(e_value)
        try:
            sample = evaluator(r, u)
        except Exception as exc:
            calls.append(_EvaluatorCall(r, u, False, None, "", "", _root_error_type(exc)))
            raise
        calls.append(
            _EvaluatorCall(
                r,
                u,
                True,
                float(sample.pressure_pa),
                str(sample.phase_class),
                str(sample.scope_status),
                "",
            )
        )
        return sample

    result: HEMEquilibriumSoundSpeedEstimate | None = None
    error: BaseException | None = None
    try:
        result = original(rho, e, proxy, config=config)
    except Exception as exc:
        error = exc
    for event in _parse_events(
        evaluation_id=evaluation_id,
        rho=rho,
        e=e,
        config=cfg,
        calls=calls,
        result=result,
        error=error,
    ):
        state.observer(event)
    if error is not None:
        raise error
    if result is None:  # pragma: no cover
        raise HEMGate9AcousticDiagnosticError("estimator returned no result")
    return result


@contextmanager
def observe_equilibrium_acoustic_attempts(
    observer: AcousticAttemptObserver,
) -> Iterator[None]:
    """Observe exact property calls while retaining the unchanged estimator."""

    if not callable(observer):
        raise TypeError("acoustic attempt observer must be callable")
    if _STATE.get() is not None:
        raise HEMGate9AcousticDiagnosticError("nested D3 observer contexts are prohibited")
    original = acoustic_module.estimate_equilibrium_sound_speed
    state = _ObserverState(observer)
    token = _STATE.set(state)

    def wrapped(
        rho_kg_m3: float,
        e_j_kg: float,
        evaluator: PressurePhaseEvaluator,
        *,
        config: HEMEquilibriumSoundSpeedConfig | None = None,
    ) -> HEMEquilibriumSoundSpeedEstimate:
        return _instrumented_estimate(
            original,
            state,
            rho_kg_m3,
            e_j_kg,
            evaluator,
            config=config,
        )

    acoustic_module.estimate_equilibrium_sound_speed = wrapped
    try:
        yield
    finally:
        acoustic_module.estimate_equilibrium_sound_speed = original
        _STATE.reset(token)


def _require_identity(off: PipelineCaseResult, on: PipelineCaseResult) -> None:
    if solver_identity(off) != solver_identity(on):
        raise HEMGate9AcousticDiagnosticError("D3 diagnostic OFF/ON identity mismatch")
    for name in ("time_history_s", "pressure_history_pa", "accepted_state_history"):
        if not np.array_equal(np.asarray(getattr(off, name)), np.asarray(getattr(on, name))):
            raise HEMGate9AcousticDiagnosticError(f"D3 OFF/ON {name} mismatch")


def _require_gate8_reference(result: PipelineCaseResult) -> None:
    if (
        float(result.config.cfl) != 0.10
        or result.outcome != "ACCEPTED_FIRST_CROSSING"
        or result.step_count != 125
        or result.crossing_step != 125
        or result.crossing_time_s != 7.999325695335248e-4
        or tuple(result.crossing_cell_indices) != (29,)
        or result.maximum_crossing_quality != 3.773646403587342e-6
    ):
        raise HEMGate9AcousticDiagnosticError(
            "D3 did not reproduce the immutable Gate 8 CFL 0.10 candidate"
        )


def run_gate9_d3_identity_pair(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig,
) -> tuple[PipelineCaseResult, PipelineCaseResult, Gate9D3Result]:
    """Run the immutable CFL=0.10 case OFF/ON and retain acoustic events."""

    if HEMEquilibriumSoundSpeedConfig().max_step_halvings != D3_MAX_EXISTING_HALVINGS:
        raise HEMGate9AcousticDiagnosticError("existing maximum halvings is not 12")
    off = run_pipeline_depressurization_case(case, config)
    collector = Gate9AcousticAttemptCollector()
    with observe_equilibrium_acoustic_attempts(collector):
        on = run_pipeline_depressurization_case(case, config)
    _require_identity(off, on)
    _require_gate8_reference(on)
    events = tuple(collector.events)
    attempts = tuple(e for e in events if e.event_kind == "STENCIL_ATTEMPT")
    if not events or not attempts:
        raise HEMGate9AcousticDiagnosticError("D3 produced no acoustic attempt evidence")
    if any(
        event.halving_index is None
        or not 0 <= event.halving_index <= D3_MAX_EXISTING_HALVINGS
        for event in attempts
    ):
        raise HEMGate9AcousticDiagnosticError("D3 halving history exceeds 0..12")
    result = Gate9D3Result(
        events=events,
        diagnostic_off_on_identity=True,
        solver_identity_off=solver_identity(off),
        solver_identity_on=solver_identity(on),
        candidate_step=on.crossing_step,
        candidate_time_s=on.crossing_time_s,
        candidate_cells=tuple(on.crossing_cell_indices),
        maximum_candidate_q_equilibrium=float(on.maximum_crossing_quality),
        formal_outcome=str(on.outcome),
        final_state_sha256=str(on.final_state_sha256),
        run_signature_sha256=str(on.run_signature_sha256),
    )
    summary = result.summary()
    if not summary["all_evaluations_have_final_record"] or not summary["halving_limit_preserved"]:
        raise HEMGate9AcousticDiagnosticError("D3 event sequence is incomplete")
    return off, on, result


def _write_rows(path: Path, rows: Sequence[Gate9AcousticAttemptEvent]) -> None:
    names = [item.name for item in fields(Gate9AcousticAttemptEvent)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_gate9_d3_artifacts(output_dir: str | Path, result: Gate9D3Result) -> dict[str, Path]:
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
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_rows(paths["acoustic"], result.events)
    paths["candidate"].write_text(
        json.dumps(summary["candidate_summary"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = []
    for path in sorted(
        (value for key, value in paths.items() if key != "digest"),
        key=lambda value: value.name,
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
    _, _, result = run_gate9_d3_identity_pair(
        FIXED_PIPELINE_DEPRESSURIZATION_CASES[0],
        HEMPipelineDepressurizationConfig(),
    )
    paths = write_gate9_d3_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
