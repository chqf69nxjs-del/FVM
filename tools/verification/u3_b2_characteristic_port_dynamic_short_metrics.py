from __future__ import annotations

from typing import Any

import numpy as np

import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
from liquid_gas_transient.state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase
from u3_b2_characteristic_port_dynamic_short_model import ACCEPTED_STEPS_PER_CASE


robustness = robustness_v4.robustness


def inventory(U: np.ndarray, *, dx: float, area_m2: float) -> dict[str, float]:
    volume = float(dx) * float(area_m2)
    return {
        "mass_kg": float(np.sum(U[:, IDX_RHO]) * volume),
        "momentum_kg_m_s": float(np.sum(U[:, IDX_MOM]) * volume),
        "energy_J": float(np.sum(U[:, IDX_RHOE]) * volume),
        "vapor_mass_kg": float(np.sum(U[:, IDX_RHO_XV]) * volume),
    }


def _residual_passed(
    residual: float,
    *,
    absolute: float,
    relative: float,
    scale_values: tuple[float, ...],
) -> bool:
    scale = max((abs(float(value)) for value in scale_values), default=0.0)
    return bool(abs(float(residual)) <= max(float(absolute), float(relative) * scale))


def build_step_row(
    *,
    case_id: str,
    state_id: str,
    requested_step: int,
    solver: Any,
    hook: Any,
    root_context: dict[str, Any],
    dt_limits: dict[str, float],
    candidate_dt: float,
    accepted_dt: float,
    before: dict[str, float],
    after: dict[str, float],
    initial: dict[str, float],
    expected_step_delta: np.ndarray,
    cumulative_expected_delta: np.ndarray,
    left_flux: np.ndarray,
    right_flux: np.ndarray,
    post_reconstruction: Any,
    primitive_after: Any,
    tolerances: dict[str, Any],
) -> dict[str, Any]:
    root = root_context["root"]
    step_residual = {
        "mass": after["mass_kg"] - before["mass_kg"] - float(expected_step_delta[IDX_RHO]),
        "momentum": (
            after["momentum_kg_m_s"]
            - before["momentum_kg_m_s"]
            - float(expected_step_delta[IDX_MOM])
        ),
        "energy": after["energy_J"] - before["energy_J"] - float(expected_step_delta[IDX_RHOE]),
    }
    cumulative_residual = {
        "mass": after["mass_kg"] - initial["mass_kg"] - float(cumulative_expected_delta[IDX_RHO]),
        "momentum": (
            after["momentum_kg_m_s"]
            - initial["momentum_kg_m_s"]
            - float(cumulative_expected_delta[IDX_MOM])
        ),
        "energy": after["energy_J"] - initial["energy_J"] - float(cumulative_expected_delta[IDX_RHOE]),
    }
    passed = {
        "step_mass": _residual_passed(
            step_residual["mass"],
            absolute=float(tolerances["mass_inventory_absolute_kg"]),
            relative=float(tolerances["mass_inventory_relative"]),
            scale_values=(before["mass_kg"], after["mass_kg"], float(expected_step_delta[IDX_RHO])),
        ),
        "step_momentum": _residual_passed(
            step_residual["momentum"],
            absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
            relative=float(tolerances["momentum_inventory_relative"]),
            scale_values=(
                before["momentum_kg_m_s"],
                after["momentum_kg_m_s"],
                float(expected_step_delta[IDX_MOM]),
            ),
        ),
        "step_energy": _residual_passed(
            step_residual["energy"],
            absolute=float(tolerances["energy_inventory_absolute_J"]),
            relative=float(tolerances["energy_inventory_relative"]),
            scale_values=(before["energy_J"], after["energy_J"], float(expected_step_delta[IDX_RHOE])),
        ),
        "cumulative_mass": _residual_passed(
            cumulative_residual["mass"],
            absolute=float(tolerances["mass_inventory_absolute_kg"]),
            relative=float(tolerances["mass_inventory_relative"]),
            scale_values=(initial["mass_kg"], after["mass_kg"], float(cumulative_expected_delta[IDX_RHO])),
        ),
        "cumulative_momentum": _residual_passed(
            cumulative_residual["momentum"],
            absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
            relative=float(tolerances["momentum_inventory_relative"]),
            scale_values=(
                initial["momentum_kg_m_s"],
                after["momentum_kg_m_s"],
                float(cumulative_expected_delta[IDX_MOM]),
            ),
        ),
        "cumulative_energy": _residual_passed(
            cumulative_residual["energy"],
            absolute=float(tolerances["energy_inventory_absolute_J"]),
            relative=float(tolerances["energy_inventory_relative"]),
            scale_values=(initial["energy_J"], after["energy_J"], float(cumulative_expected_delta[IDX_RHOE])),
        ),
    }
    vapor_exact = bool(
        np.all(solver.U[:, IDX_RHO_XV] == 0.0)
        and after["vapor_mass_kg"] == float(tolerances["vapor_mass_exact_zero_absolute_kg"])
    )
    outlet_phase_passed = bool(
        normalize_phase(post_reconstruction.static.phase) in hook.allowed_phases
    )
    reverse_velocity = bool(float(primitive_after.u[-1]) < -hook.velocity_tolerance)
    trial_dts = list(hook.trial_dts_s)

    row: dict[str, Any] = {
        "case_id": case_id,
        "state_id": state_id,
        "requested_step": requested_step,
        "accepted_step": True,
        "solver_step_count": solver.step_count,
        "time_before_s": float(root_context["solver_time_s"]),
        "time_after_s": float(solver.t),
        "cfl_candidate_dt_s": float(dt_limits["candidate_dt_s"]),
        "mass_removal_dt_s": float(dt_limits["mass_removal_dt_s"]),
        "energy_removal_dt_s": float(dt_limits["energy_removal_dt_s"]),
        "limited_candidate_dt_s": candidate_dt,
        "accepted_dt_s": accepted_dt,
        "halving_count": max(len(trial_dts) - 1, 0),
        "trial_dts_s": trial_dts,
        "interior_pressure_before_root_pa": float(root_context["interior_pressure_pa"]),
        "interior_temperature_before_root_K": float(root_context["interior_temperature_K"]),
        "interior_density_before_root_kg_m3": float(root_context["interior_density_kg_m3"]),
        "interior_velocity_before_root_m_s": float(root_context["interior_velocity_m_s"]),
        "interior_sound_speed_before_root_m_s": float(root_context["interior_sound_speed_m_s"]),
        "interior_mach_before_root": float(root_context["interior_mach"]),
        "interior_entropy_before_root_J_kg_K": float(root_context["interior_entropy_J_kg_K"]),
        "interior_phase_before_root": root_context["interior_phase"],
        "interior_h0_round_trip_residual_J_kg": float(
            root_context["interior_h0_round_trip_residual_J_kg"]
        ),
        "interior_s0_round_trip_residual_J_kg_K": float(
            root_context["interior_s0_round_trip_residual_J_kg_K"]
        ),
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(root["local_residual_slope_kg_s_Pa"]),
        "b1_formal_outcome": root["formal_outcome"],
        "b1_effective_velocity_m_s": float(root["b1_effective_velocity_m_s"]),
        "b1_discharge_state_pressure_pa": float(root["b1_discharge_state_pressure_pa"]),
        "b1_critical_pressure_pa": root["b1_critical_pressure_pa"],
        "pipe_side_momentum_port_N": float(root["pipe_momentum_port_N"]),
        "downstream_stream_pressure_port_N": float(root["downstream_stream_pressure_port_N"]),
        "restriction_reaction_on_fluid_N": float(root["restriction_reaction_on_fluid_N"]),
        "restriction_reaction_ledger_residual_N": float(root["momentum_ledger_residual_N"]),
        "pipe_energy_rate_W": float(root["pipe_energy_rate_W"]),
        "b1_energy_rate_W": float(root["b1_energy_rate_W"]),
        "energy_port_residual_W": float(root["energy_port_residual_W"]),
        "pipe_stagnation_enthalpy_J_kg": float(
            root["pipe_stagnation_enthalpy_J_kg"]
        ),
        "b1_stagnation_enthalpy_from_transfer_J_kg": float(
            root["b1_stagnation_enthalpy_from_transfer_J_kg"]
        ),
        "stagnation_enthalpy_round_trip_residual_J_kg": float(
            root["stagnation_enthalpy_round_trip_residual_J_kg"]
        ),
        "locked_stagnation_enthalpy_round_trip_absolute_J_kg": float(
            root["locked_stagnation_enthalpy_round_trip_absolute_J_kg"]
        ),
        "energy_expected_from_mass_residual_W": float(
            root["energy_expected_from_mass_residual_W"]
        ),
        "energy_mass_consistency_residual_W": float(
            root["energy_mass_consistency_residual_W"]
        ),
        "energy_consistency_roundoff_allowed_W": float(
            root["energy_consistency_roundoff_allowed_W"]
        ),
        "energy_h0_round_trip_allowed_W": float(
            root["energy_h0_round_trip_allowed_W"]
        ),
        "energy_mass_consistency_allowed_W": float(
            root["energy_mass_consistency_allowed_W"]
        ),
        "energy_allowed_from_locked_root_and_h0_tolerances_W": float(
            root["energy_allowed_from_locked_root_and_h0_tolerances_W"]
        ),
        "stagnation_enthalpy_round_trip_passed": bool(
            root["stagnation_enthalpy_round_trip_passed"]
        ),
        "energy_mass_consistency_passed": bool(
            root["energy_mass_consistency_passed"]
        ),
        "energy_port_closure_passed": bool(root["energy_port_closure_passed"]),
        "connected_scan_base_node_count": int(root_context["connected_scan_base_node_count"]),
        "connected_scan_requested_nodes": int(root_context["connected_scan_requested_nodes"]),
        "connected_scan_admissible_subsonic_nodes": int(
            root_context["connected_scan_admissible_subsonic_nodes"]
        ),
        "connected_scan_lowest_pressure_pa": float(root_context["connected_scan_lowest_pressure_pa"]),
        "connected_scan_stop_reason": root_context["connected_scan_stop_reason"],
        "connected_scan_residual_monotone": bool(root_context["connected_scan_residual_monotone"]),
        "connected_scan_sign_change_count": int(root_context["connected_scan_sign_change_count"]),
        "left_external_mass_flux_kg_m2_s": float(left_flux[IDX_RHO]),
        "right_external_mass_flux_kg_m2_s": float(right_flux[IDX_RHO]),
        "left_external_momentum_flux_pa": float(left_flux[IDX_MOM]),
        "right_external_momentum_flux_pa": float(right_flux[IDX_MOM]),
        "left_external_energy_flux_W_m2": float(left_flux[IDX_RHOE]),
        "right_external_energy_flux_W_m2": float(right_flux[IDX_RHOE]),
        "mass_before_kg": before["mass_kg"],
        "mass_after_kg": after["mass_kg"],
        "step_mass_residual_kg": step_residual["mass"],
        "cumulative_mass_residual_kg": cumulative_residual["mass"],
        "momentum_before_kg_m_s": before["momentum_kg_m_s"],
        "momentum_after_kg_m_s": after["momentum_kg_m_s"],
        "step_momentum_residual_kg_m_s": step_residual["momentum"],
        "cumulative_momentum_residual_kg_m_s": cumulative_residual["momentum"],
        "energy_before_J": before["energy_J"],
        "energy_after_J": after["energy_J"],
        "step_energy_residual_J": step_residual["energy"],
        "cumulative_energy_residual_J": cumulative_residual["energy"],
        "vapor_mass_after_kg": after["vapor_mass_kg"],
        "rho_xv_exact_zero": vapor_exact,
        "outlet_pressure_after_step_pa": float(primitive_after.p[-1]),
        "outlet_velocity_after_step_m_s": float(primitive_after.u[-1]),
        "outlet_phase_after_step": post_reconstruction.static.phase,
        "outlet_phase_passed": outlet_phase_passed,
        "reverse_velocity_detected": reverse_velocity,
        "reverse_flow_guard_triggered": False,
        "guard_status": "NOT_TRIGGERED",
        **{f"{name}_passed": value for name, value in passed.items()},
    }
    row["step_passed"] = bool(
        all(passed.values())
        and vapor_exact
        and outlet_phase_passed
        and not reverse_velocity
        and abs(float(root["root_mass_residual_kg_s"]))
        <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
        and 0.0 <= float(root["mach"]) < 1.0
        and bool(root["stagnation_enthalpy_round_trip_passed"])
        and bool(root["energy_mass_consistency_passed"])
        and bool(root["energy_port_closure_passed"])
        and abs(float(root["momentum_ledger_residual_N"]))
        <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    )
    return row


def summarize_case(
    *,
    case_id: str,
    state_id: str,
    rows: list[dict[str, Any]],
    stop_reason: str | None,
) -> dict[str, Any]:
    accepted = [row for row in rows if row.get("accepted_step") is True]
    complete = [row for row in accepted if "root_mach" in row]
    passed = bool(
        stop_reason is None
        and len(accepted) == ACCEPTED_STEPS_PER_CASE
        and len(complete) == ACCEPTED_STEPS_PER_CASE
        and all(row.get("step_passed") is True for row in accepted)
    )

    def maximum(key: str, *, absolute: bool = False) -> float | None:
        values = [float(row[key]) for row in complete]
        if absolute:
            values = [abs(value) for value in values]
        return max(values) if values else None

    return {
        "case_id": case_id,
        "state_id": state_id,
        "requested_accepted_steps": ACCEPTED_STEPS_PER_CASE,
        "accepted_steps_completed": len(accepted),
        "b1_outcome_sequence": [
            str(row.get("b1_formal_outcome", "NOT_RECORDED")) for row in accepted
        ],
        "maximum_root_mach": maximum("root_mach"),
        "minimum_root_velocity_m_s": (
            min(float(row["root_velocity_m_s"]) for row in complete)
            if complete
            else None
        ),
        "minimum_outlet_velocity_after_step_m_s": (
            min(float(row["outlet_velocity_after_step_m_s"]) for row in complete)
            if complete
            else None
        ),
        "maximum_absolute_cumulative_mass_residual_kg": maximum(
            "cumulative_mass_residual_kg", absolute=True
        ),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": maximum(
            "cumulative_momentum_residual_kg_m_s", absolute=True
        ),
        "maximum_absolute_cumulative_energy_residual_J": maximum(
            "cumulative_energy_residual_J", absolute=True
        ),
        "maximum_absolute_root_stagnation_enthalpy_round_trip_residual_J_kg": maximum(
            "stagnation_enthalpy_round_trip_residual_J_kg", absolute=True
        ),
        "maximum_absolute_root_energy_mass_consistency_residual_W": maximum(
            "energy_mass_consistency_residual_W", absolute=True
        ),
        "maximum_absolute_root_energy_port_residual_W": maximum(
            "energy_port_residual_W", absolute=True
        ),
        "minimum_root_energy_allowed_from_locked_tolerances_W": (
            min(
                float(
                    row[
                        "energy_allowed_from_locked_root_and_h0_tolerances_W"
                    ]
                )
                for row in complete
            )
            if complete
            else None
        ),
        "all_root_stagnation_enthalpy_round_trips_pass": bool(
            complete
            and all(
                row["stagnation_enthalpy_round_trip_passed"] is True
                for row in complete
            )
        ),
        "all_root_energy_mass_consistency_checks_pass": bool(
            complete
            and all(
                row["energy_mass_consistency_passed"] is True
                for row in complete
            )
        ),
        "all_root_energy_ports_close": bool(
            complete
            and all(row["energy_port_closure_passed"] is True for row in complete)
        ),
        "maximum_halving_count": (
            max(int(row["halving_count"]) for row in complete) if complete else None
        ),
        "stop_reason": stop_reason,
        "dynamic_short_case_passed": passed,
    }
