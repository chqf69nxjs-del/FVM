from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
)
from u3_b2_characteristic_port_dynamic_short_metrics import inventory
from u3_b2_a1_finite_compression_hugoniot_full_horizon_step import advance_one_step
from u3_b2_a1_finite_compression_hugoniot_full_horizon_support import (
    HORIZON_ROUNDOFF_TOLERANCE_S,
    MAXIMUM_OPERATIONAL_SOLVER_STEP,
    OUTCOME,
    PARENT_ARTIFACT,
    PARENT_ARTIFACT_NAME,
    PARENT_ARTIFACT_SHA256,
    PARENT_JOB,
    PARENT_SOURCE_SHA,
    PARENT_WORKFLOW_RUN,
    STARTING_SOLVER_STEP,
    STARTING_SOLVER_TIME_S,
    TARGET_TIME_S,
    _array_sha256,
    _inventory_array,
)


def _clear_chatter(branches: list[str]) -> bool:
    return any(
        seq[0] == seq[2] == seq[4]
        and seq[1] == seq[3]
        and seq[0] != seq[1]
        for seq in (branches[i : i + 5] for i in range(max(len(branches) - 4, 0)))
        if len(seq) == 5
    )


def _run_full_horizon(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    parent_summary: dict[str, Any],
    U_step524: np.ndarray,
    parent_step_row: dict[str, str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    np.ndarray,
    np.ndarray,
]:
    case = diagnostic._case(contract, base.CASE_ID)
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
        contract, provider, state_id, grid.n_cells
    )
    hook = base.A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(parent_summary["root_pressure_pa"])
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider, boundary_temperature_K=initial_static.temperature_K
        ),
        U=np.asarray(U_step524, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=STARTING_SOLVER_TIME_S,
        step_count=STARTING_SOLVER_STEP,
    )
    initial = inventory(U_initial, dx=grid.dx, area_m2=grid.geometry.area_m2)
    starting = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    current_minus_initial = _inventory_array(starting) - _inventory_array(initial)
    cumulative_residual = np.asarray(
        [
            float(parent_step_row["cumulative_mass_residual_kg"]),
            float(parent_step_row["cumulative_momentum_residual_kg_m_s"]),
            float(parent_step_row["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )
    cumulative_expected_delta = current_minus_initial - cumulative_residual
    U_start = np.asarray(solver.U, dtype=float).copy()
    step_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []
    density_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None
    stop_diagnostics: dict[str, Any] = {}

    while solver.t < TARGET_TIME_S - HORIZON_ROUNDOFF_TOLERANCE_S:
        if solver.step_count >= MAXIMUM_OPERATIONAL_SOLVER_STEP:
            stop_classification = "OPERATIONAL_STEP_CAP_EXCEEDED"
            stop_reason = (
                "FiniteCompressionShortRunStop: operational solver-step cap "
                f"{MAXIMUM_OPERATIONAL_SOLVER_STEP} reached before target"
            )
            break
        requested_step = int(solver.step_count + 1)
        try:
            (
                row,
                root_row,
                new_scan_rows,
                new_density_rows,
                branch_row,
                cumulative_expected_delta,
            ) = advance_one_step(
                solver=solver,
                hook=hook,
                grid=grid,
                provider=provider,
                initial=initial,
                cumulative_expected_delta=cumulative_expected_delta,
                contract=contract,
                state_id=state_id,
                requested_step=requested_step,
            )
            step_rows.append(row)
            root_rows.append(root_row)
            scan_rows.extend(new_scan_rows)
            density_rows.extend(new_density_rows)
            branch_rows.append(branch_row)
        except base.FiniteCompressionShortRunStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{type(exc).__name__}: {exc}"
            stop_diagnostics = dict(exc.diagnostics)
            break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            stop_diagnostics = {}
            break

    U_final = np.asarray(solver.U, dtype=float).copy()
    branch_sequence = [row["branch_classification"] for row in branch_rows]
    branch_transitions = sum(a != b for a, b in zip(branch_sequence, branch_sequence[1:]))
    clear_chatter = _clear_chatter(branch_sequence)
    final_error = float(solver.t - TARGET_TIME_S)
    target_reached = bool(
        solver.t >= TARGET_TIME_S
        and abs(final_error) <= HORIZON_ROUNDOFF_TOLERANCE_S
    )
    final_clipped = bool(step_rows and step_rows[-1]["step_clipped_to_target"])
    pass_gate = bool(
        stop_reason is None
        and step_rows
        and target_reached
        and final_clipped
        and int(solver.step_count) <= MAXIMUM_OPERATIONAL_SOLVER_STEP
        and all(row["increment_9_per_step_gate_passed"] for row in step_rows)
        and all(branch == base.BRANCH for branch in branch_sequence)
        and branch_transitions == 0
        and not clear_chatter
        and all(
            base.WEAK_COMPRESSION_CHI_LIMIT
            < float(row["root_requested_chi"])
            <= base.DIAGNOSTIC_CHI_CAP
            for row in step_rows
        )
    )
    final_reconstruction = provider.reconstruct_from_conserved(U_final[-1])
    rho_final = U_final[:, 0]
    velocity_final = U_final[:, 1] / rho_final
    internal_final = U_final[:, 2] / rho_final - 0.5 * velocity_final**2
    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_9",
        "scope": "model_review_full_nominal_two_l_over_c0_general_eos_hugoniot",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_artifact_verified": True,
        "parent_outcome": parent_summary["outcome"],
        "case_id": base.CASE_ID,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "starting_solver_step": STARTING_SOLVER_STEP,
        "additional_accepted_steps": len(step_rows),
        "final_solver_step": int(solver.step_count),
        "maximum_operational_solver_step": MAXIMUM_OPERATIONAL_SOLVER_STEP,
        "starting_solver_time_s": STARTING_SOLVER_TIME_S,
        "target_two_l_over_c0_time_s": TARGET_TIME_S,
        "final_solver_time_s": float(solver.t),
        "horizon_time_error_s": final_error,
        "horizon_time_roundoff_tolerance_s": HORIZON_ROUNDOFF_TOLERANCE_S,
        "horizon_fraction_reached": float(solver.t / TARGET_TIME_S),
        "target_horizon_reached": target_reached,
        "final_step_clipped_to_target": final_clipped,
        "branch_sequence": branch_sequence,
        "branch_counts": dict(Counter(branch_sequence)),
        "branch_transition_count": branch_transitions,
        "clear_branch_chatter_detected": clear_chatter,
        "minimum_root_requested_chi": base._minimum(step_rows, "root_requested_chi"),
        "maximum_root_requested_chi": base._maximum(step_rows, "root_requested_chi"),
        "minimum_root_pressure_offset_pa": base._minimum(step_rows, "root_pressure_offset_pa"),
        "maximum_root_pressure_offset_pa": base._maximum(step_rows, "root_pressure_offset_pa"),
        "maximum_absolute_root_mass_residual_kg_s": base._max_abs(step_rows, "root_mass_residual_kg_s"),
        "minimum_root_local_slope_kg_s_Pa": base._minimum(step_rows, "root_local_slope_kg_s_Pa"),
        "maximum_root_mach": base._maximum(step_rows, "root_mach"),
        "minimum_root_velocity_m_s": base._minimum(step_rows, "root_velocity_m_s"),
        "minimum_root_entropy_delta_J_kg_K": base._minimum(step_rows, "root_entropy_delta_J_kg_K"),
        "minimum_root_stagnation_pressure_margin_above_back_pa": base._minimum(root_rows, "root_stagnation_pressure_margin_above_back_pa"),
        "maximum_halving_count": base._maximum(step_rows, "halving_count"),
        "minimum_accepted_dt_s": base._minimum(step_rows, "accepted_dt_s"),
        "maximum_accepted_dt_s": base._maximum(step_rows, "accepted_dt_s"),
        "maximum_absolute_step_mass_residual_kg": base._max_abs(step_rows, "step_mass_residual_kg"),
        "maximum_absolute_step_momentum_residual_kg_m_s": base._max_abs(step_rows, "step_momentum_residual_kg_m_s"),
        "maximum_absolute_step_energy_residual_J": base._max_abs(step_rows, "step_energy_residual_J"),
        "maximum_absolute_cumulative_mass_residual_kg": base._max_abs(step_rows, "cumulative_mass_residual_kg"),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": base._max_abs(step_rows, "cumulative_momentum_residual_kg_m_s"),
        "maximum_absolute_cumulative_energy_residual_J": base._max_abs(step_rows, "cumulative_energy_residual_J"),
        "final_outlet_pressure_pa": float(final_reconstruction.static.pressure_pa),
        "final_outlet_velocity_m_s": float(final_reconstruction.static.velocity_m_s),
        "final_outlet_mach": float(final_reconstruction.static.velocity_m_s / final_reconstruction.static.sound_speed_m_s),
        "final_outlet_phase": str(final_reconstruction.static.phase),
        "final_minimum_density_kg_m3": float(np.min(rho_final)),
        "final_minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "final_rho_xv_exact_zero": bool(np.all(U_final[:, 3] == 0.0)),
        "starting_state_sha256": _array_sha256(U_start),
        "final_state_sha256": _array_sha256(U_final),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "stop_diagnostics_keys": sorted(stop_diagnostics),
        "working_vertical_slice_two_l_over_c0_reached": pass_gate,
        "increment_9_full_horizon_gate_passed": pass_gate,
        "outcome": OUTCOME if pass_gate else "INCREMENT_9_STOPPED",
        "finite_compression_flux_applied": bool(step_rows),
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
        root_rows,
        scan_rows,
        density_rows,
        branch_rows,
        U_start,
        U_final,
    )
