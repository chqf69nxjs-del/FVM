"""Locked U3 B2 single-phase finite-pipe execution layer.

This module advances the production :class:`FvmSolver` for the three locked
single-phase finite-pipe families after the B2 discharge-face Adapter has been
accepted.  It intentionally does not import the independent B2 Reference.  The
Reference is used only by a later authoritative comparison/evidence layer.

The scope remains software Verification only.  It does not approve two-phase
critical discharge, Physical Validation, design use, or production activation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from . import u3_b1_critical_state_adapter as b1_adapter
from .boundary import ReflectiveBoundary, TransmissiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .solver import FvmSolver
from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, inventory
from .u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    FaceFluxResult,
    SUCCESS_CHOKED_FACE_MAPPING,
    SUCCESS_UNCHOKED_FACE_MAPPING,
    U3B2FvmDischargeAdapter,
    adapter_for_case,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
)

SCHEMA_VERSION = "stage7_u3_b2_finite_pipe_baseline_v1"
EXTENSION_SCHEMA_VERSION = (
    "stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1"
)
SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING = (
    "SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING"
)
SUCCESS_FIXED_MESH_CFL_CHARACTERIZATION = (
    "SUCCESS_FIXED_MESH_CFL_CHARACTERIZATION"
)
ACOUSTIC_EVENT_NOT_RESOLVED = "ACOUSTIC_EVENT_NOT_RESOLVED"
FINITE_PIPE_INVENTORY_CLOSURE_FAILURE = "FINITE_PIPE_INVENTORY_CLOSURE_FAILURE"
FINITE_PIPE_FACE_REGIME_FAILURE = "FINITE_PIPE_FACE_REGIME_FAILURE"

BASELINE_CASE_IDS = (
    "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE",
    "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT",
    "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT",
)
LIQUID_CASE_ID = BASELINE_CASE_IDS[0]


@dataclass(frozen=True)
class FinitePipeRun:
    summary: dict[str, Any]
    step_history: tuple[dict[str, Any], ...]
    probe_history: tuple[dict[str, Any], ...]
    acoustic_events: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class FinitePipePackage:
    runs: tuple[FinitePipeRun, ...]
    summary: dict[str, Any]


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    payload = [dict(row) for row in rows]
    if not payload:
        raise ValueError(f"No rows supplied for {path.name}")
    fieldnames: list[str] = []
    for row in payload:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_extension_contract(path: str | Path) -> dict[str, Any]:
    extension = json.loads(Path(path).read_text(encoding="utf-8"))
    if extension.get("schema_version") != EXTENSION_SCHEMA_VERSION:
        raise ValueError("unexpected U3 B2 event/provenance contract schema")
    if extension.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B2 event/provenance contract is not locked")
    return extension


def _case(contract: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    for row in contract["benchmark_cases"]:
        if str(row["case_id"]) == case_id:
            return dict(row)
    raise KeyError(case_id)


def _family(contract: Mapping[str, Any], state_id: str) -> dict[str, Any]:
    for row in contract["fixed_state_families"]:
        if str(row["state_id"]) == state_id:
            return dict(row)
    raise KeyError(state_id)


def _allowed_error(scale: float, absolute: float, relative: float) -> float:
    return max(float(absolute), float(relative) * abs(float(scale)))


def _relative_error(actual: float, expected: float) -> float:
    return abs(float(actual) - float(expected)) / max(abs(float(expected)), 1.0e-300)


def _probe_entries(extension: Mapping[str, Any], cells: int) -> tuple[dict[str, Any], ...]:
    maps = extension["acoustic_event_detection"]["spatial_probe_sampling"][
        "fixed_mesh_probe_map"
    ]
    for row in maps:
        if int(row["cells"]) == int(cells):
            entries = tuple(dict(entry) for entry in row["entries"])
            if len(entries) != 3:
                raise ValueError(f"cells={cells}: expected three locked probe entries")
            return entries
    raise KeyError(f"No locked probe map for cells={cells}")


def sample_locked_probes(
    *,
    primitive: Any,
    extension: Mapping[str, Any],
    run_id: str,
    case_id: str,
    state_id: str,
    cells: int,
    cfl: float,
    step: int,
    time_s: float,
) -> tuple[dict[str, Any], ...]:
    pressure = np.asarray(primitive.p, dtype=float)
    velocity = np.asarray(primitive.u, dtype=float)
    if pressure.shape != (cells,) or velocity.shape != (cells,):
        raise ValueError("primitive pressure/velocity arrays do not match cells")
    rows: list[dict[str, Any]] = []
    for entry in _probe_entries(extension, cells):
        left = int(entry["left_internal_index"])
        right = int(entry["right_internal_index"])
        weight = float(entry["lambda"])
        if not (0 <= left < right < cells):
            raise ValueError("locked probe bracket lies outside internal cells")
        p_probe = (1.0 - weight) * pressure[left] + weight * pressure[right]
        u_probe = (1.0 - weight) * velocity[left] + weight * velocity[right]
        rows.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "state_id": state_id,
                "cells": cells,
                "cfl": float(cfl),
                "step": int(step),
                "time_s": float(time_s),
                "probe_normalized_position": float(entry["xi_probe"]),
                "left_internal_index": left,
                "left_center_xi": float(entry["left_center_xi"]),
                "right_internal_index": right,
                "right_center_xi": float(entry["right_center_xi"]),
                "interpolation_weight": weight,
                "pressure_pa": float(p_probe),
                "axial_velocity_m_s": float(u_probe),
            }
        )
    return tuple(rows)


def detect_acoustic_event(
    samples: Sequence[Mapping[str, Any]],
    *,
    event_kind: str,
    reference_time_s: float,
    window_half_width_s: float,
    relative_tolerance: float,
) -> dict[str, Any]:
    if event_kind not in {"direct", "reflected"}:
        raise ValueError("event_kind must be direct or reflected")
    ordered = sorted(samples, key=lambda row: float(row["time_s"]))
    if len(ordered) < 3:
        return {
            "event_kind": event_kind,
            "formal_outcome": ACOUSTIC_EVENT_NOT_RESOLVED,
            "candidate_count": 0,
            "reference_time_s": float(reference_time_s),
            "detected_time_s": None,
            "relative_arrival_error": None,
            "pressure_delta_pa": None,
            "velocity_delta_m_s": None,
            "pressure_sign_passed": False,
            "velocity_sign_passed": False,
            "arrival_tolerance_passed": False,
        }

    lower = float(reference_time_s) - float(window_half_width_s)
    upper = float(reference_time_s) + float(window_half_width_s)
    candidates: list[tuple[float, float, int, float, float]] = []
    for index in range(1, len(ordered) - 1):
        previous = ordered[index - 1]
        current = ordered[index]
        following = ordered[index + 1]
        t_prev = float(previous["time_s"])
        t_next = float(following["time_s"])
        if not (lower <= t_prev <= upper and lower <= t_next <= upper):
            continue
        denominator = t_next - t_prev
        if denominator <= 0.0:
            continue
        p_delta = float(following["pressure_pa"]) - float(previous["pressure_pa"])
        u_delta = float(following["axial_velocity_m_s"]) - float(
            previous["axial_velocity_m_s"]
        )
        slope = p_delta / denominator
        candidates.append((slope, float(current["time_s"]), index, p_delta, u_delta))

    if not candidates:
        return {
            "event_kind": event_kind,
            "formal_outcome": ACOUSTIC_EVENT_NOT_RESOLVED,
            "candidate_count": 0,
            "reference_time_s": float(reference_time_s),
            "detected_time_s": None,
            "relative_arrival_error": None,
            "pressure_delta_pa": None,
            "velocity_delta_m_s": None,
            "pressure_sign_passed": False,
            "velocity_sign_passed": False,
            "arrival_tolerance_passed": False,
        }

    # The locked rule selects the minimum centered pressure slope, with the
    # earliest time as the deterministic tie-breaker.
    slope, detected_time, index, p_delta, u_delta = min(
        candidates, key=lambda item: (item[0], item[1])
    )
    pressure_sign = p_delta < 0.0
    velocity_sign = u_delta > 0.0 if event_kind == "direct" else u_delta < 0.0
    arrival_error = _relative_error(detected_time, reference_time_s)
    arrival_pass = arrival_error <= float(relative_tolerance)
    passed = pressure_sign and velocity_sign and arrival_pass
    return {
        "event_kind": event_kind,
        "formal_outcome": (
            SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
            if passed
            else ACOUSTIC_EVENT_NOT_RESOLVED
        ),
        "candidate_count": len(candidates),
        "selected_sample_index": int(index),
        "centered_pressure_slope_pa_s": float(slope),
        "reference_time_s": float(reference_time_s),
        "detected_time_s": float(detected_time),
        "relative_arrival_error": float(arrival_error),
        "pressure_delta_pa": float(p_delta),
        "velocity_delta_m_s": float(u_delta),
        "pressure_sign_passed": bool(pressure_sign),
        "velocity_sign_passed": bool(velocity_sign),
        "arrival_tolerance_passed": bool(arrival_pass),
    }


def _event_rows(
    *,
    probe_history: Sequence[Mapping[str, Any]],
    run_id: str,
    case_id: str,
    state_id: str,
    cells: int,
    cfl: float,
    length_m: float,
    initial_sound_speed_m_s: float,
    extension: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    detection = extension["acoustic_event_detection"]
    half_width = float(detection["expected_window_half_width_L_over_c0"]) * (
        length_m / initial_sound_speed_m_s
    )
    tolerances = contract["acceptance_tolerances"]
    direct_tolerance = float(tolerances["direct_rarefaction_arrival_relative"])
    reflected_tolerance = float(tolerances["reflected_rarefaction_arrival_relative"])
    grouped: dict[float, list[Mapping[str, Any]]] = {}
    for row in probe_history:
        grouped.setdefault(float(row["probe_normalized_position"]), []).append(row)

    events: list[dict[str, Any]] = []
    for xi in sorted(grouped):
        direct_reference = (1.0 - xi) * length_m / initial_sound_speed_m_s
        reflected_reference = (1.0 + xi) * length_m / initial_sound_speed_m_s
        for kind, reference_time, tolerance in (
            ("direct", direct_reference, direct_tolerance),
            ("reflected", reflected_reference, reflected_tolerance),
        ):
            result = detect_acoustic_event(
                grouped[xi],
                event_kind=kind,
                reference_time_s=reference_time,
                window_half_width_s=half_width,
                relative_tolerance=tolerance,
            )
            events.append(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "state_id": state_id,
                    "cells": cells,
                    "cfl": float(cfl),
                    "probe_normalized_position": xi,
                    "expected_pressure_sign": "negative",
                    "expected_velocity_sign": (
                        "positive_outward" if kind == "direct" else "negative_inward"
                    ),
                    **result,
                }
            )

    direct = {
        float(row["probe_normalized_position"]): row
        for row in events
        if row["event_kind"] == "direct"
    }
    reflected = {
        float(row["probe_normalized_position"]): row
        for row in events
        if row["event_kind"] == "reflected"
    }
    direct_order = all(
        direct[xi]["detected_time_s"] is not None
        for xi in (0.75, 0.5, 0.25)
    ) and (
        float(direct[0.75]["detected_time_s"])
        < float(direct[0.5]["detected_time_s"])
        < float(direct[0.25]["detected_time_s"])
    )
    reflected_order = all(
        reflected[xi]["detected_time_s"] is not None
        for xi in (0.25, 0.5, 0.75)
    ) and (
        float(reflected[0.25]["detected_time_s"])
        < float(reflected[0.5]["detected_time_s"])
        < float(reflected[0.75]["detected_time_s"])
    )
    for row in events:
        row["event_order_passed"] = (
            bool(direct_order)
            if row["event_kind"] == "direct"
            else bool(reflected_order)
        )
        row["comparison_passed"] = (
            row["formal_outcome"] == SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
            and bool(row["event_order_passed"])
        )
    return tuple(events)


def _face_payload(face: FaceFluxResult | None) -> dict[str, Any]:
    if face is None:
        return {
            "right_face_formal_outcome": None,
            "right_mass_rate_out_kg_s": None,
            "right_energy_rate_out_W": None,
            "right_advective_momentum_rate_out_N": None,
            "right_open_pressure_force_out_N": None,
            "right_closed_pressure_force_out_N": None,
            "right_total_momentum_rate_out_N": None,
            "right_discharge_state_pressure_pa": None,
            "right_critical_pressure_pa": None,
        }
    return {
        "right_face_formal_outcome": face.formal_outcome,
        "right_mass_rate_out_kg_s": face.mass_transfer_outward_kg_s,
        "right_energy_rate_out_W": face.energy_transfer_outward_W,
        "right_advective_momentum_rate_out_N": face.advective_momentum_rate_out_N,
        "right_open_pressure_force_out_N": face.open_static_pressure_force_out_N,
        "right_closed_pressure_force_out_N": face.closed_static_pressure_force_out_N,
        "right_total_momentum_rate_out_N": face.total_momentum_rate_out_N,
        "right_discharge_state_pressure_pa": face.discharge_state_pressure_pa,
        "right_critical_pressure_pa": face.critical_pressure_pa,
    }


def execute_finite_pipe_case(
    contract: Mapping[str, Any],
    extension: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    case_id: str,
    *,
    cells: int | None = None,
    cfl: float | None = None,
    provider: CoolPropB2StateProvider | None = None,
    b1_provider: b1_adapter.PropertyProvider | None = None,
) -> FinitePipeRun:
    case = _case(contract, case_id)
    if str(case.get("execution_level")) != "finite_pipe":
        raise ValueError(f"{case_id} is not a locked finite_pipe case")
    geometry = contract["geometry"]
    locked_cells = int(geometry["baseline_cells"] if cells is None else cells)
    locked_cfl = float(geometry["baseline_cfl"] if cfl is None else cfl)
    if locked_cells not in {int(value) for value in geometry["fixed_mesh_sequence"]}:
        raise ValueError("cells is outside the locked mesh sequence")
    if locked_cfl not in {float(value) for value in geometry["fixed_cfl_sequence"]}:
        raise ValueError("cfl is outside the locked CFL sequence")

    state_id = str(case["state_id"])
    family = _family(contract, state_id)
    property_provider = provider or CoolPropB2StateProvider()
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, locked_cells)
    U_initial, static = build_uniform_initial_state(
        contract,
        property_provider,
        state_id,
        locked_cells,
    )
    eos = CoolPropSinglePhaseEOS(
        property_provider,
        boundary_temperature_K=static.temperature_K,
    )
    adapter: U3B2FvmDischargeAdapter = adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=property_provider,
        b1_provider=b1_provider,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U_initial,
        cfl=locked_cfl,
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=adapter,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    if solver.boundary_budget is None:
        raise AssertionError("finite-pipe boundary budget must be active")

    run_id = f"{case_id}_N{locked_cells}_CFL{locked_cfl:.3f}"
    initial_inventory = inventory(
        solver.U,
        grid.dx,
        grid.geometry.area_m2,
    )
    initial_face_eval = adapter.evaluate(solver.U[-1], grid.geometry.area_m2)
    if not initial_face_eval.succeeded or initial_face_eval.face is None:
        raise RuntimeError(
            f"{case_id}: initial face failed with {initial_face_eval.formal_outcome}"
        )

    full_acoustic = bool(family.get("full_acoustic_horizon_enabled", False))
    t_end: float | None = None
    step_cap: int | None = None
    if full_acoustic:
        t_end = 2.0 * pipe.length_m / static.sound_speed_m_s
    else:
        step_cap = int(
            case.get("accepted_step_cap", family.get("finite_pipe_step_cap", 0))
        )
        if step_cap <= 0:
            raise ValueError(f"{case_id}: finite-pipe step cap is not positive")

    step_rows: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []
    min_pressure = float(static.pressure_pa)
    max_outward_velocity = float(static.velocity_m_s)
    cumulative_advective_impulse = 0.0
    cumulative_open_pressure_impulse = 0.0
    cumulative_closed_pressure_impulse = 0.0
    expected_face_outcome = (
        SUCCESS_CHOKED_FACE_MAPPING
        if state_id == "GAS_CHOKED"
        else SUCCESS_UNCHOKED_FACE_MAPPING
    )
    face_outcomes_retained = initial_face_eval.formal_outcome == expected_face_outcome

    if full_acoustic:
        probe_rows.extend(
            sample_locked_probes(
                primitive=solver.primitive(),
                extension=extension,
                run_id=run_id,
                case_id=case_id,
                state_id=state_id,
                cells=locked_cells,
                cfl=locked_cfl,
                step=0,
                time_s=0.0,
            )
        )

    while True:
        if t_end is not None and solver.t >= t_end:
            break
        if step_cap is not None and solver.step_count >= step_cap:
            break
        candidate_dt = solver.compute_dt(t_end)
        pre_step_limits = dict(adapter.last_dt_limits)
        if candidate_dt <= 0.0:
            raise RuntimeError(f"{case_id}: nonpositive candidate dt before completion")
        accepted_dt = solver.step(candidate_dt)
        evaluation = adapter.last_evaluation
        if evaluation is None or evaluation.face is None or not evaluation.succeeded:
            raise RuntimeError(f"{case_id}: accepted step lacks successful face evaluation")
        face = evaluation.face
        face_outcomes_retained = (
            face_outcomes_retained and face.formal_outcome == expected_face_outcome
        )
        cumulative_advective_impulse += face.advective_momentum_rate_out_N * accepted_dt
        cumulative_open_pressure_impulse += face.open_static_pressure_force_out_N * accepted_dt
        cumulative_closed_pressure_impulse += face.closed_static_pressure_force_out_N * accepted_dt

        primitive = solver.primitive()
        min_pressure = min(min_pressure, float(np.min(primitive.p)))
        max_outward_velocity = max(max_outward_velocity, float(np.max(primitive.u)))
        current_inventory = inventory(
            solver.U,
            grid.dx,
            grid.geometry.area_m2,
        )
        budget = solver.boundary_budget
        budget_diag = budget.diagnostics(current_inventory)
        right_decomposition = (
            cumulative_advective_impulse
            + cumulative_open_pressure_impulse
            + cumulative_closed_pressure_impulse
        )
        row = {
            "run_id": run_id,
            "case_id": case_id,
            "state_id": state_id,
            "cells": locked_cells,
            "cfl": locked_cfl,
            "step": solver.step_count,
            "time_s": solver.t,
            "accepted_dt_s": accepted_dt,
            "requested_step_dt_s": candidate_dt,
            "candidate_cfl_or_horizon_dt_s": pre_step_limits.get("candidate_dt_s"),
            "mass_removal_dt_s": pre_step_limits.get("mass_removal_dt_s"),
            "energy_removal_dt_s": pre_step_limits.get("energy_removal_dt_s"),
            "pipe_mass_kg": current_inventory["mass_total"],
            "pipe_momentum_kg_m_s": current_inventory["momentum_total"],
            "pipe_energy_J": current_inventory["energy_total"],
            "pipe_vapor_mass_kg": current_inventory["vapor_mass_total"],
            "cumulative_mass_out_kg": float(budget.cumulative_right[IDX_RHO]),
            "cumulative_energy_out_J": float(budget.cumulative_right[IDX_RHOE]),
            "cumulative_right_momentum_impulse_N_s": float(
                budget.cumulative_right[IDX_MOM]
            ),
            "cumulative_left_momentum_impulse_N_s": float(
                budget.cumulative_left[IDX_MOM]
            ),
            "cumulative_advective_momentum_impulse_N_s": cumulative_advective_impulse,
            "cumulative_open_pressure_impulse_N_s": cumulative_open_pressure_impulse,
            "cumulative_closed_pressure_impulse_N_s": cumulative_closed_pressure_impulse,
            "right_momentum_decomposition_residual_N_s": float(
                budget.cumulative_right[IDX_MOM] - right_decomposition
            ),
            "mass_inventory_residual_kg": budget_diag["budget_mass_residual"],
            "momentum_inventory_residual_kg_m_s": budget_diag[
                "budget_momentum_residual"
            ],
            "energy_inventory_residual_J": budget_diag["budget_energy_residual"],
            "vapor_inventory_residual_kg": budget_diag[
                "budget_vapor_mass_residual"
            ],
            "minimum_pressure_so_far_pa": min_pressure,
            "maximum_outward_velocity_so_far_m_s": max_outward_velocity,
            **_face_payload(face),
        }
        step_rows.append(row)
        if full_acoustic:
            probe_rows.extend(
                sample_locked_probes(
                    primitive=primitive,
                    extension=extension,
                    run_id=run_id,
                    case_id=case_id,
                    state_id=state_id,
                    cells=locked_cells,
                    cfl=locked_cfl,
                    step=solver.step_count,
                    time_s=solver.t,
                )
            )

    final_inventory = inventory(
        solver.U,
        grid.dx,
        grid.geometry.area_m2,
    )
    budget = solver.boundary_budget
    final_budget = budget.diagnostics(final_inventory)
    final_face_eval = adapter.evaluate(solver.U[-1], grid.geometry.area_m2)
    if not final_face_eval.succeeded or final_face_eval.face is None:
        raise RuntimeError(
            f"{case_id}: final face failed with {final_face_eval.formal_outcome}"
        )
    face_outcomes_retained = (
        face_outcomes_retained
        and final_face_eval.formal_outcome == expected_face_outcome
    )

    tolerances = contract["acceptance_tolerances"]
    mass_allowed = _allowed_error(
        initial_inventory["mass_total"],
        tolerances["mass_inventory_absolute_kg"],
        tolerances["mass_inventory_relative"],
    )
    energy_allowed = _allowed_error(
        initial_inventory["energy_total"],
        tolerances["energy_inventory_absolute_J"],
        tolerances["energy_inventory_relative"],
    )
    momentum_scale = max(
        abs(initial_inventory["momentum_total"]),
        abs(final_inventory["momentum_total"]),
        abs(float(budget.cumulative_left[IDX_MOM] - budget.cumulative_right[IDX_MOM])),
        1.0e-300,
    )
    momentum_allowed = _allowed_error(
        momentum_scale,
        tolerances["momentum_inventory_absolute_kg_m_s"],
        tolerances["momentum_inventory_relative"],
    )
    mass_pass = abs(final_budget["budget_mass_residual"]) <= mass_allowed
    energy_pass = abs(final_budget["budget_energy_residual"]) <= energy_allowed
    momentum_pass = (
        abs(final_budget["budget_momentum_residual"]) <= momentum_allowed
    )
    right_decomposition_residual = float(
        budget.cumulative_right[IDX_MOM]
        - (
            cumulative_advective_impulse
            + cumulative_open_pressure_impulse
            + cumulative_closed_pressure_impulse
        )
    )
    decomposition_pass = abs(right_decomposition_residual) <= momentum_allowed
    vapor_pass = (
        np.all(solver.U[..., IDX_RHO_XV] == 0.0)
        and final_inventory["vapor_mass_total"] == 0.0
        and budget.cumulative_left[IDX_RHO_XV] == 0.0
        and budget.cumulative_right[IDX_RHO_XV] == 0.0
        and final_budget["budget_vapor_mass_residual"] == 0.0
    )

    events: tuple[dict[str, Any], ...] = ()
    event_pass = True
    if full_acoustic:
        events = _event_rows(
            probe_history=probe_rows,
            run_id=run_id,
            case_id=case_id,
            state_id=state_id,
            cells=locked_cells,
            cfl=locked_cfl,
            length_m=pipe.length_m,
            initial_sound_speed_m_s=static.sound_speed_m_s,
            extension=extension,
            contract=contract,
        )
        event_pass = all(bool(row["comparison_passed"]) for row in events)

    inventory_pass = mass_pass and energy_pass and momentum_pass and decomposition_pass
    formal_outcome = (
        SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
        if inventory_pass and vapor_pass and event_pass and face_outcomes_retained
        else (
            FINITE_PIPE_FACE_REGIME_FAILURE
            if inventory_pass and vapor_pass and event_pass and not face_outcomes_retained
            else (
                ACOUSTIC_EVENT_NOT_RESOLVED
                if inventory_pass and vapor_pass and face_outcomes_retained and not event_pass
                else FINITE_PIPE_INVENTORY_CLOSURE_FAILURE
            )
        )
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "state_id": state_id,
        "formal_outcome": formal_outcome,
        "expected_outcome": str(case["expected_outcome"]),
        "formal_outcome_matches_contract": (
            formal_outcome == str(case["expected_outcome"])
        ),
        "cells": locked_cells,
        "cfl": locked_cfl,
        "accepted_steps": solver.step_count,
        "final_time_s": solver.t,
        "target_horizon_s": t_end,
        "accepted_step_cap": step_cap,
        "initial_sound_speed_m_s": static.sound_speed_m_s,
        "initial_mass_kg": initial_inventory["mass_total"],
        "final_mass_kg": final_inventory["mass_total"],
        "cumulative_mass_out_kg": float(budget.cumulative_right[IDX_RHO]),
        "mass_inventory_residual_kg": final_budget["budget_mass_residual"],
        "mass_allowed_error_kg": mass_allowed,
        "mass_inventory_passed": mass_pass,
        "initial_energy_J": initial_inventory["energy_total"],
        "final_energy_J": final_inventory["energy_total"],
        "cumulative_energy_out_J": float(budget.cumulative_right[IDX_RHOE]),
        "energy_inventory_residual_J": final_budget["budget_energy_residual"],
        "energy_allowed_error_J": energy_allowed,
        "energy_inventory_passed": energy_pass,
        "initial_momentum_kg_m_s": initial_inventory["momentum_total"],
        "final_momentum_kg_m_s": final_inventory["momentum_total"],
        "cumulative_left_momentum_impulse_N_s": float(
            budget.cumulative_left[IDX_MOM]
        ),
        "cumulative_right_momentum_impulse_N_s": float(
            budget.cumulative_right[IDX_MOM]
        ),
        "momentum_inventory_residual_kg_m_s": final_budget[
            "budget_momentum_residual"
        ],
        "momentum_allowed_error_kg_m_s": momentum_allowed,
        "momentum_inventory_passed": momentum_pass,
        "right_momentum_decomposition_residual_N_s": right_decomposition_residual,
        "right_momentum_decomposition_passed": decomposition_pass,
        "vapor_identity_passed": vapor_pass,
        "acoustic_event_count": len(events),
        "acoustic_events_passed": event_pass,
        "minimum_pressure_pa": min_pressure,
        "maximum_outward_velocity_m_s": max_outward_velocity,
        "expected_face_outcome": expected_face_outcome,
        "initial_face_outcome": initial_face_eval.formal_outcome,
        "final_face_outcome": final_face_eval.formal_outcome,
        "face_outcomes_retained": face_outcomes_retained,
        "u3_b2_fvm_adapter_implemented": True,
        "single_phase_fvm_discharge_mapping_verified": True,
        "candidate_baseline_finite_pipe_execution_passed": (
            formal_outcome == SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
        ),
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    return FinitePipeRun(
        summary=summary,
        step_history=tuple(step_rows),
        probe_history=tuple(probe_rows),
        acoustic_events=events,
    )


def execute_baseline_package(
    contract: Mapping[str, Any],
    extension: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
) -> FinitePipePackage:
    runs = tuple(
        execute_finite_pipe_case(
            contract,
            extension,
            b1_contract,
            case_id,
        )
        for case_id in BASELINE_CASE_IDS
    )
    all_passed = all(
        run.summary["formal_outcome"] == SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
        for run in runs
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": "locked_baseline_three_family_finite_pipe_preflight",
        "run_count": len(runs),
        "run_ids": [run.summary["run_id"] for run in runs],
        "all_baseline_runs_passed": all_passed,
        "total_accepted_steps": sum(
            int(run.summary["accepted_steps"]) for run in runs
        ),
        "total_probe_rows": sum(len(run.probe_history) for run in runs),
        "total_acoustic_event_rows": sum(len(run.acoustic_events) for run in runs),
        "u3_b2_fvm_adapter_implemented": True,
        "single_phase_fvm_discharge_mapping_verified": True,
        "candidate_baseline_finite_pipe_execution_passed": all_passed,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    return FinitePipePackage(runs=runs, summary=summary)


def write_preflight_package(
    package: FinitePipePackage,
    *,
    output_dir: str | Path,
    contract_path: str | Path,
    extension_path: str | Path,
    b1_contract_path: str | Path,
    source_git_sha: str,
) -> None:
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    summaries = [run.summary for run in package.runs]
    steps = [row for run in package.runs for row in run.step_history]
    probes = [row for run in package.runs for row in run.probe_history]
    events = [row for run in package.runs for row in run.acoustic_events]
    _write_csv(output / "baseline_run_summary.csv", summaries)
    _write_csv(output / "baseline_step_history.csv", steps)
    if probes:
        _write_csv(output / "baseline_probe_history.csv", probes)
    if events:
        _write_csv(output / "baseline_acoustic_events.csv", events)

    for source, target in (
        (Path(contract_path), output / "benchmark_contract.json"),
        (Path(extension_path), output / "event_provenance_contract.json"),
        (Path(b1_contract_path), output / "b1_component_contract.json"),
    ):
        shutil.copyfile(source, target)

    summary = dict(package.summary)
    summary["analysis_source_git_sha"] = str(source_git_sha)
    summary["property_backend"] = "CoolProp"
    summary["property_backend_version"] = "8.0.0"
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = [
        "# U3 B2 単相finite-pipe baseline preflight",
        "",
        "## 位置づけ",
        "",
        "本成果物は、mainへmerge済みのB2 Adapterを用いて、locked baselineの",
        "LIQUID_SMALL_DROP、GAS_UNCHOKED、GAS_CHOKEDを実FvmSolverで進める",
        "implementation preflightである。B2全体のAcceptance、Physical Validation、",
        "設計利用またはproduction activationを承認しない。",
        "",
        "## 結果",
        "",
        "```text",
        f"source SHA: {source_git_sha}",
        f"run count: {summary['run_count']}",
        f"all baseline runs passed: {summary['all_baseline_runs_passed']}",
        f"accepted steps: {summary['total_accepted_steps']}",
        f"probe rows: {summary['total_probe_rows']}",
        f"acoustic event rows: {summary['total_acoustic_event_rows']}",
        "property backend: CoolProp 8.0.0",
        "```",
        "",
        "## Claim boundary",
        "",
        "```text",
        "u3_b2_finite_pipe_execution_complete = false",
        "single_phase_finite_pipe_coupling_verified = false",
        "u3_b2_verification_benchmark_accepted = false",
        "physical_validation = false",
        "design_use_acceptance = false",
        "production_hem_activation_approved = false",
        "```",
        "",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    names = sorted(
        path.name
        for path in output.iterdir()
        if path.is_file() and path.name != "artifact_sha256.txt"
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--extension-contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    contract = load_contract(args.contract)
    extension = load_extension_contract(args.extension_contract)
    b1_contract = load_b1_contract(args.b1_contract)
    package = execute_baseline_package(contract, extension, b1_contract)
    write_preflight_package(
        package,
        output_dir=args.output_dir,
        contract_path=args.contract,
        extension_path=args.extension_contract,
        b1_contract_path=args.b1_contract,
        source_git_sha=args.source_git_sha,
    )
    if not package.summary["all_baseline_runs_passed"]:
        raise SystemExit("locked baseline finite-pipe preflight did not pass")


if __name__ == "__main__":
    main()
