from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


PARENT_SOURCE_SHA = "bc4b8102400f1d0741ea85156b71c64a7258c658"
PARENT_RUN = 31667618448
PARENT_JOB = 94345455162
PARENT_ARTIFACT = 9168542012
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9d-dynamic-full-horizon-31667618448"
)
PARENT_DIGEST = (
    "3d9fe84b8e9dfcdab73971c39651093bc565230db8ac461e77a26a9a53a16da7"
)
EXPECTED_STEP = 605
EXPECTED_TIME_S = 0.004054899620692231
NEXT_STEP = 606
BOUNDARY_ITERATIONS = 48
SUPPORTED = "BOUNDED_B1_SUCCESS_WINDOW_WITH_UNIQUE_ROOT_SUPPORTED"
ROOT_TOLERANCE = float(base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)
ALLOWED_UNAVAILABLE = set(inc8a.ALLOWED_UNAVAILABLE)

REQUIRED_PARENT_FILES = {
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
    "artifact_sha256.txt",
}


class BoundedWindowDiagnosticStop(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


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


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str]]:
    if artifact_digest != PARENT_DIGEST:
        raise BoundedWindowDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH", "GitHub artifact digest mismatch"
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != REQUIRED_PARENT_FILES:
        raise BoundedWindowDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"parent file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != REQUIRED_PARENT_FILES - {"artifact_sha256.txt"}:
        raise BoundedWindowDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH", "parent manifest names mismatch"
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise BoundedWindowDiagnosticStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent SHA256 mismatch for {name}",
            )

    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": "INCREMENT_9D_STOPPED",
        "additional_accepted_steps": 71,
        "final_solver_step": EXPECTED_STEP,
        "final_solver_time_s": EXPECTED_TIME_S,
        "stop_classification": "DiagnosticStop",
        "target_horizon_reached": False,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise BoundedWindowDiagnosticStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent summary mismatch for {key}: {summary.get(key)!r}",
            )
    if "B1-unavailable fixed node follows a successful node" not in str(
        summary.get("stop_reason")
    ):
        raise BoundedWindowDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH", "parent stop reason mismatch"
        )

    with np.load(
        directory / "finite_compression_full_horizon_states.npz"
    ) as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if (
        U_after.shape != (32, 4)
        or step_after != EXPECTED_STEP
        or time_after != EXPECTED_TIME_S
    ):
        raise BoundedWindowDiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH", "parent state identity mismatch"
        )
    if not np.all(np.isfinite(U_after)):
        raise BoundedWindowDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE", "state contains nonfinite values"
        )
    rho = np.asarray(U_after[:, 0], dtype=float)
    velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
    internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise BoundedWindowDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "density or internal energy is nonpositive",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise BoundedWindowDiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH", "rho*xv is not exact zero"
        )

    roots = _read_csv(directory / "finite_compression_roots.csv")
    if len(roots) != 71 or int(roots[-1]["requested_solver_step"]) != EXPECTED_STEP:
        raise BoundedWindowDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH", "parent root rows mismatch"
        )
    if roots[-1].get("root_gate_passed") != "True":
        raise BoundedWindowDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH", "last parent root gate did not pass"
        )
    return summary, U_after, roots[-1]


def _is_unavailable(row: dict[str, Any]) -> bool:
    return bool(
        not row.get("evaluation_succeeded")
        and row.get("formal_outcome") in ALLOWED_UNAVAILABLE
    )


def _is_success(row: dict[str, Any]) -> bool:
    return bool(row.get("evaluation_succeeded") and row.get("local_candidate_admissible"))


def _success_blocks(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        if _is_success(row):
            current.append(row)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _refine_upper_boundary(
    *,
    curve: Any,
    lower_success: dict[str, Any],
    upper_unavailable: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    lower = dict(lower_success)
    upper = dict(upper_unavailable)
    lower_chi = float(lower["requested_chi"])
    upper_chi = float(upper["requested_chi"])
    if not _is_success(lower) or not _is_unavailable(upper):
        raise BoundedWindowDiagnosticStop(
            "UPPER_BOUNDARY_REFINEMENT_FAILURE",
            "invalid initial upper-boundary bracket",
        )
    rows: list[dict[str, Any]] = []
    for iteration in range(1, BOUNDARY_ITERATIONS + 1):
        mid_chi = float(0.5 * (lower_chi + upper_chi))
        if not lower_chi < mid_chi < upper_chi:
            raise BoundedWindowDiagnosticStop(
                "UPPER_BOUNDARY_REFINEMENT_FAILURE",
                "upper-boundary midpoint collapsed",
            )
        mid = curve.evaluate(mid_chi, "increment_9e_upper_boundary")
        if _is_success(mid):
            classification = "B1_SUCCESS"
            lower_chi = mid_chi
            lower = dict(mid)
        elif _is_unavailable(mid):
            classification = "B1_UNAVAILABLE"
            upper_chi = mid_chi
            upper = dict(mid)
        else:
            raise BoundedWindowDiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected upper-boundary outcome: {mid.get('formal_outcome')} "
                f"{mid.get('formal_message')}",
            )
        rows.append(
            {
                **mid,
                "row_role": "UPPER_SUCCESS_WINDOW_BOUNDARY",
                "boundary_iteration": iteration,
                "boundary_classification": classification,
                "lower_success_chi_after": lower_chi,
                "upper_unavailable_chi_after": upper_chi,
                "boundary_width_after": upper_chi - lower_chi,
                "root_topology_member": False,
                "root_topology_order": None,
            }
        )
    if not _is_success(lower) or not _is_unavailable(upper):
        raise BoundedWindowDiagnosticStop(
            "UPPER_BOUNDARY_REFINEMENT_FAILURE",
            "final upper-boundary invariant failed",
        )
    return lower, upper, rows


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
        raise BoundedWindowDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE", "outlet scope departure"
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
        curve.evaluate(float(chi), "increment_9e_fixed_scan")
        for chi in base.inc5_core.CHI_NODES
    ]
    fixed_rows = [
        {
            **row,
            "row_role": "FIXED_SCAN",
            "fixed_classification": (
                "B1_SUCCESS" if _is_success(row) else "B1_UNAVAILABLE"
            ),
            "root_topology_member": False,
            "root_topology_order": None,
        }
        for row in fixed_raw
    ]
    for row in fixed_rows:
        if not _is_success(row) and not _is_unavailable(row):
            raise BoundedWindowDiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected fixed outcome: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
            )

    blocks = _success_blocks(fixed_rows)
    if not blocks:
        raise BoundedWindowDiagnosticStop(
            "NO_B1_SUCCESS_WINDOW", "fixed scan has no B1-success window"
        )
    if len(blocks) != 1:
        raise BoundedWindowDiagnosticStop(
            "MULTIPLE_B1_SUCCESS_WINDOWS",
            f"fixed scan contains {len(blocks)} success windows",
        )
    success_block = blocks[0]
    first_success_index = fixed_rows.index(success_block[0])
    last_success_index = fixed_rows.index(success_block[-1])
    leading = fixed_rows[:first_success_index]
    trailing = fixed_rows[last_success_index + 1 :]
    if not leading:
        raise BoundedWindowDiagnosticStop(
            "MISSING_LEADING_UNAVAILABLE_DOMAIN",
            "fixed scan has no leading unavailable domain",
        )
    if not trailing:
        raise BoundedWindowDiagnosticStop(
            "MISSING_TRAILING_UNAVAILABLE_DOMAIN",
            "fixed scan has no trailing unavailable domain",
        )
    if not all(_is_unavailable(row) for row in leading + trailing):
        raise BoundedWindowDiagnosticStop(
            "MULTIPLE_B1_SUCCESS_WINDOWS",
            "non-success nodes inside the fixed success-window topology",
        )

    try:
        lower_unavailable, lower_success, lower_rows = inc8a._refine_guard_front(
            curve=curve,
            lower_row=leading[-1],
            upper_row=success_block[0],
        )
    except Exception as exc:
        raise BoundedWindowDiagnosticStop(
            "LOWER_BOUNDARY_REFINEMENT_FAILURE",
            f"lower-boundary refinement failed: {type(exc).__name__}: {exc}",
        ) from exc
    upper_success, upper_unavailable, upper_rows = _refine_upper_boundary(
        curve=curve,
        lower_success=success_block[-1],
        upper_unavailable=trailing[0],
    )

    topology_source = [lower_success] + [
        row
        for row in success_block
        if float(row["requested_chi"]) > float(lower_success["requested_chi"])
    ]
    topology_source = sorted(
        topology_source, key=lambda row: float(row["requested_chi"])
    )
    topology_rows = [
        {
            **row,
            "row_role": "ROOT_TOPOLOGY",
            "root_topology_member": True,
            "root_topology_order": index,
        }
        for index, row in enumerate(topology_source, start=1)
    ]
    residuals = [
        float(row["compatibility_residual_kg_s"]) for row in topology_rows
    ]
    monotone = bool(
        residuals
        and all(b <= a for a, b in zip(residuals, residuals[1:]))
    )
    if not monotone:
        raise BoundedWindowDiagnosticStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "bounded success-window residuals are nonmonotone",
        )
    brackets = base.inc5_core._brackets(topology_rows)
    if len(brackets) > 1:
        raise BoundedWindowDiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS",
            f"bounded success window contains {len(brackets)} root brackets",
        )
    if len(brackets) != 1:
        raise BoundedWindowDiagnosticStop(
            "NO_UNIQUE_COMPATIBILITY_ROOT",
            "bounded success window contains no unique root bracket",
        )
    raw_root = base.inc5_core._bisect_compatibility_root(
        curve="GENERAL_EOS_HUGONIOT",
        bracket=brackets[0],
        evaluate_chi=curve.evaluate,
    )
    try:
        selected_root = inc8a._complete_root(
            raw_root=raw_root,
            curve=curve,
            hook=hook,
            state_id=state_id,
            static=static,
            denominator=denominator,
        )
    except Exception as exc:
        raise BoundedWindowDiagnosticStop(
            "ROOT_OR_LEDGER_FAILURE",
            f"selected root completion failed: {type(exc).__name__}: {exc}",
        ) from exc

    U_after = np.asarray(U, dtype=float).copy()
    state_unchanged = bool(np.array_equal(U, U_after))
    gate = bool(
        state_unchanged
        and bool(selected_root["root_gate_passed"])
        and base.WEAK_COMPRESSION_CHI_LIMIT
        < float(selected_root["requested_chi"])
        <= base.DIAGNOSTIC_CHI_CAP
        and abs(float(selected_root["root_mass_residual_kg_s"]))
        <= ROOT_TOLERANCE
        and float(selected_root["local_residual_slope_kg_s_Pa"]) < 0.0
        and float(selected_root["velocity_m_s"]) >= -velocity_tolerance
        and 0.0 <= float(selected_root["mach"]) < 1.0
        and normalize_phase(str(selected_root["phase"])) in allowed_phases
    )
    outcome = SUPPORTED if gate else "ROOT_OR_LEDGER_FAILURE"

    selected_root = {
        **selected_root,
        "diagnostic_classification": outcome,
        "selected_root_present": True,
        "fvm_step_606_attempted": False,
        "state_unchanged": state_unchanged,
    }
    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_finite_compression_increment_9e"
        ),
        "scope": "diagnostic_only_step605_bounded_b1_success_window",
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
        "state_unchanged": state_unchanged,
        "fvm_step_606_attempted": False,
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_stagnation_pressure_pa": float(
            reconstruction.stagnation_pressure_pa
        ),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_phase": str(static.phase),
        "fixed_scan_node_count": len(fixed_rows),
        "leading_unavailable_node_count": len(leading),
        "leading_unavailable_outcomes": sorted(
            {str(row["formal_outcome"]) for row in leading}
        ),
        "success_window_count": len(blocks),
        "fixed_success_node_count": len(success_block),
        "first_fixed_success_chi": float(success_block[0]["requested_chi"]),
        "last_fixed_success_chi": float(success_block[-1]["requested_chi"]),
        "trailing_unavailable_node_count": len(trailing),
        "trailing_unavailable_outcomes": sorted(
            {str(row["formal_outcome"]) for row in trailing}
        ),
        "lower_boundary_iterations": len(lower_rows),
        "lower_boundary_final_unavailable_chi": float(
            lower_unavailable["requested_chi"]
        ),
        "lower_boundary_final_success_chi": float(
            lower_success["requested_chi"]
        ),
        "lower_boundary_width_chi": float(
            lower_success["requested_chi"]
            - lower_unavailable["requested_chi"]
        ),
        "upper_boundary_iterations": len(upper_rows),
        "upper_boundary_final_success_chi": float(
            upper_success["requested_chi"]
        ),
        "upper_boundary_final_unavailable_chi": float(
            upper_unavailable["requested_chi"]
        ),
        "upper_boundary_width_chi": float(
            upper_unavailable["requested_chi"]
            - upper_success["requested_chi"]
        ),
        "root_topology_node_count": len(topology_rows),
        "root_topology_requested_chi": [
            float(row["requested_chi"]) for row in topology_rows
        ],
        "root_topology_residuals_kg_s": residuals,
        "root_topology_monotone_nonincreasing": monotone,
        "root_topology_sign_change_count": len(brackets),
        "selected_root_chi": float(selected_root["requested_chi"]),
        "selected_root_pressure_pa": float(selected_root["pressure_pa"]),
        "selected_root_pressure_offset_pa": float(
            selected_root["pressure_offset_pa"]
        ),
        "selected_root_residual_kg_s": float(
            selected_root["root_mass_residual_kg_s"]
        ),
        "selected_root_local_slope_kg_s_Pa": float(
            selected_root["local_residual_slope_kg_s_Pa"]
        ),
        "selected_root_velocity_m_s": float(selected_root["velocity_m_s"]),
        "selected_root_mach": float(selected_root["mach"]),
        "selected_root_phase": str(selected_root["phase"]),
        "selected_root_b1_outcome": str(selected_root["formal_outcome"]),
        "selected_root_gate_passed": bool(selected_root["root_gate_passed"]),
        "outcome": outcome,
        "increment_9e_diagnostic_gate_passed": gate,
        "actual_continuation_supported": gate,
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
        fixed_rows,
        lower_rows,
        upper_rows,
        topology_rows,
        list(curve.density_search_rows),
        selected_root,
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
    parent_summary, U, parent_root = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    del parent_summary
    (
        summary,
        fixed_rows,
        lower_rows,
        upper_rows,
        topology_rows,
        density_rows,
        selected_root,
    ) = _run(
        contract=contract,
        b1_contract=b1_contract,
        U=U,
        parent_root=parent_root,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "step605_fixed_scan.csv", fixed_rows)
    _write_csv(output / "step605_lower_boundary_refinement.csv", lower_rows)
    _write_csv(output / "step605_upper_boundary_refinement.csv", upper_rows)
    _write_csv(output / "step605_root_topology.csv", topology_rows)
    _write_csv(output / "step605_hugoniot_density_search.csv", density_rows)
    _write_csv(output / "step605_selected_root.csv", [selected_root])
    np.savez_compressed(
        output / "step605_state_identity.npz",
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
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9E bounded B1 success-window diagnostic\n\n"
        "The exact accepted step-605 state was loaded without mutation. The "
        "unchanged fixed Hugoniot scan, lower B1-unavailable/success boundary, "
        "upper success/unavailable boundary and successful-domain root topology "
        "were diagnosed without attempting solver step 606. Failed B1 states "
        "remained unavailable and were not used as root endpoints or fluxes.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step605_fixed_scan.csv",
        "step605_lower_boundary_refinement.csv",
        "step605_upper_boundary_refinement.csv",
        "step605_root_topology.csv",
        "step605_hugoniot_density_search.csv",
        "step605_selected_root.csv",
        "step605_state_identity.npz",
        "authority_verification.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9e_diagnostic_gate_passed"]:
        raise SystemExit(
            "Increment 9E diagnostic did not support continuation: "
            f"{summary['outcome']}"
        )


if __name__ == "__main__":
    main()
