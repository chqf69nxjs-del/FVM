from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_dynamic_full_horizon as full
import u3_b2_a1_finite_compression_guard_front_8_step as runner
import u3_b2_a1_finite_compression_guard_front_8_step_dynamic_topology_fix as dynamic_fix
import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
import u3_b2_a1_finite_compression_step635_seeded_island_diagnostic as island
import u3_b2_a1_finite_compression_step635_seeded_island_float_fix as float_fix
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    normalize_phase,
)


PARENT_SOURCE_SHA = "8e2825d0a6708dd287276181eee55f9459b04ce1"
PARENT_RUN = 31669680994
PARENT_JOB = 94351542532
PARENT_ARTIFACT = 9169230736
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9h-rerun-31669680994"
)
PARENT_DIGEST = (
    "a627e2b1720429f79fd80699cb117ddc74c7b931d78c482c27aee98933ece42b"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_9H_SEEDED_ISLAND_ONE_STEP_PASS"
STARTING_STEP = 636
STARTING_TIME_S = 0.004262873917468169
MAXIMUM_OPERATIONAL_SOLVER_STEP = 650
OUTCOME = (
    "FINITE_COMPRESSION_INCREMENT_9I_DYNAMIC_SEEDED_FULL_HORIZON_"
    "WORKING_SLICE_PASS"
)
SEED_LOWER_FACTOR = 0.70
SEED_UPPER_FACTOR = 1.60
SEEDED_NODE_COUNT = 257

PARENT_REQUIRED_FILES = {
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
    "artifact_sha256.txt",
}


class DynamicSeededFinalStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str], dict[str, str]]:
    if artifact_digest != PARENT_DIGEST:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9H GitHub artifact digest mismatch",
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"Increment 9H file set mismatch: {sorted(actual)}",
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
            "Increment 9H internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise runner.ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 9H internal SHA256 mismatch for {name}",
            )

    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "increment_9h_one_step_gate_passed": True,
        "root_authority_comparison_passed": True,
        "solver_step_before": 635,
        "solver_step_after": STARTING_STEP,
        "solver_time_after_s": STARTING_TIME_S,
        "solver_step_637_authorized": False,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise runner.ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 9H summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(directory / "finite_compression_one_step_states.npz") as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if (
        U_after.shape != (32, 4)
        or step_after != STARTING_STEP
        or time_after != STARTING_TIME_S
    ):
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 9H state identity mismatch",
        )
    if not np.all(np.isfinite(U_after)):
        raise runner.ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 9H final state contains nonfinite values",
        )
    rho = np.asarray(U_after[:, 0], dtype=float)
    velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
    internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise runner.ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 9H final density or internal energy is nonpositive",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 9H final rho*xv is not exact zero",
        )

    step_rows = _read_csv(directory / "finite_compression_one_step.csv")
    root_rows = _read_csv(directory / "selected_root.csv")
    if len(step_rows) != 1 or len(root_rows) != 1:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9H step/root row count mismatch",
        )
    if step_rows[0].get("increment_9h_one_step_gate_passed") != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9H per-step gate did not pass",
        )
    if root_rows[0].get("root_gate_passed") != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9H selected-root gate did not pass",
        )
    return summary, U_after, step_rows[0], root_rows[0]


def _dynamic_seeded_root_run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U: np.ndarray,
    parent_root: dict[str, str],
):
    del b1_contract
    if dynamic_fix._active_b1_contract is None:
        raise RuntimeError("authoritative B1 contract was not bound")

    provider = CoolPropB2StateProvider()
    hook = base.A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=dynamic_fix._active_b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
    )
    previous_root_pressure = float(parent_root["root_pressure_pa"])
    hook._previous_root_pressure_pa = previous_root_pressure
    state_id = hook.state_id
    reconstruction = provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if (
        float(static.velocity_m_s) < -velocity_tolerance
        or not 0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0
        or normalize_phase(str(static.phase)) not in allowed_phases
    ):
        raise inc8a.DiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "outlet scope departure",
        )

    seed_chi = float(
        (previous_root_pressure - float(static.pressure_pa)) / denominator
    )
    if not base.WEAK_COMPRESSION_CHI_LIMIT < seed_chi < base.DIAGNOSTIC_CHI_CAP:
        raise inc8a.DiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            f"dynamic seed chi is outside finite-compression scope: {seed_chi}",
        )
    lower_chi = float(
        max(base.WEAK_COMPRESSION_CHI_LIMIT, SEED_LOWER_FACTOR * seed_chi)
    )
    upper_chi = float(
        min(base.DIAGNOSTIC_CHI_CAP, SEED_UPPER_FACTOR * seed_chi)
    )
    if not lower_chi < seed_chi < upper_chi:
        raise inc8a.DiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            "dynamic seeded interval does not contain its seed",
        )

    base.inc5_core.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        base.inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
    )
    curve = base.inc5_final.IdentityStatusPropagatedHugoniotCurve(
        static=static,
        hook=hook,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_tolerance,
        pressure_denominator_pa=denominator,
    )

    fixed_raw = [
        curve.evaluate(float(chi), "increment_9i_unchanged_fixed_scan")
        for chi in base.inc5_core.CHI_NODES
    ]
    fixed_rows = [
        {
            **row,
            "row_role": "UNCHANGED_FIXED_SCAN",
            "dynamic_seeded_classification": island._classification(row),
            "dynamic_seed_chi": seed_chi,
            "dynamic_interval_lower_chi": lower_chi,
            "dynamic_interval_upper_chi": upper_chi,
            "root_topology_member": False,
            "root_topology_order": None,
        }
        for row in fixed_raw
    ]

    interval_chi = np.linspace(
        lower_chi,
        upper_chi,
        SEEDED_NODE_COUNT,
        dtype=float,
    )
    interval_raw = [
        curve.evaluate(float(chi), "increment_9i_dynamic_seeded_interval")
        for chi in interval_chi
    ]
    interval_rows = [
        {
            **row,
            "row_role": "DYNAMIC_SEEDED_INTERVAL",
            "dynamic_seeded_classification": island._classification(row),
            "dynamic_interval_index": index,
            "dynamic_seed_chi": seed_chi,
            "dynamic_interval_lower_chi": lower_chi,
            "dynamic_interval_upper_chi": upper_chi,
            "root_topology_member": False,
            "root_topology_order": None,
        }
        for index, row in enumerate(interval_raw)
    ]
    blocks = island._success_blocks(interval_rows)
    if not blocks:
        raise inc8a.DiagnosticStop(
            "NO_ADMISSIBLE_ISLAND",
            "dynamic seeded interval contains no admissible island",
        )
    if len(blocks) != 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_ADMISSIBLE_ISLANDS",
            f"dynamic seeded interval contains {len(blocks)} islands",
        )
    admissible_island = blocks[0]
    if len(admissible_island) < 2:
        raise inc8a.DiagnosticStop(
            "ADMISSIBLE_ISLAND_TOO_NARROW_FOR_FIXED_DIAGNOSTIC",
            "dynamic seeded island contains fewer than two nodes",
        )
    first_index = interval_rows.index(admissible_island[0])
    last_index = interval_rows.index(admissible_island[-1])
    if first_index == 0 or last_index == len(interval_rows) - 1:
        raise inc8a.DiagnosticStop(
            "SEEDED_INTERVAL_EDGE_CONTACT",
            "dynamic seeded island touches an interval edge",
        )
    lower_neighbor = interval_rows[first_index - 1]
    upper_neighbor = interval_rows[last_index + 1]
    if not island._is_excluded(lower_neighbor) or not island._is_excluded(
        upper_neighbor
    ):
        raise inc8a.DiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            "dynamic seeded island is not bounded by excluded states",
        )

    _, lower_success, lower_rows = float_fix._corrected_refine_boundary(
        curve=curve,
        excluded_row=lower_neighbor,
        success_row=admissible_island[0],
        lower_excluded=True,
        label="lower",
    )
    _, upper_success, upper_rows = float_fix._corrected_refine_boundary(
        curve=curve,
        excluded_row=upper_neighbor,
        success_row=admissible_island[-1],
        lower_excluded=False,
        label="upper",
    )

    topology_source = island._deduplicate_success_rows(
        [lower_success, *admissible_island, upper_success]
    )
    topology_rows = [
        {
            **row,
            "row_role": "ROOT_TOPOLOGY",
            "root_topology_member": True,
            "root_topology_order": index,
            "dynamic_seed_chi": seed_chi,
            "dynamic_interval_lower_chi": lower_chi,
            "dynamic_interval_upper_chi": upper_chi,
        }
        for index, row in enumerate(topology_source, start=1)
    ]
    topology_chi = [
        float(row["requested_chi"]) for row in topology_rows
    ]
    if any(right <= left for left, right in zip(topology_chi, topology_chi[1:])):
        raise inc8a.DiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            "dynamic root-topology coordinates are not strictly increasing",
        )
    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in topology_rows
    ]
    monotone = bool(
        residuals
        and all(right <= left for left, right in zip(residuals, residuals[1:]))
    )
    if not monotone:
        raise inc8a.DiagnosticStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "dynamic seeded root topology is nonmonotone",
        )
    brackets = base.inc5_core._brackets(topology_rows)
    if len(brackets) > 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS",
            f"dynamic seeded island contains {len(brackets)} roots",
        )
    if len(brackets) != 1:
        raise inc8a.DiagnosticStop(
            "NO_UNIQUE_COMPATIBILITY_ROOT",
            "dynamic seeded island contains no unique root",
        )

    raw_root = base.inc5_core._bisect_compatibility_root(
        curve="GENERAL_EOS_HUGONIOT",
        bracket=brackets[0],
        evaluate_chi=curve.evaluate,
    )
    root = inc8a._complete_root(
        raw_root=raw_root,
        curve=curve,
        hook=hook,
        state_id=state_id,
        static=static,
        denominator=denominator,
    )
    classification = inc8a.SUPPORTED
    selected_root = {
        **root,
        "selected_root_present": True,
        "diagnostic_classification": classification,
    }

    combined_scan_rows = fixed_rows + interval_rows
    summary = {
        "fixed_scan_node_count": len(combined_scan_rows),
        "fixed_unavailable_node_count": sum(
            island._is_excluded(row) for row in combined_scan_rows
        ),
        "fixed_success_node_count": len(admissible_island),
        "fixed_sign_change_count": len(brackets),
        "fixed_success_residual_monotone_nonincreasing": monotone,
        "guard_front_refinement_applied": True,
        "guard_front_iterations": len(lower_rows) + len(upper_rows),
        "root_topology_node_count": len(topology_rows),
        "root_topology_requested_chi": topology_chi,
        "root_topology_residuals_kg_s": residuals,
        "root_topology_monotone_nonincreasing": monotone,
        "root_topology_sign_change_count": len(brackets),
        "selected_root_present": True,
        "selected_root_chi": float(root["requested_chi"]),
        "selected_root_residual_kg_s": float(
            root["root_mass_residual_kg_s"]
        ),
        "selected_root_gate_passed": bool(root["root_gate_passed"]),
        "dynamic_seeded_interval_applied": True,
        "dynamic_seed_chi": seed_chi,
        "dynamic_interval_lower_chi": lower_chi,
        "dynamic_interval_upper_chi": upper_chi,
        "dynamic_seeded_interval_node_count": SEEDED_NODE_COUNT,
        "admissible_island_node_count": len(admissible_island),
        "outcome": classification,
        "diagnostic_classification_complete": True,
        "actual_continuation_supported": True,
    }
    return (
        summary,
        combined_scan_rows,
        lower_rows + upper_rows,
        topology_rows,
        list(curve.density_search_rows),
        selected_root,
    )


def _postprocess(output: Path) -> dict[str, Any]:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    original_gate = bool(summary.pop("increment_9d_full_horizon_gate_passed"))
    scan_rows = _read_csv(output / "hugoniot_fixed_scans.csv")
    seeded_rows = [
        row
        for row in scan_rows
        if row.get("row_role") == "DYNAMIC_SEEDED_INTERVAL"
    ]
    step_ids = sorted(
        {int(row["requested_solver_step"]) for row in seeded_rows}
    )
    seed_values = sorted(
        {
            float(row["dynamic_seed_chi"])
            for row in seeded_rows
            if row.get("dynamic_seed_chi") not in {None, ""}
        }
    )
    lower_values = sorted(
        {
            float(row["dynamic_interval_lower_chi"])
            for row in seeded_rows
            if row.get("dynamic_interval_lower_chi") not in {None, ""}
        }
    )
    upper_values = sorted(
        {
            float(row["dynamic_interval_upper_chi"])
            for row in seeded_rows
            if row.get("dynamic_interval_upper_chi") not in {None, ""}
        }
    )
    gate = bool(
        original_gate
        and step_ids
        and len(seeded_rows) == len(step_ids) * SEEDED_NODE_COUNT
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_finite_compression_increment_9i"
            ),
            "scope": "model_review_dynamic_seeded_final_nominal_two_l_over_c0",
            "dynamic_seeded_interval_applied": True,
            "dynamic_seeded_interval_lower_factor": SEED_LOWER_FACTOR,
            "dynamic_seeded_interval_upper_factor": SEED_UPPER_FACTOR,
            "dynamic_seeded_interval_node_count_per_step": SEEDED_NODE_COUNT,
            "dynamic_seeded_interval_step_count": len(step_ids),
            "dynamic_seeded_interval_requested_steps": step_ids,
            "minimum_dynamic_seed_chi": min(seed_values),
            "maximum_dynamic_seed_chi": max(seed_values),
            "minimum_dynamic_interval_lower_chi": min(lower_values),
            "maximum_dynamic_interval_upper_chi": max(upper_values),
            "original_increment_9d_gate_passed": original_gate,
            "increment_9i_full_horizon_gate_passed": gate,
            "outcome": OUTCOME if gate else "INCREMENT_9I_STOPPED",
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
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    authority = {
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_DIGEST,
        "verified": True,
        "dynamic_seeded_rule": {
            "lower_factor": SEED_LOWER_FACTOR,
            "upper_factor": SEED_UPPER_FACTOR,
            "node_count": SEEDED_NODE_COUNT,
            "boundary_logical_iterations": island.BOUNDARY_ITERATIONS,
        },
        "b1_behavior_changed": False,
        "local_admissibility_rule_changed": False,
        "excluded_state_used_as_root_endpoint": False,
        "excluded_state_used_to_construct_flux": False,
        "tolerance_or_scope_changed": False,
    }
    (output / "dynamic_seeded_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Increment 9I dynamic seeded final segment\n\n"
        + "Every accepted final-segment step derived its deterministic seed "
        + "from the previous accepted root pressure and current outlet state, "
        + "then evaluated the fixed 0.70/1.60-factor, 257-node interval. Only "
        + "one bounded locally admissible B1-success island contributed to "
        + "root topology and flux construction. Formal states remain false.\n\n"
        + "```json\n"
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
        "dynamic_seeded_authority.json",
        "stop_evidence.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


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

    runner.DynamicGuardFrontHugoniotHook = (
        dynamic_fix.CorrectedDynamicGuardFrontHugoniotHook
    )
    runner.inc8a._run = _dynamic_seeded_root_run
    full.PARENT_SOURCE_SHA = PARENT_SOURCE_SHA
    full.PARENT_RUN = PARENT_RUN
    full.PARENT_JOB = PARENT_JOB
    full.PARENT_ARTIFACT = PARENT_ARTIFACT
    full.PARENT_ARTIFACT_NAME = PARENT_ARTIFACT_NAME
    full.PARENT_DIGEST = PARENT_DIGEST
    full.PARENT_OUTCOME = PARENT_OUTCOME
    full.STARTING_STEP = STARTING_STEP
    full.STARTING_TIME_S = STARTING_TIME_S
    full.MAXIMUM_OPERATIONAL_SOLVER_STEP = MAXIMUM_OPERATIONAL_SOLVER_STEP
    full.OUTCOME = OUTCOME
    full._verify_parent = _verify_parent

    original_argv = sys.argv
    base_exit: SystemExit | None = None
    try:
        sys.argv = [
            original_argv[0],
            "--contract",
            str(args.contract),
            "--b1-contract",
            str(args.b1_contract),
            "--model-review-spec",
            str(args.model_review_spec),
            "--parent-artifact-dir",
            str(args.parent_artifact_dir),
            "--parent-artifact-digest",
            args.parent_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        try:
            full.main()
        except SystemExit as exc:
            base_exit = exc
    finally:
        sys.argv = original_argv

    if not (args.output_dir / "summary.json").is_file():
        if base_exit is not None:
            raise base_exit
        raise DynamicSeededFinalStop(
            "full-horizon base runner did not create summary evidence"
        )
    summary = _postprocess(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9i_full_horizon_gate_passed"]:
        raise SystemExit(
            "Increment 9I full-horizon gate did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
