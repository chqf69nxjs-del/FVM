from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_guard_front_8_step as runner
import u3_b2_a1_finite_compression_guard_front_8_step_dynamic_topology_fix  # noqa: F401
import u3_b2_characteristic_port_diagnostic as diagnostic
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
from u3_b2_characteristic_port_dynamic_short_metrics import build_step_row, inventory


PARENT_SOURCE_SHA = "19955eec9802d092de3986a213a0db9fbc62c597"
PARENT_RUN = 31667111385
PARENT_JOB = 94343960303
PARENT_ARTIFACT = 9168340553
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-8d-dynamic-32-step-31667111385"
)
PARENT_DIGEST = (
    "f7d0821f7b12f14488c42856a8d24bb426bdfa17754be21011ebbd0fc5dbeadf"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_8D_DYNAMIC_32_STEP_PASS"
STARTING_STEP = 534
STARTING_TIME_S = 0.0035786412795834176
TARGET_TIME_S = 0.004285834855172021
HORIZON_ROUNDOFF_TOLERANCE_S = 8.0 * float(np.spacing(TARGET_TIME_S))
MAXIMUM_OPERATIONAL_SOLVER_STEP = 700
OUTCOME = "FINITE_COMPRESSION_INCREMENT_9D_DYNAMIC_FULL_HORIZON_WORKING_SLICE_PASS"

PARENT_REQUIRED_FILES = {
    "finite_compression_steps.csv",
    "finite_compression_roots.csv",
    "hugoniot_fixed_scans.csv",
    "guard_front_refinement.csv",
    "root_topology.csv",
    "hugoniot_density_search.csv",
    "branch_sequence.csv",
    "finite_compression_32_step_states.npz",
    "authority_verification.json",
    "stop_evidence.json",
    "step524_checkpoint.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(U, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _clear_chatter(branches: list[str]) -> bool:
    return any(
        seq[0] == seq[2] == seq[4]
        and seq[1] == seq[3]
        and seq[0] != seq[1]
        for seq in (
            branches[index : index + 5]
            for index in range(max(len(branches) - 4, 0))
        )
        if len(seq) == 5
    )


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str], dict[str, str]]:
    if artifact_digest != PARENT_DIGEST:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D GitHub artifact digest mismatch",
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"Increment 8D file set mismatch: {sorted(actual)}",
        )

    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise runner.ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 8D internal SHA256 mismatch for {name}",
            )

    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "increment_8d_32_step_gate_passed": True,
        "starting_solver_step": 502,
        "requested_accepted_steps": 32,
        "accepted_steps_completed": 32,
        "final_solver_step": STARTING_STEP,
        "final_solver_time_s": STARTING_TIME_S,
        "branch_transition_count": 0,
        "stop_classification": None,
        "stop_reason": None,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise runner.ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 8D summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(directory / "finite_compression_32_step_states.npz") as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_after.shape != (32, 4):
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8D final state shape is not (32, 4)",
        )
    if step_after != STARTING_STEP or time_after != STARTING_TIME_S:
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8D solver identity mismatch",
        )
    if not np.all(np.isfinite(U_after)):
        raise runner.ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 8D final state contains nonfinite values",
        )
    rho = np.asarray(U_after[:, 0], dtype=float)
    velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
    internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise runner.ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 8D final density or internal energy is nonpositive",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8D final rho*xv is not exact zero",
        )

    step_rows = _read_csv(directory / "finite_compression_steps.csv")
    root_rows = _read_csv(directory / "finite_compression_roots.csv")
    if len(step_rows) != 32 or len(root_rows) != 32:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D step/root row count mismatch",
        )
    last_step = step_rows[-1]
    last_root = root_rows[-1]
    if int(last_step["solver_step_count"]) != STARTING_STEP:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D last accepted step is not 534",
        )
    if float(last_step["time_after_s"]) != STARTING_TIME_S:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D last-step time mismatch",
        )
    if last_step.get("accepted_step") != "True" or last_step.get(
        "increment_8d_per_step_gate_passed"
    ) != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D last accepted-step gate did not pass",
        )
    if int(last_root["requested_solver_step"]) != STARTING_STEP:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D last root is not for requested step 534",
        )
    if last_root.get("root_gate_passed") != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8D last selected-root gate did not pass",
        )
    return summary, U_after, last_step, last_root


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U_start: np.ndarray,
    parent_step: dict[str, str],
    parent_root: dict[str, str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    np.ndarray,
    np.ndarray,
]:
    case = diagnostic._case(contract, runner.base.CASE_ID)
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
    hook = runner.DynamicGuardFrontHugoniotHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=runner.base.CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(parent_root["root_pressure_pa"])
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider, boundary_temperature_K=initial_static.temperature_K
        ),
        U=np.asarray(U_start, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=STARTING_TIME_S,
        step_count=STARTING_STEP,
    )
    initial = inventory(U_initial, dx=grid.dx, area_m2=grid.geometry.area_m2)
    starting = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    current_minus_initial = _inventory_array(starting) - _inventory_array(initial)
    cumulative_residual = np.asarray(
        [
            float(parent_step["cumulative_mass_residual_kg"]),
            float(parent_step["cumulative_momentum_residual_kg_m_s"]),
            float(parent_step["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )
    cumulative_expected_delta = current_minus_initial - cumulative_residual
    U_before_all = np.asarray(solver.U, dtype=float).copy()

    step_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    guard_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    density_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None

    while solver.t < TARGET_TIME_S - HORIZON_ROUNDOFF_TOLERANCE_S:
        if int(solver.step_count) >= MAXIMUM_OPERATIONAL_SOLVER_STEP:
            stop_classification = "OPERATIONAL_STEP_CAP_EXCEEDED"
            stop_reason = (
                "ShortRunStop: operational solver-step cap "
                f"{MAXIMUM_OPERATIONAL_SOLVER_STEP} reached before target"
            )
            break
        requested_step = int(solver.step_count + 1)
        try:
            before = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
            candidate_dt = float(solver.compute_dt())
            context = hook.root_context
            if context is None:
                raise runner.ShortRunStop(
                    "ROOT_OR_LEDGER_FAILURE",
                    "dynamic Hugoniot root context was not prepared",
                )
            dt_limits = dict(hook.last_dt_limits)
            root_row = runner._root_row(
                context, requested_step=requested_step
            )
            fixed_rows.extend(
                runner._flatten(
                    context["fixed_scan_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="HUGONIOT_FIXED_SCAN",
                )
            )
            guard_rows.extend(
                runner._flatten(
                    context["guard_front_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="B1_GUARD_FRONT_REFINEMENT",
                )
            )
            topology_rows.extend(
                runner._flatten(
                    context["root_topology_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="ROOT_TOPOLOGY",
                )
            )
            density_rows.extend(
                runner._flatten(
                    context["density_search_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="HUGONIOT_DENSITY_SEARCH",
                )
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
                case_id=runner.base.CASE_ID,
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
            rho = np.asarray(solver.U[:, 0], dtype=float)
            velocity = np.asarray(solver.U[:, 1] / rho, dtype=float)
            internal = np.asarray(
                solver.U[:, 2] / rho - 0.5 * velocity**2, dtype=float
            )
            outlet = post_reconstruction.static
            root = context["root"]
            row.update(
                {
                    "branch_classification": runner.base.BRANCH,
                    "finite_compression_model": "GENERAL_EOS_HUGONIOT",
                    "candidate_dt_before_target_clip_s": candidate_dt,
                    "target_remaining_before_step_s": remaining_before,
                    "requested_dt_after_target_clip_s": requested_dt,
                    "step_clipped_to_target": clipped_to_target,
                    "target_time_s": TARGET_TIME_S,
                    "diagnostic_classification": context[
                        "diagnostic_classification"
                    ],
                    "guard_front_refinement_applied": bool(
                        context["guard_front_refinement_applied"]
                    ),
                    "guard_front_iterations": int(
                        context["guard_front_iterations"]
                    ),
                    "root_topology_node_count": int(
                        context["root_topology_node_count"]
                    ),
                    "root_topology_monotone_nonincreasing": bool(
                        context["root_topology_monotone_nonincreasing"]
                    ),
                    "root_topology_sign_change_count": int(
                        context["root_topology_sign_change_count"]
                    ),
                    "failed_b1_state_used_as_root_endpoint": False,
                    "failed_b1_state_used_to_construct_flux": False,
                    "root_requested_chi": float(root["requested_chi"]),
                    "root_realized_chi": float(root["realized_chi"]),
                    "root_pressure_offset_pa": float(root["pressure_offset_pa"]),
                    "root_entropy_delta_J_kg_K": float(
                        root["entropy_delta_J_kg_K"]
                    ),
                    "root_hugoniot_identity_accounted_passed": bool(
                        root["hugoniot_identity_accounted_passed"]
                    ),
                    "root_lax_1_shock_passed": bool(
                        root["lax_1_shock_passed"]
                    ),
                    "root_gate_passed": bool(root["root_gate_passed"]),
                    "all_conserved_finite_after_step": bool(
                        np.all(np.isfinite(solver.U))
                    ),
                    "minimum_density_after_step_kg_m3": float(np.min(rho)),
                    "minimum_internal_energy_after_step_J_kg": float(
                        np.min(internal)
                    ),
                    "outlet_mach_after_step": float(
                        outlet.velocity_m_s / outlet.sound_speed_m_s
                    ),
                    "finite_compression_flux_applied": True,
                    "finite_compression_branch_approved": False,
                }
            )
            gate = bool(
                int(solver.step_count) == requested_step
                and accepted_dt > 0.0
                and bool(row["step_passed"])
                and bool(root["root_gate_passed"])
                and bool(row["all_conserved_finite_after_step"])
                and float(row["minimum_density_after_step_kg_m3"]) > 0.0
                and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
                and not bool(row["reverse_flow_guard_triggered"])
                and not bool(row["reverse_velocity_detected"])
                and float(row["outlet_velocity_after_step_m_s"]) >= 0.0
                and 0.0 <= float(row["outlet_mach_after_step"]) < 1.0
                and bool(row["outlet_phase_passed"])
                and bool(row["rho_xv_exact_zero"])
                and runner.base.WEAK_COMPRESSION_CHI_LIMIT
                < float(root["requested_chi"])
                <= runner.base.DIAGNOSTIC_CHI_CAP
                and int(context["root_topology_sign_change_count"]) == 1
                and bool(context["root_topology_monotone_nonincreasing"])
            )
            row["increment_9d_per_step_gate_passed"] = gate
            if not gate:
                raise runner.ShortRunStop(
                    "POST_STEP_GATE_FAILURE",
                    f"accepted step {requested_step} failed Increment 9D gate",
                )
            step_rows.append(row)
            root_rows.append(root_row)
            branch_rows.append(
                {
                    "requested_solver_step": requested_step,
                    "solver_step_count": int(solver.step_count),
                    "time_after_s": float(solver.t),
                    "branch_classification": runner.base.BRANCH,
                    "accepted": True,
                    "step_clipped_to_target": clipped_to_target,
                }
            )
        except runner.ShortRunStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{type(exc).__name__}: {exc}"
            break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            break

    U_after_all = np.asarray(solver.U, dtype=float).copy()
    branches = [row["branch_classification"] for row in branch_rows]
    transitions = sum(a != b for a, b in zip(branches, branches[1:]))
    chatter = _clear_chatter(branches)
    horizon_error = float(solver.t - TARGET_TIME_S)
    target_reached = bool(
        solver.t >= TARGET_TIME_S
        and abs(horizon_error) <= HORIZON_ROUNDOFF_TOLERANCE_S
    )
    final_clipped = bool(step_rows and step_rows[-1]["step_clipped_to_target"])
    pass_gate = bool(
        stop_reason is None
        and step_rows
        and target_reached
        and final_clipped
        and int(solver.step_count) <= MAXIMUM_OPERATIONAL_SOLVER_STEP
        and all(row["increment_9d_per_step_gate_passed"] for row in step_rows)
        and all(branch == runner.base.BRANCH for branch in branches)
        and transitions == 0
        and not chatter
    )

    final_reconstruction = provider.reconstruct_from_conserved(U_after_all[-1])
    rho_final = np.asarray(U_after_all[:, 0], dtype=float)
    velocity_final = np.asarray(U_after_all[:, 1] / rho_final, dtype=float)
    internal_final = np.asarray(
        U_after_all[:, 2] / rho_final - 0.5 * velocity_final**2, dtype=float
    )
    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_9d",
        "scope": "model_review_dynamic_full_nominal_two_l_over_c0",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_DIGEST,
        "parent_artifact_verified": True,
        "parent_outcome": PARENT_OUTCOME,
        "starting_solver_step": STARTING_STEP,
        "additional_accepted_steps": len(step_rows),
        "final_solver_step": int(solver.step_count),
        "maximum_operational_solver_step": MAXIMUM_OPERATIONAL_SOLVER_STEP,
        "starting_solver_time_s": STARTING_TIME_S,
        "target_two_l_over_c0_time_s": TARGET_TIME_S,
        "final_solver_time_s": float(solver.t),
        "horizon_time_error_s": horizon_error,
        "horizon_time_roundoff_tolerance_s": HORIZON_ROUNDOFF_TOLERANCE_S,
        "horizon_fraction_reached": float(solver.t / TARGET_TIME_S),
        "target_horizon_reached": target_reached,
        "final_step_clipped_to_target": final_clipped,
        "branch_sequence": branches,
        "branch_counts": dict(Counter(branches)),
        "branch_transition_count": transitions,
        "clear_branch_chatter_detected": chatter,
        "guard_front_refinement_step_count": sum(
            bool(row["guard_front_refinement_applied"]) for row in step_rows
        ),
        "maximum_guard_front_iterations": _maximum(
            step_rows, "guard_front_iterations"
        ),
        "minimum_root_requested_chi": _minimum(
            step_rows, "root_requested_chi"
        ),
        "maximum_root_requested_chi": _maximum(
            step_rows, "root_requested_chi"
        ),
        "minimum_root_pressure_offset_pa": _minimum(
            step_rows, "root_pressure_offset_pa"
        ),
        "maximum_root_pressure_offset_pa": _maximum(
            step_rows, "root_pressure_offset_pa"
        ),
        "maximum_absolute_root_mass_residual_kg_s": _max_abs(
            step_rows, "root_mass_residual_kg_s"
        ),
        "minimum_root_local_slope_kg_s_Pa": _minimum(
            step_rows, "root_local_slope_kg_s_Pa"
        ),
        "maximum_root_mach": _maximum(step_rows, "root_mach"),
        "minimum_root_velocity_m_s": _minimum(
            step_rows, "root_velocity_m_s"
        ),
        "minimum_root_entropy_delta_J_kg_K": _minimum(
            step_rows, "root_entropy_delta_J_kg_K"
        ),
        "minimum_root_stagnation_pressure_margin_above_back_pa": _minimum(
            root_rows, "root_stagnation_pressure_margin_above_back_pa"
        ),
        "maximum_halving_count": _maximum(step_rows, "halving_count"),
        "minimum_accepted_dt_s": _minimum(step_rows, "accepted_dt_s"),
        "maximum_accepted_dt_s": _maximum(step_rows, "accepted_dt_s"),
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
        "final_outlet_phase": str(final_reconstruction.static.phase),
        "final_minimum_density_kg_m3": float(np.min(rho_final)),
        "final_minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "final_rho_xv_exact_zero": bool(np.all(U_after_all[:, 3] == 0.0)),
        "starting_state_sha256": _state_sha256(U_before_all),
        "final_state_sha256": _state_sha256(U_after_all),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "working_vertical_slice_two_l_over_c0_reached": pass_gate,
        "increment_9d_full_horizon_gate_passed": pass_gate,
        "outcome": OUTCOME if pass_gate else "INCREMENT_9D_STOPPED",
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
        fixed_rows,
        guard_rows,
        topology_rows,
        density_rows,
        branch_rows,
        U_before_all,
        U_after_all,
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

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_start, parent_step, parent_root = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    del parent_summary
    (
        summary,
        step_rows,
        root_rows,
        fixed_rows,
        guard_rows,
        topology_rows,
        density_rows,
        branch_rows,
        U_before,
        U_after,
    ) = _run(
        contract=contract,
        b1_contract=b1_contract,
        U_start=U_start,
        parent_step=parent_step,
        parent_root=parent_root,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "finite_compression_steps.csv", step_rows)
    _write_csv(output / "finite_compression_roots.csv", root_rows)
    _write_csv(output / "hugoniot_fixed_scans.csv", fixed_rows)
    _write_csv(output / "guard_front_refinement.csv", guard_rows)
    _write_csv(output / "root_topology.csv", topology_rows)
    _write_csv(output / "hugoniot_density_search.csv", density_rows)
    _write_csv(output / "branch_sequence.csv", branch_rows)
    np.savez_compressed(
        output / "finite_compression_full_horizon_states.npz",
        U_before=U_before,
        U_after=U_after,
        solver_step_before=np.asarray([STARTING_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
        target_time_s=np.asarray([TARGET_TIME_S]),
        horizon_time_error_s=np.asarray([summary["horizon_time_error_s"]]),
    )
    (output / "authority_verification.json").write_text(
        json.dumps(
            {
                "parent_source_sha": PARENT_SOURCE_SHA,
                "parent_run": PARENT_RUN,
                "parent_job": PARENT_JOB,
                "parent_artifact": PARENT_ARTIFACT,
                "parent_artifact_name": PARENT_ARTIFACT_NAME,
                "parent_artifact_sha256": PARENT_DIGEST,
                "verified": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "stop_evidence.json").write_text(
        json.dumps(
            {
                "classification": summary["stop_classification"],
                "reason": summary["stop_reason"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9D dynamic finite-compression full-horizon attempt\n\n"
        "The authoritative corrected step-534 state was loaded. Before every "
        "actual `FvmSolver` update, the evolving outlet state was classified "
        "with the corrected dynamic root topology. A fixed successful-domain "
        "bracket was used directly when available; otherwise the retained B1 "
        "unavailable/success front was refined before constructing one "
        "successful-domain root bracket. Failed B1 states never formed a root "
        "endpoint or applied flux. The final accepted step was clipped to the "
        "fixed nominal `2L/c0` target. Formal project states remain false.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "finite_compression_steps.csv",
        "finite_compression_roots.csv",
        "hugoniot_fixed_scans.csv",
        "guard_front_refinement.csv",
        "root_topology.csv",
        "hugoniot_density_search.csv",
        "branch_sequence.csv",
        "finite_compression_full_horizon_states.npz",
        "authority_verification.json",
        "stop_evidence.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9d_full_horizon_gate_passed"]:
        raise SystemExit(
            "Increment 9D full-horizon gate did not pass: "
            f"{summary['stop_classification']} {summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
