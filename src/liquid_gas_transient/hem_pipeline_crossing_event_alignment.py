"""Stage 7 P1-A3G crossing Event A / Event B alignment.

This verification-only diagnostic preserves the authoritative P1-A3 result and
its fixed 1e-6 crossing-evidence floor.  Event A is the first retained
LIQUID_TO_TWO_PHASE_CROSSING with positive equilibrium quality.  Event B is the
first accepted state at or above the unchanged evidence floor.  Cases already
above the floor have B == A.  Sub-threshold cases are continued only on a
shadow diagnostic path from the retained Event A state.

The shadow path reuses the reviewed post-crossing FVM/projection/budget helpers.
It does not alter the production solver, EOS, boundary model, CFL algorithm,
phase classifier, projection, threshold, or tolerance, and it does not change
the authoritative P1-A3 FAIL_CLOSED / INCONCLUSIVE verdict.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import hem_pipeline_post_crossing_propagation as gate6
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    run_pipeline_depressurization_case,
)
from .hem_pipeline_mesh_cfl_sensitivity import P1_A3_CASE_SPECS
from .hem_pipeline_mesh_cfl_variant import HEMMeshCflPipelineConfig
from .hem_pipeline_subthreshold_crossing_forensics import (
    P1_A3F_EVIDENCE_FLOOR,
    _crossing_status,
)

P1_A3G_SCHEMA_VERSION = "stage7_p1_a3_crossing_event_alignment_v1"
P1_A3G_MODEL_ID = "HEM_EQUILIBRIUM"
P1_A3G_EVIDENCE_FLOOR = P1_A3F_EVIDENCE_FLOOR
P1_A3G_MAX_SHADOW_STEPS = 64
P1_A3G_OUTPUT_FILES = (
    "event_alignment_summary.json",
    "event_alignment_cases.csv",
    "event_a_cells.csv",
    "event_b_cells.csv",
    "event_interval_history.csv",
    "event_ab_time_comparison.png",
    "event_ab_step_comparison.png",
    "operator_report.md",
    "event_alignment_manifest.json",
)
P1_A3G_AUTHORITATIVE_A3 = {
    "sensitivity_execution_status": "FAIL_CLOSED",
    "ordering_verdict": "INCONCLUSIVE",
    "numerical_verdict": "INCONCLUSIVE",
}
P1_A3G_FORMAL_STATUS = {
    "implemented": True,
    "diagnostic_evidence_ready": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "mesh_independent_crossing_verified": False,
    "cfl_independent_crossing_verified": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}


class P1A3GAlignmentError(RuntimeError):
    """Raised when bounded Event A/B alignment cannot proceed safely."""


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""

    return {
        "source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def _baseline_case():
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        if case.case_id == "pipeline_crossing_candidate_p5m5_to_p2m5":
            return case
    raise P1A3GAlignmentError("fixed 5 MPa -> 2 MPa case was not found")


def _config_for_spec(spec):
    if spec.use_locked_gate6_authority:
        return HEMPipelineDepressurizationConfig()
    return HEMMeshCflPipelineConfig(n_cells=spec.n_cells, cfl=spec.cfl)


def _step_record(result: PipelineCaseResult, absolute_step: int):
    for row in result.steps:
        if row.step_index == absolute_step:
            return row
    return None


def _accepted_fields(U: np.ndarray, config: HEMPipelineDepressurizationConfig):
    state = np.asarray(U, dtype=float)
    if state.shape != (config.n_cells, gate6.N_VARS):
        raise P1A3GAlignmentError("accepted state has incompatible shape")
    if not np.all(np.isfinite(state)):
        raise P1A3GAlignmentError("accepted state contains nonfinite values")
    if np.any(state[:, gate6.IDX_RHO] <= 0.0):
        raise P1A3GAlignmentError("accepted state contains non-positive density")

    eos = gate6.VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=config.accepted_state_quality_tolerance,
        phase_config=config.phase_config,
        quality_sync_config=config.projection_config,
    )
    primitive = eos.primitive_from_conserved(state)
    regions_value = eos.last_regions
    if regions_value is None:
        raise P1A3GAlignmentError("accepted-state EOS did not retain regions")
    regions = np.asarray(regions_value).astype(str)
    q = np.asarray(gate6.vapor_mass_fraction(state), dtype=float)
    e = np.asarray(gate6.internal_energy(state), dtype=float)
    p = np.asarray(primitive.p, dtype=float)
    T = np.asarray(primitive.T, dtype=float)
    alpha = np.asarray(primitive.alpha, dtype=float)
    arrays = (q, e, p, T, alpha)
    if any(array.shape != (config.n_cells,) for array in arrays):
        raise P1A3GAlignmentError("accepted primitive arrays have incompatible shape")
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise P1A3GAlignmentError("accepted primitive arrays contain nonfinite values")
    return {
        "regions": regions,
        "quality": q,
        "internal_energy_j_kg": e,
        "pressure_pa": p,
        "temperature_K": T,
        "void_fraction": alpha,
    }


def _phase_front_distance(
    regions: np.ndarray,
    *,
    length_m: float,
    cell_centers_m: np.ndarray,
) -> float | None:
    open_cells = np.flatnonzero(regions == "OPEN_TWO_PHASE")
    if open_cells.size == 0:
        return None
    distances = length_m - np.asarray(cell_centers_m, dtype=float)[open_cells]
    return float(np.max(distances))


def _primary_cell(indices: Sequence[int], quality: np.ndarray) -> int:
    if not indices:
        raise P1A3GAlignmentError("event has no cells")
    return int(max(indices, key=lambda idx: float(quality[int(idx)])))


def _event_cell_rows(
    *,
    event_name: str,
    spec,
    absolute_step: int,
    time_s: float,
    dt_s: float,
    U: np.ndarray,
    fields: dict[str, np.ndarray],
    cell_indices: Sequence[int],
    state_sha256: str,
) -> list[dict[str, object]]:
    dx = 1.0 / float(spec.n_cells)
    rows: list[dict[str, object]] = []
    for cell_index in cell_indices:
        index = int(cell_index)
        rows.append(
            {
                "event": event_name,
                "case_id": spec.case_id,
                "role": spec.role,
                "n_cells": int(spec.n_cells),
                "cfl": float(spec.cfl),
                "absolute_step": int(absolute_step),
                "time_s": float(time_s),
                "dt_s": float(dt_s),
                "cell_index": index,
                "cell_center_m": (index + 0.5) * dx,
                "distance_from_outlet_m": 1.0 - (index + 0.5) * dx,
                "dx_m": dx,
                "region": str(fields["regions"][index]),
                "quality": float(fields["quality"][index]),
                "pressure_pa": float(fields["pressure_pa"][index]),
                "temperature_K": float(fields["temperature_K"][index]),
                "rho_kg_m3": float(U[index, gate6.IDX_RHO]),
                "internal_energy_j_kg": float(
                    fields["internal_energy_j_kg"][index]
                ),
                "void_fraction": float(fields["void_fraction"][index]),
                "state_sha256": state_sha256,
            }
        )
    return rows


def _event_a(spec, result: PipelineCaseResult):
    status = _crossing_status(result)
    if status not in {
        "ACCEPTED_ABOVE_FIXED_FLOOR",
        "SUBTHRESHOLD_CROSSING_RETAINED",
    }:
        raise P1A3GAlignmentError(
            f"{spec.case_id}: Event A was not retained: {status}: {result.failure_reason}"
        )
    if result.crossing_step is None or result.crossing_time_s is None:
        raise P1A3GAlignmentError(f"{spec.case_id}: Event A metadata is incomplete")
    if result.accepted_state_history.shape[0] <= result.crossing_step:
        raise P1A3GAlignmentError(f"{spec.case_id}: Event A state is missing")
    step = _step_record(result, result.crossing_step)
    if step is None:
        raise P1A3GAlignmentError(f"{spec.case_id}: Event A step record is missing")

    U = np.asarray(result.accepted_state_history[result.crossing_step], dtype=float)
    fields = _accepted_fields(U, result.config)
    indices = tuple(int(value) for value in result.crossing_cell_indices)
    primary = _primary_cell(indices, fields["quality"])
    state_sha = gate6._state_sha256(U)
    if state_sha != result.final_state_sha256:
        raise P1A3GAlignmentError(
            f"{spec.case_id}: Event A hash differs from authoritative retained state"
        )
    grid = gate6.UniformGrid(
        gate6.PipeGeometry(length_m=result.config.length_m, diameter_m=result.config.diameter_m),
        n_cells=result.config.n_cells,
    )
    front = _phase_front_distance(
        fields["regions"],
        length_m=result.config.length_m,
        cell_centers_m=grid.cell_centers,
    )
    event = {
        "time_s": float(result.crossing_time_s),
        "absolute_step": int(result.crossing_step),
        "primary_cell": primary,
        "primary_distance_from_outlet_m": float(
            result.config.length_m - grid.cell_centers[primary]
        ),
        "quality": float(fields["quality"][primary]),
        "pressure_pa": float(fields["pressure_pa"][primary]),
        "temperature_K": float(fields["temperature_K"][primary]),
        "rho_kg_m3": float(U[primary, gate6.IDX_RHO]),
        "internal_energy_j_kg": float(fields["internal_energy_j_kg"][primary]),
        "void_fraction": float(fields["void_fraction"][primary]),
        "dt_s": float(step.dt_s),
        "dx_m": float(grid.dx),
        "phase_front_distance_from_outlet_m": front,
        "state_sha256": state_sha,
        "cell_indices": list(indices),
    }
    cells = _event_cell_rows(
        event_name="A",
        spec=spec,
        absolute_step=event["absolute_step"],
        time_s=event["time_s"],
        dt_s=event["dt_s"],
        U=U,
        fields=fields,
        cell_indices=indices,
        state_sha256=state_sha,
    )
    return event, cells, np.array(U, dtype=float, copy=True), fields


def _same_event_b(spec, event_a, event_a_cells):
    event_b = dict(event_a)
    cells = []
    for row in event_a_cells:
        copied = dict(row)
        copied["event"] = "B"
        cells.append(copied)
    history = [
        {
            "case_id": spec.case_id,
            "n_cells": int(spec.n_cells),
            "cfl": float(spec.cfl),
            "shadow_step": 0,
            "absolute_step": int(event_a["absolute_step"]),
            "time_s": float(event_a["time_s"]),
            "elapsed_from_event_a_s": 0.0,
            "dt_s": 0.0,
            "maximum_equilibrium_quality": float(event_a["quality"]),
            "open_two_phase_cell_count": len(event_a["cell_indices"]),
            "phase_front_distance_from_outlet_m": event_a[
                "phase_front_distance_from_outlet_m"
            ],
            "boundary_mass_residual_kg": 0.0,
            "boundary_momentum_residual_kg_m_s": 0.0,
            "boundary_energy_residual_J": 0.0,
            "phase_vapor_residual_kg": 0.0,
            "reverse_flow_fallback_count": 0,
            "state_sha256": event_a["state_sha256"],
            "event_b_reached": True,
        }
    ]
    return event_b, cells, history, "", ""


def _shadow_to_event_b(spec, result: PipelineCaseResult, event_a, event_a_U):
    config = result.config
    case = result.case
    schedule = gate6.LinearPressureRamp(
        p_initial_pa=config.initial_pressure_pa,
        p_final_pa=case.final_boundary_pressure_pa,
        t_start_s=0.0,
        duration_s=result.ramp_duration_s,
    )
    provider = gate6.VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=config.subcooling_K,
        phase_config=config.phase_config,
    )
    right_boundary = gate6.VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    grid = gate6.UniformGrid(
        gate6.PipeGeometry(length_m=config.length_m, diameter_m=config.diameter_m),
        n_cells=config.n_cells,
    )
    eos = gate6.VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=config.accepted_state_quality_tolerance,
        phase_config=config.phase_config,
        quality_sync_config=config.projection_config,
    )
    solver = gate6.FvmSolver(
        grid=grid,
        eos=eos,
        U=np.array(event_a_U, dtype=float, copy=True),
        cfl=config.cfl,
        n_ghost=config.n_ghost,
        left_boundary=gate6.ReflectiveBoundary(),
        right_boundary=right_boundary,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=float(event_a["time_s"]),
        step_count=int(event_a["absolute_step"]),
    )
    continuation_initial_inventory = gate6.inventory(
        solver.U, grid.dx, grid.geometry.area_m2
    )
    phase_tracker = gate6.PhaseChangeBudgetTracker(
        initial_inventory=continuation_initial_inventory
    )
    latest_projected_budget: dict[str, float] = {}
    history: list[dict[str, object]] = [
        {
            "case_id": spec.case_id,
            "n_cells": int(spec.n_cells),
            "cfl": float(spec.cfl),
            "shadow_step": 0,
            "absolute_step": int(solver.step_count),
            "time_s": float(solver.t),
            "elapsed_from_event_a_s": 0.0,
            "dt_s": 0.0,
            "maximum_equilibrium_quality": float(event_a["quality"]),
            "open_two_phase_cell_count": len(event_a["cell_indices"]),
            "phase_front_distance_from_outlet_m": event_a[
                "phase_front_distance_from_outlet_m"
            ],
            "boundary_mass_residual_kg": 0.0,
            "boundary_momentum_residual_kg_m_s": 0.0,
            "boundary_energy_residual_J": 0.0,
            "phase_vapor_residual_kg": 0.0,
            "reverse_flow_fallback_count": 0,
            "state_sha256": event_a["state_sha256"],
            "event_b_reached": False,
        }
    ]

    try:
        for shadow_step in range(1, P1_A3G_MAX_SHADOW_STEPS + 1):
            if solver.t >= result.maximum_horizon_s:
                raise P1A3GAlignmentError(
                    "authoritative first-crossing horizon reached before Event B"
                )
            time_before = float(solver.t)
            previous_U = np.array(solver.U, dtype=float, copy=True)
            previous_primitive = solver.primitive()
            previous_inventory = gate6.inventory(
                previous_U, grid.dx, grid.geometry.area_m2
            )
            if solver.boundary_budget is None:
                raise P1A3GAlignmentError("boundary budget tracker is required")
            left_before = np.array(
                solver.boundary_budget.cumulative_left, dtype=float, copy=True
            )
            right_before = np.array(
                solver.boundary_budget.cumulative_right, dtype=float, copy=True
            )
            reverse_before = right_boundary.reverse_flow_fallback_count
            dt = float(solver.compute_dt(t_end=result.maximum_horizon_s))
            if not math.isfinite(dt) or dt <= 0.0:
                raise P1A3GAlignmentError("shadow dt must be finite and positive")

            solver.step(dt)
            raw_U = np.array(solver.U, dtype=float, copy=True)
            raw_inventory = gate6.inventory(raw_U, grid.dx, grid.geometry.area_m2)
            raw_budget = gate6._incremental_boundary_budget(
                previous_inventory=previous_inventory,
                raw_inventory=raw_inventory,
                step_left=solver.boundary_budget.cumulative_left - left_before,
                step_right=solver.boundary_budget.cumulative_right - right_before,
                config=config,
            )
            reverse_delta = right_boundary.reverse_flow_fallback_count - reverse_before
            if reverse_delta > 0:
                raise P1A3GAlignmentError("reverse flow fallback was activated")

            detection = gate6.detect_raw_transition_events(
                previous_U, raw_U, phase_config=config.phase_config
            )
            raw_class = gate6._classify_raw_state(detection)
            if raw_class not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
                raise P1A3GAlignmentError(
                    f"shadow continuation entered {raw_class}"
                )
            boundary_state = right_boundary.last_state or provider.state_at(time_before)
            raw_case = gate6._raw_case(
                case=case,
                config=config,
                grid=grid,
                previous_U=previous_U,
                raw_U=raw_U,
                previous_primitive=previous_primitive,
                detection=detection,
                boundary_state=boundary_state,
                dt=dt,
                raw_budget=raw_budget,
            )
            first, second, post_U, primitive, post_regions, projected_budget = (
                gate6._project_and_accept(
                    raw_case=raw_case,
                    detection=detection,
                    config=config,
                )
            )
            latest_projected_budget = dict(projected_budget)
            phase_tracker.record_phase_change(
                U_before=raw_U,
                U_after=post_U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
                dt=dt,
            )
            solver.U = np.array(post_U, dtype=float, copy=True)
            boundary_diag, phase_diag = gate6._validate_cumulative_budgets(
                solver=solver,
                phase_tracker=phase_tracker,
                initial_inventory=continuation_initial_inventory,
                latest_projected_budget=latest_projected_budget,
                config=config,
            )
            if np.any(second.projection_applied):
                raise P1A3GAlignmentError("second projection was not a no-op")

            regions = np.asarray(post_regions).astype(str)
            q_eq = np.asarray(first.q_equilibrium, dtype=float)
            if not np.all(np.isfinite(q_eq)) or np.any(q_eq < 0.0):
                raise P1A3GAlignmentError("shadow equilibrium quality is invalid")
            fields = _accepted_fields(post_U, config)
            if not np.allclose(
                fields["quality"],
                q_eq,
                rtol=0.0,
                atol=config.projection_config.activation_tolerance,
            ):
                raise P1A3GAlignmentError(
                    "accepted transported quality differs from equilibrium quality"
                )
            open_cells = tuple(
                int(index) for index in np.flatnonzero(regions == "OPEN_TWO_PHASE")
            )
            max_q = float(np.max(q_eq, initial=0.0))
            front = _phase_front_distance(
                regions,
                length_m=config.length_m,
                cell_centers_m=grid.cell_centers,
            )
            state_sha = gate6._state_sha256(post_U)
            history_row = {
                "case_id": spec.case_id,
                "n_cells": int(spec.n_cells),
                "cfl": float(spec.cfl),
                "shadow_step": shadow_step,
                "absolute_step": int(solver.step_count),
                "time_s": float(solver.t),
                "elapsed_from_event_a_s": float(solver.t - event_a["time_s"]),
                "dt_s": dt,
                "maximum_equilibrium_quality": max_q,
                "open_two_phase_cell_count": len(open_cells),
                "phase_front_distance_from_outlet_m": front,
                "boundary_mass_residual_kg": float(
                    boundary_diag["budget_mass_residual"]
                ),
                "boundary_momentum_residual_kg_m_s": float(
                    boundary_diag["budget_momentum_residual"]
                ),
                "boundary_energy_residual_J": float(
                    boundary_diag["budget_energy_residual"]
                ),
                "phase_vapor_residual_kg": float(
                    phase_diag["phase_vapor_mass_balance_residual_kg"]
                ),
                "reverse_flow_fallback_count": int(
                    right_boundary.reverse_flow_fallback_count
                ),
                "state_sha256": state_sha,
                "event_b_reached": bool(max_q >= P1_A3G_EVIDENCE_FLOOR),
            }
            history.append(history_row)

            if max_q >= P1_A3G_EVIDENCE_FLOOR:
                candidates = tuple(
                    int(index)
                    for index in np.flatnonzero(
                        (regions == "OPEN_TWO_PHASE")
                        & (q_eq >= P1_A3G_EVIDENCE_FLOOR)
                    )
                )
                if not candidates:
                    raise P1A3GAlignmentError(
                        "Event B quality floor reached without an OPEN_TWO_PHASE cell"
                    )
                primary = _primary_cell(candidates, q_eq)
                event_b = {
                    "time_s": float(solver.t),
                    "absolute_step": int(solver.step_count),
                    "primary_cell": primary,
                    "primary_distance_from_outlet_m": float(
                        config.length_m - grid.cell_centers[primary]
                    ),
                    "quality": float(q_eq[primary]),
                    "pressure_pa": float(fields["pressure_pa"][primary]),
                    "temperature_K": float(fields["temperature_K"][primary]),
                    "rho_kg_m3": float(post_U[primary, gate6.IDX_RHO]),
                    "internal_energy_j_kg": float(
                        fields["internal_energy_j_kg"][primary]
                    ),
                    "void_fraction": float(fields["void_fraction"][primary]),
                    "dt_s": dt,
                    "dx_m": float(grid.dx),
                    "phase_front_distance_from_outlet_m": front,
                    "state_sha256": state_sha,
                    "cell_indices": list(candidates),
                }
                cells = _event_cell_rows(
                    event_name="B",
                    spec=spec,
                    absolute_step=event_b["absolute_step"],
                    time_s=event_b["time_s"],
                    dt_s=event_b["dt_s"],
                    U=post_U,
                    fields=fields,
                    cell_indices=candidates,
                    state_sha256=state_sha,
                )
                return event_b, cells, history, "", ""
    except Exception as exc:
        return None, [], history, gate6._failure_category(exc), f"{type(exc).__name__}: {exc}"

    return (
        None,
        [],
        history,
        "EVENT_B_NOT_REACHED",
        f"Event B was not reached within {P1_A3G_MAX_SHADOW_STEPS} shadow steps",
    )


def _comparison_pattern(case_rows: Sequence[dict[str, object]]):
    by_id = {str(row["case_id"]): row for row in case_rows}
    mesh_ids = (
        "mesh_16_cfl_0p10",
        "baseline_32_cfl_0p10",
        "mesh_64_cfl_0p10",
    )
    cfl_ids = (
        "cfl_32_0p05",
        "baseline_32_cfl_0p10",
        "cfl_32_0p20",
    )

    def comparison_rows(ids):
        return [
            {
                "case_id": case_id,
                "n_cells": by_id[case_id]["n_cells"],
                "cfl": by_id[case_id]["cfl"],
                "event_a_time_s": by_id[case_id]["event_a_time_s"],
                "event_b_time_s": by_id[case_id]["event_b_time_s"],
                "delta_t_a_to_b_s": by_id[case_id]["delta_t_a_to_b_s"],
                "delta_step_a_to_b": by_id[case_id]["delta_step_a_to_b"],
                "event_b_reached": by_id[case_id]["event_b_reached"],
            }
            for case_id in ids
        ]

    mesh = comparison_rows(mesh_ids)
    cfl = comparison_rows(cfl_ids)
    if not all(bool(row["event_b_reached"]) for row in (*mesh, *cfl)):
        return (
            mesh,
            cfl,
            "INCONCLUSIVE_EVENT_B_UNREACHED",
            "INCONCLUSIVE_EVENT_B_UNREACHED",
            "INCONCLUSIVE_EVENT_B_UNREACHED",
        )

    mesh_steps = [int(row["delta_step_a_to_b"]) for row in mesh]
    cfl_steps = [int(row["delta_step_a_to_b"]) for row in cfl]
    mesh_pattern = (
        "SEPARATED_ONLY_AT_FINE_MESH"
        if mesh_steps[0] == 0 and mesh_steps[1] == 0 and mesh_steps[2] > 0
        else "MIXED"
    )
    cfl_pattern = (
        "SEPARATED_ONLY_AT_LOW_CFL"
        if cfl_steps[0] > 0 and cfl_steps[1] == 0 and cfl_steps[2] == 0
        else "MIXED"
    )
    support = (
        "STRONGLY_SUPPORTS_DISCRETE_EVENT_ALIASING"
        if mesh_pattern == "SEPARATED_ONLY_AT_FINE_MESH"
        and cfl_pattern == "SEPARATED_ONLY_AT_LOW_CFL"
        else "MIXED_OR_INCONCLUSIVE"
    )
    return mesh, cfl, mesh_pattern, cfl_pattern, support


def _evaluate(case_rows, history_rows):
    expected_ids = [spec.case_id for spec in P1_A3_CASE_SPECS]
    actual_ids = [str(row["case_id"]) for row in case_rows]
    event_a_all = all(bool(row["event_a_reproduced"]) for row in case_rows)
    event_b_all = all(bool(row["event_b_reached"]) for row in case_rows)
    event_a_hashes = all(
        len(str(row["event_a_state_sha256"])) == 64 for row in case_rows
    )
    event_b_hashes = all(
        len(str(row["event_b_state_sha256"])) == 64
        for row in case_rows
        if row["event_b_reached"]
    )
    subthreshold = [
        row
        for row in case_rows
        if row["authoritative_crossing_status"] == "SUBTHRESHOLD_CROSSING_RETAINED"
    ]
    guards_preserved = bool(subthreshold) and all(
        row["authoritative_outcome"] == "GUARD_FAILURE"
        and row["shadow_continuation_used"] is True
        and float(row["event_a_quality"]) < P1_A3G_EVIDENCE_FLOOR
        for row in subthreshold
    )
    accepted = [
        row
        for row in case_rows
        if row["authoritative_crossing_status"] == "ACCEPTED_ABOVE_FIXED_FLOOR"
    ]
    accepted_coalesced = bool(accepted) and all(
        row["event_b_reached"] is True
        and int(row["delta_step_a_to_b"]) == 0
        and math.isclose(float(row["delta_t_a_to_b_s"]), 0.0, abs_tol=0.0)
        for row in accepted
    )
    finite_deltas = all(
        row["event_b_reached"]
        and math.isfinite(float(row["delta_t_a_to_b_s"]))
        and float(row["delta_t_a_to_b_s"]) >= 0.0
        and int(row["delta_step_a_to_b"]) >= 0
        and math.isfinite(float(row["delta_x_front_a_to_b_m"]))
        for row in case_rows
    )
    history_finite = bool(history_rows) and all(
        math.isfinite(float(row["time_s"]))
        and math.isfinite(float(row["maximum_equilibrium_quality"]))
        and math.isfinite(float(row["boundary_mass_residual_kg"]))
        and math.isfinite(float(row["boundary_momentum_residual_kg_m_s"]))
        and math.isfinite(float(row["boundary_energy_residual_J"]))
        and math.isfinite(float(row["phase_vapor_residual_kg"]))
        for row in history_rows
    )
    no_reverse = bool(history_rows) and all(
        int(row["reverse_flow_fallback_count"]) == 0 for row in history_rows
    )
    no_shadow_failures = all(not str(row["shadow_failure_reason"]) for row in case_rows)

    gates = (
        {"gate": "PREDECLARED_MATRIX_EXACT", "passed": actual_ids == expected_ids},
        {"gate": "EVENT_A_REPRODUCED_FOR_ALL_CASES", "passed": event_a_all},
        {"gate": "EVENT_A_STATE_HASH_RETAINED", "passed": event_a_hashes},
        {"gate": "AUTHORITATIVE_A3_GUARDS_PRESERVED", "passed": guards_preserved},
        {"gate": "ABOVE_FLOOR_CASES_COALESCE_A_AND_B", "passed": accepted_coalesced},
        {"gate": "EVENT_B_OBSERVED_FOR_ALL_CASES", "passed": event_b_all},
        {"gate": "EVENT_B_STATE_HASH_RETAINED", "passed": event_b_all and event_b_hashes},
        {"gate": "A_TO_B_DELTAS_FINITE", "passed": finite_deltas},
        {"gate": "SHADOW_CONTINUATION_NO_UNRELATED_FAILURE", "passed": no_shadow_failures},
        {"gate": "SHADOW_HISTORY_FINITE", "passed": history_finite},
        {"gate": "NO_REVERSE_FLOW_FALLBACK", "passed": no_reverse},
        {"gate": "FIXED_EVIDENCE_FLOOR_UNCHANGED", "passed": P1_A3G_EVIDENCE_FLOOR == 1.0e-6},
    )
    ready = all(bool(gate["passed"]) for gate in gates)
    return gates, ready


def analyze_crossing_event_alignment() -> dict[str, object]:
    case = _baseline_case()
    case_rows: list[dict[str, object]] = []
    event_a_cells: list[dict[str, object]] = []
    event_b_cells: list[dict[str, object]] = []
    interval_history: list[dict[str, object]] = []

    for spec in P1_A3_CASE_SPECS:
        config = _config_for_spec(spec)
        authoritative = run_pipeline_depressurization_case(case, config)
        event_a, a_cells, event_a_U, _ = _event_a(spec, authoritative)
        event_a_cells.extend(a_cells)
        status = _crossing_status(authoritative)
        if event_a["quality"] >= P1_A3G_EVIDENCE_FLOOR:
            event_b, b_cells, history, failure_category, failure_reason = _same_event_b(
                spec, event_a, a_cells
            )
            shadow_used = False
        else:
            event_b, b_cells, history, failure_category, failure_reason = _shadow_to_event_b(
                spec, authoritative, event_a, event_a_U
            )
            shadow_used = True
        interval_history.extend(history)
        event_b_cells.extend(b_cells)

        event_b_reached = event_b is not None
        delta_t = None if event_b is None else float(event_b["time_s"] - event_a["time_s"])
        delta_step = None if event_b is None else int(event_b["absolute_step"] - event_a["absolute_step"])
        if event_b is None:
            delta_x = None
        else:
            a_front = event_a["phase_front_distance_from_outlet_m"]
            b_front = event_b["phase_front_distance_from_outlet_m"]
            delta_x = 0.0 if a_front is None and b_front is None else float(b_front) - float(a_front)

        case_rows.append(
            {
                "case_id": spec.case_id,
                "role": spec.role,
                "n_cells": int(spec.n_cells),
                "cfl": float(spec.cfl),
                "dx_m": 1.0 / float(spec.n_cells),
                "authoritative_outcome": authoritative.outcome,
                "authoritative_failure_reason": authoritative.failure_reason,
                "authoritative_crossing_status": status,
                "authoritative_a3_verdict_frozen": True,
                "event_a_reproduced": True,
                "event_a_time_s": event_a["time_s"],
                "event_a_absolute_step": event_a["absolute_step"],
                "event_a_primary_cell": event_a["primary_cell"],
                "event_a_distance_from_outlet_m": event_a["primary_distance_from_outlet_m"],
                "event_a_quality": event_a["quality"],
                "event_a_pressure_pa": event_a["pressure_pa"],
                "event_a_temperature_K": event_a["temperature_K"],
                "event_a_rho_kg_m3": event_a["rho_kg_m3"],
                "event_a_internal_energy_j_kg": event_a["internal_energy_j_kg"],
                "event_a_void_fraction": event_a["void_fraction"],
                "event_a_dt_s": event_a["dt_s"],
                "event_a_phase_front_distance_from_outlet_m": event_a[
                    "phase_front_distance_from_outlet_m"
                ],
                "event_a_state_sha256": event_a["state_sha256"],
                "shadow_continuation_used": shadow_used,
                "event_b_reached": event_b_reached,
                "event_b_time_s": None if event_b is None else event_b["time_s"],
                "event_b_absolute_step": None if event_b is None else event_b["absolute_step"],
                "event_b_primary_cell": None if event_b is None else event_b["primary_cell"],
                "event_b_distance_from_outlet_m": None if event_b is None else event_b["primary_distance_from_outlet_m"],
                "event_b_quality": None if event_b is None else event_b["quality"],
                "event_b_pressure_pa": None if event_b is None else event_b["pressure_pa"],
                "event_b_temperature_K": None if event_b is None else event_b["temperature_K"],
                "event_b_rho_kg_m3": None if event_b is None else event_b["rho_kg_m3"],
                "event_b_internal_energy_j_kg": None if event_b is None else event_b["internal_energy_j_kg"],
                "event_b_void_fraction": None if event_b is None else event_b["void_fraction"],
                "event_b_phase_front_distance_from_outlet_m": None if event_b is None else event_b[
                    "phase_front_distance_from_outlet_m"
                ],
                "event_b_state_sha256": "" if event_b is None else event_b["state_sha256"],
                "delta_t_a_to_b_s": delta_t,
                "delta_step_a_to_b": delta_step,
                "delta_x_front_a_to_b_m": delta_x,
                "shadow_failure_category": failure_category,
                "shadow_failure_reason": failure_reason,
            }
        )

    gates, ready = _evaluate(case_rows, interval_history)
    mesh_comparison, cfl_comparison, mesh_pattern, cfl_pattern, support = (
        _comparison_pattern(case_rows)
    )
    warnings = [
        "AUTHORITATIVE_P1_A3_REMAINS_FAIL_CLOSED_AND_INCONCLUSIVE",
        "FIXED_1E6_CROSSING_EVIDENCE_FLOOR_NOT_TUNED",
        "SHADOW_CONTINUATION_IS_DIAGNOSTIC_ONLY",
        "EVENT_A_TO_B_INTERVAL_IS_A_DISCRETE_HEM_NUMERICAL_THERMODYNAMIC_DIAGNOSTIC",
        "DO_NOT_INTERPRET_A_TO_B_AS_PHYSICAL_NUCLEATION_OR_FLASHING_DELAY",
        "MESH_AND_CFL_INDEPENDENCE_NOT_VERIFIED",
    ]
    payload = {
        "schema_version": P1_A3G_SCHEMA_VERSION,
        "scope": "crossing_event_alignment_with_authoritative_a3_frozen",
        "model_id": P1_A3G_MODEL_ID,
        "case_count": len(case_rows),
        "fixed_crossing_evidence_floor": P1_A3G_EVIDENCE_FLOOR,
        "maximum_shadow_steps": P1_A3G_MAX_SHADOW_STEPS,
        "threshold_or_tolerance_changed": False,
        "solver_or_physics_changed": False,
        "authoritative_a3_verdict": dict(P1_A3G_AUTHORITATIVE_A3),
        "authoritative_a3_verdict_changed": False,
        "case_alignment": case_rows,
        "event_a_cells": event_a_cells,
        "event_b_cells": event_b_cells,
        "event_interval_history": interval_history,
        "mesh_comparison": mesh_comparison,
        "cfl_comparison": cfl_comparison,
        "mesh_event_separation_pattern": mesh_pattern,
        "cfl_event_separation_pattern": cfl_pattern,
        "event_definition_interpretation": support,
        "subthreshold_case_ids": [
            row["case_id"]
            for row in case_rows
            if row["authoritative_crossing_status"] == "SUBTHRESHOLD_CROSSING_RETAINED"
        ],
        "event_b_unreached_case_ids": [
            row["case_id"] for row in case_rows if not row["event_b_reached"]
        ],
        "gates": list(gates),
        "gate_results": {str(gate["gate"]): bool(gate["passed"]) for gate in gates},
        "alignment_ready": ready,
        "alignment_execution_status": "ALIGNMENT_READY" if ready else "FAIL_CLOSED",
        "warnings": warnings,
        "provenance": _git_provenance(),
        "formal_status": dict(P1_A3G_FORMAL_STATUS),
    }
    digest_payload = dict(payload)
    payload["event_alignment_sha256"] = _canonical_json_sha256(digest_payload)
    return payload


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise P1A3GAlignmentError(f"cannot write empty CSV: {path.name}")
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        json.dumps(value, separators=(",", ":"))
                        if isinstance(value, (list, tuple, dict))
                        else value
                    )
                    for key, value in row.items()
                }
            )


def _plot_time(path: Path, rows: Sequence[dict[str, object]]) -> None:
    labels = [str(row["case_id"]) for row in rows]
    values = [
        np.nan if row["delta_t_a_to_b_s"] is None
        else 1.0e6 * float(row["delta_t_a_to_b_s"])
        for row in rows
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.bar(np.arange(len(labels)), values)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=22, ha="right")
    ax.set_ylabel("Event A -> B elapsed time [microseconds]")
    ax.set_title("P1-A3G Event A / Event B physical-time separation")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_steps(path: Path, rows: Sequence[dict[str, object]]) -> None:
    labels = [str(row["case_id"]) for row in rows]
    values = [
        np.nan if row["delta_step_a_to_b"] is None
        else float(row["delta_step_a_to_b"])
        for row in rows
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.bar(np.arange(len(labels)), values)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=22, ha="right")
    ax.set_ylabel("Accepted steps from Event A to Event B")
    ax.set_title("P1-A3G Event A / Event B step separation")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _fmt_optional(value: object, fmt: str = ".6g") -> str:
    if value is None:
        return "N/A"
    return format(float(value), fmt)


def _operator_report(summary: dict[str, object]) -> str:
    lines = [
        "# P1-A3G Crossing Event Alignment",
        "",
        f"- execution status: `{summary['alignment_execution_status']}`",
        f"- fixed evidence floor: `{summary['fixed_crossing_evidence_floor']}`",
        "- authoritative A3 verdict changed: `false`",
        f"- event-definition interpretation: `{summary['event_definition_interpretation']}`",
        f"- mesh pattern: `{summary['mesh_event_separation_pattern']}`",
        f"- CFL pattern: `{summary['cfl_event_separation_pattern']}`",
        "",
        "## Event A / Event B matrix",
        "",
        "| case | cells | CFL | A q | A outcome | shadow | B q | A->B us | steps | dx front [m] |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in summary["case_alignment"]:
        delta_us = (
            None if row["delta_t_a_to_b_s"] is None
            else 1.0e6 * float(row["delta_t_a_to_b_s"])
        )
        steps = "N/A" if row["delta_step_a_to_b"] is None else str(row["delta_step_a_to_b"])
        lines.append(
            "| {case} | {cells} | {cfl:.2f} | {aq:.12g} | {outcome} | {shadow} | "
            "{bq} | {dt} | {steps} | {dx} |".format(
                case=row["case_id"],
                cells=row["n_cells"],
                cfl=row["cfl"],
                aq=row["event_a_quality"],
                outcome=row["authoritative_outcome"],
                shadow=str(row["shadow_continuation_used"]).lower(),
                bq=_fmt_optional(row["event_b_quality"], ".12g"),
                dt=_fmt_optional(delta_us),
                steps=steps,
                dx=_fmt_optional(row["delta_x_front_a_to_b_m"]),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "Event A is the first retained thermodynamic entry into OPEN_TWO_PHASE. "
                "Event B is the first accepted state meeting the unchanged 1e-6 evidence floor. "
                "A3 remains FAIL_CLOSED / INCONCLUSIVE; the shadow continuation does not repair, "
                "override, or reclassify A3."
            ),
            "",
            (
                "A->B is an HEM numerical/thermodynamic event-alignment diagnostic. It is not "
                "a physical nucleation delay and does not establish mesh or CFL independence."
            ),
            "",
            "## Formal maturity boundary",
            "",
            "- IMPLEMENTED: true",
            "- WORKING VERTICAL SLICE: false",
            "- VERIFIED: false",
            "- ACCEPTED: false",
            "- PHYSICALLY VALIDATED: false",
            "- DESIGN-USE ACCEPTED: false",
            "- PRODUCTION APPROVED: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_crossing_event_alignment_artifacts(
    output_dir: str | Path,
    summary: dict[str, object],
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_A3G_OUTPUT_FILES)
    existing = {path.name for path in target.iterdir() if path.is_file()}
    unexpected = existing - expected
    if unexpected:
        raise P1A3GAlignmentError(
            f"output directory contains unexpected files: {sorted(unexpected)}"
        )
    paths = {
        "summary": target / "event_alignment_summary.json",
        "cases": target / "event_alignment_cases.csv",
        "event_a_cells": target / "event_a_cells.csv",
        "event_b_cells": target / "event_b_cells.csv",
        "history": target / "event_interval_history.csv",
        "time_plot": target / "event_ab_time_comparison.png",
        "step_plot": target / "event_ab_step_comparison.png",
        "operator_report": target / "operator_report.md",
        "manifest": target / "event_alignment_manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["cases"], summary["case_alignment"])
    _write_csv(paths["event_a_cells"], summary["event_a_cells"])
    _write_csv(paths["event_b_cells"], summary["event_b_cells"])
    _write_csv(paths["history"], summary["event_interval_history"])
    _plot_time(paths["time_plot"], summary["case_alignment"])
    _plot_steps(paths["step_plot"], summary["case_alignment"])
    paths["operator_report"].write_text(_operator_report(summary), encoding="utf-8")

    payload_files: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if key == "manifest":
            continue
        payload_files[path.name] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": P1_A3G_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_a3g_crossing_event_alignment_exactly_9_files",
        "declared_file_count": len(P1_A3G_OUTPUT_FILES),
        "declared_file_names": list(P1_A3G_OUTPUT_FILES),
        "alignment_execution_status": summary["alignment_execution_status"],
        "alignment_ready": summary["alignment_ready"],
        "event_alignment_sha256": summary["event_alignment_sha256"],
        "threshold_or_tolerance_changed": False,
        "solver_or_physics_changed": False,
        "authoritative_a3_verdict_changed": False,
        "payload_files": payload_files,
        "formal_status": dict(P1_A3G_FORMAL_STATUS),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1A3GAlignmentError(
            f"A3G output contract mismatch: expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    summary = analyze_crossing_event_alignment()
    paths = write_crossing_event_alignment_artifacts(output_dir, summary)
    output = dict(summary)
    output["artifact_paths"] = {key: str(path) for key, path in paths.items()}
    return output


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Quantify Event A thermodynamic crossing versus Event B fixed-evidence-floor "
            "crossing without changing the authoritative P1-A3 result."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["alignment_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
