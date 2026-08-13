from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
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
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_hook import A1DynamicShortHook
from u3_b2_characteristic_port_dynamic_short_metrics import build_step_row, inventory


DIAGNOSTIC_SOURCE_SHA = "d8766a6e2b362d7fc3c577410de59c50c04834f3"
DIAGNOSTIC_RUN = 31662145018
DIAGNOSTIC_JOB = 94328958641
DIAGNOSTIC_ARTIFACT = 9166560133
DIAGNOSTIC_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-8a-31662145018"
)
DIAGNOSTIC_DIGEST = (
    "457e4ad3a2c432d532e483fdc94d8e5f62b9ac600387fb6b3215322858acc6d2"
)
EXPECTED_STEP_BEFORE = 493
EXPECTED_STEP_AFTER = 494
EXPECTED_TIME_BEFORE_S = 0.0033036489591120113
OUTCOME = "FINITE_COMPRESSION_INCREMENT_8B_GUARD_FRONT_ONE_STEP_PASS"

DIAGNOSTIC_REQUIRED_FILES = {
    "step493_hugoniot_fixed_scan.csv",
    "step493_guard_front_refinement.csv",
    "step493_root_topology.csv",
    "step493_hugoniot_density_search.csv",
    "step493_selected_root.csv",
    "step493_state_identity.npz",
    "authority_verification.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}

ROOT_COMPARE_TOLERANCES = {
    "requested_chi": 1.0e-15,
    "pressure_pa": 1.0e-6,
    "density_kg_m3": 1.0e-9,
    "velocity_m_s": 1.0e-9,
    "root_mass_residual_kg_s": 1.0e-8,
}


class OneStepStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def _verify_diagnostic(
    directory: Path,
    *,
    artifact_digest: str,
    parent_U: np.ndarray,
) -> tuple[dict[str, Any], dict[str, str]]:
    if artifact_digest != DIAGNOSTIC_DIGEST:
        raise OneStepStop("Increment 8A GitHub artifact digest mismatch")
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != DIAGNOSTIC_REQUIRED_FILES:
        raise OneStepStop(f"Increment 8A file set mismatch: {sorted(actual)}")
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != DIAGNOSTIC_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise OneStepStop("Increment 8A manifest names mismatch")
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise OneStepStop(f"Increment 8A internal SHA256 mismatch for {name}")

    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "source_git_sha": DIAGNOSTIC_SOURCE_SHA,
        "outcome": inc8a.SUPPORTED,
        "diagnostic_classification_complete": True,
        "actual_continuation_supported": True,
        "solver_step_loaded": EXPECTED_STEP_BEFORE,
        "next_requested_solver_step": EXPECTED_STEP_AFTER,
        "state_unchanged": True,
        "fvm_step_494_attempted": False,
        "guard_front_refinement_applied": True,
        "guard_front_iterations": inc8a.GUARD_ITERATIONS,
        "root_topology_sign_change_count": 1,
        "selected_root_present": True,
        "selected_root_gate_passed": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise OneStepStop(
                f"Increment 8A summary mismatch for {key}: {summary.get(key)!r}"
            )
    with np.load(directory / "step493_state_identity.npz") as states:
        before = np.asarray(states["U_before"], dtype=float)
        after = np.asarray(states["U_after"], dtype=float)
        step_before = int(states["solver_step_before"][0])
        step_after = int(states["solver_step_after"][0])
    if (
        before.shape != (32, 4)
        or not np.array_equal(before, after)
        or not np.array_equal(before, parent_U)
        or step_before != EXPECTED_STEP_BEFORE
        or step_after != EXPECTED_STEP_BEFORE
    ):
        raise OneStepStop("Increment 8A state identity mismatch")
    roots = _read_csv(directory / "step493_selected_root.csv")
    if len(roots) != 1 or roots[0].get("selected_root_present") != "True":
        raise OneStepStop("Increment 8A selected-root evidence mismatch")
    return summary, roots[0]


def _compare_root(authority: dict[str, str], recomputed: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for key, tolerance in ROOT_COMPARE_TOLERANCES.items():
        expected = float(authority[key])
        actual = float(recomputed[key])
        difference = actual - expected
        checks[key] = {
            "authority": expected,
            "recomputed": actual,
            "difference": difference,
            "absolute_difference": abs(difference),
            "tolerance": tolerance,
            "passed": abs(difference) <= tolerance,
        }
    return {
        "checks": checks,
        "passed": all(item["passed"] for item in checks.values()),
    }


class FixedRefinedRootHook(A1DynamicShortHook):
    def __init__(
        self,
        *,
        contract: dict[str, Any],
        b1_contract: dict[str, Any],
        case_id: str,
        provider: CoolPropB2StateProvider,
        expected_U: np.ndarray,
        expected_time_s: float,
        root: dict[str, Any],
        root_topology_node_count: int,
    ) -> None:
        super().__init__(
            contract=contract,
            b1_contract=b1_contract,
            case_id=case_id,
            provider=provider,
        )
        self.expected_U = np.asarray(expected_U, dtype=float).copy()
        self.expected_time_s = float(expected_time_s)
        self.fixed_root = dict(root)
        self.root_topology_node_count = int(root_topology_node_count)

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        if float(t) != self.expected_time_s or not np.array_equal(U, self.expected_U):
            raise OneStepStop("fixed Increment 8B root requested for an unexpected state")
        reconstruction = self.provider.reconstruct_from_conserved(U[-1])
        static = reconstruction.static
        allowed = {
            normalize_phase(value)
            for value in diagnostic._family(self.contract, self.state_id)[
                "allowed_normalized_phases"
            ]
        }
        velocity_tolerance = float(
            self.contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
        )
        root = dict(self.fixed_root)
        mass_rate = float(root["pipe_mass_rate_kg_s"])
        velocity = float(root["velocity_m_s"])
        pressure = float(root["pressure_pa"])
        h0 = float(root["h0_J_kg"])
        flux = np.asarray(
            [
                mass_rate / self.area_m2,
                (mass_rate * velocity + pressure * self.area_m2) / self.area_m2,
                mass_rate * h0 / self.area_m2,
                0.0,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(flux)):
            raise OneStepStop("fixed refined Hugoniot flux is nonfinite")
        self.root_context = {
            "solver_time_s": float(t),
            "interior_pressure_pa": float(static.pressure_pa),
            "interior_temperature_K": float(static.temperature_K),
            "interior_density_kg_m3": float(static.density_kg_m3),
            "interior_velocity_m_s": float(static.velocity_m_s),
            "interior_sound_speed_m_s": float(static.sound_speed_m_s),
            "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
            "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
            "interior_phase": str(static.phase),
            "interior_h0_round_trip_residual_J_kg": float(
                reconstruction.enthalpy_round_trip_residual_J_kg
            ),
            "interior_s0_round_trip_residual_J_kg_K": float(
                reconstruction.entropy_round_trip_residual_J_kg_K
            ),
            "connected_scan_base_node_count": len(base.inc5_core.CHI_NODES),
            "connected_scan_requested_nodes": (
                len(base.inc5_core.CHI_NODES) + inc8a.GUARD_ITERATIONS
            ),
            "connected_scan_admissible_subsonic_nodes": self.root_topology_node_count,
            "connected_scan_lowest_pressure_pa": float(root["pressure_pa"]),
            "connected_scan_stop_reason": None,
            "connected_scan_residual_monotone": True,
            "connected_scan_sign_change_count": 1,
            "root": root,
            "flux": flux,
            "allowed_phases": allowed,
            "velocity_tolerance_m_s": velocity_tolerance,
            "branch_classification": base.BRANCH,
            "root_chi": float(root["requested_chi"]),
            "root_gate_passed": bool(root["root_gate_passed"]),
            "guard_front_refinement_applied": True,
            "failed_b1_state_used_as_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
            "finite_compression_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
        self.flux = flux.copy()
        self._cache_t = float(t)
        self._cache_outlet = np.asarray(U[-1], dtype=float).copy()
        self.trial_dts_s = []


def _run_one_step(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U_step493: np.ndarray,
    parent_step_row: dict[str, str],
    root: dict[str, Any],
    topology_count: int,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
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
    hook = FixedRefinedRootHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
        expected_U=U_step493,
        expected_time_s=EXPECTED_TIME_BEFORE_S,
        root=root,
        root_topology_node_count=topology_count,
    )
    hook._previous_root_pressure_pa = float(parent_step_row["root_pressure_pa"])
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider, boundary_temperature_K=initial_static.temperature_K
        ),
        U=np.asarray(U_step493, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=EXPECTED_TIME_BEFORE_S,
        step_count=EXPECTED_STEP_BEFORE,
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
    U_before = np.asarray(solver.U, dtype=float).copy()
    before = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    candidate_dt = float(solver.compute_dt())
    dt_limits = dict(hook.last_dt_limits)
    context = hook.root_context
    if context is None:
        raise OneStepStop("fixed root was not prepared by compute_dt")
    flux_left, _ = solver._base_fluxes()
    left_flux = np.asarray(flux_left[0], dtype=float)
    right_flux = np.asarray(hook.flux, dtype=float)
    accepted_dt = float(solver.step(candidate_dt))
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
        requested_step=EXPECTED_STEP_AFTER,
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
    rho = np.asarray(solver.U[:, 0], dtype=float)
    velocity = np.asarray(solver.U[:, 1] / rho, dtype=float)
    internal = np.asarray(solver.U[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    outlet = post_reconstruction.static
    row.update(
        {
            "branch_classification": base.BRANCH,
            "finite_compression_model": "GENERAL_EOS_HUGONIOT",
            "guard_front_refinement_applied": True,
            "failed_b1_state_used_as_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
            "root_requested_chi": float(root["requested_chi"]),
            "root_realized_chi": float(root["realized_chi"]),
            "root_pressure_offset_pa": float(root["pressure_offset_pa"]),
            "root_entropy_delta_J_kg_K": float(root["entropy_delta_J_kg_K"]),
            "root_hugoniot_identity_accounted_passed": bool(
                root["hugoniot_identity_accounted_passed"]
            ),
            "root_lax_1_shock_passed": bool(root["lax_1_shock_passed"]),
            "root_gate_passed": bool(root["root_gate_passed"]),
            "all_conserved_finite_after_step": bool(np.all(np.isfinite(solver.U))),
            "minimum_density_after_step_kg_m3": float(np.min(rho)),
            "minimum_internal_energy_after_step_J_kg": float(np.min(internal)),
            "outlet_mach_after_step": float(
                outlet.velocity_m_s / outlet.sound_speed_m_s
            ),
            "finite_compression_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
    )
    gate = bool(
        int(solver.step_count) == EXPECTED_STEP_AFTER
        and accepted_dt > 0.0
        and bool(row["step_passed"])
        and bool(root["root_gate_passed"])
        and bool(row["all_conserved_finite_after_step"])
        and float(row["minimum_density_after_step_kg_m3"]) > 0.0
        and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
        and not bool(row["reverse_velocity_detected"])
        and float(row["outlet_velocity_after_step_m_s"]) >= 0.0
        and 0.0 <= float(row["outlet_mach_after_step"]) < 1.0
        and bool(row["outlet_phase_passed"])
        and bool(row["rho_xv_exact_zero"])
    )
    row["increment_8b_one_step_gate_passed"] = gate
    if not gate:
        raise OneStepStop("actual step 494 failed the fixed post-step gate")
    return row, U_before, np.asarray(solver.U, dtype=float).copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--diagnostic-artifact-dir", type=Path, required=True)
    parser.add_argument("--diagnostic-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U, parent_root = inc8a._verify_parent(
        args.parent_artifact_dir, artifact_digest=args.parent_artifact_digest
    )
    del parent_summary
    diagnostic_summary, authority_root = _verify_diagnostic(
        args.diagnostic_artifact_dir,
        artifact_digest=args.diagnostic_artifact_digest,
        parent_U=U,
    )
    recomputed_summary, fixed_rows, guard_rows, topology_rows, density_rows, root = inc8a._run(
        contract=contract,
        b1_contract=b1_contract,
        U=U,
        parent_root=parent_root,
    )
    if recomputed_summary["outcome"] != inc8a.SUPPORTED or not bool(
        root.get("selected_root_present")
    ):
        raise OneStepStop("Increment 8A supported root did not reproduce")
    comparison = _compare_root(authority_root, root)
    if not comparison["passed"]:
        raise OneStepStop("recomputed root does not match Increment 8A authority")
    parent_steps = _read_csv(args.parent_artifact_dir / "finite_compression_steps.csv")
    if len(parent_steps) != 1:
        raise OneStepStop("parent accepted-step evidence mismatch")
    step_row, U_before, U_after = _run_one_step(
        contract=contract,
        b1_contract=b1_contract,
        U_step493=U,
        parent_step_row=parent_steps[0],
        root=root,
        topology_count=int(diagnostic_summary["root_topology_node_count"]),
    )

    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_8b",
        "scope": "model_review_one_actual_fvm_step_guard_front_refined_hugoniot",
        "source_git_sha": args.source_git_sha,
        "accepted_state_parent_artifact": inc8a.PARENT_ARTIFACT,
        "accepted_state_parent_artifact_sha256": inc8a.PARENT_DIGEST,
        "diagnostic_source_sha": DIAGNOSTIC_SOURCE_SHA,
        "diagnostic_run": DIAGNOSTIC_RUN,
        "diagnostic_job": DIAGNOSTIC_JOB,
        "diagnostic_artifact": DIAGNOSTIC_ARTIFACT,
        "diagnostic_artifact_name": DIAGNOSTIC_ARTIFACT_NAME,
        "diagnostic_artifact_sha256": DIAGNOSTIC_DIGEST,
        "diagnostic_authority_verified": True,
        "root_authority_comparison": comparison,
        "root_authority_comparison_passed": comparison["passed"],
        "solver_step_before": EXPECTED_STEP_BEFORE,
        "solver_step_after": int(step_row["solver_step_count"]),
        "solver_time_before_s": EXPECTED_TIME_BEFORE_S,
        "solver_time_after_s": float(step_row["time_after_s"]),
        "accepted_dt_s": float(step_row["accepted_dt_s"]),
        "halving_count": int(step_row["halving_count"]),
        "root_requested_chi": float(root["requested_chi"]),
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(root["local_residual_slope_kg_s_Pa"]),
        "root_gate_passed": bool(root["root_gate_passed"]),
        "final_outlet_pressure_pa": float(step_row["outlet_pressure_after_step_pa"]),
        "final_outlet_velocity_m_s": float(step_row["outlet_velocity_after_step_m_s"]),
        "final_outlet_mach": float(step_row["outlet_mach_after_step"]),
        "final_outlet_phase": step_row["outlet_phase_after_step"],
        "final_minimum_density_kg_m3": float(step_row["minimum_density_after_step_kg_m3"]),
        "final_minimum_internal_energy_J_kg": float(
            step_row["minimum_internal_energy_after_step_J_kg"]
        ),
        "final_rho_xv_exact_zero": bool(step_row["rho_xv_exact_zero"]),
        "increment_8b_one_step_gate_passed": bool(
            step_row["increment_8b_one_step_gate_passed"]
        ),
        "outcome": OUTCOME,
        "solver_step_495_authorized": False,
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

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "recomputed_fixed_scan.csv", fixed_rows)
    _write_csv(output / "recomputed_guard_front.csv", guard_rows)
    _write_csv(output / "recomputed_root_topology.csv", topology_rows)
    _write_csv(output / "recomputed_density_search.csv", density_rows)
    _write_csv(output / "selected_root.csv", [root])
    _write_csv(output / "finite_compression_one_step.csv", [step_row])
    np.savez_compressed(
        output / "finite_compression_one_step_states.npz",
        U_before=U_before,
        U_after=U_after,
        solver_step_before=np.asarray([EXPECTED_STEP_BEFORE], dtype=np.int64),
        solver_step_after=np.asarray([EXPECTED_STEP_AFTER], dtype=np.int64),
        solver_time_before_s=np.asarray([EXPECTED_TIME_BEFORE_S]),
        solver_time_after_s=np.asarray([summary["solver_time_after_s"]]),
    )
    (output / "authority_verification.json").write_text(
        json.dumps(
            {
                "accepted_state_parent_verified": True,
                "diagnostic_authority_verified": True,
                "root_authority_comparison": comparison,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(
        "# Increment 8B Guard-front refined one-step\n\n"
        "The exact step-493 state and Increment 8A root authority were verified. "
        "Only the B1-success Hugoniot root constructed the flux for one actual "
        "FvmSolver update to step 494. Formal states remain unchanged.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "recomputed_fixed_scan.csv",
        "recomputed_guard_front.csv",
        "recomputed_root_topology.csv",
        "recomputed_density_search.csv",
        "selected_root.csv",
        "finite_compression_one_step.csv",
        "finite_compression_one_step_states.npz",
        "authority_verification.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
