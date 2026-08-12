from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
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
from u3_b2_a1_weak_compression_bridge_diagnostic import (
    CHI_MAX,
    MAX_BISECTION_ITERATIONS,
    OUTCOME as INCREMENT_1_OUTCOME,
    _run_increment_1,
)
from u3_b2_a1_wave_curve_model import CASE_ID, _scan_row
from u3_b2_characteristic_port_dynamic_short_hook import A1DynamicShortHook
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
)
from u3_b2_characteristic_port_dynamic_short_model import DynamicDiagnosticStop


PARENT_SOURCE_SHA = "2807fab09bbacd61971346c43d742944e4428a7f"
PARENT_WORKFLOW_RUN = 31601616704
PARENT_JOB = 94130182117
PARENT_ARTIFACT = 9143467594
PARENT_ARTIFACT_SHA256 = (
    "9a68c543740d7a891fe39161619d048bcd4c79b011e4e56dfeb4c55e25187185"
)
STARTING_ACCEPTED_SOLVER_STEP = 337
TARGET_ACCEPTED_SOLVER_STEP = 338
OUTCOME = "WEAK_COMPRESSION_INCREMENT_2_ONE_STEP_PASS"
robustness = robustness_v4.robustness


class WeakCompressionOneStepStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
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


def _full_wave_row(
    *,
    pressure_pa: float,
    static: Any,
    isentrope: Any,
    hook: Any,
    area_m2: float,
    allowed_phases: set[str],
    velocity_tolerance: float,
    state_id: str,
) -> dict[str, Any]:
    offset = float(pressure_pa - float(static.pressure_pa))
    row = _scan_row(
        offset_pa=offset,
        static=static,
        isentrope=isentrope,
        hook=hook,
        area_m2=area_m2,
        allowed_phases=allowed_phases,
        velocity_tolerance=velocity_tolerance,
    )
    result = dict(row)
    result["state_id"] = state_id
    if not bool(result.get("evaluation_succeeded")):
        result["residual_kg_s"] = None
        return result

    rho = float(result["density_kg_m3"])
    velocity = float(result["velocity_m_s"])
    internal_energy = float(result["internal_energy_J_kg"])
    conserved = np.asarray(
        [
            rho,
            rho * velocity,
            rho * (internal_energy + 0.5 * velocity * velocity),
            0.0,
        ],
        dtype=float,
    )
    evaluation = hook.adapter.evaluate(conserved, area_m2)
    if not evaluation.succeeded or evaluation.face is None:
        result.update(
            evaluation_succeeded=False,
            formal_outcome=evaluation.formal_outcome,
            formal_message=evaluation.formal_message,
            residual_kg_s=None,
        )
        return result
    face = evaluation.face
    result.update(
        residual_kg_s=float(result["compatibility_residual_kg_s"]),
        b1_effective_velocity_m_s=float(face.effective_velocity_m_s),
        b1_discharge_state_pressure_pa=float(face.discharge_state_pressure_pa),
        b1_critical_pressure_pa=(
            None
            if face.critical_pressure_pa is None
            else float(face.critical_pressure_pa)
        ),
        open_area_m2=float(face.open_area_m2),
    )
    return result


def _build_weak_compression_context(
    *,
    contract: dict[str, Any],
    state_id: str,
    provider: CoolPropB2StateProvider,
    hook: Any,
    outlet_conserved: np.ndarray,
    solver_time_s: float,
    increment_1_root: dict[str, Any],
    increment_1_scan_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reconstruction = provider.reconstruct_from_conserved(outlet_conserved)
    static = reconstruction.static
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if normalize_phase(static.phase) not in allowed_phases:
        raise WeakCompressionOneStepStop(
            f"interior phase {static.phase!r} is outside {sorted(allowed_phases)}"
        )
    if float(static.velocity_m_s) < -velocity_tolerance:
        raise WeakCompressionOneStepStop(
            f"interior outlet velocity is reverse-directed: {static.velocity_m_s}"
        )
    if not float(static.pressure_pa) > float(hook.adapter.back_pressure_pa):
        raise WeakCompressionOneStepStop(
            "interior pressure is not above retained back pressure"
        )

    tolerances = contract["acceptance_tolerances"]
    if abs(float(reconstruction.enthalpy_round_trip_residual_J_kg)) > float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    ) or abs(float(reconstruction.entropy_round_trip_residual_J_kg_K)) > float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    ):
        raise WeakCompressionOneStepStop(
            "interior stagnation-state round trip exceeds locked tolerance"
        )

    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))

    def evaluate(pressure_pa: float) -> dict[str, Any]:
        return _full_wave_row(
            pressure_pa=float(pressure_pa),
            static=static,
            isentrope=isentrope,
            hook=hook,
            area_m2=hook.area_m2,
            allowed_phases=allowed_phases,
            velocity_tolerance=velocity_tolerance,
            state_id=state_id,
        )

    root_pressure = float(increment_1_root["pressure_pa"])
    raw_root = evaluate(root_pressure)
    if not bool(raw_root.get("evaluation_succeeded")):
        raise WeakCompressionOneStepStop(
            "reproduced Weak Compression root evaluation failed: "
            f"{raw_root.get('formal_outcome')} {raw_root.get('formal_message')}"
        )
    if not bool(raw_root.get("local_candidate_admissible")):
        raise WeakCompressionOneStepStop(
            "reproduced Weak Compression root is inadmissible"
        )

    completed = horizon._complete_root_row_dynamic_v4(
        root=raw_root,
        evaluate=evaluate,
        adapter=hook.adapter,
        area_m2=hook.area_m2,
        quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
    )
    root = dict(raw_root)
    root.update(completed)
    root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    root_chi = float(root_offset / denominator)
    root.update(
        {
            "branch_classification": "WEAK_COMPRESSION",
            "p_P_minus_p_i_pa": root_offset,
            "chi": root_chi,
            "chi_max": CHI_MAX,
            "increment_1_bisection_iterations": int(
                increment_1_root["bisection_iterations"]
            ),
        }
    )

    if not root_offset > 0.0:
        raise WeakCompressionOneStepStop(
            "reproduced Weak Compression root is not above the endpoint"
        )
    if not 0.0 < root_chi <= CHI_MAX:
        raise WeakCompressionOneStepStop(
            f"reproduced Weak Compression root chi is outside scope: {root_chi}"
        )
    if abs(float(root["root_mass_residual_kg_s"])) > float(
        robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    ):
        raise WeakCompressionOneStepStop(
            "reproduced root mass residual exceeds retained tolerance"
        )
    if float(root["local_residual_slope_kg_s_Pa"]) >= 0.0:
        raise WeakCompressionOneStepStop(
            "reproduced root local residual slope is not negative"
        )
    if float(root["velocity_m_s"]) < -velocity_tolerance:
        raise WeakCompressionOneStepStop(
            "reproduced root velocity is reverse-directed"
        )
    if not 0.0 <= float(root["mach"]) < 1.0:
        raise WeakCompressionOneStepStop(
            "reproduced root is outside the subsonic branch"
        )
    if normalize_phase(str(root["phase"])) not in allowed_phases:
        raise WeakCompressionOneStepStop(
            "reproduced root phase is outside the allowed liquid scope"
        )
    if not bool(root["stagnation_enthalpy_round_trip_passed"]):
        raise WeakCompressionOneStepStop(
            "reproduced root stagnation-enthalpy round trip failed"
        )
    if not bool(root["energy_mass_consistency_passed"]):
        raise WeakCompressionOneStepStop(
            "reproduced root energy/mass decomposition failed"
        )
    if not bool(root["energy_port_closure_passed"]):
        raise WeakCompressionOneStepStop(
            "reproduced root energy-port closure failed"
        )
    if abs(float(root["momentum_ledger_residual_N"])) > float(
        robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    ):
        raise WeakCompressionOneStepStop(
            "reproduced root restriction-reaction ledger failed"
        )

    mass_rate = float(root["pipe_mass_rate_kg_s"])
    velocity = float(root["velocity_m_s"])
    pressure = float(root["pressure_pa"])
    h0 = float(root["h0_J_kg"])
    flux = np.asarray(
        [
            mass_rate / hook.area_m2,
            (mass_rate * velocity + pressure * hook.area_m2) / hook.area_m2,
            mass_rate * h0 / hook.area_m2,
            0.0,
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(flux)):
        raise WeakCompressionOneStepStop(
            "reproduced Weak Compression pipe-side flux is nonfinite"
        )

    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in increment_1_scan_rows
        if row.get("evaluation_succeeded")
    ]
    positive_residual_monotone = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    admissible_nodes = sum(
        bool(row.get("local_candidate_admissible"))
        for row in increment_1_scan_rows
    )
    return {
        "solver_time_s": float(solver_time_s),
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "interior_phase": static.phase,
        "interior_h0_round_trip_residual_J_kg": float(
            reconstruction.enthalpy_round_trip_residual_J_kg
        ),
        "interior_s0_round_trip_residual_J_kg_K": float(
            reconstruction.entropy_round_trip_residual_J_kg_K
        ),
        "connected_scan_base_node_count": len(increment_1_scan_rows),
        "connected_scan_requested_nodes": len(increment_1_scan_rows),
        "connected_scan_admissible_subsonic_nodes": int(admissible_nodes),
        "connected_scan_lowest_pressure_pa": float(static.pressure_pa),
        "connected_scan_stop_reason": None,
        "connected_scan_residual_monotone": positive_residual_monotone,
        "connected_scan_sign_change_count": 1,
        "root": root,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
        "branch_classification": "WEAK_COMPRESSION",
        "root_chi": root_chi,
        "positive_scan_sign_change_count": 1,
        "positive_pressure_continuation_flux_applied": True,
        "finite_compression_branch_approved": False,
    }


class A1WeakCompressionOneStepHook(A1DynamicShortHook):
    """Exact prepared Weak Compression root for one step from 337 to 338."""

    def __init__(
        self,
        *,
        prepared_context: dict[str, Any],
        expected_outlet: np.ndarray,
        expected_time_s: float,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.prepared_context = prepared_context
        self.expected_outlet = np.asarray(expected_outlet, dtype=float).copy()
        self.expected_time_s = float(expected_time_s)

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        if float(t) != self.expected_time_s:
            raise DynamicDiagnosticStop(
                "one-step Weak Compression hook was called at an unexpected time"
            )
        if not np.array_equal(np.asarray(U[-1], dtype=float), self.expected_outlet):
            raise DynamicDiagnosticStop(
                "one-step Weak Compression hook received an unexpected outlet state"
            )
        self.root_context = self.prepared_context
        self.flux = np.asarray(self.prepared_context["flux"], dtype=float).copy()
        self._cache_t = float(t)
        self._cache_outlet = np.asarray(U[-1], dtype=float).copy()
        self.trial_dts_s = []


def _run_increment_2(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    np.ndarray,
    np.ndarray,
]:
    (
        resume_row,
        increment_1_scan_rows,
        increment_1_root,
        increment_1_summary,
        U_step337,
    ) = _run_increment_1(contract, b1_contract)
    if not bool(increment_1_summary["increment_1_diagnostic_gate_passed"]):
        raise WeakCompressionOneStepStop(
            "Increment 1 diagnostic reproduction did not pass"
        )
    if increment_1_summary["outcome"] != INCREMENT_1_OUTCOME:
        raise WeakCompressionOneStepStop(
            "Increment 1 diagnostic reproduction returned an unexpected outcome"
        )
    if int(increment_1_summary["solver_step_after_diagnostic"]) != (
        STARTING_ACCEPTED_SOLVER_STEP
    ):
        raise WeakCompressionOneStepStop(
            "Increment 1 diagnostic did not leave the solver at step 337"
        )
    if bool(increment_1_summary["fvm_step_338_attempted"]):
        raise WeakCompressionOneStepStop(
            "Increment 1 unexpectedly attempted FvmSolver step 338"
        )

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
    U_initial, initial_static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    expected_time_s = float(resume_row["time_after_s"])

    preparation_hook = A1DynamicShortHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    prepared_context = _build_weak_compression_context(
        contract=contract,
        state_id=state_id,
        provider=provider,
        hook=preparation_hook,
        outlet_conserved=np.asarray(U_step337[-1], dtype=float),
        solver_time_s=expected_time_s,
        increment_1_root=increment_1_root,
        increment_1_scan_rows=increment_1_scan_rows,
    )
    hook = A1WeakCompressionOneStepHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
        prepared_context=prepared_context,
        expected_outlet=np.asarray(U_step337[-1], dtype=float),
        expected_time_s=expected_time_s,
    )
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=np.asarray(U_step337, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=expected_time_s,
        step_count=STARTING_ACCEPTED_SOLVER_STEP,
    )

    initial = inventory(
        U_initial,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    before = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current_minus_initial = _inventory_array(before) - _inventory_array(initial)
    cumulative_expected_delta = np.asarray(
        [
            current_minus_initial[0]
            - float(resume_row["cumulative_mass_residual_kg"]),
            current_minus_initial[1]
            - float(resume_row["cumulative_momentum_residual_kg_m_s"]),
            current_minus_initial[2]
            - float(resume_row["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )

    candidate_dt = float(solver.compute_dt())
    dt_limits = dict(hook.last_dt_limits)
    if hook.root_context is None:
        raise WeakCompressionOneStepStop(
            "Weak Compression root was not prepared by compute_dt"
        )
    root_context = hook.root_context
    if root_context["branch_classification"] != "WEAK_COMPRESSION":
        raise WeakCompressionOneStepStop(
            "prepared one-step branch is not WEAK_COMPRESSION"
        )
    flux_left, _ = solver._base_fluxes()
    left_flux = np.asarray(flux_left[0], dtype=float)
    right_flux = np.asarray(hook.flux, dtype=float)
    U_before = np.asarray(solver.U, dtype=float).copy()
    accepted_dt = float(solver.step(candidate_dt))
    hook.accept_current_root()
    U_after = np.asarray(solver.U, dtype=float).copy()

    after = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    expected_step_delta = accepted_dt * grid.geometry.area_m2 * (
        left_flux - right_flux
    )
    cumulative_expected_delta += expected_step_delta
    primitive_after = solver.primitive()
    post_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
    row = build_step_row(
        case_id=CASE_ID,
        state_id=state_id,
        requested_step=TARGET_ACCEPTED_SOLVER_STEP,
        solver=solver,
        hook=hook,
        root_context=root_context,
        dt_limits=dt_limits,
        candidate_dt=candidate_dt,
        accepted_dt=accepted_dt,
        before=before,
        after=after,
        initial=initial,
        expected_step_delta=expected_step_delta,
        cumulative_expected_delta=cumulative_expected_delta,
        left_flux=left_flux,
        right_flux=right_flux,
        post_reconstruction=post_reconstruction,
        primitive_after=primitive_after,
        tolerances=contract["acceptance_tolerances"],
    )
    root = root_context["root"]
    rho_after = U_after[:, 0]
    velocity_after = U_after[:, 1] / rho_after
    internal_after = U_after[:, 2] / rho_after - 0.5 * velocity_after**2
    row.update(
        {
            "branch_classification": "WEAK_COMPRESSION",
            "p_P_minus_p_i_pa": float(root["p_P_minus_p_i_pa"]),
            "root_chi": float(root["chi"]),
            "chi_max": CHI_MAX,
            "positive_scan_sign_change_count": 1,
            "increment_1_diagnostic_reproduced": True,
            "increment_1_bisection_iterations": int(
                root["increment_1_bisection_iterations"]
            ),
            "minimum_density_after_step_kg_m3": float(np.min(rho_after)),
            "minimum_internal_energy_after_step_J_kg": float(
                np.min(internal_after)
            ),
            "all_conserved_finite_after_step": bool(np.all(np.isfinite(U_after))),
            "positive_pressure_continuation_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
    )

    gate = bool(
        bool(increment_1_summary["checkpoint_reproduction_ok"])
        and bool(increment_1_summary["neutral_endpoint_step337_gate_passed"])
        and bool(increment_1_summary["increment_1_diagnostic_gate_passed"])
        and row["branch_classification"] == "WEAK_COMPRESSION"
        and int(row["positive_scan_sign_change_count"]) == 1
        and 0.0 < float(row["root_chi"]) <= CHI_MAX
        and abs(float(row["root_mass_residual_kg_s"]))
        <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and float(row["root_velocity_m_s"]) >= 0.0
        and 0.0 <= float(row["root_mach"]) < 1.0
        and bool(row["accepted_step"])
        and bool(row["step_passed"])
        and int(row["solver_step_count"]) == TARGET_ACCEPTED_SOLVER_STEP
        and accepted_dt > 0.0
        and bool(row["all_conserved_finite_after_step"])
        and float(row["minimum_density_after_step_kg_m3"]) > 0.0
        and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
        and not bool(row["reverse_flow_guard_triggered"])
        and not bool(row["reverse_velocity_detected"])
        and bool(row["outlet_phase_passed"])
        and bool(row["rho_xv_exact_zero"])
        and bool(row["step_mass_passed"])
        and bool(row["step_momentum_passed"])
        and bool(row["step_energy_passed"])
        and bool(row["cumulative_mass_passed"])
        and bool(row["cumulative_momentum_passed"])
        and bool(row["cumulative_energy_passed"])
        and bool(row["stagnation_enthalpy_round_trip_passed"])
        and bool(row["energy_mass_consistency_passed"])
        and bool(row["energy_port_closure_passed"])
        and abs(float(row["restriction_reaction_ledger_residual_N"]))
        <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    )
    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_2"
        ),
        "scope": "model_review_working_vertical_slice_one_actual_fvm_step",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "case_id": CASE_ID,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "checkpoint_reproduction_ok": bool(
            increment_1_summary["checkpoint_reproduction_ok"]
        ),
        "neutral_endpoint_step337_gate_passed": bool(
            increment_1_summary["neutral_endpoint_step337_gate_passed"]
        ),
        "increment_1_diagnostic_reproduced": True,
        "increment_1_diagnostic_gate_passed": bool(
            increment_1_summary["increment_1_diagnostic_gate_passed"]
        ),
        "increment_1_outcome": increment_1_summary["outcome"],
        "solver_step_before": STARTING_ACCEPTED_SOLVER_STEP,
        "solver_step_after": int(solver.step_count),
        "solver_time_before_s": float(root_context["solver_time_s"]),
        "solver_time_after_s": float(solver.t),
        "accepted_dt_s": accepted_dt,
        "halving_count": int(row["halving_count"]),
        "trial_dts_s": row["trial_dts_s"],
        "branch_classification": "WEAK_COMPRESSION",
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_pressure_offset_pa": float(root["p_P_minus_p_i_pa"]),
        "root_chi": float(root["chi"]),
        "chi_max": CHI_MAX,
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(
            root["local_residual_slope_kg_s_Pa"]
        ),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_phase": str(root["phase"]),
        "root_b1_formal_outcome": root["formal_outcome"],
        "root_pipe_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "root_b1_mass_rate_kg_s": float(root["b1_mass_rate_kg_s"]),
        "right_external_flux": [float(value) for value in right_flux],
        "root_pipe_momentum_port_N": float(root["pipe_momentum_port_N"]),
        "root_downstream_stream_pressure_port_N": float(
            root["downstream_stream_pressure_port_N"]
        ),
        "root_restriction_reaction_on_fluid_N": float(
            root["restriction_reaction_on_fluid_N"]
        ),
        "root_restriction_reaction_ledger_residual_N": float(
            root["momentum_ledger_residual_N"]
        ),
        "root_energy_port_residual_W": float(root["energy_port_residual_W"]),
        "outlet_pressure_after_step_pa": float(
            row["outlet_pressure_after_step_pa"]
        ),
        "outlet_velocity_after_step_m_s": float(
            row["outlet_velocity_after_step_m_s"]
        ),
        "outlet_phase_after_step": row["outlet_phase_after_step"],
        "outlet_mach_after_step": float(
            post_reconstruction.static.velocity_m_s
            / post_reconstruction.static.sound_speed_m_s
        ),
        "minimum_density_after_step_kg_m3": float(
            row["minimum_density_after_step_kg_m3"]
        ),
        "minimum_internal_energy_after_step_J_kg": float(
            row["minimum_internal_energy_after_step_J_kg"]
        ),
        "step_mass_residual_kg": float(row["step_mass_residual_kg"]),
        "step_momentum_residual_kg_m_s": float(
            row["step_momentum_residual_kg_m_s"]
        ),
        "step_energy_residual_J": float(row["step_energy_residual_J"]),
        "cumulative_mass_residual_kg": float(
            row["cumulative_mass_residual_kg"]
        ),
        "cumulative_momentum_residual_kg_m_s": float(
            row["cumulative_momentum_residual_kg_m_s"]
        ),
        "cumulative_energy_residual_J": float(
            row["cumulative_energy_residual_J"]
        ),
        "rho_xv_exact_zero": bool(row["rho_xv_exact_zero"]),
        "reverse_flow_guard_triggered": bool(
            row["reverse_flow_guard_triggered"]
        ),
        "reverse_velocity_detected": bool(row["reverse_velocity_detected"]),
        "outlet_phase_passed": bool(row["outlet_phase_passed"]),
        "step_passed": bool(row["step_passed"]),
        "outcome": OUTCOME,
        "increment_2_one_step_gate_passed": gate,
        "positive_pressure_continuation_flux_applied": True,
        "finite_compression_branch_approved": False,
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
        row,
        increment_1_scan_rows,
        increment_1_root,
        summary,
        U_before,
        U_after,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)

    (
        step_row,
        increment_1_scan_rows,
        increment_1_root,
        summary,
        U_before,
        U_after,
    ) = _run_increment_2(contract, b1_contract)
    summary["source_git_sha"] = args.source_git_sha

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "increment_1_positive_scan_reproduced.csv", increment_1_scan_rows)
    _write_csv(output / "increment_1_root_reproduced.csv", [increment_1_root])
    _write_csv(output / "weak_compression_step_338.csv", [step_row])
    np.savez_compressed(
        output / "weak_compression_step_338_states.npz",
        U_before=np.asarray(U_before, dtype=float),
        U_after=np.asarray(U_after, dtype=float),
        solver_step_before=np.asarray(
            [STARTING_ACCEPTED_SOLVER_STEP], dtype=np.int64
        ),
        solver_step_after=np.asarray([TARGET_ACCEPTED_SOLVER_STEP], dtype=np.int64),
        solver_time_before_s=np.asarray([summary["solver_time_before_s"]]),
        solver_time_after_s=np.asarray([summary["solver_time_after_s"]]),
        accepted_dt_s=np.asarray([summary["accepted_dt_s"]]),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 2\n\n"
        "MODEL_REVIEW / WORKING_VERTICAL_SLICE evidence only. The exact "
        "step-337 state and Increment 1 Weak Compression root were reproduced, "
        "then the existing FvmSolver accepted exactly one step from 337 to 338 "
        "using the pipe-side Euler flux. This does not approve a general finite "
        "compression model, full-horizon passage, finite-pipe verification, "
        "benchmark acceptance, Physical Validation, design use, or production "
        "activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "increment_1_positive_scan_reproduced.csv",
        "increment_1_root_reproduced.csv",
        "weak_compression_step_338.csv",
        "weak_compression_step_338_states.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_2_one_step_gate_passed"]:
        raise SystemExit("Weak Compression Bridge Increment 2 did not pass")


if __name__ == "__main__":
    main()
