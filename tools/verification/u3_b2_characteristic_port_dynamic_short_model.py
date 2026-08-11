from __future__ import annotations

from typing import Any

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase


robustness = robustness_v4.robustness


CASE_IDS = (
    "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE",
    "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT",
    "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT",
)
ROOT_QUADRATURE_ORDER = 32
CONNECTED_SCAN_NODE_COUNT = 17
ACCEPTED_STEPS_PER_CASE = 4


class DynamicDiagnosticStop(RuntimeError):
    """Fail-closed stop for a diagnostic condition that is not approved."""


def solve_dynamic_root(
    *,
    contract: dict[str, Any],
    case_id: str,
    state_id: str,
    provider: Any,
    adapter: Any,
    area_m2: float,
    outlet_conserved: np.ndarray,
    solver_time_s: float,
    previous_root_pressure_pa: float | None,
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
        raise DynamicDiagnosticStop(
            f"outlet phase {static.phase!r} is outside {sorted(allowed_phases)}"
        )
    if static.velocity_m_s < -velocity_tolerance:
        raise DynamicDiagnosticStop(
            f"reverse outlet-cell velocity before root solve: {static.velocity_m_s} m/s"
        )

    back_pressure = float(adapter.back_pressure_pa)
    if not static.pressure_pa > back_pressure:
        raise DynamicDiagnosticStop(
            "root domain disappeared because outlet pressure is not above "
            f"back pressure: p_i={static.pressure_pa}, p_back={back_pressure}"
        )

    tolerances = contract["acceptance_tolerances"]
    if abs(reconstruction.enthalpy_round_trip_residual_J_kg) > float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    ) or abs(reconstruction.entropy_round_trip_residual_J_kg_K) > float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    ):
        raise DynamicDiagnosticStop(
            "outlet stagnation-state round trip exceeds locked tolerance"
        )

    diagnostic.QUADRATURE_ORDER = ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))

    def evaluate(pressure_pa: float) -> dict[str, Any]:
        return diagnostic.evaluate_pressure(
            pressure_pa=float(pressure_pa),
            static=static,
            isentrope=isentrope,
            adapter=adapter,
            area_m2=area_m2,
            case_id=case_id,
            state_id=state_id,
        )

    pressures = list(
        np.linspace(
            float(static.pressure_pa),
            back_pressure,
            CONNECTED_SCAN_NODE_COUNT,
        )
    )
    previous = previous_root_pressure_pa
    if previous is not None and back_pressure < previous < static.pressure_pa:
        pressures.append(float(previous))
    pressures = sorted(set(float(value) for value in pressures), reverse=True)

    scan_rows: list[dict[str, Any]] = []
    scan_stop_reason: str | None = None
    for pressure in pressures:
        row = evaluate(pressure)
        if not row.get("evaluation_succeeded"):
            scan_stop_reason = (
                f"inadmissible connected scan node p={pressure}: "
                f"{row.get('formal_outcome')} {row.get('formal_message')}"
            )
            break
        mach = float(row["mach"])
        if not 0.0 <= mach < 1.0:
            scan_stop_reason = (
                f"connected scan left subsonic branch at p={pressure}, Mach={mach}"
            )
            break
        scan_rows.append(row)

    if len(scan_rows) < 2:
        raise DynamicDiagnosticStop(
            "connected subsonic scan has fewer than two admissible nodes; "
            f"stop={scan_stop_reason}"
        )
    residuals = [float(row["residual_kg_s"]) for row in scan_rows]
    monotone = all(
        residuals[index + 1] >= residuals[index]
        for index in range(len(residuals) - 1)
    )
    brackets = diagnostic.find_sign_change_brackets(scan_rows)
    if not monotone:
        raise DynamicDiagnosticStop(
            "connected residual scan is non-monotone; unique root branch is inconclusive"
        )
    if len(brackets) != 1:
        raise DynamicDiagnosticStop(
            "connected subsonic scan did not retain exactly one root branch: "
            f"sign_changes={len(brackets)}, stop={scan_stop_reason}"
        )

    root = robustness._bisection_root(
        lower_pressure_pa=brackets[0][0],
        upper_pressure_pa=brackets[0][1],
        evaluate=evaluate,
    )
    completed = robustness_v4._complete_root_row_v4(
        root=root,
        evaluate=evaluate,
        adapter=adapter,
        area_m2=area_m2,
        quadrature_order=ROOT_QUADRATURE_ORDER,
    )
    merged = dict(root)
    merged.update(completed)

    if abs(float(merged["root_mass_residual_kg_s"])) > float(
        robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    ):
        raise DynamicDiagnosticStop("root mass residual exceeds retained limit")
    if float(merged["local_residual_slope_kg_s_Pa"]) >= 0.0:
        raise DynamicDiagnosticStop("root local residual slope is not negative")
    if not 0.0 <= float(merged["mach"]) < 1.0:
        raise DynamicDiagnosticStop("root is outside the subsonic branch")
    if float(merged["velocity_m_s"]) < -velocity_tolerance:
        raise DynamicDiagnosticStop("root velocity is reverse-directed")
    if not bool(merged["stagnation_enthalpy_round_trip_passed"]):
        raise DynamicDiagnosticStop(
            "root stagnation-enthalpy round trip exceeds locked B2 tolerance: "
            f"residual={merged['stagnation_enthalpy_round_trip_residual_J_kg']!r} "
            "J/kg, "
            f"limit={merged['locked_stagnation_enthalpy_round_trip_absolute_J_kg']!r} "
            "J/kg"
        )
    if not bool(merged["energy_mass_consistency_passed"]):
        raise DynamicDiagnosticStop(
            "root energy/mass ledger decomposition does not close: "
            f"residual={merged['energy_mass_consistency_residual_W']!r} W, "
            f"allowed={merged['energy_mass_consistency_allowed_W']!r} W"
        )
    if not bool(merged["energy_port_closure_passed"]):
        raise DynamicDiagnosticStop(
            "root energy-port ledger does not close under retained mass-root and "
            "locked h0 round-trip tolerances: "
            f"pipe={merged['pipe_energy_rate_W']!r} W, "
            f"b1={merged['b1_energy_rate_W']!r} W, "
            f"residual={merged['energy_port_residual_W']!r} W, "
            f"allowed={merged['energy_allowed_from_locked_root_and_h0_tolerances_W']!r} W, "
            f"p_P={merged['pressure_pa']!r} Pa, "
            f"u_P={merged['velocity_m_s']!r} m/s, "
            f"m_dot={merged['pipe_mass_rate_kg_s']!r} kg/s, "
            f"h0={merged['h0_J_kg']!r} J/kg"
        )
    if abs(float(merged["momentum_ledger_residual_N"])) > float(
        robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    ):
        raise DynamicDiagnosticStop("restriction reaction ledger does not close")

    mass_rate = float(merged["pipe_mass_rate_kg_s"])
    velocity = float(merged["velocity_m_s"])
    pressure = float(merged["pressure_pa"])
    h0 = float(merged["h0_J_kg"])
    flux = np.asarray(
        [
            mass_rate / area_m2,
            (mass_rate * velocity + pressure * area_m2) / area_m2,
            mass_rate * h0 / area_m2,
            0.0,
        ],
        dtype=float,
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
        "connected_scan_base_node_count": CONNECTED_SCAN_NODE_COUNT,
        "connected_scan_requested_nodes": len(pressures),
        "connected_scan_admissible_subsonic_nodes": len(scan_rows),
        "connected_scan_lowest_pressure_pa": float(scan_rows[-1]["pressure_pa"]),
        "connected_scan_stop_reason": scan_stop_reason,
        "connected_scan_residual_monotone": monotone,
        "connected_scan_sign_change_count": len(brackets),
        "root": merged,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
    }
