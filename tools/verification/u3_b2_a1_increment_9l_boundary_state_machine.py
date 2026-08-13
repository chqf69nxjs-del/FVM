from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_dynamic_seeded_final_horizon as seeded
import u3_b2_a1_finite_compression_guard_front_8_step as outward_runner
import u3_b2_a1_finite_compression_guard_front_8_step_dynamic_topology_fix as dynamic_fix
import u3_b2_a1_increment_9k_zero_transfer_closure as increment_9k
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_metrics import inventory


CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
TECHNICAL_ISSUE = "TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION"
OUTCOME = "INCREMENT_9L_GATE_A_TRANSITION_WORKING_SLICE_PASS"

PARENT_SOURCE_SHA = seeded.PARENT_SOURCE_SHA
PARENT_RUN = seeded.PARENT_RUN
PARENT_JOB = seeded.PARENT_JOB
PARENT_ARTIFACT = seeded.PARENT_ARTIFACT
PARENT_ARTIFACT_NAME = seeded.PARENT_ARTIFACT_NAME
PARENT_DIGEST = seeded.PARENT_DIGEST
STARTING_STEP = seeded.STARTING_STEP
STARTING_TIME_S = seeded.STARTING_TIME_S
TARGET_TIME_S = 0.004285834855172021
HORIZON_ROUNDOFF_TOLERANCE_S = 8.0 * float(np.spacing(TARGET_TIME_S))
MAXIMUM_OPERATIONAL_SOLVER_STEP = 650

TRANSITION_CLASSIFICATION = "NO_ADMISSIBLE_ISLAND"
TRANSITION_MESSAGE_FRAGMENT = "dynamic seeded interval contains no admissible island"


class Increment9LStop(RuntimeError):
    pass


class BoundaryState(str, Enum):
    OUTWARD_FLOW = "OUTWARD_FLOW"
    ZERO_TRANSFER_CLOSED = "ZERO_TRANSFER_CLOSED"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(U, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        rows = [{"no_rows_recorded": True}]
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _inventory_array(values: dict[str, float]) -> np.ndarray:
    return np.asarray(
        [
            values["mass_kg"],
            values["momentum_kg_m_s"],
            values["energy_J"],
            values["vapor_mass_kg"],
        ],
        dtype=float,
    )


def _residual_passed(
    residual: float,
    *,
    absolute: float,
    relative: float,
    scale_values: tuple[float, ...],
) -> bool:
    scale = max((abs(float(value)) for value in scale_values), default=0.0)
    return bool(abs(float(residual)) <= max(float(absolute), float(relative) * scale))


def _classification(exc: BaseException) -> str | None:
    value = getattr(exc, "classification", None)
    return None if value is None else str(value)


class TwoStateBoundaryController:
    """Latch OUTWARD_FLOW into ZERO_TRANSFER_CLOSED on one exact branch-end event."""

    maximum_halvings = 12
    failure_outcome = "BOUNDARY_STATE_MACHINE_TRIAL_FAILURE"

    def __init__(
        self,
        *,
        outward_hook: Any,
        closure_hook: increment_9k.ZeroTransferClosureHook,
        provider: CoolPropB2StateProvider,
        allowed_phases: set[str],
        velocity_tolerance_m_s: float,
    ) -> None:
        self.outward_hook = outward_hook
        self.closure_hook = closure_hook
        self.provider = provider
        self.allowed_phases = set(allowed_phases)
        self.velocity_tolerance_m_s = float(velocity_tolerance_m_s)
        self.state = BoundaryState.OUTWARD_FLOW
        self.transition_event: dict[str, Any] | None = None
        self.outward_accepted_steps = 0
        self.closed_accepted_steps = 0
        self.requested_solver_step: int | None = None
        self.solver_time_s: float | None = None
        self.last_flux = np.zeros(4, dtype=float)
        self.last_transition_candidate_exception: dict[str, Any] | None = None
        self.step_number_used_for_transition_decision = False

    @property
    def root_context(self) -> Any:
        if self.state is not BoundaryState.OUTWARD_FLOW:
            return None
        return getattr(self.outward_hook, "root_context", None)

    @property
    def last_dt_limits(self) -> dict[str, Any]:
        if self.state is not BoundaryState.OUTWARD_FLOW:
            candidate = getattr(self.closure_hook, "last_candidate_dt_s", None)
            return {"candidate_dt_s": candidate}
        return dict(getattr(self.outward_hook, "last_dt_limits", {}))

    @property
    def trial_dts_s(self) -> list[float]:
        hook = (
            self.outward_hook
            if self.state is BoundaryState.OUTWARD_FLOW
            else self.closure_hook
        )
        return list(getattr(hook, "trial_dts_s", []))

    @property
    def flux(self) -> np.ndarray:
        return np.asarray(self.last_flux, dtype=float).copy()

    def begin_step(self, *, requested_solver_step: int, solver_time_s: float) -> None:
        self.requested_solver_step = int(requested_solver_step)
        self.solver_time_s = float(solver_time_s)
        self.last_flux = np.zeros(4, dtype=float)
        hook = (
            self.outward_hook
            if self.state is BoundaryState.OUTWARD_FLOW
            else self.closure_hook
        )
        begin = getattr(hook, "begin_step", None)
        if callable(begin):
            begin()

    def _scope_snapshot(self, U: np.ndarray) -> dict[str, Any]:
        array = np.asarray(U, dtype=float)
        if array.ndim != 2 or array.shape[1] != 4:
            raise Increment9LStop("state-machine candidate U has invalid shape")
        finite = bool(np.all(np.isfinite(array)))
        rho = np.asarray(array[:, 0], dtype=float)
        positive_density = bool(finite and np.all(rho > 0.0))
        velocity = np.full_like(rho, np.nan)
        internal = np.full_like(rho, np.nan)
        if positive_density:
            velocity = np.asarray(array[:, 1] / rho, dtype=float)
            internal = np.asarray(array[:, 2] / rho - 0.5 * velocity**2, dtype=float)
        positive_internal = bool(
            positive_density
            and np.all(np.isfinite(internal))
            and np.all(internal > 0.0)
        )
        vapor_exact = bool(np.all(array[:, 3] == 0.0))

        outlet = self.provider.reconstruct_from_conserved(array[-1]).static
        phase = normalize_phase(str(outlet.phase))
        mach = float(outlet.velocity_m_s / outlet.sound_speed_m_s)
        snapshot = {
            "all_conserved_finite": finite,
            "positive_density": positive_density,
            "positive_internal_energy": positive_internal,
            "rho_xv_exact_zero": vapor_exact,
            "minimum_density_kg_m3": (
                None if not positive_density else float(np.min(rho))
            ),
            "minimum_internal_energy_J_kg": (
                None if not positive_internal else float(np.min(internal))
            ),
            "outlet_pressure_pa": float(outlet.pressure_pa),
            "outlet_velocity_m_s": float(outlet.velocity_m_s),
            "outlet_sound_speed_m_s": float(outlet.sound_speed_m_s),
            "outlet_mach": mach,
            "outlet_phase": str(outlet.phase),
            "outlet_normalized_phase": phase,
            "allowed_phase": phase in self.allowed_phases,
            "nonreverse_within_locked_tolerance": bool(
                float(outlet.velocity_m_s) >= -self.velocity_tolerance_m_s
            ),
            "subsonic": bool(math.isfinite(mach) and 0.0 <= mach < 1.0),
        }
        snapshot["transition_scope_passed"] = bool(
            snapshot["all_conserved_finite"]
            and snapshot["positive_density"]
            and snapshot["positive_internal_energy"]
            and snapshot["rho_xv_exact_zero"]
            and snapshot["allowed_phase"]
            and snapshot["nonreverse_within_locked_tolerance"]
            and snapshot["subsonic"]
        )
        return snapshot

    def _may_transition(self, exc: BaseException, U: np.ndarray) -> tuple[bool, dict[str, Any]]:
        classification = _classification(exc)
        message = str(exc)
        snapshot = self._scope_snapshot(U)
        exact_event = bool(
            classification == TRANSITION_CLASSIFICATION
            and TRANSITION_MESSAGE_FRAGMENT in message
        )
        allowed = bool(
            self.state is BoundaryState.OUTWARD_FLOW
            and self.transition_event is None
            and self.outward_accepted_steps >= 1
            and exact_event
            and snapshot["transition_scope_passed"]
        )
        evidence = {
            **snapshot,
            "exception_type": type(exc).__name__,
            "classification": classification,
            "message": message,
            "exact_retained_branch_end_event": exact_event,
            "outward_accepted_steps_before_transition": self.outward_accepted_steps,
            "transition_allowed": allowed,
        }
        return allowed, evidence

    def _transition(self, *, exc: BaseException, U: np.ndarray, stage: str) -> None:
        allowed, evidence = self._may_transition(exc, U)
        self.last_transition_candidate_exception = dict(evidence)
        if not allowed:
            raise exc
        if self.requested_solver_step is None or self.solver_time_s is None:
            raise Increment9LStop("state-machine step identity was not prepared")
        before = self.state
        self.state = BoundaryState.ZERO_TRANSFER_CLOSED
        self.closure_hook.begin_step()
        self.transition_event = {
            "state_before": before.value,
            "state_after": self.state.value,
            "transition_stage": stage,
            "requested_solver_step": self.requested_solver_step,
            "solver_time_s": self.solver_time_s,
            "state_sha256_before_transition": _state_sha256(U),
            "step_number_used_for_transition_decision": False,
            **evidence,
        }

    def limit_dt(
        self,
        *,
        U: np.ndarray,
        eos: Any,
        grid: UniformGrid,
        t: float,
        candidate_dt: float,
    ) -> float:
        if self.state is BoundaryState.ZERO_TRANSFER_CLOSED:
            return float(
                self.closure_hook.limit_dt(
                    U=U,
                    eos=eos,
                    grid=grid,
                    t=t,
                    candidate_dt=candidate_dt,
                )
            )
        try:
            return float(
                self.outward_hook.limit_dt(
                    U=U,
                    eos=eos,
                    grid=grid,
                    t=t,
                    candidate_dt=candidate_dt,
                )
            )
        except Exception as exc:
            self._transition(exc=exc, U=U, stage="limit_dt")
            return float(
                self.closure_hook.limit_dt(
                    U=U,
                    eos=eos,
                    grid=grid,
                    t=t,
                    candidate_dt=candidate_dt,
                )
            )

    def evaluate_flux(
        self,
        *,
        U: np.ndarray,
        eos: Any,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> np.ndarray:
        if self.state is BoundaryState.ZERO_TRANSFER_CLOSED:
            flux = self.closure_hook.evaluate_flux(
                U=U, eos=eos, grid=grid, t=t, dt=dt
            )
        else:
            try:
                flux = self.outward_hook.evaluate_flux(
                    U=U, eos=eos, grid=grid, t=t, dt=dt
                )
            except Exception as exc:
                self._transition(exc=exc, U=U, stage="evaluate_flux")
                flux = self.closure_hook.evaluate_flux(
                    U=U, eos=eos, grid=grid, t=t, dt=dt
                )
        self.last_flux = np.asarray(flux, dtype=float).copy()
        return self.last_flux.copy()

    def validate_trial(
        self,
        *,
        U_before: np.ndarray,
        U_trial: np.ndarray,
        eos: Any,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> None:
        hook = (
            self.outward_hook
            if self.state is BoundaryState.OUTWARD_FLOW
            else self.closure_hook
        )
        hook.validate_trial(
            U_before=U_before,
            U_trial=U_trial,
            eos=eos,
            grid=grid,
            t=t,
            dt=dt,
        )

    def accept_current_root(self) -> None:
        if self.state is BoundaryState.OUTWARD_FLOW:
            accept = getattr(self.outward_hook, "accept_current_root", None)
            if callable(accept):
                accept()

    def record_accepted_step(self) -> None:
        if self.state is BoundaryState.OUTWARD_FLOW:
            self.outward_accepted_steps += 1
        else:
            self.closed_accepted_steps += 1


def _all_phases(
    U: np.ndarray,
    *,
    provider: CoolPropB2StateProvider,
) -> list[str]:
    return [
        normalize_phase(str(provider.reconstruct_from_conserved(row).static.phase))
        for row in np.asarray(U, dtype=float)
    ]


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U_start: np.ndarray,
    parent_root: dict[str, str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    np.ndarray,
    np.ndarray,
]:
    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = CoolPropB2StateProvider()
    _, initial_static = build_uniform_initial_state(
        contract, provider, state_id, grid.n_cells
    )
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )

    dynamic_fix._active_b1_contract = b1_contract
    outward_runner.DynamicGuardFrontHugoniotHook = (
        dynamic_fix.CorrectedDynamicGuardFrontHugoniotHook
    )
    outward_runner.inc8a._run = seeded._dynamic_seeded_root_run
    outward_hook = outward_runner.DynamicGuardFrontHugoniotHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    outward_hook._previous_root_pressure_pa = float(parent_root["root_pressure_pa"])
    closure_hook = increment_9k.ZeroTransferClosureHook(
        provider=provider,
        allowed_phases=allowed_phases,
    )
    controller = TwoStateBoundaryController(
        outward_hook=outward_hook,
        closure_hook=closure_hook,
        provider=provider,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_tolerance,
    )

    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider, boundary_temperature_K=initial_static.temperature_K
        ),
        U=np.asarray(U_start, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=controller,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=STARTING_TIME_S,
        step_count=STARTING_STEP,
    )

    U_before_all = np.asarray(solver.U, dtype=float).copy()
    segment_initial = inventory(
        solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2
    )
    cumulative_expected_delta = np.zeros(4, dtype=float)
    step_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None

    tolerances = contract["acceptance_tolerances"]
    while solver.t < TARGET_TIME_S - HORIZON_ROUNDOFF_TOLERANCE_S:
        if int(solver.step_count) >= MAXIMUM_OPERATIONAL_SOLVER_STEP:
            stop_classification = "OPERATIONAL_STEP_CAP_EXCEEDED"
            stop_reason = (
                f"solver step cap {MAXIMUM_OPERATIONAL_SOLVER_STEP} reached"
            )
            break

        requested_step = int(solver.step_count + 1)
        controller.begin_step(
            requested_solver_step=requested_step,
            solver_time_s=float(solver.t),
        )
        state_before_compute = controller.state.value
        U_before = np.asarray(solver.U, dtype=float).copy()
        before = inventory(U_before, dx=grid.dx, area_m2=grid.geometry.area_m2)
        try:
            cfl_candidate_dt = float(solver.compute_dt())
            remaining = float(TARGET_TIME_S - solver.t)
            requested_dt = float(min(cfl_candidate_dt, remaining))
            clipped = bool(remaining <= cfl_candidate_dt)
            state_for_step = controller.state.value
            left_fluxes, _ = solver._base_fluxes()
            left_flux = np.asarray(left_fluxes[0], dtype=float).copy()
            accepted_dt = float(solver.step(requested_dt))
            controller.accept_current_root()
            controller.record_accepted_step()
            right_flux = np.asarray(controller.last_flux, dtype=float).copy()
            U_after = np.asarray(solver.U, dtype=float).copy()
            after = inventory(U_after, dx=grid.dx, area_m2=grid.geometry.area_m2)
        except Exception as exc:
            stop_classification = _classification(exc) or type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            break

        expected_step_delta = (
            accepted_dt * grid.geometry.area_m2 * (left_flux - right_flux)
        )
        cumulative_expected_delta = cumulative_expected_delta + expected_step_delta
        actual_step_delta = _inventory_array(after) - _inventory_array(before)
        step_residual = actual_step_delta - expected_step_delta
        actual_cumulative_delta = (
            _inventory_array(after) - _inventory_array(segment_initial)
        )
        cumulative_residual = actual_cumulative_delta - cumulative_expected_delta

        rho = np.asarray(U_after[:, 0], dtype=float)
        velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
        internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
        phases = _all_phases(U_after, provider=provider)
        outlet = provider.reconstruct_from_conserved(U_after[-1]).static
        pressure_before = float(
            provider.reconstruct_from_conserved(U_before[-1]).static.pressure_pa
        )
        wall_residual = float(right_flux[1] - pressure_before)

        step_mass_passed = _residual_passed(
            float(step_residual[0]),
            absolute=float(tolerances["mass_inventory_absolute_kg"]),
            relative=float(tolerances["mass_inventory_relative"]),
            scale_values=(before["mass_kg"], after["mass_kg"], expected_step_delta[0]),
        )
        step_momentum_passed = _residual_passed(
            float(step_residual[1]),
            absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
            relative=float(tolerances["momentum_inventory_relative"]),
            scale_values=(
                before["momentum_kg_m_s"],
                after["momentum_kg_m_s"],
                expected_step_delta[1],
            ),
        )
        step_energy_passed = _residual_passed(
            float(step_residual[2]),
            absolute=float(tolerances["energy_inventory_absolute_J"]),
            relative=float(tolerances["energy_inventory_relative"]),
            scale_values=(before["energy_J"], after["energy_J"], expected_step_delta[2]),
        )
        cumulative_mass_passed = _residual_passed(
            float(cumulative_residual[0]),
            absolute=float(tolerances["mass_inventory_absolute_kg"]),
            relative=float(tolerances["mass_inventory_relative"]),
            scale_values=(
                segment_initial["mass_kg"],
                after["mass_kg"],
                cumulative_expected_delta[0],
            ),
        )
        cumulative_momentum_passed = _residual_passed(
            float(cumulative_residual[1]),
            absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
            relative=float(tolerances["momentum_inventory_relative"]),
            scale_values=(
                segment_initial["momentum_kg_m_s"],
                after["momentum_kg_m_s"],
                cumulative_expected_delta[1],
            ),
        )
        cumulative_energy_passed = _residual_passed(
            float(cumulative_residual[2]),
            absolute=float(tolerances["energy_inventory_absolute_J"]),
            relative=float(tolerances["energy_inventory_relative"]),
            scale_values=(
                segment_initial["energy_J"],
                after["energy_J"],
                cumulative_expected_delta[2],
            ),
        )

        closure = state_for_step == BoundaryState.ZERO_TRANSFER_CLOSED.value
        closure_identity = bool(
            not closure
            or (
                right_flux[0] == 0.0
                and right_flux[2] == 0.0
                and right_flux[3] == 0.0
                and wall_residual == 0.0
            )
        )
        outward_context = getattr(outward_hook, "root_context", None)
        outward_root_gate = bool(
            not closure
            and outward_context is not None
            and bool(outward_context["root"]["root_gate_passed"])
        )
        branch_gate = bool(closure_identity if closure else outward_root_gate)
        per_step_gate = bool(
            int(solver.step_count) == requested_step
            and accepted_dt > 0.0
            and np.all(np.isfinite(U_after))
            and np.all(rho > 0.0)
            and np.all(internal > 0.0)
            and np.all(U_after[:, 3] == 0.0)
            and all(phase in allowed_phases for phase in phases)
            and step_mass_passed
            and step_momentum_passed
            and step_energy_passed
            and cumulative_mass_passed
            and cumulative_momentum_passed
            and cumulative_energy_passed
            and branch_gate
        )

        transition_applied_this_step = bool(
            controller.transition_event is not None
            and int(controller.transition_event["requested_solver_step"])
            == requested_step
        )
        row = {
            "requested_solver_step": requested_step,
            "solver_step_count": int(solver.step_count),
            "time_before_s": float(solver.t - accepted_dt),
            "time_after_s": float(solver.t),
            "state_before_compute_dt": state_before_compute,
            "boundary_state_for_accepted_step": state_for_step,
            "transition_applied_this_step": transition_applied_this_step,
            "cfl_candidate_dt_s": cfl_candidate_dt,
            "requested_dt_s": requested_dt,
            "accepted_dt_s": accepted_dt,
            "step_clipped_to_target": clipped,
            "halving_count": max(len(controller.trial_dts_s) - 1, 0),
            "right_external_mass_flux_kg_m2_s": float(right_flux[0]),
            "right_external_momentum_flux_pa": float(right_flux[1]),
            "right_external_energy_flux_W_m2": float(right_flux[2]),
            "right_external_vapor_flux_kg_m2_s": float(right_flux[3]),
            "interior_pressure_before_step_pa": pressure_before,
            "momentum_wall_identity_residual_pa": wall_residual,
            "step_mass_residual_kg": float(step_residual[0]),
            "step_momentum_residual_kg_m_s": float(step_residual[1]),
            "step_energy_residual_J": float(step_residual[2]),
            "segment_cumulative_mass_residual_kg": float(cumulative_residual[0]),
            "segment_cumulative_momentum_residual_kg_m_s": float(
                cumulative_residual[1]
            ),
            "segment_cumulative_energy_residual_J": float(cumulative_residual[2]),
            "step_mass_passed": step_mass_passed,
            "step_momentum_passed": step_momentum_passed,
            "step_energy_passed": step_energy_passed,
            "segment_cumulative_mass_passed": cumulative_mass_passed,
            "segment_cumulative_momentum_passed": cumulative_momentum_passed,
            "segment_cumulative_energy_passed": cumulative_energy_passed,
            "all_conserved_finite": bool(np.all(np.isfinite(U_after))),
            "minimum_density_kg_m3": float(np.min(rho)),
            "minimum_internal_energy_J_kg": float(np.min(internal)),
            "all_phases_allowed": all(phase in allowed_phases for phase in phases),
            "normalized_phases": sorted(set(phases)),
            "rho_xv_exact_zero": bool(np.all(U_after[:, 3] == 0.0)),
            "outlet_pressure_pa": float(outlet.pressure_pa),
            "outlet_velocity_m_s": float(outlet.velocity_m_s),
            "outlet_mach": float(outlet.velocity_m_s / outlet.sound_speed_m_s),
            "outlet_phase": str(outlet.phase),
            "closure_identity_passed": closure_identity,
            "outward_root_gate_passed": outward_root_gate,
            "increment_9l_per_step_gate_passed": per_step_gate,
        }
        step_rows.append(row)
        state_rows.append(
            {
                "solver_step_count": int(solver.step_count),
                "time_after_s": float(solver.t),
                "boundary_state": state_for_step,
                "transition_applied": transition_applied_this_step,
                "accepted": True,
                "per_step_gate_passed": per_step_gate,
            }
        )
        if not per_step_gate:
            stop_classification = "POST_STEP_GATE_FAILURE"
            stop_reason = f"Increment 9L step {requested_step} gate failed"
            break

    U_after_all = np.asarray(solver.U, dtype=float).copy()
    horizon_error = float(solver.t - TARGET_TIME_S)
    target_reached = bool(
        solver.t >= TARGET_TIME_S
        and abs(horizon_error) <= HORIZON_ROUNDOFF_TOLERANCE_S
    )
    branches = [str(row["boundary_state_for_accepted_step"]) for row in step_rows]
    transitions = sum(left != right for left, right in zip(branches, branches[1:]))
    reentry = any(
        left == BoundaryState.ZERO_TRANSFER_CLOSED.value
        and right == BoundaryState.OUTWARD_FLOW.value
        for left, right in zip(branches, branches[1:])
    )
    final_phases = _all_phases(U_after_all, provider=provider)
    rho_final = np.asarray(U_after_all[:, 0], dtype=float)
    velocity_final = np.asarray(U_after_all[:, 1] / rho_final, dtype=float)
    internal_final = np.asarray(
        U_after_all[:, 2] / rho_final - 0.5 * velocity_final**2,
        dtype=float,
    )
    final_outlet = provider.reconstruct_from_conserved(U_after_all[-1]).static
    transition = controller.transition_event

    gate = bool(
        stop_reason is None
        and step_rows
        and target_reached
        and bool(step_rows[-1]["step_clipped_to_target"])
        and controller.outward_accepted_steps >= 1
        and controller.closed_accepted_steps >= 1
        and transition is not None
        and transition["state_before"] == BoundaryState.OUTWARD_FLOW.value
        and transition["state_after"] == BoundaryState.ZERO_TRANSFER_CLOSED.value
        and transition["classification"] == TRANSITION_CLASSIFICATION
        and transition["exact_retained_branch_end_event"] is True
        and transition["step_number_used_for_transition_decision"] is False
        and controller.step_number_used_for_transition_decision is False
        and transitions == 1
        and not reentry
        and all(row["increment_9l_per_step_gate_passed"] for row in step_rows)
        and all(phase in allowed_phases for phase in final_phases)
        and np.all(np.isfinite(U_after_all))
        and np.all(rho_final > 0.0)
        and np.all(internal_final > 0.0)
        and np.all(U_after_all[:, 3] == 0.0)
    )

    def max_abs(key: str) -> float | None:
        return max((abs(float(row[key])) for row in step_rows), default=None)

    summary = {
        "schema_version": "stage7_u3_b2_a1_increment_9l_gate_a_state_machine_v1",
        "scope": "model_review_two_state_boundary_controller_authoritative_transition_segment",
        "source_git_sha": None,
        "model_review_gate": "GATE_A",
        "full_initial_state_gate_b_executed": False,
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_DIGEST,
        "parent_artifact_verified": True,
        "starting_solver_step": STARTING_STEP,
        "starting_solver_time_s": STARTING_TIME_S,
        "starting_state_sha256": _state_sha256(U_before_all),
        "target_two_l_over_c0_time_s": TARGET_TIME_S,
        "final_solver_step": int(solver.step_count),
        "final_solver_time_s": float(solver.t),
        "final_state_sha256": _state_sha256(U_after_all),
        "additional_accepted_steps": len(step_rows),
        "outward_accepted_steps": controller.outward_accepted_steps,
        "closed_accepted_steps": controller.closed_accepted_steps,
        "boundary_state_sequence": branches,
        "boundary_state_counts": dict(Counter(branches)),
        "boundary_transition_count": transitions,
        "transition_event_count": 0 if transition is None else 1,
        "transition_classification": (
            None if transition is None else transition["classification"]
        ),
        "transition_message": None if transition is None else transition["message"],
        "transition_requested_solver_step": (
            None if transition is None else transition["requested_solver_step"]
        ),
        "transition_solver_time_s": (
            None if transition is None else transition["solver_time_s"]
        ),
        "transition_scope_passed": (
            False if transition is None else transition["transition_scope_passed"]
        ),
        "step_number_used_for_transition_decision": False,
        "zero_transfer_reentry_observed": reentry,
        "target_horizon_reached": target_reached,
        "horizon_fraction_reached": float(solver.t / TARGET_TIME_S),
        "horizon_time_error_s": horizon_error,
        "final_step_clipped_to_target": bool(
            step_rows and step_rows[-1]["step_clipped_to_target"]
        ),
        "maximum_absolute_step_mass_residual_kg": max_abs("step_mass_residual_kg"),
        "maximum_absolute_step_momentum_residual_kg_m_s": max_abs(
            "step_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_step_energy_residual_J": max_abs("step_energy_residual_J"),
        "maximum_absolute_segment_cumulative_mass_residual_kg": max_abs(
            "segment_cumulative_mass_residual_kg"
        ),
        "maximum_absolute_segment_cumulative_momentum_residual_kg_m_s": max_abs(
            "segment_cumulative_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_segment_cumulative_energy_residual_J": max_abs(
            "segment_cumulative_energy_residual_J"
        ),
        "minimum_density_kg_m3": float(np.min(rho_final)),
        "minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "final_normalized_phases": sorted(set(final_phases)),
        "final_all_phases_allowed": all(
            phase in allowed_phases for phase in final_phases
        ),
        "final_rho_xv_exact_zero": bool(np.all(U_after_all[:, 3] == 0.0)),
        "final_outlet_pressure_pa": float(final_outlet.pressure_pa),
        "final_outlet_velocity_m_s": float(final_outlet.velocity_m_s),
        "final_outlet_mach": float(
            final_outlet.velocity_m_s / final_outlet.sound_speed_m_s
        ),
        "final_outlet_phase": str(final_outlet.phase),
        "technical_issue": TECHNICAL_ISSUE,
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "increment_9l_gate_a_passed": gate,
        "working_vertical_slice": gate,
        "working_vertical_slice_kind": (
            "INCREMENT_9L_GATE_A_TRANSITION_WORKING_SLICE" if gate else None
        ),
        "outcome": OUTCOME if gate else "INCREMENT_9L_GATE_A_STOPPED",
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    transition_output = transition or {
        "transition_recorded": False,
        "last_transition_candidate_exception": (
            controller.last_transition_candidate_exception
        ),
    }
    return summary, step_rows, state_rows, transition_output, U_before_all, U_after_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (args.contract, args.b1_contract, args.model_review_spec):
        if not path.is_file():
            raise FileNotFoundError(path)

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_start, parent_step, parent_root = seeded._verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    del parent_summary, parent_step

    summary, step_rows, state_rows, transition, U_before, U_after = _run(
        contract=contract,
        b1_contract=b1_contract,
        U_start=U_start,
        parent_root=parent_root,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec"] = str(args.model_review_spec)
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise Increment9LStop("Increment 9L output directory is not empty")

    _write_csv(output / "state_machine_steps.csv", step_rows)
    _write_csv(output / "boundary_state_history.csv", state_rows)
    (output / "transition_event.json").write_text(
        json.dumps(transition, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "authority_verification.json").write_text(
        json.dumps(
            {
                "parent_source_sha": PARENT_SOURCE_SHA,
                "parent_run": PARENT_RUN,
                "parent_job": PARENT_JOB,
                "parent_artifact": PARENT_ARTIFACT,
                "parent_artifact_name": PARENT_ARTIFACT_NAME,
                "parent_artifact_sha256": PARENT_DIGEST,
                "parent_internal_manifest_verified": True,
                "starting_state_sha256": summary["starting_state_sha256"],
                "verified": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "technical_issue.json").write_text(
        json.dumps(
            {
                "technical_issue": TECHNICAL_ISSUE,
                "strict_increment_9j_classification": (
                    "ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE"
                ),
                "engineering_transition_trigger": TRANSITION_CLASSIFICATION,
                "engineering_transition_message_fragment": (
                    TRANSITION_MESSAGE_FRAGMENT
                ),
                "transition_is_physical_verification": False,
                "reentry_implemented": False,
                "reverse_mass_transfer_implemented": False,
                "physical_validation": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        output / "state_machine_full_horizon_states.npz",
        U_before=np.asarray(U_before, dtype=float),
        U_after=np.asarray(U_after, dtype=float),
        solver_step_before=np.asarray([STARTING_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
        target_time_s=np.asarray([TARGET_TIME_S]),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9L Gate A boundary state-machine result\n\n"
        "The authoritative Increment 9H step-636 state was loaded. The boundary "
        "controller accepted outward finite-compression flow while the retained "
        "root existed, then latched into `ZERO_TRANSFER_CLOSED` only after the "
        "exact predeclared `NO_ADMISSIBLE_ISLAND` event passed the engineering "
        "scope guards. The transition decision did not inspect the solver step "
        "number. Gate A isolates transition behavior; it is not the complete "
        "initial-state Gate B trajectory and is not verification or validation.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "state_machine_steps.csv",
        "boundary_state_history.csv",
        "transition_event.json",
        "authority_verification.json",
        "technical_issue.json",
        "state_machine_full_horizon_states.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9l_gate_a_passed"]:
        raise SystemExit(
            "Increment 9L Gate A did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
