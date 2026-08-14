"""Working Tool W2 canonical full-horizon backend.

This integration-side adapter drives the completed public Working Tool shell
through the retained Increment 9M A2 live FVM path from the exact locked initial
state to the canonical 2L/c0 horizon.  It reuses the existing Increment 9L
conservative run ledger and records separate runtime evidence for the external
W2 regression harness.  The public Working Tool package remains independent of
verification runners and authority artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Mapping

import numpy as np

import u3_b2_a1_increment_9l_two_state_boundary_state_machine as base
import u3_b2_a1_increment_9l_two_state_boundary_state_machine_v3 as topology_v3
import u3_b2_a1_increment_9m_a2_live_fvm_composition as a2
import u3_b2_a1_working_tool_w1_a2_live_backend as w1
from liquid_gas_transient.solver import FvmSolver as CoreFvmSolver
from liquid_gas_transient.state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, make_conserved
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
)
from liquid_gas_transient.working_tool import (
    BackendRunData,
    TransitionRecord,
    WarningSeverity,
    WorkingToolCase,
    WorkingToolWarning,
)


BACKEND_NAME = "INCREMENT_9M_A2_FULL_HORIZON_WORKING_TOOL_BACKEND"
BACKEND_SCHEMA = "stage7_u3_b2_a1_working_tool_w2_full_horizon_backend_v1"
EXPECTED_ACCEPTED_STEPS = 640
EXPECTED_TARGET_TIME_S = 0.004285834855172021
W2_FULL_HORIZON_WARNING_CODE = "WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_SCOPE"
W2_FULL_HORIZON_WARNING = WorkingToolWarning(
    code=W2_FULL_HORIZON_WARNING_CODE,
    severity=WarningSeverity.WARNING,
    message=(
        "This result is limited to the canonical provisional single-phase "
        "Working Tool W2 full-horizon case. It remains not VERIFIED, ACCEPTED, "
        "VALIDATED, or DESIGN-USE APPROVED."
    ),
)


class W2CaseScopeError(ValueError):
    """Raised before solver construction for a noncanonical W2 case."""


class W2FullHorizonBackendError(RuntimeError):
    """Raised when the retained full-horizon runtime fails a W2 gate."""


@dataclass(frozen=True)
class W2RuntimeEvidence:
    """Verification-only runtime evidence kept outside the public result."""

    summary: Mapping[str, Any]
    step_rows: tuple[Mapping[str, Any], ...]
    state_rows: tuple[Mapping[str, Any], ...]
    outward_model_transition_rows: tuple[Mapping[str, Any], ...]
    boundary_transition_rows: tuple[Mapping[str, Any], ...]
    three_branch_algorithm_rows: tuple[Mapping[str, Any], ...]
    bounded_window_rows: tuple[Mapping[str, Any], ...]
    guard_front_topology_rows: tuple[Mapping[str, Any], ...]
    manager_transition_rows: tuple[Mapping[str, Any], ...]
    manager_selection_rows: tuple[Mapping[str, Any], ...]
    context_restoration_rows: tuple[Mapping[str, Any], ...]
    U_initial: np.ndarray
    U_final: np.ndarray
    accepted_state_snapshots: np.ndarray
    accepted_time_snapshots_s: np.ndarray


class RecordingFvmSolver(CoreFvmSolver):
    """Record accepted states without changing the retained solver step."""

    last_instance: ClassVar["RecordingFvmSolver | None"] = None
    instance_count: ClassVar[int] = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.accepted_state_snapshots: list[np.ndarray] = [
            np.asarray(self.U, dtype=float).copy()
        ]
        self.accepted_time_snapshots_s: list[float] = [float(self.t)]
        type(self).instance_count += 1
        type(self).last_instance = self

    def step(self, dt: float | None = None) -> float:
        accepted_dt = float(super().step(dt))
        self.accepted_state_snapshots.append(
            np.asarray(self.U, dtype=float).copy()
        )
        self.accepted_time_snapshots_s.append(float(self.t))
        return accepted_dt


def _dict_rows(rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in rows)


def _public_history(step_rows: tuple[Mapping[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    fields = (
        "solver_step_count",
        "time_after_s",
        "accepted_dt_s",
        "public_boundary_state",
        "outward_internal_model",
        "branch_classification",
        "finite_compression_algorithm",
        "state_transition_triggered_this_step",
        "outward_model_transition_triggered_this_step",
        "transition_trigger_classification",
        "right_external_mass_flux_kg_m2_s",
        "right_external_momentum_flux_pa",
        "right_external_energy_flux_W_m2",
        "right_external_vapor_flux_kg_m2_s",
        "outlet_pressure_after_pa",
        "outlet_velocity_after_m_s",
        "outlet_mach_after",
        "minimum_density_after_kg_m3",
        "minimum_internal_energy_after_J_kg",
        "cumulative_mass_residual_kg",
        "cumulative_momentum_residual_kg_m_s",
        "cumulative_energy_residual_J",
        "rho_xv_exact_zero",
    )
    history: list[dict[str, Any]] = []
    for row in step_rows:
        item = {name: row.get(name) for name in fields}
        item["step"] = item.pop("solver_step_count")
        item["time_s"] = item.pop("time_after_s")
        history.append(item)
    return tuple(history)


def _public_state_history(
    *,
    case: WorkingToolCase,
    states: np.ndarray,
    times_s: np.ndarray,
) -> dict[str, np.ndarray]:
    provider = CoolPropB2StateProvider()
    eos = CoolPropSinglePhaseEOS(
        provider,
        boundary_temperature_K=case.initial.temperature_k,
    )
    rho_rows: list[np.ndarray] = []
    velocity_rows: list[np.ndarray] = []
    pressure_rows: list[np.ndarray] = []
    temperature_rows: list[np.ndarray] = []
    internal_rows: list[np.ndarray] = []
    vapor_fraction_rows: list[np.ndarray] = []
    for conserved in states:
        primitive = eos.primitive_from_conserved(conserved)
        rho_rows.append(np.asarray(primitive.rho, dtype=float).copy())
        velocity_rows.append(np.asarray(primitive.u, dtype=float).copy())
        pressure_rows.append(np.asarray(primitive.p, dtype=float).copy())
        temperature_rows.append(np.asarray(primitive.T, dtype=float).copy())
        internal_rows.append(np.asarray(primitive.e, dtype=float).copy())
        vapor_fraction_rows.append(np.asarray(primitive.xv, dtype=float).copy())
    x_m = (
        np.arange(case.numerics.n_cells, dtype=float) + 0.5
    ) * (case.geometry.length_m / case.numerics.n_cells)
    return {
        "time_s": np.asarray(times_s, dtype=float).copy(),
        "x_m": x_m,
        "conserved": np.asarray(states, dtype=float).copy(),
        "rho_kg_m3": np.stack(rho_rows, axis=0),
        "velocity_m_s": np.stack(velocity_rows, axis=0),
        "pressure_pa": np.stack(pressure_rows, axis=0),
        "temperature_k": np.stack(temperature_rows, axis=0),
        "internal_energy_j_kg": np.stack(internal_rows, axis=0),
        "vapor_mass_fraction": np.stack(vapor_fraction_rows, axis=0),
    }


class A2FullHorizonWorkingToolBackend(w1.A2LiveWorkingToolBackend):
    """Run the exact canonical A2 path to 2L/c0 through the public API."""

    def __init__(
        self,
        *,
        contract_path: str | Path,
        b1_contract_path: str | Path,
    ) -> None:
        super().__init__(
            contract_path=contract_path,
            b1_contract_path=b1_contract_path,
            smoke_accepted_steps=EXPECTED_ACCEPTED_STEPS,
        )
        self.runtime_evidence: W2RuntimeEvidence | None = None

    def _validate_w2_case(
        self,
        case: WorkingToolCase,
        provider: CoolPropB2StateProvider,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], float]:
        try:
            locked_case, family, target_time_s = self._validate_case(case, provider)
        except w1.W1CaseScopeError as exc:
            raise W2CaseScopeError(
                str(exc).replace("W1_NONCANONICAL_CASE", "W2_NONCANONICAL_CASE")
            ) from exc
        if case.time.max_steps < EXPECTED_ACCEPTED_STEPS:
            raise W2CaseScopeError(
                "W2_NONCANONICAL_CASE: max_steps is below 640"
            )
        if target_time_s != EXPECTED_TARGET_TIME_S:
            raise W2CaseScopeError(
                "W2_NONCANONICAL_CASE: locked target time changed"
            )
        return locked_case, family, target_time_s

    def run_case(self, case: WorkingToolCase) -> BackendRunData:
        provider = CoolPropB2StateProvider()
        _, _, target_time_s = self._validate_w2_case(case, provider)

        static = provider.static_state_from_pT(
            case.initial.pressure_pa,
            case.initial.temperature_k,
            case.initial.velocity_m_s,
        )
        case_initial = make_conserved(
            np.full(case.numerics.n_cells, static.density_kg_m3),
            np.full(case.numerics.n_cells, case.initial.velocity_m_s),
            np.full(case.numerics.n_cells, static.internal_energy_J_kg),
            np.zeros(case.numerics.n_cells),
        )
        case_starting_sha = w1._state_sha256(case_initial)
        if case_starting_sha != w1.A2_STARTING_STATE_SHA256:
            raise W2FullHorizonBackendError(
                "W2_STARTING_STATE_SHA_MISMATCH"
            )

        original_hook = base.TwoStateBoundaryStateMachineHook
        original_solver = base.FvmSolver
        original_positive_scan = (
            base.weak_refined._guard_front_positive_scan
        )
        original_boundary_solve = (
            base.weak_refined._guard_front_solve_three_branch_boundary
        )

        topology_v3._TOPOLOGY_EVENTS.clear()
        a2.ModelManagedLiveFvmHook.last_instance = None
        RecordingFvmSolver.last_instance = None
        RecordingFvmSolver.instance_count = 0

        try:
            topology_v3._install_correction()
            base.TwoStateBoundaryStateMachineHook = a2.ModelManagedLiveFvmHook
            base.FvmSolver = RecordingFvmSolver
            (
                run_summary,
                step_rows,
                state_rows,
                boundary_transition_rows,
                outward_model_transition_rows,
                U_initial,
                U_final,
            ) = base._run(
                contract=self.contract,
                b1_contract=self.b1_contract,
            )
            hook = a2.ModelManagedLiveFvmHook.last_instance
            solver = RecordingFvmSolver.last_instance
            topology_rows = sorted(
                (dict(row) for row in topology_v3._TOPOLOGY_EVENTS),
                key=lambda row: (
                    int(row["requested_solver_step"]),
                    float(row["solver_time_s"]),
                ),
            )
        finally:
            base.TwoStateBoundaryStateMachineHook = original_hook
            base.FvmSolver = original_solver
            base.weak_refined._guard_front_positive_scan = original_positive_scan
            base.weak_refined._guard_front_solve_three_branch_boundary = (
                original_boundary_solve
            )

        if hook is None or solver is None:
            raise W2FullHorizonBackendError(
                "W2_LIVE_RUNTIME_INSTANCE_MISSING"
            )
        self.solver_instances_created += RecordingFvmSolver.instance_count
        if RecordingFvmSolver.instance_count != 1:
            raise W2FullHorizonBackendError(
                "W2_EXPECTED_EXACTLY_ONE_FVM_SOLVER"
            )

        U_initial_array = np.asarray(U_initial, dtype=float).copy()
        U_final_array = np.asarray(U_final, dtype=float).copy()
        if not np.array_equal(case_initial, U_initial_array):
            raise W2FullHorizonBackendError(
                "W2_CASE_INPUT_RUNTIME_INITIAL_STATE_MISMATCH"
            )

        accepted_states = np.stack(
            solver.accepted_state_snapshots,
            axis=0,
        )
        accepted_times = np.asarray(
            solver.accepted_time_snapshots_s,
            dtype=float,
        )
        if accepted_states.shape[0] != EXPECTED_ACCEPTED_STEPS + 1:
            raise W2FullHorizonBackendError(
                "W2_ACCEPTED_STATE_SNAPSHOT_COUNT_MISMATCH"
            )
        if accepted_times.shape != (EXPECTED_ACCEPTED_STEPS + 1,):
            raise W2FullHorizonBackendError(
                "W2_ACCEPTED_TIME_SNAPSHOT_COUNT_MISMATCH"
            )
        if not np.array_equal(accepted_states[0], U_initial_array):
            raise W2FullHorizonBackendError(
                "W2_RECORDED_INITIAL_STATE_MISMATCH"
            )
        if not np.array_equal(accepted_states[-1], U_final_array):
            raise W2FullHorizonBackendError(
                "W2_RECORDED_FINAL_STATE_MISMATCH"
            )

        manager_transition_rows = tuple(
            a2._manager_event_rows(hook.model_manager)
        )
        manager_selection_rows = tuple(
            a2._manager_selection_rows(hook.model_manager)
        )
        restoration_rows = tuple(
            dict(row)
            for row in hook.model_manager_context_restoration_rows
        )
        restoration_gate = bool(
            len(restoration_rows) == EXPECTED_ACCEPTED_STEPS
            and all(bool(row["restoration_gate_passed"]) for row in restoration_rows)
            and all(
                row["context_restored_without_root_reconstruction"] is True
                and row["flux_modified_by_manager"] is False
                for row in restoration_rows
            )
        )

        full_horizon_gate = bool(
            run_summary["increment_9l_state_machine_gate_passed"] is True
            and run_summary["target_horizon_reached"] is True
            and run_summary["accepted_steps_completed"] == EXPECTED_ACCEPTED_STEPS
            and run_summary["final_solver_step"] == EXPECTED_ACCEPTED_STEPS
            and run_summary["target_two_l_over_c0_time_s"] == target_time_s
            and run_summary["final_solver_time_s"] == target_time_s
            and run_summary["horizon_time_error_s"] == 0.0
            and len(manager_transition_rows) == 2
            and len(manager_selection_rows) == 3
            and restoration_gate
            and run_summary["final_all_phases_allowed"] is True
            and run_summary["final_rho_xv_exact_zero"] is True
        )
        if not full_horizon_gate:
            raise W2FullHorizonBackendError(
                "W2_CANONICAL_FULL_HORIZON_GATE_FAILURE"
            )

        step_rows_tuple = _dict_rows(step_rows)
        state_rows_tuple = _dict_rows(state_rows)
        outward_rows_tuple = _dict_rows(outward_model_transition_rows)
        boundary_rows_tuple = _dict_rows(boundary_transition_rows)
        handoff_rows_tuple = _dict_rows(
            list(hook.three_branch_algorithm_transition_events)
        )
        bounded_rows_tuple = _dict_rows(
            sorted(
                (dict(row) for row in hook.bounded_window_fallback_events),
                key=lambda row: (
                    int(row["requested_solver_step"]),
                    float(row["solver_time_s"]),
                ),
            )
        )
        topology_rows_tuple = _dict_rows(topology_rows)

        self.runtime_evidence = W2RuntimeEvidence(
            summary=dict(run_summary),
            step_rows=step_rows_tuple,
            state_rows=state_rows_tuple,
            outward_model_transition_rows=outward_rows_tuple,
            boundary_transition_rows=boundary_rows_tuple,
            three_branch_algorithm_rows=handoff_rows_tuple,
            bounded_window_rows=bounded_rows_tuple,
            guard_front_topology_rows=topology_rows_tuple,
            manager_transition_rows=_dict_rows(manager_transition_rows),
            manager_selection_rows=_dict_rows(manager_selection_rows),
            context_restoration_rows=_dict_rows(restoration_rows),
            U_initial=U_initial_array.copy(),
            U_final=U_final_array.copy(),
            accepted_state_snapshots=accepted_states.copy(),
            accepted_time_snapshots_s=accepted_times.copy(),
        )

        transitions = tuple(
            TransitionRecord(
                axis=str(row["axis"]),
                from_state=str(row["from_state"]),
                to_state=str(row["to_state"]),
                trigger_classification=str(row["trigger_classification"]),
                solver_time_s=float(row["solver_time_s"]),
                observed_solver_step=int(row["observed_solver_step"]),
                absolute_step_number_trigger_used=False,
            )
            for row in manager_transition_rows
        )
        summary = {
            "backend_schema": BACKEND_SCHEMA,
            "backend_name": BACKEND_NAME,
            "a2_live_path_connected": True,
            "a2_model_managed_live_hook_used": True,
            "canonical_locked_case_id": w1.A2_CASE_ID,
            "canonical_full_horizon_scope": True,
            "accepted_steps": int(run_summary["accepted_steps_completed"]),
            "final_solver_step": int(run_summary["final_solver_step"]),
            "final_solver_time_s": float(run_summary["final_solver_time_s"]),
            "target_two_l_over_c0_time_s": float(
                run_summary["target_two_l_over_c0_time_s"]
            ),
            "horizon_time_error_s": float(run_summary["horizon_time_error_s"]),
            "target_horizon_reached": bool(run_summary["target_horizon_reached"]),
            "full_two_l_over_c0_execution_completed": True,
            "starting_state_sha256": str(run_summary["starting_state_sha256"]),
            "final_state_sha256": str(run_summary["final_state_sha256"]),
            "case_input_reproduced_runtime_initial_state": True,
            "one_fvm_solver_instance": RecordingFvmSolver.instance_count == 1,
            "model_manager_profile": hook.model_manager.profile_name,
            "manager_transition_count": len(manager_transition_rows),
            "manager_selection_history_count": len(manager_selection_rows),
            "successful_context_restoration_count": len(restoration_rows),
            "context_restoration_gate_passed": restoration_gate,
            "context_restored_without_root_reconstruction": restoration_gate,
            "physics_flux_modified_by_manager": False,
            "checkpoint_state_used": False,
            "absolute_step_number_transition_condition_used": False,
            "public_boundary_state_counts": dict(
                run_summary["public_boundary_state_counts"]
            ),
            "outward_internal_model_counts": dict(
                run_summary["outward_internal_model_counts"]
            ),
            "outward_branch_counts": dict(run_summary["outward_branch_counts"]),
            "public_state_transition_count": int(
                run_summary["public_state_transition_count"]
            ),
            "right_mass_transfer_exact_zero_all_closed_steps": bool(
                run_summary["right_mass_transfer_exact_zero_all_closed_steps"]
            ),
            "right_energy_transfer_exact_zero_all_closed_steps": bool(
                run_summary["right_energy_transfer_exact_zero_all_closed_steps"]
            ),
            "right_vapor_transfer_exact_zero_all_closed_steps": bool(
                run_summary["right_vapor_transfer_exact_zero_all_closed_steps"]
            ),
            "wall_momentum_identity_exact_all_closed_steps": bool(
                run_summary["wall_momentum_identity_exact_all_closed_steps"]
            ),
            "maximum_absolute_cumulative_mass_residual_kg": float(
                run_summary["maximum_absolute_cumulative_mass_residual_kg"]
            ),
            "maximum_absolute_cumulative_momentum_residual_kg_m_s": float(
                run_summary[
                    "maximum_absolute_cumulative_momentum_residual_kg_m_s"
                ]
            ),
            "maximum_absolute_cumulative_energy_residual_j": float(
                run_summary["maximum_absolute_cumulative_energy_residual_J"]
            ),
            "minimum_density_kg_m3": float(run_summary["minimum_density_kg_m3"]),
            "minimum_internal_energy_j_kg": float(
                run_summary["minimum_internal_energy_J_kg"]
            ),
            "final_normalized_phases": list(
                run_summary["final_normalized_phases"]
            ),
            "final_rho_xv_exact_zero": bool(
                run_summary["final_rho_xv_exact_zero"]
            ),
            "a2_behavioral_regression_tested": False,
            "outcome": "WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_EXECUTION_PASS",
        }
        state_history = _public_state_history(
            case=case,
            states=accepted_states,
            times_s=accepted_times,
        )
        return BackendRunData(
            summary=summary,
            history=_public_history(step_rows_tuple),
            transitions=transitions,
            state_history=state_history,
            warnings=(W2_FULL_HORIZON_WARNING,),
        )
