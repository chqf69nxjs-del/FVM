from __future__ import annotations

from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
from u3_b2_characteristic_port_dynamic_short_metrics import build_step_row, inventory
from u3_b2_a1_finite_compression_hugoniot_full_horizon_support import TARGET_TIME_S


def advance_one_step(
    *,
    solver: Any,
    hook: Any,
    grid: Any,
    provider: Any,
    initial: dict[str, float],
    cumulative_expected_delta: np.ndarray,
    contract: dict[str, Any],
    state_id: str,
    requested_step: int,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    np.ndarray,
]:
    before = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    candidate_dt = float(solver.compute_dt())
    dt_limits = dict(hook.last_dt_limits)
    if hook.root_context is None:
        raise base.FiniteCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE", "Hugoniot root was not prepared by compute_dt"
        )
    context = hook.root_context
    if context["branch_classification"] != base.BRANCH:
        raise base.FiniteCompressionShortRunStop(
            "UNAPPROVED_BRANCH", f"unexpected branch {context['branch_classification']!r}"
        )
    root_row = base._root_evidence_row(
        context=context, requested_solver_step=requested_step
    )
    scan_rows = base._flatten_rows(
        rows=list(context["hugoniot_scan_rows"]),
        requested_solver_step=requested_step,
        solver_time_s=float(context["solver_time_s"]),
        row_kind="HUGONIOT_FIXED_SCAN",
    )
    density_rows = base._flatten_rows(
        rows=list(context["hugoniot_density_search_rows"]),
        requested_solver_step=requested_step,
        solver_time_s=float(context["solver_time_s"]),
        row_kind="HUGONIOT_DENSITY_SEARCH",
    )
    remaining_before = float(TARGET_TIME_S - solver.t)
    requested_dt = float(min(candidate_dt, remaining_before))
    clipped_to_target = bool(remaining_before <= candidate_dt)
    flux_left, _ = solver._base_fluxes()
    left_flux = np.asarray(flux_left[0], dtype=float)
    right_flux = np.asarray(hook.flux, dtype=float)
    accepted_dt = float(solver.step(requested_dt))
    hook.accept_current_root()
    after = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    expected_step_delta = (
        accepted_dt * grid.geometry.area_m2 * (left_flux - right_flux)
    )
    cumulative_expected_delta = cumulative_expected_delta + expected_step_delta
    primitive_after = solver.primitive()
    post_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
    row = build_step_row(
        case_id=base.CASE_ID,
        state_id=state_id,
        requested_step=requested_step,
        solver=solver,
        hook=hook,
        root_context=context,
        dt_limits=dt_limits,
        candidate_dt=requested_dt,
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
    rho_after = np.asarray(solver.U[:, 0], dtype=float)
    velocity_after = np.asarray(solver.U[:, 1] / rho_after, dtype=float)
    internal_after = np.asarray(
        solver.U[:, 2] / rho_after - 0.5 * velocity_after**2, dtype=float
    )
    outlet_after = post_reconstruction.static
    root = context["root"]
    row.update(
        {
            "branch_classification": base.BRANCH,
            "finite_compression_model": "GENERAL_EOS_HUGONIOT",
            "candidate_dt_before_target_clip_s": candidate_dt,
            "target_remaining_before_step_s": remaining_before,
            "requested_dt_after_target_clip_s": requested_dt,
            "step_clipped_to_target": clipped_to_target,
            "target_time_s": TARGET_TIME_S,
            "root_requested_chi": float(root["requested_chi"]),
            "root_realized_chi": float(root["realized_chi"]),
            "approved_weak_compression_chi_limit": base.WEAK_COMPRESSION_CHI_LIMIT,
            "diagnostic_chi_cap": base.DIAGNOSTIC_CHI_CAP,
            "root_pressure_offset_pa": float(root["p_P_minus_p_i_pa"]),
            "root_density_kg_m3": float(root["density_kg_m3"]),
            "root_temperature_K": float(root["temperature_K"]),
            "root_entropy_delta_J_kg_K": float(root["entropy_delta_J_kg_K"]),
            "root_hugoniot_energy_residual_J_kg": float(
                root["hugoniot_energy_residual_J_kg"]
            ),
            "root_hugoniot_enthalpy_residual_J_kg": float(
                root["hugoniot_enthalpy_residual_J_kg"]
            ),
            "root_hugoniot_identity_accounted_passed": bool(
                root["hugoniot_identity_accounted_passed"]
            ),
            "root_lax_1_shock_passed": bool(root["lax_1_shock_passed"]),
            "root_shock_speed_m_s": float(root["shock_speed_m_s"]),
            "root_lambda_1_candidate_m_s": float(root["lambda_1_candidate_m_s"]),
            "root_lambda_1_interior_m_s": float(root["lambda_1_interior_m_s"]),
            "hugoniot_scan_monotone_nonincreasing": bool(
                context["hugoniot_scan_monotone_nonincreasing"]
            ),
            "hugoniot_scan_sign_change_count": int(
                context["hugoniot_scan_sign_change_count"]
            ),
            "root_gate_passed": bool(context["root_gate_passed"]),
            "all_conserved_finite_after_step": bool(np.all(np.isfinite(solver.U))),
            "minimum_density_after_step_kg_m3": float(np.min(rho_after)),
            "minimum_internal_energy_after_step_J_kg": float(np.min(internal_after)),
            "outlet_mach_after_step": float(
                outlet_after.velocity_m_s / outlet_after.sound_speed_m_s
            ),
            "finite_compression_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
    )
    per_step_gate = bool(
        bool(context["root_gate_passed"])
        and bool(row["step_passed"])
        and accepted_dt > 0.0
        and int(solver.step_count) == requested_step
        and bool(row["all_conserved_finite_after_step"])
        and float(row["minimum_density_after_step_kg_m3"]) > 0.0
        and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
        and not bool(row["reverse_flow_guard_triggered"])
        and not bool(row["reverse_velocity_detected"])
        and float(row["outlet_velocity_after_step_m_s"]) >= 0.0
        and 0.0 <= float(row["outlet_mach_after_step"]) < 1.0
        and bool(row["outlet_phase_passed"])
        and bool(row["rho_xv_exact_zero"])
        and base.WEAK_COMPRESSION_CHI_LIMIT
        < float(root["requested_chi"])
        <= base.DIAGNOSTIC_CHI_CAP
    )
    row["increment_9_per_step_gate_passed"] = per_step_gate
    if not per_step_gate:
        raise base.FiniteCompressionShortRunStop(
            "POST_STEP_GATE_FAILURE",
            f"accepted solver step {requested_step} failed the Increment 9 per-step gate",
            {"step_row": row},
        )
    branch_row = {
        "requested_solver_step": requested_step,
        "solver_step_count": int(solver.step_count),
        "time_after_s": float(solver.t),
        "branch_classification": base.BRANCH,
        "accepted": True,
        "step_clipped_to_target": clipped_to_target,
    }
    return (
        row,
        root_row,
        scan_rows,
        density_rows,
        branch_row,
        cumulative_expected_delta,
    )
