from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_a1_weak_compression_bridge_short_run_scope_roundoff as scope_roundoff
import u3_b2_characteristic_port_diagnostic as diagnostic
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
)
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
)


PARENT_SOURCE_SHA = "00a410127c10d5c2fa2f79c7471daa8f896a0e76"
PARENT_WORKFLOW_RUN = 31605175607
PARENT_JOB = 94142164951
PARENT_ARTIFACT = 9144936292
PARENT_ARTIFACT_SHA256 = (
    "eaaf54b9012ed2748c1e0d425a238915a030c497517a6651f7f916a8b09ecaf6"
)
PARENT_OUTCOME = "WEAK_COMPRESSION_INCREMENT_3_32_STEP_PASS"
PARENT_SOLVER_STEP = 369
PARENT_ACCEPTED_STEPS = 32
PARENT_SOLVER_TIME_S = 0.0024719939763977834
TARGET_TWO_L_OVER_C0_S = 0.004285834855172021
MAX_SOLVER_STEP = 10000
OUTCOME = "WEAK_COMPRESSION_INCREMENT_4_FULL_HORIZON_WORKING_SLICE_PASS"
PARENT_REQUIRED_FILES = {
    "short_run_steps.csv",
    "short_run_roots.csv",
    "local_wave_scans.csv",
    "positive_pressure_scans.csv",
    "branch_transitions.csv",
    "short_run_states.npz",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}

# Apply the already-fixed scan-coordinate bookkeeping before any continuation
# root is evaluated.  The physical model, tolerance, and chi scope are unchanged.
short_run._positive_pressure_scan = (
    scope_roundoff._corrected_positive_pressure_scan
)


class FullHorizonStop(short_run.WeakCompressionShortRunStop):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _verify_parent_manifest(parent_dir: Path) -> dict[str, str]:
    actual_files = {path.name for path in parent_dir.iterdir() if path.is_file()}
    if actual_files != PARENT_REQUIRED_FILES:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent artifact files do not match the fixed Increment 3 set: "
            f"actual={sorted(actual_files)}",
        )
    manifest: dict[str, str] = {}
    for line in (parent_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    expected_names = PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}
    if set(manifest) != expected_names:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent internal manifest names do not match the fixed evidence set",
        )
    for name, digest in manifest.items():
        actual = _sha256(parent_dir / name)
        if actual != digest:
            raise FullHorizonStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent internal SHA256 mismatch for {name}: {actual}",
            )
    return manifest


def _load_parent(
    parent_dir: Path,
    *,
    parent_artifact_digest: str,
) -> dict[str, Any]:
    if parent_artifact_digest != PARENT_ARTIFACT_SHA256:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent GitHub artifact digest does not match the fixed Increment 3 "
            f"digest: {parent_artifact_digest}",
        )
    manifest = _verify_parent_manifest(parent_dir)
    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    steps = _read_csv(parent_dir / "short_run_steps.csv")
    roots = _read_csv(parent_dir / "short_run_roots.csv")
    transitions = _read_csv(parent_dir / "branch_transitions.csv")
    if summary.get("source_git_sha") != PARENT_SOURCE_SHA:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent source SHA does not match the fixed Increment 3 source",
        )
    if summary.get("outcome") != PARENT_OUTCOME or not bool(
        summary.get("increment_3_32_step_gate_passed")
    ):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent Increment 3 outcome or gate is not accepted",
        )
    if int(summary.get("solver_step_after", -1)) != PARENT_SOLVER_STEP:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent solver step is not 369",
        )
    if float(summary.get("solver_time_after_s", np.nan)) != (
        PARENT_SOLVER_TIME_S
    ):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent solver time does not match the fixed step-369 evidence",
        )
    if len(steps) != PARENT_ACCEPTED_STEPS or len(roots) != (
        PARENT_ACCEPTED_STEPS
    ):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent accepted step/root row count is not 32",
        )
    if len(transitions) != PARENT_ACCEPTED_STEPS:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent branch transition row count is not 32",
        )
    expected_steps = list(range(338, 370))
    if [int(row["solver_step_count"]) for row in steps] != expected_steps:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent solver step sequence is not 338 through 369",
        )
    if [int(row["requested_solver_step"]) for row in roots] != expected_steps:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent root step sequence is not 338 through 369",
        )
    if not all(row["increment_3_per_step_gate_passed"] == "True" for row in steps):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "one or more parent per-step gates are not passed",
        )
    states_path = parent_dir / "short_run_states.npz"
    with np.load(states_path) as states:
        U_start = np.asarray(states["U_start"], dtype=float).copy()
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_before = int(states["solver_step_before"][0])
        step_after = int(states["solver_step_after"][0])
        time_before = float(states["solver_time_before_s"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_start.shape != (32, 4) or U_final.shape != (32, 4):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent conserved-state shape is not (32, 4)",
        )
    if not np.all(np.isfinite(U_final)) or not np.all(U_final[:, 0] > 0.0):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent final conserved state is nonfinite or nonpositive",
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent final rho*xv is not exact zero",
        )
    if step_before != 337 or step_after != PARENT_SOLVER_STEP:
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent NPZ solver-step identity is not 337 -> 369",
        )
    if time_before != float(summary["solver_time_before_s"]) or time_after != (
        PARENT_SOLVER_TIME_S
    ):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent NPZ solver-time identity does not match summary evidence",
        )
    branch_sequence = [str(value) for value in summary["branch_sequence"]]
    if len(branch_sequence) != PARENT_ACCEPTED_STEPS or not set(
        branch_sequence
    ).issubset(short_run.ALLOWED_BRANCHES):
        raise FullHorizonStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent branch history is outside the fixed three-branch set",
        )
    return {
        "summary": summary,
        "steps": steps,
        "roots": roots,
        "transitions": transitions,
        "U_start": U_start,
        "U_final": U_final,
        "manifest": manifest,
        "artifact_digest": parent_artifact_digest,
        "branch_sequence": branch_sequence,
    }


def _probe_summary(
    probe_rows: list[dict[str, Any]],
    probe_indices: list[int],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index in probe_indices:
        pressure_key = f"probe_cell_{index}_pressure_pa"
        velocity_key = f"probe_cell_{index}_velocity_m_s"
        pressures = [float(row[pressure_key]) for row in probe_rows]
        velocities = [float(row[velocity_key]) for row in probe_rows]
        result[f"cell_{index}"] = {
            "x_m": float(probe_rows[0][f"probe_cell_{index}_x_m"]),
            "minimum_pressure_pa": min(pressures),
            "maximum_pressure_pa": max(pressures),
            "minimum_velocity_m_s": min(velocities),
            "maximum_velocity_m_s": max(velocities),
        }
    return result


def _run_full_horizon(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    parent: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    np.ndarray,
    np.ndarray,
]:
    case = diagnostic._case(contract, short_run.CASE_ID)
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
    initial_sound_speed = float(initial_static.sound_speed_m_s)
    one_way_time_s = float(pipe.length_m / initial_sound_speed)
    target_time_s = float(2.0 * one_way_time_s)
    target_spacing = float(np.spacing(target_time_s))
    if abs(target_time_s - TARGET_TWO_L_OVER_C0_S) > 8.0 * target_spacing:
        raise FullHorizonStop(
            "TARGET_HORIZON_MISMATCH",
            "reconstructed 2L/c0 does not match the fixed Increment 4 target: "
            f"{target_time_s}",
        )

    U_parent = np.asarray(parent["U_final"], dtype=float).copy()
    parent_summary = parent["summary"]
    parent_steps = parent["steps"]
    parent_roots = parent["roots"]
    parent_last_step = parent_steps[-1]
    parent_last_root = parent_roots[-1]

    hook = short_run.A1WeakCompressionBridgeShortRunHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=short_run.CASE_ID,
        provider=provider,
    )
    hook.accepted_branch_history = [
        "NEUTRAL_ENDPOINT",
        *parent["branch_sequence"],
    ]
    hook._previous_root_pressure_pa = float(
        parent_last_root["root_pressure_pa"]
    )
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=U_parent,
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=float(parent_summary["solver_time_after_s"]),
        step_count=int(parent_summary["solver_step_after"]),
    )
    if not float(solver.t) < target_time_s:
        raise FullHorizonStop(
            "TARGET_HORIZON_MISMATCH",
            "parent state is not before the fixed 2L/c0 horizon",
        )

    initial = inventory(
        U_initial,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current_minus_initial = _inventory_array(current) - _inventory_array(initial)
    parent_cumulative_residual = np.asarray(
        [
            float(parent_last_step["cumulative_mass_residual_kg"]),
            float(parent_last_step["cumulative_momentum_residual_kg_m_s"]),
            float(parent_last_step["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )
    cumulative_expected_delta = (
        current_minus_initial - parent_cumulative_residual
    )

    step_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    local_scan_rows: list[dict[str, Any]] = []
    positive_scan_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None
    stop_diagnostics: dict[str, Any] = {}
    probes = horizon._probe_indices(grid.n_cells)
    U_continuation_start = np.asarray(solver.U, dtype=float).copy()

    while float(solver.t) < target_time_s:
        requested_solver_step = int(solver.step_count + 1)
        if requested_solver_step > MAX_SOLVER_STEP:
            stop_classification = "OPERATIONAL_STEP_CAP_EXCEEDED"
            stop_reason = (
                f"OPERATIONAL_STEP_CAP_EXCEEDED: solver step exceeded "
                f"{MAX_SOLVER_STEP} before 2L/c0"
            )
            break
        accepted_dt_for_stop: float | None = None
        time_before_for_stop = float(solver.t)
        try:
            before = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            computed_dt = float(solver.compute_dt())
            dt_limits = dict(hook.last_dt_limits)
            if hook.root_context is None:
                raise FullHorizonStop(
                    "ROOT_OR_LEDGER_FAILURE",
                    "branch-aware root was not prepared by compute_dt",
                )
            context = hook.root_context
            branch = str(context["branch_classification"])
            history_before = list(hook.accepted_branch_history)
            remaining_time = float(target_time_s - solver.t)
            candidate_dt = float(min(computed_dt, remaining_time))
            final_horizon_clip_requested = bool(candidate_dt < computed_dt)
            if not np.isfinite(candidate_dt) or candidate_dt <= 0.0:
                raise FullHorizonStop(
                    "NONPOSITIVE_HORIZON_DT",
                    f"non-positive clipped horizon candidate dt: {candidate_dt}",
                )

            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)
            accepted_dt = float(solver.step(candidate_dt))
            accepted_dt_for_stop = accepted_dt
            hook.accept_current_root()
            if not np.isfinite(accepted_dt) or accepted_dt <= 0.0:
                raise FullHorizonStop(
                    "NONPOSITIVE_ACCEPTED_DT",
                    f"accepted dt is not positive and finite: {accepted_dt}",
                )

            after = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            expected_step_delta = (
                accepted_dt
                * grid.geometry.area_m2
                * (left_flux - right_flux)
            )
            cumulative_expected_delta += expected_step_delta
            primitive_after = solver.primitive()
            post_reconstruction = provider.reconstruct_from_conserved(
                solver.U[-1]
            )
            row = build_step_row(
                case_id=short_run.CASE_ID,
                state_id=state_id,
                requested_step=requested_solver_step,
                solver=solver,
                hook=hook,
                root_context=context,
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
            rho_after = np.asarray(solver.U[:, 0], dtype=float)
            velocity_after = np.asarray(
                solver.U[:, 1] / rho_after,
                dtype=float,
            )
            internal_after = np.asarray(
                solver.U[:, 2] / rho_after - 0.5 * velocity_after**2,
                dtype=float,
            )
            row.update(
                {
                    "branch_classification": branch,
                    "endpoint_residual_kg_s": float(
                        context["endpoint_residual_kg_s"]
                    ),
                    "endpoint_within_locked_root_mass_tolerance": bool(
                        context[
                            "endpoint_within_locked_root_mass_tolerance"
                        ]
                    ),
                    "connected_rarefaction_sign_change_count": int(
                        context[
                            "connected_rarefaction_sign_change_count"
                        ]
                    ),
                    "connected_rarefaction_residual_monotone": bool(
                        context[
                            "connected_rarefaction_residual_monotone"
                        ]
                    ),
                    "positive_scan_sign_change_count": int(
                        context["positive_scan_sign_change_count"]
                    ),
                    "positive_scan_residual_monotone_nonincreasing": context[
                        "positive_scan_residual_monotone_nonincreasing"
                    ],
                    "p_P_minus_p_i_pa": float(
                        context["p_P_minus_p_i_pa"]
                    ),
                    "root_chi": float(context["root_chi"]),
                    "chi_max": short_run.CHI_MAX,
                    "weak_compression_bisection_iterations": int(
                        context.get(
                            "weak_compression_bisection_iterations",
                            0,
                        )
                    ),
                    "branch_history_before": history_before,
                    "branch_history_after": list(
                        hook.accepted_branch_history
                    ),
                    "clear_branch_chatter_detected": False,
                    "minimum_density_after_step_kg_m3": float(
                        np.min(rho_after)
                    ),
                    "minimum_internal_energy_after_step_J_kg": float(
                        np.min(internal_after)
                    ),
                    "all_conserved_finite_after_step": bool(
                        np.all(np.isfinite(solver.U))
                    ),
                    "positive_pressure_continuation_flux_applied": bool(
                        branch == "WEAK_COMPRESSION"
                    ),
                    "finite_compression_branch_approved": False,
                    "computed_dt_s": computed_dt,
                    "remaining_time_before_step_s": remaining_time,
                    "final_horizon_clip_requested": final_horizon_clip_requested,
                    "target_two_l_over_c0_time_s": target_time_s,
                    "horizon_fraction_before": float(
                        time_before_for_stop / target_time_s
                    ),
                    "horizon_fraction_after": float(solver.t / target_time_s),
                    "reached_one_way_l_over_c0": bool(
                        solver.t >= one_way_time_s
                    ),
                    "reached_two_way_two_l_over_c0": bool(
                        solver.t >= target_time_s
                    ),
                }
            )
            for index in probes:
                row[f"probe_cell_{index}_x_m"] = float(
                    (index + 0.5) * grid.dx
                )
                row[f"probe_cell_{index}_pressure_pa"] = float(
                    primitive_after.p[index]
                )
                row[f"probe_cell_{index}_velocity_m_s"] = float(
                    primitive_after.u[index]
                )

            branch_specific = bool(
                (
                    branch == "WEAK_COMPRESSION"
                    and int(row["positive_scan_sign_change_count"]) == 1
                    and 0.0 < float(row["root_chi"]) <= short_run.CHI_MAX
                    and float(row["p_P_minus_p_i_pa"]) > 0.0
                )
                or (
                    branch == "RAREFACTION"
                    and int(
                        row["connected_rarefaction_sign_change_count"]
                    )
                    == 1
                    and float(row["p_P_minus_p_i_pa"]) < 0.0
                )
                or (
                    branch == "NEUTRAL_ENDPOINT"
                    and bool(
                        row[
                            "endpoint_within_locked_root_mass_tolerance"
                        ]
                    )
                    and float(row["p_P_minus_p_i_pa"]) == 0.0
                )
            )
            per_step_gate = bool(
                branch in short_run.ALLOWED_BRANCHES
                and branch_specific
                and bool(row["accepted_step"])
                and int(row["solver_step_count"]) == requested_solver_step
                and accepted_dt > 0.0
                and abs(float(row["root_mass_residual_kg_s"]))
                <= short_run.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
                and float(row["root_velocity_m_s"]) >= 0.0
                and 0.0 <= float(row["root_mach"]) < 1.0
                and bool(row["stagnation_enthalpy_round_trip_passed"])
                and bool(row["energy_mass_consistency_passed"])
                and bool(row["energy_port_closure_passed"])
                and abs(
                    float(
                        row[
                            "restriction_reaction_ledger_residual_N"
                        ]
                    )
                )
                <= short_run.robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
                and bool(row["all_conserved_finite_after_step"])
                and float(row["minimum_density_after_step_kg_m3"]) > 0.0
                and float(
                    row["minimum_internal_energy_after_step_J_kg"]
                )
                > 0.0
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
                and bool(row["step_passed"])
            )
            row["increment_4_per_step_gate_passed"] = per_step_gate
            step_rows.append(row)
            root_rows.append(
                short_run._root_evidence_row(
                    context=context,
                    requested_solver_step=requested_solver_step,
                )
            )
            local_scan_rows.extend(
                short_run._flatten_scan(
                    rows=list(context["local_scan_rows"]),
                    requested_solver_step=requested_solver_step,
                    solver_time_s=float(context["solver_time_s"]),
                    branch=branch,
                    scan_kind="LOCAL_FIXED_OFFSETS",
                )
            )
            if context["positive_scan_rows"]:
                positive_scan_rows.extend(
                    short_run._flatten_scan(
                        rows=list(context["positive_scan_rows"]),
                        requested_solver_step=requested_solver_step,
                        solver_time_s=float(context["solver_time_s"]),
                        branch=branch,
                        scan_kind="POSITIVE_CHI_SCOPED",
                    )
                )
            previous_branch = history_before[-1]
            transition_rows.append(
                {
                    "from_solver_step": requested_solver_step - 1,
                    "to_solver_step": requested_solver_step,
                    "from_branch": previous_branch,
                    "to_branch": branch,
                    "branch_changed": bool(previous_branch != branch),
                    "clear_branch_chatter_detected": False,
                    "five_point_history_after": list(
                        hook.accepted_branch_history[-5:]
                    ),
                }
            )
            probe_rows.append(
                {
                    "solver_step_count": int(solver.step_count),
                    "time_s": float(solver.t),
                    "horizon_fraction": float(solver.t / target_time_s),
                    **{
                        key: value
                        for key, value in row.items()
                        if key.startswith("probe_cell_")
                    },
                }
            )
            if not per_step_gate:
                raise FullHorizonStop(
                    "PER_STEP_GATE_FAILURE",
                    f"accepted step {requested_solver_step} failed the fixed "
                    "Increment 4 gate",
                    {"step_row": row},
                )
        except FullHorizonStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{exc.classification}: {exc}"
            stop_diagnostics = dict(exc.diagnostics)
            if step_rows and int(step_rows[-1].get("requested_step", -1)) == (
                requested_solver_step
            ):
                step_rows[-1]["stop_classification"] = stop_classification
                step_rows[-1]["stop_reason"] = stop_reason
            else:
                step_rows.append(
                    {
                        "case_id": short_run.CASE_ID,
                        "state_id": state_id,
                        "requested_step": requested_solver_step,
                        "accepted_step": accepted_dt_for_stop is not None,
                        "solver_step_count": int(solver.step_count),
                        "time_before_s": time_before_for_stop,
                        "time_after_s": float(solver.t),
                        "accepted_dt_s": accepted_dt_for_stop,
                        "step_passed": False,
                        "increment_4_per_step_gate_passed": False,
                        "stop_classification": stop_classification,
                        "stop_reason": stop_reason,
                    }
                )
            break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            stop_diagnostics = {}
            if step_rows and int(step_rows[-1].get("requested_step", -1)) == (
                requested_solver_step
            ):
                step_rows[-1]["stop_classification"] = stop_classification
                step_rows[-1]["stop_reason"] = stop_reason
            else:
                step_rows.append(
                    {
                        "case_id": short_run.CASE_ID,
                        "state_id": state_id,
                        "requested_step": requested_solver_step,
                        "accepted_step": accepted_dt_for_stop is not None,
                        "solver_step_count": int(solver.step_count),
                        "time_before_s": time_before_for_stop,
                        "time_after_s": float(solver.t),
                        "accepted_dt_s": accepted_dt_for_stop,
                        "step_passed": False,
                        "increment_4_per_step_gate_passed": False,
                        "stop_classification": stop_classification,
                        "stop_reason": stop_reason,
                    }
                )
            break

    complete_rows = [
        row
        for row in step_rows
        if row.get("accepted_step") is True
        and row.get("branch_classification") in short_run.ALLOWED_BRANCHES
    ]
    continuation_branch_sequence = [
        str(row["branch_classification"]) for row in complete_rows
    ]
    total_branch_sequence = [
        *parent["branch_sequence"],
        *continuation_branch_sequence,
    ]
    continuation_counts = Counter(continuation_branch_sequence)
    total_counts = Counter(total_branch_sequence)
    time_error_s = float(solver.t - target_time_s)
    time_tolerance_s = float(8.0 * np.spacing(target_time_s))
    horizon_reached = bool(
        stop_reason is None
        and complete_rows
        and abs(time_error_s) <= time_tolerance_s
        and all(
            bool(row["increment_4_per_step_gate_passed"])
            for row in complete_rows
        )
        and int(solver.step_count) <= MAX_SOLVER_STEP
    )
    final_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
    U_final = np.asarray(solver.U, dtype=float).copy()
    parent_verification = {
        "parent_source_git_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_internal_manifest": parent["manifest"],
        "parent_outcome": parent_summary["outcome"],
        "parent_gate_passed": bool(
            parent_summary["increment_3_32_step_gate_passed"]
        ),
        "parent_solver_step": int(parent_summary["solver_step_after"]),
        "parent_solver_time_s": float(parent_summary["solver_time_after_s"]),
        "parent_accepted_steps": len(parent_steps),
        "parent_final_state_shape": list(U_parent.shape),
        "parent_final_state_finite": bool(np.all(np.isfinite(U_parent))),
        "parent_final_density_positive": bool(np.all(U_parent[:, 0] > 0.0)),
        "parent_final_rho_xv_exact_zero": bool(np.all(U_parent[:, 3] == 0.0)),
        "parent_artifact_verified": True,
    }
    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4"
        ),
        "scope": "model_review_working_vertical_slice_full_two_l_over_c0",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_artifact_verified": True,
        "parent_outcome": parent_summary["outcome"],
        "case_id": short_run.CASE_ID,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "pipe_length_m": float(pipe.length_m),
        "initial_sound_speed_m_s": initial_sound_speed,
        "one_way_acoustic_time_s": one_way_time_s,
        "target_two_l_over_c0_time_s": target_time_s,
        "solver_step_before": PARENT_SOLVER_STEP,
        "solver_step_after": int(solver.step_count),
        "solver_time_before_s": PARENT_SOLVER_TIME_S,
        "solver_time_after_s": float(solver.t),
        "horizon_time_error_s": time_error_s,
        "horizon_time_roundoff_tolerance_s": time_tolerance_s,
        "horizon_fraction_reached": float(solver.t / target_time_s),
        "continuation_accepted_steps_completed": len(complete_rows),
        "total_accepted_steps_from_parent_step_337": (
            PARENT_ACCEPTED_STEPS + len(complete_rows)
        ),
        "maximum_operational_solver_step": MAX_SOLVER_STEP,
        "parent_branch_sequence": parent["branch_sequence"],
        "continuation_branch_sequence": continuation_branch_sequence,
        "continuation_branch_counts": {
            branch: int(continuation_counts.get(branch, 0))
            for branch in sorted(short_run.ALLOWED_BRANCHES)
        },
        "total_branch_counts_from_step_338": {
            branch: int(total_counts.get(branch, 0))
            for branch in sorted(short_run.ALLOWED_BRANCHES)
        },
        "continuation_branch_transition_count": int(
            sum(bool(row["branch_changed"]) for row in transition_rows)
        ),
        "total_branch_transition_count_from_step_337": int(
            int(parent_summary["branch_transition_count"])
            + sum(bool(row["branch_changed"]) for row in transition_rows)
        ),
        "clear_branch_chatter_detected": False,
        "clear_branch_chatter_rule": "five accepted classifications A-B-A-B-A",
        "maximum_continuation_weak_compression_chi": _maximum(
            [
                row
                for row in complete_rows
                if row["branch_classification"] == "WEAK_COMPRESSION"
            ],
            "root_chi",
        ),
        "maximum_total_weak_compression_chi": max(
            value
            for value in (
                float(parent_summary["maximum_weak_compression_chi"]),
                _maximum(
                    [
                        row
                        for row in complete_rows
                        if row["branch_classification"] == "WEAK_COMPRESSION"
                    ],
                    "root_chi",
                ),
            )
            if value is not None
        ),
        "minimum_continuation_root_pressure_offset_pa": _minimum(
            complete_rows,
            "p_P_minus_p_i_pa",
        ),
        "maximum_continuation_root_pressure_offset_pa": _maximum(
            complete_rows,
            "p_P_minus_p_i_pa",
        ),
        "maximum_absolute_continuation_root_mass_residual_kg_s": _max_abs(
            complete_rows,
            "root_mass_residual_kg_s",
        ),
        "maximum_continuation_root_mach": _maximum(
            complete_rows,
            "root_mach",
        ),
        "minimum_continuation_root_velocity_m_s": _minimum(
            complete_rows,
            "root_velocity_m_s",
        ),
        "maximum_continuation_halving_count": _maximum(
            complete_rows,
            "halving_count",
        ),
        "maximum_absolute_continuation_step_mass_residual_kg": _max_abs(
            complete_rows,
            "step_mass_residual_kg",
        ),
        "maximum_absolute_continuation_step_momentum_residual_kg_m_s": _max_abs(
            complete_rows,
            "step_momentum_residual_kg_m_s",
        ),
        "maximum_absolute_continuation_step_energy_residual_J": _max_abs(
            complete_rows,
            "step_energy_residual_J",
        ),
        "maximum_absolute_full_cumulative_mass_residual_kg": _max_abs(
            complete_rows,
            "cumulative_mass_residual_kg",
        ),
        "maximum_absolute_full_cumulative_momentum_residual_kg_m_s": _max_abs(
            complete_rows,
            "cumulative_momentum_residual_kg_m_s",
        ),
        "maximum_absolute_full_cumulative_energy_residual_J": _max_abs(
            complete_rows,
            "cumulative_energy_residual_J",
        ),
        "final_outlet_pressure_pa": float(
            final_reconstruction.static.pressure_pa
        ),
        "final_outlet_velocity_m_s": float(
            final_reconstruction.static.velocity_m_s
        ),
        "final_outlet_mach": float(
            final_reconstruction.static.velocity_m_s
            / final_reconstruction.static.sound_speed_m_s
        ),
        "final_outlet_phase": final_reconstruction.static.phase,
        "final_minimum_density_kg_m3": float(np.min(U_final[:, 0])),
        "final_minimum_internal_energy_J_kg": float(
            np.min(
                U_final[:, 2] / U_final[:, 0]
                - 0.5 * (U_final[:, 1] / U_final[:, 0]) ** 2
            )
        ),
        "final_rho_xv_exact_zero": bool(np.all(U_final[:, 3] == 0.0)),
        "probe_observation": (
            _probe_summary(probe_rows, probes) if probe_rows else {}
        ),
        "acoustic_timing_validation_performed": False,
        "acoustic_probe_series_purpose": (
            "observation_only_for_follow_on_direct_reflected_acoustic_validation"
        ),
        "final_step_clipped_to_target_horizon": bool(
            complete_rows and complete_rows[-1]["final_horizon_clip_requested"]
        ),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "stop_diagnostics_keys": sorted(stop_diagnostics),
        "outcome": OUTCOME if horizon_reached else "INCREMENT_4_STOPPED",
        "working_vertical_slice_two_l_over_c0_passed": horizon_reached,
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
        step_rows,
        root_rows,
        local_scan_rows,
        positive_scan_rows,
        transition_rows,
        probe_rows,
        parent_verification,
        summary,
        U_continuation_start,
        U_final,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    parent = _load_parent(
        args.parent_artifact_dir,
        parent_artifact_digest=args.parent_artifact_digest,
    )
    (
        step_rows,
        root_rows,
        local_scan_rows,
        positive_scan_rows,
        transition_rows,
        probe_rows,
        parent_verification,
        summary,
        U_start,
        U_final,
    ) = _run_full_horizon(
        contract=contract,
        b1_contract=b1_contract,
        parent=parent,
    )
    summary["source_git_sha"] = args.source_git_sha

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "full_horizon_continuation_steps.csv", step_rows)
    _write_csv(output / "full_horizon_continuation_roots.csv", root_rows)
    _write_csv(output / "local_wave_scans.csv", local_scan_rows)
    _write_csv(output / "positive_pressure_scans.csv", positive_scan_rows)
    _write_csv(output / "branch_transitions.csv", transition_rows)
    _write_csv(output / "probe_series.csv", probe_rows)
    np.savez_compressed(
        output / "full_horizon_states.npz",
        U_start=np.asarray(U_start, dtype=float),
        U_final=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray([PARENT_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray(
            [summary["solver_step_after"]],
            dtype=np.int64,
        ),
        solver_time_before_s=np.asarray([PARENT_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([summary["solver_time_after_s"]]),
        target_two_l_over_c0_time_s=np.asarray(
            [summary["target_two_l_over_c0_time_s"]]
        ),
    )
    (output / "parent_verification.json").write_text(
        json.dumps(parent_verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 4\n\n"
        "MODEL_REVIEW / WORKING_VERTICAL_SLICE evidence only. The exact "
        "accepted Increment 3 step-369 state and cumulative finite-volume "
        "ledger were loaded from the authoritative parent artifact, then the "
        "unchanged three-branch A1 boundary continued to the clipped nominal "
        "`2L/c0` horizon. A passing result does not verify finite-pipe coupling, "
        "accept a benchmark, perform Physical Validation, approve design use, "
        "or activate production behavior.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "full_horizon_continuation_steps.csv",
        "full_horizon_continuation_roots.csv",
        "local_wave_scans.csv",
        "positive_pressure_scans.csv",
        "branch_transitions.csv",
        "probe_series.csv",
        "full_horizon_states.npz",
        "parent_verification.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["working_vertical_slice_two_l_over_c0_passed"]:
        raise SystemExit(
            "Weak Compression Bridge Increment 4 did not pass: "
            f"{summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
