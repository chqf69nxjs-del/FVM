from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase


robustness = robustness_v4.robustness
CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
PARENT_NUMERICAL_SOURCE_SHA = "eee113e40911b11c62644609f9b8c57ac85707b4"
EXPECTED_ACCEPTED_STEPS = 336
EXPECTED_STOP_TOKEN = "sign_changes=0"
PRESSURE_OFFSETS_PA = (
    -1.0, -0.1, -0.01, -0.001, -0.0001, -0.00001, -0.000001,
    0.0,
    0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1.0,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


def _signed_characteristic_velocity(
    isentrope: Any,
    pressure_pa: float,
    interior_pressure_pa: float,
    interior_velocity_m_s: float,
) -> float:
    p = float(pressure_pa)
    p_i = float(interior_pressure_pa)
    if p == p_i:
        return float(interior_velocity_m_s)
    low, high = min(p, p_i), max(p, p_i)
    midpoint, half = 0.5 * (high + low), 0.5 * (high - low)
    integral = 0.0
    for node, weight in zip(isentrope.nodes, isentrope.weights, strict=True):
        props = isentrope.props(midpoint + half * float(node))
        integral += float(weight) / (
            float(props["density_kg_m3"])
            * float(props["sound_speed_m_s"])
        )
    integral *= half
    return float(
        interior_velocity_m_s + integral
        if p < p_i
        else interior_velocity_m_s - integral
    )


def _energy_ledger(
    pipe_mass: float,
    b1_mass: float,
    h0_pipe: float,
    pipe_energy: float,
    b1_energy: float,
) -> dict[str, Any]:
    mass_residual = float(pipe_mass - b1_mass)
    energy_residual = float(pipe_energy - b1_energy)
    if pipe_mass <= 0.0 or b1_mass <= 0.0:
        return {
            "compatibility_residual_kg_s": mass_residual,
            "energy_port_residual_W": energy_residual,
            "stagnation_enthalpy_round_trip_residual_J_kg": None,
            "energy_mass_consistency_residual_W": None,
            "energy_allowed_W": None,
            "energy_ledger_passed": False,
        }
    h0_b1 = float(b1_energy / b1_mass)
    h0_residual = float(h0_pipe - h0_b1)
    expected_from_mass = float(h0_pipe * mass_residual)
    consistency = float(energy_residual - expected_from_mass)
    roundoff = float(
        robustness_v4.ENERGY_CONSISTENCY_ROUNDOFF_FACTOR
        * np.finfo(float).eps
        * max(
            abs(pipe_energy),
            abs(b1_energy),
            abs(expected_from_mass),
            1.0,
        )
    )
    h0_allowed_energy = float(
        abs(b1_mass)
        * robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
    )
    consistency_allowed = float(h0_allowed_energy + roundoff)
    total_allowed = float(
        abs(h0_pipe) * robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        + h0_allowed_energy
        + roundoff
    )
    passed = bool(
        abs(h0_residual)
        <= robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
        and abs(consistency) <= consistency_allowed
        and abs(energy_residual) <= total_allowed
    )
    return {
        "compatibility_residual_kg_s": mass_residual,
        "energy_port_residual_W": energy_residual,
        "b1_stagnation_enthalpy_J_kg": h0_b1,
        "stagnation_enthalpy_round_trip_residual_J_kg": h0_residual,
        "energy_expected_from_mass_residual_W": expected_from_mass,
        "energy_mass_consistency_residual_W": consistency,
        "energy_mass_consistency_allowed_W": consistency_allowed,
        "energy_allowed_W": total_allowed,
        "energy_ledger_passed": passed,
    }


def _scan_row(
    *,
    offset_pa: float,
    static: Any,
    isentrope: Any,
    hook: Any,
    area_m2: float,
    allowed_phases: set[str],
    velocity_tolerance: float,
) -> dict[str, Any]:
    pressure = float(static.pressure_pa + offset_pa)
    branch = (
        "RAREFACTION"
        if offset_pa < 0.0
        else "LOCAL_COMPRESSION_CONTINUATION"
        if offset_pa > 0.0
        else "NEUTRAL_ENDPOINT"
    )
    row: dict[str, Any] = {
        "case_id": CASE_ID,
        "branch": branch,
        "pressure_offset_pa": float(offset_pa),
        "pressure_pa": pressure,
        "evaluation_succeeded": False,
    }
    try:
        props = isentrope.props(pressure)
        velocity = _signed_characteristic_velocity(
            isentrope,
            pressure,
            float(static.pressure_pa),
            float(static.velocity_m_s),
        )
        rho = float(props["density_kg_m3"])
        e = float(props["internal_energy_J_kg"])
        h = float(props["enthalpy_J_kg"])
        c = float(props["sound_speed_m_s"])
        phase = str(props["phase"])
        h0 = float(h + 0.5 * velocity * velocity)
        conserved = np.asarray(
            [
                rho,
                rho * velocity,
                rho * (e + 0.5 * velocity * velocity),
                0.0,
            ]
        )
        evaluation = hook.adapter.evaluate(conserved, area_m2)
        if not evaluation.succeeded or evaluation.face is None:
            row.update(
                formal_outcome=evaluation.formal_outcome,
                formal_message=evaluation.formal_message,
                evaluation_failure_stage="B1_ADAPTER",
            )
            return row
        face = evaluation.face
        pipe_mass = float(rho * velocity * area_m2)
        b1_mass = float(face.mass_transfer_outward_kg_s)
        pipe_energy = float(pipe_mass * h0)
        b1_energy = float(face.energy_transfer_outward_W)
        energy = _energy_ledger(
            pipe_mass,
            b1_mass,
            h0,
            pipe_energy,
            b1_energy,
        )
        pipe_momentum = float(pipe_mass * velocity + pressure * area_m2)
        downstream_momentum = float(
            face.advective_momentum_rate_out_N
            + face.discharge_state_pressure_pa * face.open_area_m2
        )
        reaction = float(downstream_momentum - pipe_momentum)
        reaction_residual = float(
            downstream_momentum - pipe_momentum - reaction
        )
        hugoniot_residual = float(
            e
            - float(static.internal_energy_J_kg)
            + 0.5
            * (pressure + float(static.pressure_pa))
            * (1.0 / rho - 1.0 / float(static.density_kg_m3))
        )
        mach = float(velocity / c)
        outward = bool(velocity >= -velocity_tolerance)
        subsonic = bool(0.0 <= mach < 1.0)
        phase_ok = bool(normalize_phase(phase) in allowed_phases)
        p0_ok = bool(
            float(face.stagnation_pressure_pa)
            > float(hook.adapter.back_pressure_pa)
        )
        reaction_ok = bool(
            abs(reaction_residual)
            <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
        )
        state_admissible = bool(
            outward and subsonic and phase_ok and p0_ok and reaction_ok
        )
        residual = float(energy["compatibility_residual_kg_s"])
        within_root_tolerance = bool(
            abs(residual) <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        )
        root_closure_passed = bool(
            state_admissible
            and within_root_tolerance
            and energy["energy_ledger_passed"]
        )
        row.update(
            evaluation_succeeded=True,
            formal_outcome=evaluation.formal_outcome,
            formal_message=evaluation.formal_message,
            temperature_K=float(props["temperature_K"]),
            density_kg_m3=rho,
            specific_volume_m3_kg=float(1.0 / rho),
            internal_energy_J_kg=e,
            enthalpy_J_kg=h,
            entropy_J_kg_K=float(static.entropy_J_kg_K),
            entropy_delta_from_interior_J_kg_K=0.0,
            sound_speed_m_s=c,
            phase=phase,
            velocity_m_s=velocity,
            mach=mach,
            h0_J_kg=h0,
            stagnation_pressure_pa=float(face.stagnation_pressure_pa),
            back_pressure_pa=float(hook.adapter.back_pressure_pa),
            pipe_mass_rate_kg_s=pipe_mass,
            b1_mass_rate_kg_s=b1_mass,
            root_mass_tolerance_kg_s=float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            within_locked_root_mass_tolerance=within_root_tolerance,
            pipe_momentum_port_N=pipe_momentum,
            downstream_stream_pressure_port_N=downstream_momentum,
            restriction_reaction_on_fluid_N=reaction,
            restriction_reaction_ledger_residual_N=reaction_residual,
            pipe_energy_rate_W=pipe_energy,
            b1_energy_rate_W=b1_energy,
            hugoniot_energy_residual_J_kg=hugoniot_residual,
            outward_velocity_passed=outward,
            subsonic_passed=subsonic,
            phase_passed=phase_ok,
            stagnation_pressure_above_back_pressure=p0_ok,
            reaction_ledger_passed=reaction_ok,
            local_candidate_admissible=state_admissible,
            root_closure_passed=root_closure_passed,
            **energy,
        )
        return row
    except Exception as exc:
        row.update(
            formal_outcome=type(exc).__name__,
            formal_message=str(exc),
            evaluation_failure_stage="LOCAL_WAVE_CURVE",
        )
        return row


def _sign(value: float) -> int:
    return -1 if value < 0.0 else 1 if value > 0.0 else 0


def _brackets(
    rows: list[dict[str, Any]],
    *,
    admissible_only: bool,
) -> list[dict[str, float | None]]:
    valid = [
        row
        for row in sorted(
            rows,
            key=lambda item: float(item["pressure_offset_pa"]),
        )
        if row.get("evaluation_succeeded")
        and row.get("compatibility_residual_kg_s") is not None
        and (
            not admissible_only
            or row.get("local_candidate_admissible")
        )
    ]
    result: list[dict[str, float | None]] = []
    for left, right in zip(valid, valid[1:]):
        r0 = float(left["compatibility_residual_kg_s"])
        r1 = float(right["compatibility_residual_kg_s"])
        if (
            _sign(r0) == 0
            or _sign(r1) == 0
            or _sign(r0) != _sign(r1)
        ):
            p0 = float(left["pressure_offset_pa"])
            p1 = float(right["pressure_offset_pa"])
            estimate = (
                None
                if r1 == r0
                else float(p0 - r0 * (p1 - p0) / (r1 - r0))
            )
            result.append(
                {
                    "lower_offset_pa": p0,
                    "upper_offset_pa": p1,
                    "lower_residual_kg_s": r0,
                    "upper_residual_kg_s": r1,
                    "linear_root_offset_estimate_pa": estimate,
                }
            )
    return result
