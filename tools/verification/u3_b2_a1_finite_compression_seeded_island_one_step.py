from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_guard_front_one_step as one_step
import u3_b2_a1_finite_compression_step635_seeded_island_diagnostic as diagnostic
import u3_b2_a1_finite_compression_step635_seeded_island_float_fix as float_fix
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
)


DIAGNOSTIC_SOURCE_SHA = "0eab5c8e53a8e875b01e88e0cfc6a3c915c90689"
DIAGNOSTIC_RUN = 31669167528
DIAGNOSTIC_JOB = 94350087340
DIAGNOSTIC_ARTIFACT = 9169064374
DIAGNOSTIC_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9g-float-31669167528"
)
DIAGNOSTIC_DIGEST = (
    "d18a0d33ca7a157338a8ddc364edfe5aad89e413720627e7bf02e19c1b32b689"
)
EXPECTED_STEP_BEFORE = 635
EXPECTED_STEP_AFTER = 636
EXPECTED_TIME_BEFORE_S = 0.004256164770712251
OUTCOME = "FINITE_COMPRESSION_INCREMENT_9H_SEEDED_ISLAND_ONE_STEP_PASS"

DIAGNOSTIC_REQUIRED_FILES = {
    "step635_fixed_scan.csv",
    "step635_seeded_interval_scan.csv",
    "step635_lower_boundary_refinement.csv",
    "step635_upper_boundary_refinement.csv",
    "step635_root_topology.csv",
    "step635_hugoniot_density_search.csv",
    "step635_selected_root.csv",
    "step635_state_identity.npz",
    "authority_verification.json",
    "float_resolution_correction_authority.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}

ROOT_COMPARE_TOLERANCES = dict(one_step.ROOT_COMPARE_TOLERANCES)


class SeededIslandOneStepStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _verify_diagnostic(
    directory: Path,
    *,
    artifact_digest: str,
    parent_U: np.ndarray,
) -> tuple[dict[str, Any], dict[str, str]]:
    if artifact_digest != DIAGNOSTIC_DIGEST:
        raise SeededIslandOneStepStop(
            "Increment 9G GitHub artifact digest mismatch"
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != DIAGNOSTIC_REQUIRED_FILES:
        raise SeededIslandOneStepStop(
            f"Increment 9G file set mismatch: {sorted(actual)}"
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != DIAGNOSTIC_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise SeededIslandOneStepStop(
            "Increment 9G internal manifest names mismatch"
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise SeededIslandOneStepStop(
                f"Increment 9G internal SHA256 mismatch for {name}"
            )

    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": DIAGNOSTIC_SOURCE_SHA,
        "outcome": diagnostic.SUPPORTED,
        "increment_9g_diagnostic_gate_passed": True,
        "increment_9g_rerun_gate_passed": True,
        "actual_continuation_supported": True,
        "solver_step_loaded": EXPECTED_STEP_BEFORE,
        "next_requested_solver_step": EXPECTED_STEP_AFTER,
        "state_unchanged": True,
        "fvm_step_636_attempted": False,
        "fixed_admissible_success_count": 0,
        "diagnostic_interval_node_count": diagnostic.INTERVAL_NODE_COUNT,
        "admissible_island_count": 1,
        "root_topology_sign_change_count": 1,
        "selected_root_gate_passed": True,
        "float_resolution_boundary_correction_applied": True,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise SeededIslandOneStepStop(
                f"Increment 9G summary mismatch for {key}: "
                f"{summary.get(key)!r}"
            )

    with np.load(directory / "step635_state_identity.npz") as states:
        before = np.asarray(states["U_before"], dtype=float)
        after = np.asarray(states["U_after"], dtype=float)
        step_before = int(states["solver_step_before"][0])
        step_after = int(states["solver_step_after"][0])
        time_before = float(states["solver_time_before_s"][0])
        time_after = float(states["solver_time_after_s"][0])
    if (
        before.shape != (32, 4)
        or not np.array_equal(before, after)
        or not np.array_equal(before, parent_U)
        or step_before != EXPECTED_STEP_BEFORE
        or step_after != EXPECTED_STEP_BEFORE
        or time_before != EXPECTED_TIME_BEFORE_S
        or time_after != EXPECTED_TIME_BEFORE_S
    ):
        raise SeededIslandOneStepStop(
            "Increment 9G state identity mismatch"
        )
    roots = _read_csv(directory / "step635_selected_root.csv")
    if (
        len(roots) != 1
        or roots[0].get("selected_root_present") != "True"
        or roots[0].get("root_gate_passed") != "True"
    ):
        raise SeededIslandOneStepStop(
            "Increment 9G selected-root evidence mismatch"
        )
    return summary, roots[0]


def _compare_root(
    authority: dict[str, str],
    recomputed: dict[str, Any],
) -> dict[str, Any]:
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


class SeededIslandFixedRootHook(one_step.FixedRefinedRootHook):
    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        super()._ensure_root(U, t)
        if self.root_context is None:
            raise SeededIslandOneStepStop(
                "seeded-island root context was not prepared"
            )
        self.root_context.update(
            {
                "connected_scan_base_node_count": len(
                    diagnostic.base.inc5_core.CHI_NODES
                ),
                "connected_scan_requested_nodes": (
                    len(diagnostic.base.inc5_core.CHI_NODES)
                    + diagnostic.INTERVAL_NODE_COUNT
                    + 2 * diagnostic.BOUNDARY_ITERATIONS
                ),
                "connected_scan_admissible_subsonic_nodes": (
                    self.root_topology_node_count
                ),
                "seeded_interval_scan_applied": True,
                "seeded_interval_node_count": diagnostic.INTERVAL_NODE_COUNT,
                "lower_boundary_logical_iterations": (
                    diagnostic.BOUNDARY_ITERATIONS
                ),
                "upper_boundary_logical_iterations": (
                    diagnostic.BOUNDARY_ITERATIONS
                ),
            }
        )


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

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)

    parent_summary, U, parent_step, parent_root = diagnostic._verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    del parent_summary
    diagnostic_summary, authority_root = _verify_diagnostic(
        args.diagnostic_artifact_dir,
        artifact_digest=args.diagnostic_artifact_digest,
        parent_U=U,
    )

    diagnostic._refine_boundary = float_fix._corrected_refine_boundary
    (
        recomputed_summary,
        fixed_rows,
        interval_rows,
        lower_rows,
        upper_rows,
        topology_rows,
        density_rows,
        root,
    ) = diagnostic._run(
        contract=contract,
        b1_contract=b1_contract,
        U=U,
        parent_root=parent_root,
    )
    if (
        recomputed_summary["outcome"] != diagnostic.SUPPORTED
        or not bool(root.get("selected_root_present"))
        or not bool(root.get("root_gate_passed"))
    ):
        raise SeededIslandOneStepStop(
            "Increment 9G supported root did not reproduce"
        )
    comparison = _compare_root(authority_root, root)
    if not comparison["passed"]:
        raise SeededIslandOneStepStop(
            "recomputed root does not match Increment 9G authority"
        )

    one_step.EXPECTED_STEP_BEFORE = EXPECTED_STEP_BEFORE
    one_step.EXPECTED_STEP_AFTER = EXPECTED_STEP_AFTER
    one_step.EXPECTED_TIME_BEFORE_S = EXPECTED_TIME_BEFORE_S
    one_step.FixedRefinedRootHook = SeededIslandFixedRootHook
    step_row, U_before, U_after = one_step._run_one_step(
        contract=contract,
        b1_contract=b1_contract,
        U_step493=U,
        parent_step_row=parent_step,
        root=root,
        topology_count=int(diagnostic_summary["root_topology_node_count"]),
    )
    old_gate = bool(step_row.pop("increment_8b_one_step_gate_passed"))
    gate = bool(
        old_gate
        and not bool(step_row["reverse_flow_guard_triggered"])
        and bool(root["root_gate_passed"])
        and diagnostic.base.WEAK_COMPRESSION_CHI_LIMIT
        < float(root["requested_chi"])
        <= diagnostic.base.DIAGNOSTIC_CHI_CAP
        and abs(float(root["root_mass_residual_kg_s"]))
        <= diagnostic.ROOT_TOLERANCE
        and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
    )
    step_row.update(
        {
            "increment_9h_one_step_gate_passed": gate,
            "diagnostic_classification": diagnostic.SUPPORTED,
            "seeded_interval_scan_applied": True,
            "seeded_interval_node_count": diagnostic.INTERVAL_NODE_COUNT,
            "admissible_island_node_count": int(
                diagnostic_summary["admissible_island_node_count"]
            ),
            "root_topology_node_count": int(
                diagnostic_summary["root_topology_node_count"]
            ),
            "root_topology_monotone_nonincreasing": True,
            "root_topology_sign_change_count": 1,
            "failed_or_inadmissible_state_used_as_root_endpoint": False,
            "failed_or_inadmissible_state_used_to_construct_flux": False,
        }
    )
    if not gate:
        raise SeededIslandOneStepStop(
            "actual step 636 failed the Increment 9H post-step gate"
        )

    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_finite_compression_increment_9h"
        ),
        "scope": (
            "model_review_one_actual_fvm_step_seeded_admissible_island"
        ),
        "source_git_sha": args.source_git_sha,
        "accepted_state_parent_source_sha": diagnostic.PARENT_SOURCE_SHA,
        "accepted_state_parent_run": diagnostic.PARENT_RUN,
        "accepted_state_parent_job": diagnostic.PARENT_JOB,
        "accepted_state_parent_artifact": diagnostic.PARENT_ARTIFACT,
        "accepted_state_parent_artifact_sha256": diagnostic.PARENT_DIGEST,
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
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_pressure_offset_pa": float(root["pressure_offset_pa"]),
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(
            root["local_residual_slope_kg_s_Pa"]
        ),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_phase": str(root["phase"]),
        "root_gate_passed": bool(root["root_gate_passed"]),
        "final_outlet_pressure_pa": float(
            step_row["outlet_pressure_after_step_pa"]
        ),
        "final_outlet_velocity_m_s": float(
            step_row["outlet_velocity_after_step_m_s"]
        ),
        "final_outlet_mach": float(step_row["outlet_mach_after_step"]),
        "final_outlet_phase": step_row["outlet_phase_after_step"],
        "final_minimum_density_kg_m3": float(
            step_row["minimum_density_after_step_kg_m3"]
        ),
        "final_minimum_internal_energy_J_kg": float(
            step_row["minimum_internal_energy_after_step_J_kg"]
        ),
        "final_rho_xv_exact_zero": bool(step_row["rho_xv_exact_zero"]),
        "increment_9h_one_step_gate_passed": gate,
        "outcome": OUTCOME,
        "solver_step_637_authorized": False,
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
    _write_csv(output / "recomputed_seeded_interval_scan.csv", interval_rows)
    _write_csv(output / "recomputed_lower_boundary.csv", lower_rows)
    _write_csv(output / "recomputed_upper_boundary.csv", upper_rows)
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
                "b1_behavior_changed": False,
                "local_admissibility_rule_changed": False,
                "excluded_state_used_as_root_endpoint": False,
                "excluded_state_used_to_construct_flux": False,
                "tolerance_or_scope_changed": False,
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
        "# Increment 9H seeded-island one-step\n\n"
        "The exact accepted step-635 state and Increment 9G root authority "
        "were verified. The selected root was recomputed from the unchanged "
        "129-node seeded interval and corrected binary64 boundary handling. "
        "Only that B1-success, locally admissible Hugoniot root constructed "
        "the flux for one actual `FvmSolver` update to step 636. Formal states "
        "remain unchanged.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "recomputed_fixed_scan.csv",
        "recomputed_seeded_interval_scan.csv",
        "recomputed_lower_boundary.csv",
        "recomputed_upper_boundary.csv",
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
