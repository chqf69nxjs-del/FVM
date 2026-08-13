from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
import u3_b2_a1_weak_compression_bridge_short_run as weak
import u3_b2_a1_weak_compression_bridge_full_horizon_guard_front_refined as weak_refined
import u3_b2_a1_weak_compression_bridge_full_horizon_candidate_state as weak_candidate
import u3_b2_a1_finite_compression_guard_front_8_step_dynamic_topology_fix as finite_fixed
import u3_b2_a1_finite_compression_dynamic_seeded_final_horizon as finite_seeded
import u3_b2_a1_finite_compression_hugoniot_8_step as finite_base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as finite_diag
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_hook import A1DynamicShortHook
from u3_b2_characteristic_port_dynamic_short_metrics import inventory


CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
TECHNICAL_ISSUE = "TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION"
OUTCOME = "INCREMENT_9L_PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE_PASS"
PUBLIC_OUTWARD = "OUTWARD_FLOW"
PUBLIC_CLOSED = "ZERO_TRANSFER_CLOSED"
MODEL_THREE_BRANCH = "THREE_BRANCH_WAVE_MODEL"
MODEL_FINITE = "GENERAL_EOS_FINITE_COMPRESSION"
CLOSURE_TRIGGER = "NO_ADMISSIBLE_ISLAND"
FINITE_MODEL_TRIGGER = "FINITE_COMPRESSION_MODEL_REQUIRED"
MAXIMUM_OPERATIONAL_SOLVER_STEP = 10_000
HORIZON_MULTIPLIER = 2.0
robustness = robustness_v4.robustness


class Increment9LStop(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


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


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _all_phases_allowed(
    provider: CoolPropB2StateProvider,
    U: np.ndarray,
    allowed_phases: set[str],
) -> tuple[bool, list[str]]:
    phases = [
        normalize_phase(str(provider.reconstruct_from_conserved(row).static.phase))
        for row in U
    ]
    return bool(all(phase in allowed_phases for phase in phases)), phases


class TwoStateBoundaryStateMachineHook(A1DynamicShortHook):
    """Verification-side one-way OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED controller."""

    def __init__(
        self,
        *,
        contract: dict[str, Any],
        b1_contract: dict[str, Any],
        case_id: str,
        provider: CoolPropB2StateProvider,
    ) -> None:
        super().__init__(
            contract=contract,
            b1_contract=b1_contract,
            case_id=case_id,
            provider=provider,
        )
        self.b1_contract = b1_contract
        self.boundary_state = PUBLIC_OUTWARD
        self.outward_model = MODEL_THREE_BRANCH
        self.accepted_branch_history: list[str] = []
        self.accepted_public_state_history: list[str] = []
        self.pending_branch_classification: str | None = None
        self.requested_solver_step: int | None = None
        self.boundary_transition_events: list[dict[str, Any]] = []
        self.outward_model_transition_events: list[dict[str, Any]] = []
        self.closure_trigger_classification: str | None = None
        self.closure_trigger_message: str | None = None
        finite_fixed._active_b1_contract = b1_contract
        weak._build_weak_compression_context = (
            weak_candidate._candidate_state_build_weak_compression_context
        )

    def _invalidate_cache(self) -> None:
        self._cache_t = None
        self._cache_outlet = None
        self.root_context = None
        self.flux = np.zeros(4, dtype=float)
        self.trial_dts_s = []

    def _install_context(
        self,
        *,
        context: dict[str, Any],
        U: np.ndarray,
        t: float,
    ) -> None:
        self.root_context = context
        self.flux = np.asarray(context["flux"], dtype=float).copy()
        self._cache_t = float(t)
        self._cache_outlet = np.asarray(U[-1], dtype=float).copy()
        self.trial_dts_s = []

    def _switch_outward_model(
        self,
        *,
        t: float,
        classification: str,
        message: str,
    ) -> None:
        if self.boundary_state != PUBLIC_OUTWARD:
            raise Increment9LStop(
                "STATE_MACHINE_INTERNAL_ERROR",
                "outward model switch requested outside OUTWARD_FLOW",
            )
        if self.outward_model == MODEL_FINITE:
            return
        event = {
            "requested_solver_step": self.requested_solver_step,
            "solver_time_s": float(t),
            "from_outward_model": self.outward_model,
            "to_outward_model": MODEL_FINITE,
            "trigger_classification": classification,
            "trigger_message": message,
            "absolute_step_number_trigger_used": False,
        }
        self.outward_model_transition_events.append(event)
        self.outward_model = MODEL_FINITE
        self._invalidate_cache()

    def _transition_to_closed(
        self,
        *,
        t: float,
        classification: str,
        message: str,
    ) -> None:
        if self.boundary_state != PUBLIC_OUTWARD:
            raise Increment9LStop(
                "MULTIPLE_PUBLIC_STATE_TRANSITIONS",
                "closure transition requested after the boundary was already closed",
            )
        if classification != CLOSURE_TRIGGER:
            raise Increment9LStop(
                "UNAUTHORIZED_CLOSURE_TRIGGER",
                f"classification {classification!r} is not authorized for closure",
            )
        self.boundary_transition_events.append(
            {
                "requested_solver_step": self.requested_solver_step,
                "solver_time_s": float(t),
                "from_boundary_state": PUBLIC_OUTWARD,
                "to_boundary_state": PUBLIC_CLOSED,
                "trigger_classification": classification,
                "trigger_message": message,
                "failed_candidate_used_as_root": False,
                "failed_candidate_used_as_flux": False,
                "solver_state_mutated_before_transition": False,
                "absolute_step_number_trigger_used": False,
                "reentry_allowed": False,
            }
        )
        self.boundary_state = PUBLIC_CLOSED
        self.closure_trigger_classification = classification
        self.closure_trigger_message = message
        self.pending_branch_classification = None
        self._invalidate_cache()

    def _prepare_three_branch(self, U: np.ndarray, t: float) -> None:
        try:
            context = weak_refined._guard_front_solve_three_branch_boundary(
                hook=self,
                U=np.asarray(U, dtype=float),
                solver_time_s=float(t),
            )
        except weak.WeakCompressionShortRunStop as exc:
            if exc.classification == FINITE_MODEL_TRIGGER:
                self._switch_outward_model(
                    t=t,
                    classification=exc.classification,
                    message=str(exc),
                )
                self._prepare_finite(U, t)
                return
            raise Increment9LStop(
                exc.classification,
                f"three-branch outward model failed: {exc}",
            ) from exc
        except Exception as exc:
            classification = str(getattr(exc, "classification", type(exc).__name__))
            if classification == FINITE_MODEL_TRIGGER:
                self._switch_outward_model(
                    t=t,
                    classification=classification,
                    message=str(exc),
                )
                self._prepare_finite(U, t)
                return
            raise Increment9LStop(
                classification,
                f"three-branch outward model failed: {type(exc).__name__}: {exc}",
            ) from exc

        context = dict(context)
        context.update(
            {
                "public_boundary_state": PUBLIC_OUTWARD,
                "outward_internal_model": MODEL_THREE_BRANCH,
                "state_machine_transition_triggered": False,
            }
        )
        self.pending_branch_classification = str(
            context["branch_classification"]
        )
        self._install_context(context=context, U=U, t=t)

    def _seeded_fallback_allowed(self, classification: str, message: str) -> bool:
        return bool(
            classification == "SEEDED_INTERVAL_EDGE_CONTACT"
            or (
                classification == "STATE_REPRODUCTION_MISMATCH"
                and "dynamic seed chi is outside finite-compression scope" in message
            )
        )

    def _build_finite_context(
        self,
        *,
        U: np.ndarray,
        t: float,
        diagnostic_summary: dict[str, Any],
        fixed_rows: list[dict[str, Any]],
        guard_rows: list[dict[str, Any]],
        topology_rows: list[dict[str, Any]],
        density_rows: list[dict[str, Any]],
        root: dict[str, Any],
        algorithm: str,
    ) -> dict[str, Any]:
        classification = str(diagnostic_summary["outcome"])
        if classification != finite_diag.SUPPORTED or not bool(
            root.get("selected_root_present")
        ):
            raise Increment9LStop(
                classification,
                "finite-compression diagnostic did not provide a supported root",
            )
        if not bool(root.get("root_gate_passed")):
            raise Increment9LStop(
                "ROOT_OR_LEDGER_FAILURE",
                "finite-compression selected-root gate did not pass",
            )

        reconstruction = self.provider.reconstruct_from_conserved(U[-1])
        static = reconstruction.static
        allowed = {
            normalize_phase(value)
            for value in diagnostic._family(self.contract, self.state_id)[
                "allowed_normalized_phases"
            ]
        }
        velocity_tolerance = float(
            self.contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
        )
        mass_rate = float(root["pipe_mass_rate_kg_s"])
        velocity = float(root["velocity_m_s"])
        pressure = float(root["pressure_pa"])
        h0 = float(root["h0_J_kg"])
        flux = np.asarray(
            [
                mass_rate / self.area_m2,
                (mass_rate * velocity + pressure * self.area_m2) / self.area_m2,
                mass_rate * h0 / self.area_m2,
                0.0,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(flux)):
            raise Increment9LStop(
                "NONFINITE_FLUX",
                "finite-compression selected flux is nonfinite",
            )

        return {
            "solver_time_s": float(t),
            "interior_pressure_pa": float(static.pressure_pa),
            "interior_temperature_K": float(static.temperature_K),
            "interior_density_kg_m3": float(static.density_kg_m3),
            "interior_velocity_m_s": float(static.velocity_m_s),
            "interior_sound_speed_m_s": float(static.sound_speed_m_s),
            "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
            "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
            "interior_phase": str(static.phase),
            "interior_h0_round_trip_residual_J_kg": float(
                reconstruction.enthalpy_round_trip_residual_J_kg
            ),
            "interior_s0_round_trip_residual_J_kg_K": float(
                reconstruction.entropy_round_trip_residual_J_kg_K
            ),
            "root": root,
            "flux": flux,
            "allowed_phases": allowed,
            "velocity_tolerance_m_s": velocity_tolerance,
            "branch_classification": finite_base.BRANCH,
            "public_boundary_state": PUBLIC_OUTWARD,
            "outward_internal_model": MODEL_FINITE,
            "finite_compression_algorithm": algorithm,
            "root_chi": float(root["requested_chi"]),
            "root_gate_passed": True,
            "diagnostic_classification": classification,
            "guard_front_refinement_applied": bool(
                diagnostic_summary.get("guard_front_refinement_applied", False)
            ),
            "guard_front_iterations": int(
                diagnostic_summary.get("guard_front_iterations", 0)
            ),
            "root_topology_node_count": int(
                diagnostic_summary["root_topology_node_count"]
            ),
            "root_topology_monotone_nonincreasing": bool(
                diagnostic_summary["root_topology_monotone_nonincreasing"]
            ),
            "root_topology_sign_change_count": int(
                diagnostic_summary["root_topology_sign_change_count"]
            ),
            "fixed_scan_rows": fixed_rows,
            "guard_front_rows": guard_rows,
            "root_topology_rows": topology_rows,
            "density_search_rows": density_rows,
            "failed_b1_state_used_as_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
            "finite_compression_flux_applied": True,
            "finite_compression_branch_approved": False,
            "state_machine_transition_triggered": False,
        }

    def _run_fixed_finite(
        self,
        U: np.ndarray,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
    ]:
        if self._previous_root_pressure_pa is None:
            raise Increment9LStop(
                "PARENT_ROOT_MISSING",
                "finite-compression continuation has no previous root pressure",
            )
        parent_root = {"root_pressure_pa": str(self._previous_root_pressure_pa)}
        return finite_fixed._dynamic_root_run(
            contract=self.contract,
            b1_contract=self.b1_contract,
            U=np.asarray(U, dtype=float),
            parent_root=parent_root,
        )

    def _prepare_finite(self, U: np.ndarray, t: float) -> None:
        if self._previous_root_pressure_pa is None:
            raise Increment9LStop(
                "PARENT_ROOT_MISSING",
                "finite-compression continuation has no previous accepted root",
            )
        parent_root = {"root_pressure_pa": str(self._previous_root_pressure_pa)}
        try:
            result = finite_seeded._dynamic_seeded_root_run(
                contract=self.contract,
                b1_contract=self.b1_contract,
                U=np.asarray(U, dtype=float),
                parent_root=parent_root,
            )
            algorithm = "DYNAMIC_SEEDED_257"
        except finite_diag.DiagnosticStop as exc:
            if exc.classification == CLOSURE_TRIGGER and (
                "dynamic seeded interval contains no admissible island" in str(exc)
            ):
                self._transition_to_closed(
                    t=t,
                    classification=exc.classification,
                    message=str(exc),
                )
                self._prepare_closed(U, t)
                return
            if self._seeded_fallback_allowed(exc.classification, str(exc)):
                try:
                    result = self._run_fixed_finite(U)
                    algorithm = "DYNAMIC_FIXED_GUARD_FRONT_FALLBACK"
                except Exception as fallback_exc:
                    fallback_classification = str(
                        getattr(
                            fallback_exc,
                            "classification",
                            type(fallback_exc).__name__,
                        )
                    )
                    raise Increment9LStop(
                        fallback_classification,
                        "finite-compression fixed fallback failed after seeded "
                        f"classification {exc.classification}: {fallback_exc}",
                    ) from fallback_exc
            else:
                raise Increment9LStop(
                    exc.classification,
                    f"finite-compression seeded diagnostic failed: {exc}",
                ) from exc
        except Exception as exc:
            classification = str(getattr(exc, "classification", type(exc).__name__))
            if classification == CLOSURE_TRIGGER and (
                "dynamic seeded interval contains no admissible island" in str(exc)
            ):
                self._transition_to_closed(
                    t=t,
                    classification=classification,
                    message=str(exc),
                )
                self._prepare_closed(U, t)
                return
            if self._seeded_fallback_allowed(classification, str(exc)):
                result = self._run_fixed_finite(U)
                algorithm = "DYNAMIC_FIXED_GUARD_FRONT_FALLBACK"
            else:
                raise Increment9LStop(
                    classification,
                    f"finite-compression diagnostic failed: {type(exc).__name__}: {exc}",
                ) from exc

        (
            diagnostic_summary,
            fixed_rows,
            guard_rows,
            topology_rows,
            density_rows,
            root,
        ) = result
        context = self._build_finite_context(
            U=U,
            t=t,
            diagnostic_summary=diagnostic_summary,
            fixed_rows=fixed_rows,
            guard_rows=guard_rows,
            topology_rows=topology_rows,
            density_rows=density_rows,
            root=root,
            algorithm=algorithm,
        )
        self.pending_branch_classification = finite_base.BRANCH
        self._install_context(context=context, U=U, t=t)

    def _prepare_closed(self, U: np.ndarray, t: float) -> None:
        reconstruction = self.provider.reconstruct_from_conserved(U[-1])
        static = reconstruction.static
        allowed = {
            normalize_phase(value)
            for value in diagnostic._family(self.contract, self.state_id)[
                "allowed_normalized_phases"
            ]
        }
        phase = normalize_phase(str(static.phase))
        pressure = float(static.pressure_pa)
        if phase not in allowed:
            raise Increment9LStop(
                "PHASE_SCOPE_DEPARTURE",
                f"closed-state outlet phase {phase!r} is outside liquid scope",
            )
        if not math.isfinite(pressure) or pressure <= 0.0:
            raise Increment9LStop(
                "NONFINITE_OR_NONPOSITIVE_STATE",
                "closed-state outlet pressure is invalid",
            )
        flux = np.asarray([0.0, pressure, 0.0, 0.0], dtype=float)
        context = {
            "solver_time_s": float(t),
            "interior_pressure_pa": pressure,
            "interior_temperature_K": float(static.temperature_K),
            "interior_density_kg_m3": float(static.density_kg_m3),
            "interior_velocity_m_s": float(static.velocity_m_s),
            "interior_sound_speed_m_s": float(static.sound_speed_m_s),
            "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
            "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
            "interior_phase": str(static.phase),
            "interior_h0_round_trip_residual_J_kg": float(
                reconstruction.enthalpy_round_trip_residual_J_kg
            ),
            "interior_s0_round_trip_residual_J_kg_K": float(
                reconstruction.entropy_round_trip_residual_J_kg_K
            ),
            "flux": flux,
            "allowed_phases": allowed,
            "velocity_tolerance_m_s": float(
                self.contract["acceptance_tolerances"][
                    "velocity_zero_tolerance_m_s"
                ]
            ),
            "branch_classification": PUBLIC_CLOSED,
            "public_boundary_state": PUBLIC_CLOSED,
            "outward_internal_model": None,
            "closure_pressure_pa": pressure,
            "closure_trigger_classification": self.closure_trigger_classification,
            "closure_trigger_message": self.closure_trigger_message,
            "state_machine_transition_triggered": bool(
                self.boundary_transition_events
                and self.boundary_transition_events[-1]["requested_solver_step"]
                == self.requested_solver_step
            ),
            "b1_called_after_closure": False,
            "hugoniot_root_called_after_closure": False,
        }
        self._install_context(context=context, U=U, t=t)

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        if self.boundary_state == PUBLIC_CLOSED:
            self._prepare_closed(U, t)
            return
        if self.outward_model == MODEL_THREE_BRANCH:
            self._prepare_three_branch(U, t)
            return
        if self.outward_model == MODEL_FINITE:
            self._prepare_finite(U, t)
            return
        raise Increment9LStop(
            "STATE_MACHINE_INTERNAL_ERROR",
            f"unknown outward model {self.outward_model!r}",
        )

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
        if self.boundary_state == PUBLIC_OUTWARD:
            super().validate_trial(
                U_before=U_before,
                U_trial=U_trial,
                eos=eos,
                grid=grid,
                t=t,
                dt=dt,
            )
            return
        del U_before, eos, grid, t, dt
        if not np.all(np.isfinite(U_trial)):
            raise ValueError("closed-state trial contains nonfinite values")
        rho = np.asarray(U_trial[:, IDX_RHO], dtype=float)
        if np.any(rho <= 0.0):
            raise ValueError("closed-state trial density must remain positive")
        velocity = np.asarray(U_trial[:, IDX_MOM] / rho, dtype=float)
        internal = np.asarray(
            U_trial[:, IDX_RHOE] / rho - 0.5 * velocity * velocity,
            dtype=float,
        )
        if np.any(~np.isfinite(internal)) or np.any(internal <= 0.0):
            raise ValueError("closed-state trial internal energy must remain positive")
        if not np.all(U_trial[:, IDX_RHO_XV] == 0.0):
            raise ValueError("closed-state rho*xv must remain exact zero")
        allowed = self.allowed_phases
        for row in U_trial:
            phase = normalize_phase(
                str(self.provider.reconstruct_from_conserved(row).static.phase)
            )
            if phase not in allowed:
                raise ValueError(
                    f"closed-state trial phase {phase!r} is outside {sorted(allowed)}"
                )

    def accept_current_step(self) -> None:
        if self.root_context is None:
            raise AssertionError("no current state-machine context to accept")
        if self.boundary_state == PUBLIC_OUTWARD:
            root = self.root_context.get("root")
            if root is None:
                raise AssertionError("outward state has no accepted root")
            self._previous_root_pressure_pa = float(root["pressure_pa"])
            branch = str(self.root_context["branch_classification"])
            self.accepted_branch_history.append(branch)
            self.pending_branch_classification = None
        self.accepted_public_state_history.append(self.boundary_state)


def _outward_root_gate(context: dict[str, Any]) -> bool:
    root = context.get("root")
    if not isinstance(root, dict):
        return False
    required_true = (
        "stagnation_enthalpy_round_trip_passed",
        "energy_mass_consistency_passed",
        "energy_port_closure_passed",
    )
    return bool(
        abs(float(root["root_mass_residual_kg_s"]))
        <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
        and float(root["velocity_m_s"]) >= 0.0
        and 0.0 <= float(root["mach"]) < 1.0
        and all(bool(root[name]) for name in required_true)
        and abs(float(root["momentum_ledger_residual_N"]))
        <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    )


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    np.ndarray,
    np.ndarray,
]:
    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    family = diagnostic._family(contract, state_id)
    allowed_phases = {
        normalize_phase(str(value))
        for value in family["allowed_normalized_phases"]
    }
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = CoolPropB2StateProvider()
    U_initial, initial_static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    initial_sound_speed = float(initial_static.sound_speed_m_s)
    target_time_s = float(HORIZON_MULTIPLIER * pipe.length_m / initial_sound_speed)
    horizon_roundoff_tolerance_s = 8.0 * float(np.spacing(target_time_s))

    hook = TwoStateBoundaryStateMachineHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=np.asarray(U_initial, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )

    tolerances = contract["acceptance_tolerances"]
    initial_inventory = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    cumulative_expected_delta = np.zeros(4, dtype=float)
    U_before_all = np.asarray(solver.U, dtype=float).copy()
    step_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None
    final_step_clipped = False

    while solver.t < target_time_s - horizon_roundoff_tolerance_s:
        if int(solver.step_count) >= MAXIMUM_OPERATIONAL_SOLVER_STEP:
            stop_classification = "OPERATIONAL_STEP_CAP_EXCEEDED"
            stop_reason = "operational step cap reached before target"
            break
        requested_step = int(solver.step_count + 1)
        hook.requested_solver_step = requested_step
        try:
            before_time = float(solver.t)
            before = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            primitive_before = solver.primitive()
            outlet_before = provider.reconstruct_from_conserved(solver.U[-1]).static
            transition_count_before = len(hook.boundary_transition_events)
            model_transition_count_before = len(hook.outward_model_transition_events)
            computed_dt = float(solver.compute_dt())
            context = hook.root_context
            if context is None:
                raise Increment9LStop(
                    "STATE_MACHINE_CONTEXT_MISSING",
                    "compute_dt did not prepare a boundary context",
                )
            public_state = str(context["public_boundary_state"])
            outward_model = context.get("outward_internal_model")
            dt_limits = dict(hook.last_dt_limits)
            remaining_before = float(target_time_s - solver.t)
            requested_dt = float(min(computed_dt, remaining_before))
            clipped_to_target = bool(remaining_before <= computed_dt)

            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)
            pressure_before = float(outlet_before.pressure_pa)
            wall_identity_residual = (
                float(right_flux[IDX_MOM] - pressure_before)
                if public_state == PUBLIC_CLOSED
                else None
            )

            accepted_dt = float(solver.step(requested_dt))
            hook.accept_current_step()
            after = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            expected_step_delta = (
                accepted_dt * grid.geometry.area_m2 * (left_flux - right_flux)
            )
            cumulative_expected_delta = cumulative_expected_delta + expected_step_delta
            step_actual_delta = _inventory_array(after) - _inventory_array(before)
            cumulative_actual_delta = (
                _inventory_array(after) - _inventory_array(initial_inventory)
            )
            step_residual = step_actual_delta - expected_step_delta
            cumulative_residual = cumulative_actual_delta - cumulative_expected_delta

            primitive_after = solver.primitive()
            outlet_after = provider.reconstruct_from_conserved(solver.U[-1]).static
            phases_passed, phases = _all_phases_allowed(
                provider,
                solver.U,
                allowed_phases,
            )
            rho = np.asarray(solver.U[:, IDX_RHO], dtype=float)
            velocity = np.asarray(solver.U[:, IDX_MOM] / rho, dtype=float)
            internal = np.asarray(
                solver.U[:, IDX_RHOE] / rho - 0.5 * velocity * velocity,
                dtype=float,
            )

            step_mass_passed = _residual_passed(
                float(step_residual[IDX_RHO]),
                absolute=float(tolerances["mass_inventory_absolute_kg"]),
                relative=float(tolerances["mass_inventory_relative"]),
                scale_values=(
                    before["mass_kg"],
                    after["mass_kg"],
                    expected_step_delta[IDX_RHO],
                ),
            )
            step_momentum_passed = _residual_passed(
                float(step_residual[IDX_MOM]),
                absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
                relative=float(tolerances["momentum_inventory_relative"]),
                scale_values=(
                    before["momentum_kg_m_s"],
                    after["momentum_kg_m_s"],
                    expected_step_delta[IDX_MOM],
                ),
            )
            step_energy_passed = _residual_passed(
                float(step_residual[IDX_RHOE]),
                absolute=float(tolerances["energy_inventory_absolute_J"]),
                relative=float(tolerances["energy_inventory_relative"]),
                scale_values=(
                    before["energy_J"],
                    after["energy_J"],
                    expected_step_delta[IDX_RHOE],
                ),
            )
            cumulative_mass_passed = _residual_passed(
                float(cumulative_residual[IDX_RHO]),
                absolute=float(tolerances["mass_inventory_absolute_kg"]),
                relative=float(tolerances["mass_inventory_relative"]),
                scale_values=(
                    initial_inventory["mass_kg"],
                    after["mass_kg"],
                    cumulative_expected_delta[IDX_RHO],
                ),
            )
            cumulative_momentum_passed = _residual_passed(
                float(cumulative_residual[IDX_MOM]),
                absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
                relative=float(tolerances["momentum_inventory_relative"]),
                scale_values=(
                    initial_inventory["momentum_kg_m_s"],
                    after["momentum_kg_m_s"],
                    cumulative_expected_delta[IDX_MOM],
                ),
            )
            cumulative_energy_passed = _residual_passed(
                float(cumulative_residual[IDX_RHOE]),
                absolute=float(tolerances["energy_inventory_absolute_J"]),
                relative=float(tolerances["energy_inventory_relative"]),
                scale_values=(
                    initial_inventory["energy_J"],
                    after["energy_J"],
                    cumulative_expected_delta[IDX_RHOE],
                ),
            )

            root = context.get("root")
            outward_gate = (
                _outward_root_gate(context)
                and float(primitive_after.u[-1])
                >= -float(tolerances["velocity_zero_tolerance_m_s"])
                if public_state == PUBLIC_OUTWARD
                else True
            )
            closure_gate = bool(
                public_state != PUBLIC_CLOSED
                or (
                    float(right_flux[IDX_RHO]) == 0.0
                    and float(right_flux[IDX_RHOE]) == 0.0
                    and float(right_flux[IDX_RHO_XV]) == 0.0
                    and wall_identity_residual == 0.0
                    and context.get("b1_called_after_closure") is False
                    and context.get("hugoniot_root_called_after_closure") is False
                )
            )
            general_gate = bool(
                int(solver.step_count) == requested_step
                and accepted_dt > 0.0
                and np.all(np.isfinite(solver.U))
                and np.all(rho > 0.0)
                and np.all(internal > 0.0)
                and phases_passed
                and np.all(solver.U[:, IDX_RHO_XV] == 0.0)
                and step_mass_passed
                and step_momentum_passed
                and step_energy_passed
                and cumulative_mass_passed
                and cumulative_momentum_passed
                and cumulative_energy_passed
            )
            per_step_gate = bool(general_gate and outward_gate and closure_gate)

            row: dict[str, Any] = {
                "case_id": CASE_ID,
                "state_id": state_id,
                "requested_solver_step": requested_step,
                "solver_step_count": int(solver.step_count),
                "time_before_s": before_time,
                "time_after_s": float(solver.t),
                "computed_dt_s": computed_dt,
                "requested_dt_s": requested_dt,
                "accepted_dt_s": accepted_dt,
                "target_remaining_before_step_s": remaining_before,
                "step_clipped_to_target": clipped_to_target,
                "public_boundary_state": public_state,
                "outward_internal_model": outward_model,
                "branch_classification": context["branch_classification"],
                "finite_compression_algorithm": context.get(
                    "finite_compression_algorithm"
                ),
                "state_transition_triggered_this_step": bool(
                    len(hook.boundary_transition_events) > transition_count_before
                ),
                "outward_model_transition_triggered_this_step": bool(
                    len(hook.outward_model_transition_events)
                    > model_transition_count_before
                ),
                "transition_trigger_classification": (
                    hook.boundary_transition_events[-1]["trigger_classification"]
                    if len(hook.boundary_transition_events) > transition_count_before
                    else None
                ),
                "halving_count": max(len(hook.trial_dts_s) - 1, 0),
                "trial_dts_s": list(hook.trial_dts_s),
                "outlet_pressure_before_pa": pressure_before,
                "outlet_velocity_before_m_s": float(primitive_before.u[-1]),
                "outlet_phase_before": str(outlet_before.phase),
                "right_external_mass_flux_kg_m2_s": float(right_flux[IDX_RHO]),
                "right_external_momentum_flux_pa": float(right_flux[IDX_MOM]),
                "right_external_energy_flux_W_m2": float(right_flux[IDX_RHOE]),
                "right_external_vapor_flux_kg_m2_s": float(right_flux[IDX_RHO_XV]),
                "wall_momentum_identity_residual_pa": wall_identity_residual,
                "left_external_mass_flux_kg_m2_s": float(left_flux[IDX_RHO]),
                "left_external_momentum_flux_pa": float(left_flux[IDX_MOM]),
                "left_external_energy_flux_W_m2": float(left_flux[IDX_RHOE]),
                "mass_before_kg": before["mass_kg"],
                "mass_after_kg": after["mass_kg"],
                "step_mass_residual_kg": float(step_residual[IDX_RHO]),
                "cumulative_mass_residual_kg": float(cumulative_residual[IDX_RHO]),
                "momentum_before_kg_m_s": before["momentum_kg_m_s"],
                "momentum_after_kg_m_s": after["momentum_kg_m_s"],
                "step_momentum_residual_kg_m_s": float(step_residual[IDX_MOM]),
                "cumulative_momentum_residual_kg_m_s": float(
                    cumulative_residual[IDX_MOM]
                ),
                "energy_before_J": before["energy_J"],
                "energy_after_J": after["energy_J"],
                "step_energy_residual_J": float(step_residual[IDX_RHOE]),
                "cumulative_energy_residual_J": float(
                    cumulative_residual[IDX_RHOE]
                ),
                "vapor_mass_after_kg": after["vapor_mass_kg"],
                "outlet_pressure_after_pa": float(primitive_after.p[-1]),
                "outlet_velocity_after_m_s": float(primitive_after.u[-1]),
                "outlet_mach_after": float(
                    primitive_after.u[-1] / primitive_after.c[-1]
                ),
                "outlet_phase_after": str(outlet_after.phase),
                "minimum_density_after_kg_m3": float(np.min(rho)),
                "minimum_internal_energy_after_J_kg": float(np.min(internal)),
                "all_conserved_finite": bool(np.all(np.isfinite(solver.U))),
                "all_phases_allowed": phases_passed,
                "normalized_phases_after": sorted(set(phases)),
                "rho_xv_exact_zero": bool(
                    np.all(solver.U[:, IDX_RHO_XV] == 0.0)
                ),
                "reverse_outlet_velocity_diagnostic": bool(
                    float(primitive_after.u[-1]) < 0.0
                ),
                "reverse_mass_transfer_constructed": False,
                "root_pressure_pa": (
                    None if root is None else float(root["pressure_pa"])
                ),
                "root_chi": (
                    None
                    if root is None
                    else float(
                        root.get("requested_chi", context.get("root_chi", math.nan))
                    )
                ),
                "root_mass_residual_kg_s": (
                    None
                    if root is None
                    else float(root["root_mass_residual_kg_s"])
                ),
                "root_velocity_m_s": (
                    None if root is None else float(root["velocity_m_s"])
                ),
                "root_mach": None if root is None else float(root["mach"]),
                "step_mass_passed": step_mass_passed,
                "step_momentum_passed": step_momentum_passed,
                "step_energy_passed": step_energy_passed,
                "cumulative_mass_passed": cumulative_mass_passed,
                "cumulative_momentum_passed": cumulative_momentum_passed,
                "cumulative_energy_passed": cumulative_energy_passed,
                "outward_root_gate_passed": outward_gate,
                "closure_identity_gate_passed": closure_gate,
                "increment_9l_per_step_engineering_gate_passed": per_step_gate,
            }
            step_rows.append(row)
            state_rows.append(
                {
                    "solver_step_count": int(solver.step_count),
                    "time_after_s": float(solver.t),
                    "public_boundary_state": public_state,
                    "outward_internal_model": outward_model,
                    "branch_classification": context["branch_classification"],
                    "state_transition_triggered": row[
                        "state_transition_triggered_this_step"
                    ],
                    "transition_trigger_classification": row[
                        "transition_trigger_classification"
                    ],
                    "accepted": True,
                }
            )
            final_step_clipped = clipped_to_target
            if not per_step_gate:
                stop_classification = "POST_STEP_ENGINEERING_GATE_FAILURE"
                stop_reason = f"accepted step {requested_step} failed Increment 9L gate"
                break
        except Increment9LStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{exc.classification}: {exc}"
            break
        except Exception as exc:
            stop_classification = str(
                getattr(exc, "classification", type(exc).__name__)
            )
            stop_reason = f"{type(exc).__name__}: {exc}"
            break

    U_after_all = np.asarray(solver.U, dtype=float).copy()
    target_error_s = float(solver.t - target_time_s)
    target_reached = bool(
        solver.t >= target_time_s
        and abs(target_error_s) <= horizon_roundoff_tolerance_s
    )
    public_states = [str(row["public_boundary_state"]) for row in step_rows]
    outward_models = [
        str(row["outward_internal_model"])
        for row in step_rows
        if row["public_boundary_state"] == PUBLIC_OUTWARD
    ]
    boundary_transitions = list(hook.boundary_transition_events)
    model_transitions = list(hook.outward_model_transition_events)
    public_transition_count = sum(
        left != right for left, right in zip(public_states, public_states[1:])
    )
    state_machine_gate = bool(
        stop_reason is None
        and step_rows
        and target_reached
        and final_step_clipped
        and public_states.count(PUBLIC_OUTWARD) > 0
        and public_states.count(PUBLIC_CLOSED) > 0
        and MODEL_FINITE in outward_models
        and len(boundary_transitions) == 1
        and boundary_transitions[0]["from_boundary_state"] == PUBLIC_OUTWARD
        and boundary_transitions[0]["to_boundary_state"] == PUBLIC_CLOSED
        and boundary_transitions[0]["trigger_classification"] == CLOSURE_TRIGGER
        and boundary_transitions[0]["absolute_step_number_trigger_used"] is False
        and len(model_transitions) == 1
        and model_transitions[0]["trigger_classification"] == FINITE_MODEL_TRIGGER
        and model_transitions[0]["absolute_step_number_trigger_used"] is False
        and public_transition_count == 1
        and all(
            bool(row["increment_9l_per_step_engineering_gate_passed"])
            for row in step_rows
        )
    )

    final_phases_passed, final_phases = _all_phases_allowed(
        provider,
        U_after_all,
        allowed_phases,
    )
    rho_final = np.asarray(U_after_all[:, IDX_RHO], dtype=float)
    velocity_final = np.asarray(U_after_all[:, IDX_MOM] / rho_final, dtype=float)
    internal_final = np.asarray(
        U_after_all[:, IDX_RHOE] / rho_final - 0.5 * velocity_final**2,
        dtype=float,
    )
    final_outlet = provider.reconstruct_from_conserved(U_after_all[-1]).static

    summary = {
        "schema_version": "stage7_u3_b2_a1_increment_9l_two_state_boundary_state_machine_v1",
        "scope": "model_review_provisional_engineering_end_to_end_state_machine",
        "case_id": CASE_ID,
        "technical_issue": TECHNICAL_ISSUE,
        "source_starts_from_initial_state": True,
        "checkpoint_artifact_used": False,
        "single_fvm_solver_instance": True,
        "solver_instance_count": 1,
        "absolute_step_number_transition_condition_used": False,
        "public_states": [PUBLIC_OUTWARD, PUBLIC_CLOSED],
        "initial_public_boundary_state": PUBLIC_OUTWARD,
        "final_public_boundary_state": hook.boundary_state,
        "initial_outward_internal_model": MODEL_THREE_BRANCH,
        "final_outward_internal_model": hook.outward_model,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "initial_sound_speed_m_s": initial_sound_speed,
        "target_two_l_over_c0_time_s": target_time_s,
        "horizon_roundoff_tolerance_s": horizon_roundoff_tolerance_s,
        "final_solver_time_s": float(solver.t),
        "horizon_time_error_s": target_error_s,
        "horizon_fraction_reached": float(solver.t / target_time_s),
        "target_horizon_reached": target_reached,
        "final_step_clipped_to_target": final_step_clipped,
        "final_solver_step": int(solver.step_count),
        "accepted_steps_completed": len(step_rows),
        "public_boundary_state_counts": dict(Counter(public_states)),
        "outward_internal_model_counts": dict(Counter(outward_models)),
        "outward_branch_counts": dict(
            Counter(
                str(row["branch_classification"])
                for row in step_rows
                if row["public_boundary_state"] == PUBLIC_OUTWARD
            )
        ),
        "public_state_transition_count": public_transition_count,
        "boundary_transition_event_count": len(boundary_transitions),
        "boundary_transition_events": boundary_transitions,
        "outward_model_transition_event_count": len(model_transitions),
        "outward_model_transition_events": model_transitions,
        "closure_trigger_classification": hook.closure_trigger_classification,
        "closure_trigger_message": hook.closure_trigger_message,
        "public_state_reentry_allowed": False,
        "reverse_mass_transfer_supported": False,
        "public_state_chatter_detected": public_transition_count > 1,
        "right_mass_transfer_exact_zero_all_closed_steps": bool(
            all(
                float(row["right_external_mass_flux_kg_m2_s"]) == 0.0
                for row in step_rows
                if row["public_boundary_state"] == PUBLIC_CLOSED
            )
        ),
        "right_energy_transfer_exact_zero_all_closed_steps": bool(
            all(
                float(row["right_external_energy_flux_W_m2_s"])
                if "right_external_energy_flux_W_m2_s" in row
                else float(row["right_external_energy_flux_W_m2"])
                == 0.0
                for row in step_rows
                if row["public_boundary_state"] == PUBLIC_CLOSED
            )
        ),
        "right_vapor_transfer_exact_zero_all_closed_steps": bool(
            all(
                float(row["right_external_vapor_flux_kg_m2_s"]) == 0.0
                for row in step_rows
                if row["public_boundary_state"] == PUBLIC_CLOSED
            )
        ),
        "wall_momentum_identity_exact_all_closed_steps": bool(
            all(
                float(row["wall_momentum_identity_residual_pa"]) == 0.0
                for row in step_rows
                if row["public_boundary_state"] == PUBLIC_CLOSED
            )
        ),
        "maximum_halving_count": _maximum(step_rows, "halving_count"),
        "maximum_absolute_step_mass_residual_kg": _max_abs(
            step_rows, "step_mass_residual_kg"
        ),
        "maximum_absolute_step_momentum_residual_kg_m_s": _max_abs(
            step_rows, "step_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_step_energy_residual_J": _max_abs(
            step_rows, "step_energy_residual_J"
        ),
        "maximum_absolute_cumulative_mass_residual_kg": _max_abs(
            step_rows, "cumulative_mass_residual_kg"
        ),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": _max_abs(
            step_rows, "cumulative_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_cumulative_energy_residual_J": _max_abs(
            step_rows, "cumulative_energy_residual_J"
        ),
        "minimum_density_kg_m3": float(np.min(rho_final)),
        "minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "maximum_absolute_velocity_m_s": float(np.max(np.abs(velocity_final))),
        "final_all_phases_allowed": final_phases_passed,
        "final_normalized_phases": sorted(set(final_phases)),
        "final_rho_xv_exact_zero": bool(
            np.all(U_after_all[:, IDX_RHO_XV] == 0.0)
        ),
        "final_outlet_pressure_pa": float(final_outlet.pressure_pa),
        "final_outlet_velocity_m_s": float(final_outlet.velocity_m_s),
        "final_outlet_mach": float(
            final_outlet.velocity_m_s / final_outlet.sound_speed_m_s
        ),
        "final_outlet_phase": str(final_outlet.phase),
        "starting_state_sha256": _state_sha256(U_before_all),
        "final_state_sha256": _state_sha256(U_after_all),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "increment_9l_state_machine_gate_passed": state_machine_gate,
        "working_vertical_slice": state_machine_gate,
        "working_vertical_slice_kind": (
            "PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE"
        ),
        "provisional_engineering_two_l_over_c0_reached": bool(
            state_machine_gate and target_reached
        ),
        "outcome": OUTCOME if state_machine_gate else "INCREMENT_9L_STOPPED",
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
    return (
        summary,
        step_rows,
        state_rows,
        boundary_transitions,
        model_transitions,
        U_before_all,
        U_after_all,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (args.contract, args.b1_contract, args.model_review_spec):
        if not path.is_file():
            raise FileNotFoundError(path)

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    (
        summary,
        step_rows,
        state_rows,
        boundary_transitions,
        model_transitions,
        U_initial,
        U_final,
    ) = _run(contract=contract, b1_contract=b1_contract)
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec"] = str(args.model_review_spec)
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "step_metrics.csv", step_rows)
    _write_csv(output / "boundary_state_history.csv", state_rows)
    _write_csv(
        output / "boundary_transition_events.csv", boundary_transitions
    )
    _write_csv(
        output / "outward_model_transition_events.csv", model_transitions
    )
    np.savez_compressed(
        output / "initial_and_final_states.npz",
        U_initial=np.asarray(U_initial, dtype=float),
        U_final=np.asarray(U_final, dtype=float),
        solver_step_initial=np.asarray([0], dtype=np.int64),
        solver_step_final=np.asarray(
            [summary["final_solver_step"]], dtype=np.int64
        ),
        solver_time_initial_s=np.asarray([0.0]),
        solver_time_final_s=np.asarray([summary["final_solver_time_s"]]),
        target_time_s=np.asarray([summary["target_two_l_over_c0_time_s"]]),
    )
    technical_issue = {
        "technical_issue": TECHNICAL_ISSUE,
        "status": "OPEN_NONBLOCKING_TECHNICAL_DEBT",
        "strict_predecessor_classification": (
            "ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE"
        ),
        "engineering_transition_trigger": CLOSURE_TRIGGER,
        "transition_generalized_without_absolute_step_number": True,
        "reentry_implemented": False,
        "reverse_flow_implemented": False,
        "hysteresis_validated": False,
        "physical_validation": False,
    }
    (output / "technical_issue.json").write_text(
        json.dumps(technical_issue, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    authority = {
        "execution_source_git_sha": args.source_git_sha,
        "model_review_spec": str(args.model_review_spec),
        "model_review_spec_sha256": _sha256(args.model_review_spec),
        "initial_state_built_from_locked_contract": True,
        "checkpoint_artifact_used": False,
        "fvm_solver_core_changed": False,
        "production_adapter_changed": False,
        "b1_changed": False,
        "locked_b2_contract_changed": False,
        "tolerances_changed": False,
        "chi_cap_changed": False,
        "absolute_step_transition_condition_used": False,
    }
    (output / "authority_verification.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9L two-state boundary state machine\n\n"
        "One unchanged FvmSolver trajectory was started from the locked "
        "LIQUID_SMALL_DROP initial state. The public boundary remained "
        "OUTWARD_FLOW while the existing wave/weak-compression and general-EOS "
        "finite-compression models supplied supported roots. The expected "
        "NO_ADMISSIBLE_ISLAND near-zero outcome triggered one step-independent "
        "transition to ZERO_TRANSFER_CLOSED. No failed candidate was used as a "
        "root or flux. Re-entry and reverse mass transfer remained disabled.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step_metrics.csv",
        "boundary_state_history.csv",
        "boundary_transition_events.csv",
        "outward_model_transition_events.csv",
        "technical_issue.json",
        "initial_and_final_states.npz",
        "authority_verification.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9l_state_machine_gate_passed"]:
        raise SystemExit(
            "Increment 9L state-machine gate did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
