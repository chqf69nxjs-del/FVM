from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


PARENT_SOURCE_SHA = "9fd7ac6bcb6eefcf12099028da2fc731ae96dd3c"
PARENT_RUN = 31661720453
PARENT_JOB = 94327704607
PARENT_ARTIFACT = 9166412782
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-8-rerun-31661720453"
)
PARENT_DIGEST = (
    "d1d704997ec5e8fd038a0645b31e598939528cd9295de8762c06aaf3b81081d8"
)
EXPECTED_STEP = 493
EXPECTED_TIME_S = 0.0033036489591120113
NEXT_STEP = 494
GUARD_ITERATIONS = 48
ROOT_TOLERANCE = float(base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)
ALLOWED_UNAVAILABLE = {
    "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED",
    "NONPOSITIVE_KINETIC_ENERGY_HEAD",
}
SUPPORTED = "FINITE_COMPRESSION_GUARD_FRONT_REFINEMENT_SUPPORTED"
WEAK_SCOPE = "ROOT_RETURNED_TO_WEAK_COMPRESSION_SCOPE"
INSIDE_UNAVAILABLE = "ROOT_LIES_INSIDE_B1_UNAVAILABLE_DOMAIN"
CAP_REQUIRED = "FINITE_COMPRESSION_DIAGNOSTIC_CAP_REQUIRED"
CLASSIFIED = {SUPPORTED, WEAK_SCOPE, INSIDE_UNAVAILABLE, CAP_REQUIRED}

REQUIRED_PARENT_FILES = {
    "finite_compression_steps.csv",
    "finite_compression_roots.csv",
    "hugoniot_fixed_scans.csv",
    "hugoniot_density_search.csv",
    "branch_sequence.csv",
    "finite_compression_32_step_states.npz",
    "authority_verification.json",
    "stop_evidence.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


class DiagnosticStop(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(U, dtype="<f8").tobytes()).hexdigest()


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


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str]]:
    if artifact_digest != PARENT_DIGEST:
        raise DiagnosticStop("PARENT_ARTIFACT_MISMATCH", "GitHub artifact digest mismatch")
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != REQUIRED_PARENT_FILES:
        raise DiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH", f"parent file set mismatch: {sorted(actual)}"
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != REQUIRED_PARENT_FILES - {"artifact_sha256.txt"}:
        raise DiagnosticStop("PARENT_ARTIFACT_MISMATCH", "parent manifest names mismatch")
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise DiagnosticStop(
                "PARENT_ARTIFACT_MISMATCH", f"parent SHA256 mismatch for {name}"
            )

    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": "INCREMENT_8_STOPPED",
        "accepted_steps_completed": 1,
        "final_solver_step": EXPECTED_STEP,
        "final_solver_time_s": EXPECTED_TIME_S,
        "stop_classification": "NO_UNIQUE_HUGONIOT_ROOT",
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise DiagnosticStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(directory / "finite_compression_32_step_states.npz") as states:
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_final.shape != (32, 4) or step_after != EXPECTED_STEP or time_after != EXPECTED_TIME_S:
        raise DiagnosticStop("STATE_REPRODUCTION_MISMATCH", "parent state identity mismatch")
    if not np.all(np.isfinite(U_final)):
        raise DiagnosticStop("NONFINITE_OR_NONPOSITIVE_STATE", "state contains nonfinite values")
    rho = U_final[:, 0]
    velocity = U_final[:, 1] / rho
    internal = U_final[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise DiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE", "density or internal energy is nonpositive"
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise DiagnosticStop("STATE_REPRODUCTION_MISMATCH", "rho*xv is not exact zero")

    roots = _read_csv(directory / "finite_compression_roots.csv")
    if len(roots) != 1 or int(roots[0]["requested_solver_step"]) != EXPECTED_STEP:
        raise DiagnosticStop("PARENT_ARTIFACT_MISMATCH", "parent root row mismatch")
    return summary, U_final, roots[0]


def _is_unavailable(row: dict[str, Any]) -> bool:
    return bool(
        not row.get("evaluation_succeeded")
        and row.get("formal_outcome") in ALLOWED_UNAVAILABLE
    )


def _is_success(row: dict[str, Any]) -> bool:
    return bool(row.get("evaluation_succeeded") and row.get("local_candidate_admissible"))


def _annotate_fixed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "row_role": "FIXED_SCAN",
            "guard_iteration": None,
            "root_topology_member": False,
            "root_topology_order": None,
            "selected_root_bracket_member": False,
        }
        for row in rows
    ]


def _refine_guard_front(
    *,
    curve: Any,
    lower_row: dict[str, Any],
    upper_row: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    lower = dict(lower_row)
    upper = dict(upper_row)
    lower_chi = float(lower["requested_chi"])
    upper_chi = float(upper["requested_chi"])
    if not _is_unavailable(lower) or not _is_success(upper):
        raise DiagnosticStop("UNEXPECTED_B1_FAILURE", "invalid initial Guard-front bracket")
    rows: list[dict[str, Any]] = []
    for iteration in range(1, GUARD_ITERATIONS + 1):
        mid_chi = float(0.5 * (lower_chi + upper_chi))
        if not lower_chi < mid_chi < upper_chi:
            raise DiagnosticStop("STATE_REPRODUCTION_MISMATCH", "Guard midpoint collapsed")
        mid = curve.evaluate(mid_chi, "increment_8a_guard_front")
        if _is_unavailable(mid):
            classification = "B1_UNAVAILABLE"
            lower_chi = mid_chi
            lower = dict(mid)
        elif _is_success(mid):
            classification = "B1_SUCCESS"
            upper_chi = mid_chi
            upper = dict(mid)
        else:
            raise DiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected Guard-front outcome: {mid.get('formal_outcome')} "
                f"{mid.get('formal_message')}",
            )
        rows.append(
            {
                **mid,
                "row_role": "GUARD_FRONT_BISECTION",
                "guard_iteration": iteration,
                "guard_classification": classification,
                "lower_unavailable_chi_after": lower_chi,
                "upper_success_chi_after": upper_chi,
                "guard_width_after": upper_chi - lower_chi,
                "root_topology_member": False,
                "root_topology_order": None,
                "selected_root_bracket_member": False,
            }
        )
    if not _is_unavailable(lower) or not _is_success(upper):
        raise DiagnosticStop("UNEXPECTED_B1_FAILURE", "final Guard-front invariant failed")
    return lower, upper, rows


def _complete_root(
    *,
    raw_root: dict[str, Any],
    curve: Any,
    hook: Any,
    state_id: str,
    static: Any,
    denominator: float,
) -> dict[str, Any]:
    requested_chi = float(raw_root["requested_chi"])

    def evaluate_pressure(pressure_pa: float) -> dict[str, Any]:
        chi = float((float(pressure_pa) - float(static.pressure_pa)) / denominator)
        candidate = curve.evaluate(chi, "increment_8a_root_completion")
        return base.inc6._augment_candidate_for_completion(
            candidate=candidate, hook=hook, state_id=state_id
        )

    candidate = evaluate_pressure(float(raw_root["pressure_pa"]))
    if not _is_success(candidate):
        raise DiagnosticStop("ROOT_OR_LEDGER_FAILURE", "selected root is not B1-admissible")
    completed = horizon._complete_root_row_dynamic_v4(
        root=candidate,
        evaluate=evaluate_pressure,
        adapter=hook.adapter,
        area_m2=hook.area_m2,
        quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
    )
    root = dict(candidate)
    root.update(completed)
    root.update(
        {
            "requested_chi": requested_chi,
            "realized_chi": float(
                (float(root["pressure_pa"]) - float(static.pressure_pa)) / denominator
            ),
            "pressure_offset_pa": float(root["pressure_pa"] - static.pressure_pa),
            "compatibility_bisection_iterations": int(
                raw_root.get("compatibility_bisection_iterations", 0)
            ),
        }
    )
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(hook.contract, state_id)["allowed_normalized_phases"]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    gate = bool(
        base.WEAK_COMPRESSION_CHI_LIMIT < requested_chi <= base.DIAGNOSTIC_CHI_CAP
        and abs(float(root["root_mass_residual_kg_s"])) <= ROOT_TOLERANCE
        and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
        and float(root["velocity_m_s"]) >= -velocity_tolerance
        and 0.0 <= float(root["mach"]) < 1.0
        and normalize_phase(str(root["phase"])) in allowed_phases
        and bool(root["hugoniot_closure_passed"])
        and bool(root["hugoniot_identity_accounted_passed"])
        and bool(root["lax_1_shock_passed"])
        and bool(root["entropy_bound_passed"])
        and float(root["stagnation_pressure_pa"]) > float(hook.adapter.back_pressure_pa)
        and bool(root["stagnation_enthalpy_round_trip_passed"])
        and bool(root["energy_mass_consistency_passed"])
        and bool(root["energy_port_closure_passed"])
        and abs(float(root["momentum_ledger_residual_N"]))
        <= base.robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    )
    root["root_gate_passed"] = gate
    if not gate:
        raise DiagnosticStop("ROOT_OR_LEDGER_FAILURE", "selected root failed fixed gates")
    return root


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U: np.ndarray,
    parent_root: dict[str, str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    provider = CoolPropB2StateProvider()
    hook = base.A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(parent_root["root_pressure_pa"])
    state_id = hook.state_id
    reconstruction = provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)["allowed_normalized_phases"]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if (
        float(static.velocity_m_s) < -velocity_tolerance
        or not 0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0
        or normalize_phase(str(static.phase)) not in allowed_phases
    ):
        raise DiagnosticStop("NONFINITE_OR_NONPOSITIVE_STATE", "outlet scope departure")

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
        curve.evaluate(float(chi), "increment_8a_fixed_scan")
        for chi in base.inc5_core.CHI_NODES
    ]
    fixed_rows = _annotate_fixed(fixed_raw)

    success_seen = False
    for row in fixed_rows:
        if _is_success(row):
            success_seen = True
        elif _is_unavailable(row):
            if success_seen:
                raise DiagnosticStop(
                    "UNEXPECTED_B1_FAILURE", "B1-unavailable node follows a successful node"
                )
        else:
            raise DiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected fixed-scan outcome: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
            )

    successful_fixed = [row for row in fixed_rows if _is_success(row)]
    unavailable_fixed = [row for row in fixed_rows if _is_unavailable(row)]
    if not successful_fixed:
        raise DiagnosticStop("NO_SUCCESSFUL_DOMAIN", "fixed scan has no B1-success domain")
    if not base.inc5_core._monotone_nonincreasing(fixed_rows):
        raise DiagnosticStop("SUCCESS_DOMAIN_NONMONOTONE", "fixed successful residuals are nonmonotone")
    fixed_brackets = base.inc5_core._brackets(fixed_rows)
    if len(fixed_brackets) > 1:
        raise DiagnosticStop("MULTIPLE_COMPATIBILITY_ROOTS", "multiple fixed root brackets")
    if len(fixed_brackets) == 1:
        raise DiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            "parent NO_UNIQUE_HUGONIOT_ROOT stop was not reproduced",
        )

    guard_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    selected_root: dict[str, Any] = {
        "selected_root_present": False,
        "diagnostic_classification": None,
    }

    first_success = successful_fixed[0]
    first_residual = float(first_success["compatibility_residual_kg_s"])
    if float(first_success["requested_chi"]) <= base.WEAK_COMPRESSION_CHI_LIMIT and (
        first_residual < -ROOT_TOLERANCE
    ):
        classification = WEAK_SCOPE
        topology_source = successful_fixed
    elif unavailable_fixed:
        lower, refined_success, guard_rows = _refine_guard_front(
            curve=curve,
            lower_row=unavailable_fixed[-1],
            upper_row=first_success,
        )
        del lower
        topology_source = [refined_success] + [
            row
            for row in successful_fixed
            if float(row["requested_chi"]) > float(refined_success["requested_chi"])
        ]
        topology_source = sorted(
            topology_source, key=lambda row: float(row["requested_chi"])
        )
        refined_residual = float(refined_success["compatibility_residual_kg_s"])
        if refined_residual < -ROOT_TOLERANCE:
            classification = INSIDE_UNAVAILABLE
        else:
            brackets = base.inc5_core._brackets(topology_source)
            if len(brackets) > 1:
                raise DiagnosticStop("MULTIPLE_COMPATIBILITY_ROOTS", "multiple refined roots")
            if len(brackets) == 0:
                last_residual = float(topology_source[-1]["compatibility_residual_kg_s"])
                classification = CAP_REQUIRED if last_residual > ROOT_TOLERANCE else WEAK_SCOPE
            else:
                raw_root = base.inc5_core._bisect_compatibility_root(
                    curve="GENERAL_EOS_HUGONIOT",
                    bracket=brackets[0],
                    evaluate_chi=curve.evaluate,
                )
                root = _complete_root(
                    raw_root=raw_root,
                    curve=curve,
                    hook=hook,
                    state_id=state_id,
                    static=static,
                    denominator=denominator,
                )
                classification = SUPPORTED
                selected_root = {**root, "selected_root_present": True}
    else:
        topology_source = successful_fixed
        if first_residual < -ROOT_TOLERANCE:
            classification = WEAK_SCOPE
        else:
            last_residual = float(successful_fixed[-1]["compatibility_residual_kg_s"])
            classification = CAP_REQUIRED if last_residual > ROOT_TOLERANCE else WEAK_SCOPE

    for index, row in enumerate(topology_source, start=1):
        topology_rows.append(
            {
                **row,
                "row_role": "ROOT_TOPOLOGY",
                "root_topology_member": True,
                "root_topology_order": index,
            }
        )
    topology_residuals = [
        float(row["compatibility_residual_kg_s"]) for row in topology_rows
    ]
    topology_monotone = bool(
        len(topology_residuals) >= 1
        and all(b <= a for a, b in zip(topology_residuals, topology_residuals[1:]))
    )
    if not topology_monotone:
        raise DiagnosticStop("SUCCESS_DOMAIN_NONMONOTONE", "refined topology is nonmonotone")

    U_after = np.asarray(U, dtype=float).copy()
    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_8a",
        "scope": "diagnostic_only_step493_hugoniot_root_topology",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_DIGEST,
        "parent_artifact_verified": True,
        "solver_step_loaded": EXPECTED_STEP,
        "next_requested_solver_step": NEXT_STEP,
        "solver_time_s": EXPECTED_TIME_S,
        "state_sha256_before": _state_sha256(U),
        "state_sha256_after": _state_sha256(U_after),
        "state_unchanged": bool(np.array_equal(U, U_after)),
        "fvm_step_494_attempted": False,
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_stagnation_pressure_pa": float(reconstruction.stagnation_pressure_pa),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_phase": str(static.phase),
        "fixed_scan_node_count": len(fixed_rows),
        "fixed_unavailable_node_count": len(unavailable_fixed),
        "fixed_success_node_count": len(successful_fixed),
        "fixed_sign_change_count": 0,
        "fixed_success_residual_monotone_nonincreasing": True,
        "first_fixed_success_chi": float(first_success["requested_chi"]),
        "first_fixed_success_residual_kg_s": first_residual,
        "last_fixed_success_chi": float(successful_fixed[-1]["requested_chi"]),
        "last_fixed_success_residual_kg_s": float(
            successful_fixed[-1]["compatibility_residual_kg_s"]
        ),
        "guard_front_refinement_applied": bool(guard_rows),
        "guard_front_iterations": len(guard_rows),
        "root_topology_node_count": len(topology_rows),
        "root_topology_requested_chi": [
            float(row["requested_chi"]) for row in topology_rows
        ],
        "root_topology_residuals_kg_s": topology_residuals,
        "root_topology_monotone_nonincreasing": topology_monotone,
        "root_topology_sign_change_count": len(base.inc5_core._brackets(topology_rows)),
        "selected_root_present": bool(selected_root.get("selected_root_present")),
        "selected_root_chi": selected_root.get("requested_chi"),
        "selected_root_residual_kg_s": selected_root.get("root_mass_residual_kg_s"),
        "selected_root_gate_passed": selected_root.get("root_gate_passed", False),
        "outcome": classification,
        "diagnostic_classification_complete": classification in CLASSIFIED,
        "actual_continuation_supported": classification == SUPPORTED,
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
    selected_root["diagnostic_classification"] = classification
    return summary, fixed_rows, guard_rows, topology_rows, list(curve.density_search_rows), selected_root


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
    parent_summary, U, parent_root = _verify_parent(
        args.parent_artifact_dir, artifact_digest=args.parent_artifact_digest
    )
    del parent_summary
    summary, fixed_rows, guard_rows, topology_rows, density_rows, selected_root = _run(
        contract=contract,
        b1_contract=b1_contract,
        U=U,
        parent_root=parent_root,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "step493_hugoniot_fixed_scan.csv", fixed_rows)
    _write_csv(output / "step493_guard_front_refinement.csv", guard_rows)
    _write_csv(output / "step493_root_topology.csv", topology_rows)
    _write_csv(output / "step493_hugoniot_density_search.csv", density_rows)
    _write_csv(output / "step493_selected_root.csv", [selected_root])
    np.savez_compressed(
        output / "step493_state_identity.npz",
        U_before=np.asarray(U, dtype=float),
        U_after=np.asarray(U, dtype=float),
        solver_step_before=np.asarray([EXPECTED_STEP], dtype=np.int64),
        solver_step_after=np.asarray([EXPECTED_STEP], dtype=np.int64),
        solver_time_before_s=np.asarray([EXPECTED_TIME_S]),
        solver_time_after_s=np.asarray([EXPECTED_TIME_S]),
    )
    authority = {
        "source_sha": PARENT_SOURCE_SHA,
        "workflow_run": PARENT_RUN,
        "job": PARENT_JOB,
        "artifact": PARENT_ARTIFACT,
        "artifact_name": PARENT_ARTIFACT_NAME,
        "artifact_sha256": PARENT_DIGEST,
        "verified": True,
    }
    (output / "authority_verification.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(
        "# Increment 8A step-493 root-topology diagnostic\n\n"
        "The exact accepted step-493 state was loaded without mutation. The "
        "unchanged Hugoniot scan, B1-unavailable front and successful-domain "
        "root topology were diagnosed without attempting solver step 494.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step493_hugoniot_fixed_scan.csv",
        "step493_guard_front_refinement.csv",
        "step493_root_topology.csv",
        "step493_hugoniot_density_search.csv",
        "step493_selected_root.csv",
        "step493_state_identity.npz",
        "authority_verification.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["diagnostic_classification_complete"]:
        raise SystemExit("Increment 8A diagnostic classification incomplete")


if __name__ == "__main__":
    main()
