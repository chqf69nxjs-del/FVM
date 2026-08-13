from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_contract,
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_metrics import inventory


CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
BRANCH = "ZERO_TRANSFER_CLOSED"
TECHNICAL_ISSUE = "TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION"
OUTCOME = "INCREMENT_9K_PROVISIONAL_ENGINEERING_WORKING_SLICE_PASS"

PARENT_SOURCE_SHA = "c89a992d69c2985fc081fe3750c5b27136d3941e"
PARENT_RUN = 31670285271
PARENT_JOB = 94353300958
PARENT_ARTIFACT = 9169437776
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9i-root-schema-31670285271"
)
PARENT_DIGEST = (
    "ed48b82be9f6cc8d6e081a416ab2b61bd97401782279506d83c8afd4d173f5d3"
)
PARENT_STATE_SHA256 = (
    "7d2633e58adcc36e7ea7a1204af95455f5e8942e2c4e9a6dbf76cf437efd2a25"
)
STARTING_STEP = 637
STARTING_TIME_S = 0.004269583083221582
TARGET_TIME_S = 0.004285834855172021
HORIZON_ROUNDOFF_TOLERANCE_S = 8.0 * float(np.spacing(TARGET_TIME_S))
MAXIMUM_OPERATIONAL_SOLVER_STEP = 650

PARENT_REQUIRED_FILES = {
    "artifact_sha256.txt",
    "authority_verification.json",
    "branch_sequence.csv",
    "dynamic_seeded_authority.json",
    "finite_compression_full_horizon_states.npz",
    "finite_compression_roots.csv",
    "finite_compression_steps.csv",
    "guard_front_refinement.csv",
    "hugoniot_density_search.csv",
    "hugoniot_fixed_scans.csv",
    "parent_root_schema_correction.json",
    "report.md",
    "root_topology.csv",
    "stop_evidence.json",
    "summary.json",
}


class Increment9KStop(RuntimeError):
    pass


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


def _residual_passed(
    residual: float,
    *,
    absolute: float,
    relative: float,
    scale_values: tuple[float, ...],
) -> bool:
    scale = max((abs(float(value)) for value in scale_values), default=0.0)
    return bool(abs(float(residual)) <= max(float(absolute), float(relative) * scale))


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray]:
    if artifact_digest != PARENT_DIGEST:
        raise Increment9KStop("parent GitHub artifact digest mismatch")
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise Increment9KStop(f"parent artifact file set mismatch: {sorted(actual)}")

    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise Increment9KStop("parent internal manifest names mismatch")
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise Increment9KStop(f"parent internal SHA256 mismatch for {name}")

    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": "INCREMENT_9I_STOPPED",
        "final_solver_step": STARTING_STEP,
        "final_solver_time_s": STARTING_TIME_S,
        "target_two_l_over_c0_time_s": TARGET_TIME_S,
        "target_horizon_reached": False,
        "increment_9i_full_horizon_gate_passed": False,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise Increment9KStop(
                f"parent summary mismatch for {key}: {summary.get(key)!r}"
            )
    if "dynamic seeded interval contains no admissible island" not in str(
        summary.get("stop_reason")
    ):
        raise Increment9KStop("parent stop reason is not the retained near-zero stop")

    with np.load(directory / "finite_compression_full_horizon_states.npz") as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
        target = float(states["target_time_s"][0])
    if U_after.shape != (32, 4):
        raise Increment9KStop("parent state shape is not (32, 4)")
    if step_after != STARTING_STEP or time_after != STARTING_TIME_S:
        raise Increment9KStop("parent solver identity mismatch")
    if target != TARGET_TIME_S:
        raise Increment9KStop("parent target time mismatch")
    if _state_sha256(U_after) != PARENT_STATE_SHA256:
        raise Increment9KStop("parent state SHA256 mismatch")
    if not np.all(np.isfinite(U_after)):
        raise Increment9KStop("parent state contains nonfinite values")
    rho = np.asarray(U_after[:, 0], dtype=float)
    velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
    internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise Increment9KStop("parent state is nonpositive")
    if not np.all(U_after[:, 3] == 0.0):
        raise Increment9KStop("parent rho*xv is not exact zero")
    return summary, U_after


class ZeroTransferClosureHook:
    """One-way discharge closure represented by the exact wall flux identity."""

    maximum_halvings = 12
    failure_outcome = "ZERO_TRANSFER_CLOSURE_TRIAL_FAILURE"

    def __init__(
        self,
        *,
        provider: CoolPropB2StateProvider,
        allowed_phases: set[str],
    ) -> None:
        self.provider = provider
        self.allowed_phases = set(allowed_phases)
        self.trial_dts_s: list[float] = []
        self.last_interior_pressure_pa: float | None = None
        self.last_flux = np.zeros(4, dtype=float)
        self.last_candidate_dt_s: float | None = None

    def begin_step(self) -> None:
        self.trial_dts_s = []
        self.last_interior_pressure_pa = None
        self.last_flux = np.zeros(4, dtype=float)

    def limit_dt(
        self,
        *,
        U: np.ndarray,
        eos: Any,
        grid: UniformGrid,
        t: float,
        candidate_dt: float,
    ) -> float:
        del U, eos, grid, t
        self.last_candidate_dt_s = float(candidate_dt)
        return float(candidate_dt)

    def flux_from_state(self, U: np.ndarray) -> np.ndarray:
        reconstruction = self.provider.reconstruct_from_conserved(U[-1])
        pressure = float(reconstruction.static.pressure_pa)
        phase = normalize_phase(str(reconstruction.static.phase))
        if not math.isfinite(pressure) or pressure <= 0.0:
            raise ValueError("zero-transfer closure interior pressure is invalid")
        if phase not in self.allowed_phases:
            raise ValueError(
                f"zero-transfer closure outlet phase {phase!r} is outside scope"
            )
        return np.asarray([0.0, pressure, 0.0, 0.0], dtype=float)

    def evaluate_flux(
        self,
        *,
        U: np.ndarray,
        eos: Any,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> np.ndarray:
        del eos, grid, t
        flux = self.flux_from_state(U)
        self.trial_dts_s.append(float(dt))
        self.last_interior_pressure_pa = float(flux[1])
        self.last_flux = flux.copy()
        return flux

    def validate_trial(
        self,
        *,
        U_before: np.ndarray,
        U_trial: np.ndarray,
        eos: Any,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> None:
        del U_before, eos, grid, t, dt
        if not np.all(np.isfinite(U_trial)):
            raise ValueError("zero-transfer trial contains nonfinite values")
        rho = np.asarray(U_trial[:, 0], dtype=float)
        if not np.all(rho > 0.0):
            raise ValueError("zero-transfer trial density is nonpositive")
        velocity = np.asarray(U_trial[:, 1] / rho, dtype=float)
        internal = np.asarray(U_trial[:, 2] / rho - 0.5 * velocity**2, dtype=float)
        if not np.all(internal > 0.0):
            raise ValueError("zero-transfer trial internal energy is nonpositive")
        if not np.all(U_trial[:, 3] == 0.0):
            raise ValueError("zero-transfer trial rho*xv is not exact zero")
        for conserved in U_trial:
            phase = normalize_phase(
                str(self.provider.reconstruct_from_conserved(conserved).static.phase)
            )
            if phase not in self.allowed_phases:
                raise ValueError(
                    f"zero-transfer trial phase {phase!r} is outside liquid scope"
                )


def _all_phases_allowed(
    provider: CoolPropB2StateProvider,
    U: np.ndarray,
    allowed_phases: set[str],
) -> tuple[bool, list[str]]:
    phases = [
        normalize_phase(str(provider.reconstruct_from_conserved(row).static.phase))
        for row in U
    ]
    return bool(all(phase in allowed_phases for phase in phases)), phases


def _run(
    *,
    contract: dict[str, Any],
    U_start: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, np.ndarray]:
    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    family = diagnostic._family(contract, state_id)
    allowed_phases = {
        normalize_phase(str(value))
        for value in family["allowed_normalized_phases"]
    }
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = CoolPropB2StateProvider()
    _, initial_static = build_uniform_initial_state(
        contract, provider, state_id, grid.n_cells
    )
    hook = ZeroTransferClosureHook(
        provider=provider,
        allowed_phases=allowed_phases,
    )
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

    tolerances = contract["acceptance_tolerances"]
    segment_initial = inventory(
        solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2
    )
    segment_expected_delta = np.zeros(4, dtype=float)
    U_before_all = np.asarray(solver.U, dtype=float).copy()
    rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None

    while solver.t < TARGET_TIME_S - HORIZON_ROUNDOFF_TOLERANCE_S:
        if int(solver.step_count) >= MAXIMUM_OPERATIONAL_SOLVER_STEP:
            stop_classification = "OPERATIONAL_STEP_CAP_EXCEEDED"
            stop_reason = "operational step cap reached before target"
            break
        requested_step = int(solver.step_count + 1)
        try:
            before_time = float(solver.t)
            before = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
            primitive_before = solver.primitive()
            outlet_before = provider.reconstruct_from_conserved(solver.U[-1]).static
            hook.begin_step()
            candidate_dt = float(solver.compute_dt())
            remaining_before = float(TARGET_TIME_S - solver.t)
            requested_dt = float(min(candidate_dt, remaining_before))
            clipped_to_target = bool(remaining_before <= candidate_dt)

            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = hook.flux_from_state(solver.U)
            pressure_before = float(outlet_before.pressure_pa)
            momentum_identity_residual = float(right_flux[1] - pressure_before)

            accepted_dt = float(solver.step(requested_dt))
            after = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
            expected_step_delta = (
                accepted_dt * grid.geometry.area_m2 * (left_flux - right_flux)
            )
            segment_expected_delta = segment_expected_delta + expected_step_delta
            segment_actual_delta = _inventory_array(after) - _inventory_array(
                segment_initial
            )
            step_actual_delta = _inventory_array(after) - _inventory_array(before)
            step_residual = step_actual_delta - expected_step_delta
            cumulative_residual = segment_actual_delta - segment_expected_delta

            primitive_after = solver.primitive()
            outlet_after = provider.reconstruct_from_conserved(solver.U[-1]).static
            phases_passed, phases = _all_phases_allowed(
                provider, solver.U, allowed_phases
            )
            rho = np.asarray(solver.U[:, 0], dtype=float)
            velocity = np.asarray(solver.U[:, 1] / rho, dtype=float)
            internal = np.asarray(
                solver.U[:, 2] / rho - 0.5 * velocity**2, dtype=float
            )

            step_mass_passed = _residual_passed(
                float(step_residual[0]),
                absolute=float(tolerances["mass_inventory_absolute_kg"]),
                relative=float(tolerances["mass_inventory_relative"]),
                scale_values=(before["mass_kg"], after["mass_kg"], expected_step_delta[0]),
            )
            step_momentum_passed = _residual_passed(
                float(step_residual[1]),
                absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
                relative=float(tolerances["momentum_inventory_relative"]),
                scale_values=(
                    before["momentum_kg_m_s"],
                    after["momentum_kg_m_s"],
                    expected_step_delta[1],
                ),
            )
            step_energy_passed = _residual_passed(
                float(step_residual[2]),
                absolute=float(tolerances["energy_inventory_absolute_J"]),
                relative=float(tolerances["energy_inventory_relative"]),
                scale_values=(before["energy_J"], after["energy_J"], expected_step_delta[2]),
            )
            cumulative_mass_passed = _residual_passed(
                float(cumulative_residual[0]),
                absolute=float(tolerances["mass_inventory_absolute_kg"]),
                relative=float(tolerances["mass_inventory_relative"]),
                scale_values=(
                    segment_initial["mass_kg"],
                    after["mass_kg"],
                    segment_expected_delta[0],
                ),
            )
            cumulative_momentum_passed = _residual_passed(
                float(cumulative_residual[1]),
                absolute=float(tolerances["momentum_inventory_absolute_kg_m_s"]),
                relative=float(tolerances["momentum_inventory_relative"]),
                scale_values=(
                    segment_initial["momentum_kg_m_s"],
                    after["momentum_kg_m_s"],
                    segment_expected_delta[1],
                ),
            )
            cumulative_energy_passed = _residual_passed(
                float(cumulative_residual[2]),
                absolute=float(tolerances["energy_inventory_absolute_J"]),
                relative=float(tolerances["energy_inventory_relative"]),
                scale_values=(
                    segment_initial["energy_J"],
                    after["energy_J"],
                    segment_expected_delta[2],
                ),
            )

            row: dict[str, Any] = {
                "case_id": CASE_ID,
                "state_id": state_id,
                "technical_issue": TECHNICAL_ISSUE,
                "branch_classification": BRANCH,
                "requested_solver_step": requested_step,
                "solver_step_count": int(solver.step_count),
                "time_before_s": before_time,
                "time_after_s": float(solver.t),
                "candidate_dt_s": candidate_dt,
                "target_remaining_before_step_s": remaining_before,
                "requested_dt_s": requested_dt,
                "accepted_dt_s": accepted_dt,
                "step_clipped_to_target": clipped_to_target,
                "halving_count": max(len(hook.trial_dts_s) - 1, 0),
                "trial_dts_s": list(hook.trial_dts_s),
                "outlet_pressure_before_pa": pressure_before,
                "outlet_velocity_before_m_s": float(primitive_before.u[-1]),
                "outlet_mach_before": float(
                    primitive_before.u[-1] / primitive_before.c[-1]
                ),
                "outlet_phase_before": str(outlet_before.phase),
                "right_external_mass_flux_kg_m2_s": float(right_flux[0]),
                "right_external_momentum_flux_pa": float(right_flux[1]),
                "right_external_energy_flux_W_m2": float(right_flux[2]),
                "right_external_vapor_flux_kg_m2_s": float(right_flux[3]),
                "momentum_wall_identity_residual_pa": momentum_identity_residual,
                "left_external_mass_flux_kg_m2_s": float(left_flux[0]),
                "left_external_momentum_flux_pa": float(left_flux[1]),
                "left_external_energy_flux_W_m2": float(left_flux[2]),
                "mass_before_kg": before["mass_kg"],
                "mass_after_kg": after["mass_kg"],
                "step_mass_residual_kg": float(step_residual[0]),
                "segment_cumulative_mass_residual_kg": float(cumulative_residual[0]),
                "momentum_before_kg_m_s": before["momentum_kg_m_s"],
                "momentum_after_kg_m_s": after["momentum_kg_m_s"],
                "step_momentum_residual_kg_m_s": float(step_residual[1]),
                "segment_cumulative_momentum_residual_kg_m_s": float(
                    cumulative_residual[1]
                ),
                "energy_before_J": before["energy_J"],
                "energy_after_J": after["energy_J"],
                "step_energy_residual_J": float(step_residual[2]),
                "segment_cumulative_energy_residual_J": float(cumulative_residual[2]),
                "vapor_mass_after_kg": after["vapor_mass_kg"],
                "outlet_pressure_after_pa": float(primitive_after.p[-1]),
                "outlet_velocity_after_m_s": float(primitive_after.u[-1]),
                "outlet_mach_after": float(primitive_after.u[-1] / primitive_after.c[-1]),
                "outlet_phase_after": str(outlet_after.phase),
                "minimum_density_after_kg_m3": float(np.min(rho)),
                "minimum_internal_energy_after_J_kg": float(np.min(internal)),
                "maximum_absolute_velocity_after_m_s": float(np.max(np.abs(velocity))),
                "all_conserved_finite": bool(np.all(np.isfinite(solver.U))),
                "all_phases_allowed": phases_passed,
                "normalized_phases_after": sorted(set(phases)),
                "rho_xv_exact_zero": bool(np.all(solver.U[:, 3] == 0.0)),
                "step_mass_passed": step_mass_passed,
                "step_momentum_passed": step_momentum_passed,
                "step_energy_passed": step_energy_passed,
                "segment_cumulative_mass_passed": cumulative_mass_passed,
                "segment_cumulative_momentum_passed": cumulative_momentum_passed,
                "segment_cumulative_energy_passed": cumulative_energy_passed,
                "reverse_outlet_velocity_diagnostic": bool(
                    float(primitive_after.u[-1]) < 0.0
                ),
                "reverse_mass_transfer_constructed": False,
                "b1_called_after_closure": False,
                "hugoniot_root_called_after_closure": False,
            }
            gate = bool(
                int(solver.step_count) == requested_step
                and accepted_dt > 0.0
                and row["all_conserved_finite"]
                and row["minimum_density_after_kg_m3"] > 0.0
                and row["minimum_internal_energy_after_J_kg"] > 0.0
                and row["all_phases_allowed"]
                and row["rho_xv_exact_zero"]
                and row["right_external_mass_flux_kg_m2_s"] == 0.0
                and row["right_external_energy_flux_W_m2"] == 0.0
                and row["right_external_vapor_flux_kg_m2_s"] == 0.0
                and row["momentum_wall_identity_residual_pa"] == 0.0
                and step_mass_passed
                and step_momentum_passed
                and step_energy_passed
                and cumulative_mass_passed
                and cumulative_momentum_passed
                and cumulative_energy_passed
            )
            row["increment_9k_per_step_engineering_gate_passed"] = gate
            rows.append(row)
            if not gate:
                stop_classification = "POST_STEP_ENGINEERING_GATE_FAILURE"
                stop_reason = f"accepted step {requested_step} failed Increment 9K gate"
                break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            break

    U_after_all = np.asarray(solver.U, dtype=float).copy()
    final_reconstruction = provider.reconstruct_from_conserved(U_after_all[-1])
    rho_final = np.asarray(U_after_all[:, 0], dtype=float)
    velocity_final = np.asarray(U_after_all[:, 1] / rho_final, dtype=float)
    internal_final = np.asarray(
        U_after_all[:, 2] / rho_final - 0.5 * velocity_final**2,
        dtype=float,
    )
    final_phases_passed, final_phases = _all_phases_allowed(
        provider, U_after_all, allowed_phases
    )
    horizon_error = float(solver.t - TARGET_TIME_S)
    target_reached = bool(
        solver.t >= TARGET_TIME_S
        and abs(horizon_error) <= HORIZON_ROUNDOFF_TOLERANCE_S
    )
    final_clipped = bool(rows and rows[-1]["step_clipped_to_target"])
    pass_gate = bool(
        stop_reason is None
        and rows
        and target_reached
        and final_clipped
        and all(row["increment_9k_per_step_engineering_gate_passed"] for row in rows)
        and all(row["branch_classification"] == BRANCH for row in rows)
        and final_phases_passed
        and np.all(np.isfinite(U_after_all))
        and np.all(rho_final > 0.0)
        and np.all(internal_final > 0.0)
        and np.all(U_after_all[:, 3] == 0.0)
    )

    summary = {
        "schema_version": "stage7_u3_b2_a1_increment_9k_zero_transfer_closure_v1",
        "scope": "model_review_provisional_engineering_zero_transfer_closure",
        "technical_issue": TECHNICAL_ISSUE,
        "source_git_sha": None,
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_DIGEST,
        "parent_state_sha256": PARENT_STATE_SHA256,
        "parent_artifact_verified": True,
        "starting_solver_step": STARTING_STEP,
        "starting_solver_time_s": STARTING_TIME_S,
        "target_two_l_over_c0_time_s": TARGET_TIME_S,
        "additional_accepted_steps": len(rows),
        "final_solver_step": int(solver.step_count),
        "final_solver_time_s": float(solver.t),
        "horizon_time_error_s": horizon_error,
        "horizon_fraction_reached": float(solver.t / TARGET_TIME_S),
        "provisional_engineering_two_l_over_c0_reached": target_reached,
        "final_step_clipped_to_target": final_clipped,
        "branch_sequence": [row["branch_classification"] for row in rows],
        "branch_counts": dict(Counter(row["branch_classification"] for row in rows)),
        "transition_from_parent_finite_compression_to_zero_transfer": True,
        "zero_transfer_branch_reentry_allowed": False,
        "reverse_mass_transfer_supported": False,
        "minimum_density_kg_m3": float(np.min(rho_final)),
        "minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "final_outlet_pressure_pa": float(final_reconstruction.static.pressure_pa),
        "final_outlet_velocity_m_s": float(final_reconstruction.static.velocity_m_s),
        "final_outlet_mach": float(
            final_reconstruction.static.velocity_m_s
            / final_reconstruction.static.sound_speed_m_s
        ),
        "final_outlet_phase": str(final_reconstruction.static.phase),
        "final_normalized_phases": sorted(set(final_phases)),
        "final_all_phases_allowed": final_phases_passed,
        "final_rho_xv_exact_zero": bool(np.all(U_after_all[:, 3] == 0.0)),
        "starting_state_sha256": _state_sha256(U_before_all),
        "final_state_sha256": _state_sha256(U_after_all),
        "maximum_halving_count": max(
            (int(row["halving_count"]) for row in rows), default=0
        ),
        "maximum_absolute_step_mass_residual_kg": max(
            (abs(float(row["step_mass_residual_kg"])) for row in rows), default=0.0
        ),
        "maximum_absolute_step_momentum_residual_kg_m_s": max(
            (abs(float(row["step_momentum_residual_kg_m_s"])) for row in rows),
            default=0.0,
        ),
        "maximum_absolute_step_energy_residual_J": max(
            (abs(float(row["step_energy_residual_J"])) for row in rows), default=0.0
        ),
        "maximum_absolute_segment_cumulative_mass_residual_kg": max(
            (
                abs(float(row["segment_cumulative_mass_residual_kg"]))
                for row in rows
            ),
            default=0.0,
        ),
        "maximum_absolute_segment_cumulative_momentum_residual_kg_m_s": max(
            (
                abs(float(row["segment_cumulative_momentum_residual_kg_m_s"]))
                for row in rows
            ),
            default=0.0,
        ),
        "maximum_absolute_segment_cumulative_energy_residual_J": max(
            (
                abs(float(row["segment_cumulative_energy_residual_J"]))
                for row in rows
            ),
            default=0.0,
        ),
        "right_mass_transfer_exact_zero_all_steps": bool(
            rows
            and all(float(row["right_external_mass_flux_kg_m2_s"]) == 0.0 for row in rows)
        ),
        "right_energy_transfer_exact_zero_all_steps": bool(
            rows
            and all(float(row["right_external_energy_flux_W_m2"]) == 0.0 for row in rows)
        ),
        "right_vapor_transfer_exact_zero_all_steps": bool(
            rows
            and all(float(row["right_external_vapor_flux_kg_m2_s"]) == 0.0 for row in rows)
        ),
        "wall_momentum_identity_exact_all_steps": bool(
            rows
            and all(float(row["momentum_wall_identity_residual_pa"]) == 0.0 for row in rows)
        ),
        "reverse_outlet_velocity_observed": bool(
            any(bool(row["reverse_outlet_velocity_diagnostic"]) for row in rows)
        ),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "increment_9k_engineering_gate_passed": pass_gate,
        "outcome": OUTCOME if pass_gate else "INCREMENT_9K_STOPPED",
        "working_vertical_slice": pass_gate,
        "working_vertical_slice_kind": "PROVISIONAL_ENGINEERING_WORKING_SLICE",
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
    return summary, rows, U_before_all, U_after_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    contract = load_contract(args.contract)
    parent_summary, U_start = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    del parent_summary
    summary, rows, U_before, U_after = _run(
        contract=contract,
        U_start=U_start,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec"] = str(args.model_review_spec)
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise Increment9KStop("output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "zero_transfer_steps.csv", rows)
    _write_csv(
        output / "branch_sequence.csv",
        [
            {
                "requested_solver_step": row["requested_solver_step"],
                "solver_step_count": row["solver_step_count"],
                "time_after_s": row["time_after_s"],
                "branch_classification": row["branch_classification"],
                "accepted": row["increment_9k_per_step_engineering_gate_passed"],
                "step_clipped_to_target": row["step_clipped_to_target"],
            }
            for row in rows
        ],
    )
    np.savez_compressed(
        output / "zero_transfer_full_horizon_states.npz",
        U_before=np.asarray(U_before, dtype=float),
        U_after=np.asarray(U_after, dtype=float),
        solver_step_before=np.asarray([STARTING_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
        target_time_s=np.asarray([TARGET_TIME_S]),
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
                "parent_state_sha256": PARENT_STATE_SHA256,
                "parent_verified": True,
                "locked_contract_changed": False,
                "b1_changed": False,
                "production_adapter_changed": False,
                "fvm_solver_changed": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "technical_issue.json").write_text(
        json.dumps(
            {
                "id": TECHNICAL_ISSUE,
                "status": "OPEN_TECHNICAL_DEBT_NONBLOCKING_FOR_WORKING_TOOL",
                "provisional_model": "ONE_WAY_DISCHARGE_ZERO_TRANSFER_CLOSURE",
                "transition_authority": "AUTHORITATIVE_STEP_637_AFTER_INCREMENT_9J_CASE_3",
                "unresolved": [
                    "general outward-to-zero transition criterion",
                    "open-orifice versus non-return-device interpretation",
                    "zero-transfer hold and re-entry",
                    "reverse-flow model",
                    "hysteresis and chatter prevention",
                    "closure reflection physical validation",
                ],
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
        "# Increment 9K provisional zero-transfer closure\n\n"
        "This run starts from the immutable accepted step-637 Increment 9I "
        "state and applies a one-way non-return closure for the unresolved "
        "near-zero-flow transition. The right face uses exact zero mass, "
        "energy, and vapor transfer with interior static pressure traction. "
        "The result is an engineering working slice only; all formal "
        "verification, acceptance, validation, and production states remain "
        "false.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = sorted(
        path.name
        for path in output.iterdir()
        if path.is_file() and path.name != "artifact_sha256.txt"
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9k_engineering_gate_passed"]:
        raise SystemExit(
            "Increment 9K provisional engineering gate did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
