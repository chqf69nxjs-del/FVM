"""Working Tool W1 adapter to the retained Increment 9M A2 live FVM path.

The module is integration-side by design.  It implements the public
``WorkingToolBackend`` protocol without making the public Working Tool package
import any verification runner, workflow metadata, or authority artifact.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

import u3_b2_a1_increment_9m_a2_live_fvm_composition as a2
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import NumericsConfig, PipeGeometry, TimeConfig
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    make_conserved,
)
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from liquid_gas_transient.working_tool import (
    BackendRunData,
    InitialCondition,
    ModelProfile,
    OutletCondition,
    TransitionRecord,
    WarningSeverity,
    WorkingToolCase,
    WorkingToolWarning,
)


A2_CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
A2_STARTING_STATE_SHA256 = a2.PARENT_STARTING_STATE_SHA256
BACKEND_NAME = "INCREMENT_9M_A2_LIVE_FVM_SMOKE_BACKEND"
BACKEND_SCHEMA = "stage7_u3_b2_a1_working_tool_w1_a2_live_backend_v1"
DEFAULT_SMOKE_ACCEPTED_STEPS = 8
W1_SMOKE_WARNING_CODE = "WORKING_TOOL_W1_SMOKE_SCOPE"
W1_SMOKE_WARNING = WorkingToolWarning(
    code=W1_SMOKE_WARNING_CODE,
    severity=WarningSeverity.WARNING,
    message=(
        "This result exercises only the short Working Tool W1 connection to the "
        "Increment 9M A2 live FVM path. It is not a full 2L/c0 regression, "
        "physical validation, or design-use approval."
    ),
)


class W1CaseScopeError(ValueError):
    """Raised before solver construction for a noncanonical W1 case."""


class W1LiveBackendError(RuntimeError):
    """Raised when the retained A2 live path fails a W1 integration gate."""


def _case_row(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    for row in contract["benchmark_cases"]:
        if str(row["case_id"]) == A2_CASE_ID:
            return row
    raise KeyError(A2_CASE_ID)


def _family_row(contract: Mapping[str, Any], state_id: str) -> Mapping[str, Any]:
    for row in contract["fixed_state_families"]:
        if str(row["state_id"]) == state_id:
            return row
    raise KeyError(state_id)


def _locked_temperature_k(
    family: Mapping[str, Any],
    provider: CoolPropB2StateProvider,
) -> float:
    if "temperature_K" in family:
        return float(family["temperature_K"])
    pressure = float(family["pressure_pa"])
    return float(
        provider.saturation_temperature(pressure) - float(family["subcooling_K"])
    )


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(U, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _require_close(
    name: str,
    actual: float,
    expected: float,
    *,
    absolute_tolerance: float = 0.0,
) -> None:
    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=0.0,
        abs_tol=float(absolute_tolerance),
    ):
        raise W1CaseScopeError(
            f"W1_NONCANONICAL_CASE: {name}={actual!r} does not match "
            f"locked value {expected!r}"
        )


def build_canonical_w1_case(
    contract_path: str | Path,
    *,
    case_id: str = "W1-A2-LIVE-CANONICAL",
) -> WorkingToolCase:
    """Build the normal-user case that exactly represents the locked A2 case."""

    contract = load_contract(contract_path)
    case = _case_row(contract)
    state_id = str(case["state_id"])
    family = _family_row(contract, state_id)
    geometry = contract["geometry"]
    provider = CoolPropB2StateProvider()
    temperature_k = _locked_temperature_k(family, provider)
    velocity_m_s = float(family["initial_velocity_m_s"])
    static = provider.static_state_from_pT(
        float(family["pressure_pa"]),
        temperature_k,
        velocity_m_s,
    )
    length_m = float(geometry["pipe_length_m"])
    target_time_s = float(2.0 * length_m / static.sound_speed_m_s)
    back_pressure_pa = float(
        case.get("back_pressure_override_pa", family["back_pressure_pa"])
    )
    return WorkingToolCase(
        case_id=case_id,
        geometry=PipeGeometry(
            length_m=length_m,
            diameter_m=float(geometry["pipe_diameter_m"]),
            roughness_m=float(geometry["roughness_m"]),
        ),
        numerics=NumericsConfig(
            n_cells=int(geometry["baseline_cells"]),
            n_ghost=int(geometry["ghost_cells_each_side"]),
            cfl=float(geometry["baseline_cfl"]),
        ),
        time=TimeConfig(
            t_end_s=target_time_s,
            max_steps=max(int(geometry["baseline_cells"]) * 1000, 10_000),
        ),
        initial=InitialCondition(
            pressure_pa=float(family["pressure_pa"]),
            temperature_k=temperature_k,
            velocity_m_s=velocity_m_s,
        ),
        outlet=OutletCondition(
            back_pressure_pa=back_pressure_pa,
            opening_fraction=float(case["opening_fraction"]),
            discharge_coefficient=float(case["discharge_coefficient"]),
        ),
    )


class A2LiveWorkingToolBackend:
    """Canonical short-run implementation of the W0 backend protocol."""

    def __init__(
        self,
        *,
        contract_path: str | Path,
        b1_contract_path: str | Path,
        smoke_accepted_steps: int = DEFAULT_SMOKE_ACCEPTED_STEPS,
    ) -> None:
        if isinstance(smoke_accepted_steps, bool) or int(smoke_accepted_steps) <= 0:
            raise ValueError("smoke_accepted_steps must be a positive integer")
        self.contract_path = Path(contract_path)
        self.b1_contract_path = Path(b1_contract_path)
        self.contract = load_contract(self.contract_path)
        self.b1_contract = load_b1_contract(self.b1_contract_path)
        self.smoke_accepted_steps = int(smoke_accepted_steps)
        self.solver_instances_created = 0

    def _validate_case(
        self,
        case: WorkingToolCase,
        provider: CoolPropB2StateProvider,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], float]:
        if not isinstance(case, WorkingToolCase):
            raise TypeError("case must be WorkingToolCase")
        if case.fluid != "CO2":
            raise W1CaseScopeError("W1_NONCANONICAL_CASE: fluid must be CO2")
        if (
            case.model_profile
            is not ModelProfile.STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0
        ):
            raise W1CaseScopeError(
                "W1_NONCANONICAL_CASE: unsupported model profile"
            )

        locked_case = _case_row(self.contract)
        state_id = str(locked_case["state_id"])
        family = _family_row(self.contract, state_id)
        geometry = self.contract["geometry"]
        locked_temperature = _locked_temperature_k(family, provider)
        locked_static = provider.static_state_from_pT(
            float(family["pressure_pa"]),
            locked_temperature,
            float(family["initial_velocity_m_s"]),
        )
        locked_target_time = float(
            2.0 * float(geometry["pipe_length_m"])
            / locked_static.sound_speed_m_s
        )
        locked_back_pressure = float(
            locked_case.get(
                "back_pressure_override_pa",
                family["back_pressure_pa"],
            )
        )

        _require_close(
            "geometry.length_m",
            case.geometry.length_m,
            float(geometry["pipe_length_m"]),
        )
        _require_close(
            "geometry.diameter_m",
            case.geometry.diameter_m,
            float(geometry["pipe_diameter_m"]),
        )
        _require_close(
            "geometry.roughness_m",
            case.geometry.roughness_m,
            float(geometry["roughness_m"]),
        )
        _require_close(
            "geometry.area_m2",
            case.geometry.area_m2,
            float(geometry["pipe_area_m2"]),
            absolute_tolerance=1.0e-15,
        )
        if case.numerics.n_cells != int(geometry["baseline_cells"]):
            raise W1CaseScopeError(
                "W1_NONCANONICAL_CASE: n_cells does not match locked baseline"
            )
        if case.numerics.n_ghost != int(geometry["ghost_cells_each_side"]):
            raise W1CaseScopeError(
                "W1_NONCANONICAL_CASE: n_ghost does not match locked baseline"
            )
        _require_close(
            "numerics.cfl",
            case.numerics.cfl,
            float(geometry["baseline_cfl"]),
        )
        _require_close(
            "initial.pressure_pa",
            case.initial.pressure_pa,
            float(family["pressure_pa"]),
        )
        _require_close(
            "initial.temperature_k",
            case.initial.temperature_k,
            locked_temperature,
            absolute_tolerance=8.0 * float(np.spacing(locked_temperature)),
        )
        _require_close(
            "initial.velocity_m_s",
            case.initial.velocity_m_s,
            float(family["initial_velocity_m_s"]),
        )
        _require_close(
            "outlet.back_pressure_pa",
            case.outlet.back_pressure_pa,
            locked_back_pressure,
        )
        _require_close(
            "outlet.opening_fraction",
            case.outlet.opening_fraction,
            float(locked_case["opening_fraction"]),
        )
        _require_close(
            "outlet.discharge_coefficient",
            case.outlet.discharge_coefficient,
            float(locked_case["discharge_coefficient"]),
        )
        _require_close(
            "time.t_end_s",
            case.time.t_end_s,
            locked_target_time,
            absolute_tolerance=8.0 * float(np.spacing(locked_target_time)),
        )
        if case.time.max_steps < self.smoke_accepted_steps:
            raise W1CaseScopeError(
                "W1_NONCANONICAL_CASE: max_steps is below the smoke-step target"
            )
        return locked_case, family, locked_target_time

    @staticmethod
    def _snapshot(
        solver: FvmSolver,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        primitive = solver.primitive()
        return (
            np.asarray(solver.U, dtype=float).copy(),
            np.asarray(primitive.rho, dtype=float).copy(),
            np.asarray(primitive.u, dtype=float).copy(),
            np.asarray(primitive.p, dtype=float).copy(),
            np.asarray(primitive.T, dtype=float).copy(),
        )

    def run_case(self, case: WorkingToolCase) -> BackendRunData:
        provider = CoolPropB2StateProvider()
        locked_case, family, locked_target_time = self._validate_case(case, provider)
        allowed_phases = {
            normalize_phase(str(value))
            for value in family["allowed_normalized_phases"]
        }

        static = provider.static_state_from_pT(
            case.initial.pressure_pa,
            case.initial.temperature_k,
            case.initial.velocity_m_s,
        )
        U_initial = make_conserved(
            np.full(case.numerics.n_cells, static.density_kg_m3),
            np.full(case.numerics.n_cells, case.initial.velocity_m_s),
            np.full(case.numerics.n_cells, static.internal_energy_J_kg),
            np.zeros(case.numerics.n_cells),
        )
        starting_state_sha256 = _state_sha256(U_initial)
        if starting_state_sha256 != A2_STARTING_STATE_SHA256:
            raise W1LiveBackendError(
                "W1_STARTING_STATE_SHA_MISMATCH: normal case input did not "
                "reproduce the retained A2 initial state"
            )

        grid = UniformGrid(case.geometry, case.numerics.n_cells)
        a2.ModelManagedLiveFvmHook.last_instance = None
        hook = a2.ModelManagedLiveFvmHook(
            contract=self.contract,
            b1_contract=self.b1_contract,
            case_id=A2_CASE_ID,
            provider=provider,
        )
        solver = FvmSolver(
            grid=grid,
            eos=CoolPropSinglePhaseEOS(
                provider,
                boundary_temperature_K=case.initial.temperature_k,
            ),
            U=np.asarray(U_initial, dtype=float),
            cfl=case.numerics.cfl,
            n_ghost=case.numerics.n_ghost,
            left_boundary=ReflectiveBoundary(),
            right_boundary=TransmissiveBoundary(),
            right_external_face_flux_override=hook,
            enable_boundary_budget=True,
            enable_phase_budget=False,
            enable_energy_budget=False,
            enable_interface_budget=False,
        )
        self.solver_instances_created += 1

        times = [float(solver.t)]
        conserved_snapshots: list[np.ndarray] = []
        rho_snapshots: list[np.ndarray] = []
        velocity_snapshots: list[np.ndarray] = []
        pressure_snapshots: list[np.ndarray] = []
        temperature_snapshots: list[np.ndarray] = []
        initial_snapshot = self._snapshot(solver)
        conserved_snapshots.append(initial_snapshot[0])
        rho_snapshots.append(initial_snapshot[1])
        velocity_snapshots.append(initial_snapshot[2])
        pressure_snapshots.append(initial_snapshot[3])
        temperature_snapshots.append(initial_snapshot[4])
        history: list[dict[str, Any]] = []

        for _ in range(self.smoke_accepted_steps):
            requested_step = int(solver.step_count + 1)
            hook.requested_solver_step = requested_step
            restoration_before = len(hook.model_manager_context_restoration_rows)
            candidate_dt = float(solver.compute_dt(case.time.t_end_s))
            context = hook.root_context
            if not isinstance(context, dict):
                raise W1LiveBackendError(
                    "W1_A2_CONTEXT_MISSING: compute_dt did not prepare a live context"
                )
            right_flux = np.asarray(hook.flux, dtype=float).copy()
            accepted_dt = float(solver.step(candidate_dt))
            hook.accept_current_step()
            restoration_after = len(hook.model_manager_context_restoration_rows)
            if restoration_after != restoration_before + 1:
                raise W1LiveBackendError(
                    "W1_CONTEXT_RESTORATION_COUNT_MISMATCH"
                )
            if int(solver.step_count) != requested_step:
                raise W1LiveBackendError("W1_SOLVER_STEP_COMMIT_MISMATCH")

            primitive = solver.primitive()
            history.append(
                {
                    "step": int(solver.step_count),
                    "time_s": float(solver.t),
                    "accepted_dt_s": accepted_dt,
                    "public_boundary_state": str(
                        context["public_boundary_state"]
                    ),
                    "outward_internal_model": str(
                        context["outward_internal_model"]
                    ),
                    "branch_classification": str(
                        context["branch_classification"]
                    ),
                    "manager_transition_count": len(
                        hook.model_manager.transition_history
                    ),
                    "context_restoration_count": restoration_after,
                    "right_mass_flux_kg_m2_s": float(right_flux[IDX_RHO]),
                    "right_momentum_flux_pa": float(right_flux[IDX_MOM]),
                    "right_energy_flux_w_m2": float(right_flux[IDX_RHOE]),
                    "right_vapor_flux_kg_m2_s": float(right_flux[IDX_RHO_XV]),
                    "p_min_pa": float(np.min(primitive.p)),
                    "p_max_pa": float(np.max(primitive.p)),
                    "rho_min_kg_m3": float(np.min(primitive.rho)),
                    "rho_max_kg_m3": float(np.max(primitive.rho)),
                    "u_min_m_s": float(np.min(primitive.u)),
                    "u_max_m_s": float(np.max(primitive.u)),
                }
            )
            snapshot = self._snapshot(solver)
            times.append(float(solver.t))
            conserved_snapshots.append(snapshot[0])
            rho_snapshots.append(snapshot[1])
            velocity_snapshots.append(snapshot[2])
            pressure_snapshots.append(snapshot[3])
            temperature_snapshots.append(snapshot[4])

        restoration_rows = list(hook.model_manager_context_restoration_rows)
        restoration_gate = bool(
            len(restoration_rows) == self.smoke_accepted_steps
            and all(bool(row["restoration_gate_passed"]) for row in restoration_rows)
            and all(
                row["context_restored_without_root_reconstruction"] is True
                and row["flux_modified_by_manager"] is False
                for row in restoration_rows
            )
        )
        manager_transition_count = len(hook.model_manager.transition_history)
        selection_history_count = len(hook.model_manager.selection_history)
        if manager_transition_count != 0:
            raise W1LiveBackendError(
                "W1_UNEXPECTED_EARLY_MANAGER_TRANSITION"
            )
        if selection_history_count != 1:
            raise W1LiveBackendError(
                "W1_UNEXPECTED_MANAGER_SELECTION_HISTORY"
            )
        if not restoration_gate:
            raise W1LiveBackendError(
                "W1_CONTEXT_RESTORATION_GATE_FAILURE"
            )

        U_final = np.asarray(solver.U, dtype=float)
        rho = np.asarray(U_final[:, IDX_RHO], dtype=float)
        velocity = np.asarray(U_final[:, IDX_MOM] / rho, dtype=float)
        internal = np.asarray(
            U_final[:, IDX_RHOE] / rho - 0.5 * velocity * velocity,
            dtype=float,
        )
        phases = [
            normalize_phase(
                str(provider.reconstruct_from_conserved(row).static.phase)
            )
            for row in U_final
        ]
        physical_gate = bool(
            np.all(np.isfinite(U_final))
            and np.all(rho > 0.0)
            and np.all(np.isfinite(internal))
            and np.all(internal > 0.0)
            and all(phase in allowed_phases for phase in phases)
            and np.all(U_final[:, IDX_RHO_XV] == 0.0)
        )
        if not physical_gate:
            raise W1LiveBackendError("W1_SHORT_RUN_PHYSICAL_GATE_FAILURE")

        transitions = tuple(
            TransitionRecord(
                axis=event.axis.value,
                from_state=event.from_state,
                to_state=event.to_state,
                trigger_classification=event.trigger_classification,
                solver_time_s=event.solver_time_s,
                observed_solver_step=(
                    0
                    if event.observed_solver_step is None
                    else event.observed_solver_step
                ),
                absolute_step_number_trigger_used=False,
            )
            for event in hook.model_manager.transition_history
        )
        summary = {
            "backend_schema": BACKEND_SCHEMA,
            "backend_name": BACKEND_NAME,
            "a2_live_path_connected": True,
            "a2_model_managed_live_hook_used": True,
            "canonical_locked_case_id": A2_CASE_ID,
            "smoke_scope": True,
            "smoke_target_accepted_steps": self.smoke_accepted_steps,
            "accepted_steps": int(solver.step_count),
            "final_solver_step": int(solver.step_count),
            "final_solver_time_s": float(solver.t),
            "case_target_time_s": float(locked_target_time),
            "target_horizon_reached": bool(solver.t >= locked_target_time),
            "starting_state_sha256": starting_state_sha256,
            "final_state_sha256": _state_sha256(U_final),
            "starting_state_matches_a2": True,
            "one_fvm_solver_instance": self.solver_instances_created == 1,
            "model_manager_profile": hook.model_manager.profile_name,
            "manager_transition_count": manager_transition_count,
            "manager_selection_history_count": selection_history_count,
            "successful_context_restoration_count": len(restoration_rows),
            "context_restoration_gate_passed": restoration_gate,
            "context_restored_without_root_reconstruction": restoration_gate,
            "physics_flux_modified_by_manager": False,
            "checkpoint_state_used": False,
            "absolute_step_number_transition_condition_used": False,
            "final_all_conserved_finite": bool(np.all(np.isfinite(U_final))),
            "final_minimum_density_kg_m3": float(np.min(rho)),
            "final_minimum_internal_energy_j_kg": float(np.min(internal)),
            "final_normalized_phases": sorted(set(phases)),
            "final_rho_xv_exact_zero": bool(
                np.all(U_final[:, IDX_RHO_XV] == 0.0)
            ),
            "short_run_physical_gate_passed": physical_gate,
            "full_two_l_over_c0_regression_tested": False,
            "outcome": "WORKING_TOOL_W1_A2_LIVE_BACKEND_SMOKE_PASS",
        }
        state_history = {
            "time_s": np.asarray(times, dtype=float),
            "x_m": np.asarray(grid.cell_centers, dtype=float),
            "conserved": np.stack(conserved_snapshots, axis=0),
            "rho_kg_m3": np.stack(rho_snapshots, axis=0),
            "velocity_m_s": np.stack(velocity_snapshots, axis=0),
            "pressure_pa": np.stack(pressure_snapshots, axis=0),
            "temperature_k": np.stack(temperature_snapshots, axis=0),
        }
        return BackendRunData(
            summary=summary,
            history=tuple(history),
            transitions=transitions,
            state_history=state_history,
            warnings=(W1_SMOKE_WARNING,),
        )
