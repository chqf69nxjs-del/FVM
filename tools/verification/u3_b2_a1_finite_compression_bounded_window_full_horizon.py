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
import u3_b2_a1_finite_compression_guard_front_8_step_dynamic_topology_fix as dyn
import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
import u3_b2_a1_finite_compression_step605_bounded_success_window_diagnostic as inc9e
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    normalize_phase,
)


PRIMARY_SOURCE_SHA = "bc4b8102400f1d0741ea85156b71c64a7258c658"
PRIMARY_RUN = 31667618448
PRIMARY_JOB = 94345455162
PRIMARY_ARTIFACT = 9168542012
PRIMARY_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9d-dynamic-full-horizon-31667618448"
)
PRIMARY_DIGEST = (
    "3d9fe84b8e9dfcdab73971c39651093bc565230db8ac461e77a26a9a53a16da7"
)
PRIMARY_OUTCOME = "INCREMENT_9D_STOPPED"

DIAGNOSTIC_SOURCE_SHA = "4b96bee28a6abeb1080256d965be408ebd565d37"
DIAGNOSTIC_RUN = 31668258876
DIAGNOSTIC_JOB = 94347432910
DIAGNOSTIC_ARTIFACT = 9168751076
DIAGNOSTIC_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9e-admissibility-31668258876"
)
DIAGNOSTIC_DIGEST = (
    "9a5e3c500ba379370827276ce5b098ca51e81e49685b1fab5e4dabbcbf16baaa"
)
DIAGNOSTIC_OUTCOME = (
    "BOUNDED_B1_SUCCESS_WINDOW_WITH_UNIQUE_ROOT_SUPPORTED"
)

STARTING_STEP = 605
STARTING_TIME_S = 0.004054899620692231
MAXIMUM_OPERATIONAL_SOLVER_STEP = 700
OUTCOME = (
    "FINITE_COMPRESSION_INCREMENT_9F_BOUNDED_WINDOW_FULL_HORIZON_"
    "WORKING_SLICE_PASS"
)
BOUNDARY_ITERATIONS = 48

DIAGNOSTIC_REQUIRED_FILES = {
    "step605_fixed_scan.csv",
    "step605_lower_boundary_refinement.csv",
    "step605_upper_boundary_refinement.csv",
    "step605_root_topology.csv",
    "step605_hugoniot_density_search.csv",
    "step605_selected_root.csv",
    "step605_state_identity.npz",
    "authority_verification.json",
    "admissibility_correction_authority.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


class BoundedContinuationStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_diagnostic_authority(
    directory: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    if artifact_digest != DIAGNOSTIC_DIGEST:
        raise BoundedContinuationStop(
            "Increment 9E GitHub artifact digest mismatch"
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != DIAGNOSTIC_REQUIRED_FILES:
        raise BoundedContinuationStop(
            f"Increment 9E file set mismatch: {sorted(actual)}"
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != DIAGNOSTIC_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise BoundedContinuationStop(
            "Increment 9E internal manifest names mismatch"
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise BoundedContinuationStop(
                f"Increment 9E internal SHA256 mismatch for {name}"
            )
    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": DIAGNOSTIC_SOURCE_SHA,
        "outcome": DIAGNOSTIC_OUTCOME,
        "increment_9e_diagnostic_gate_passed": True,
        "increment_9e_rerun_gate_passed": True,
        "actual_continuation_supported": True,
        "solver_step_loaded": STARTING_STEP,
        "next_requested_solver_step": 606,
        "solver_time_s": STARTING_TIME_S,
        "state_unchanged": True,
        "fvm_step_606_attempted": False,
        "success_window_count": 1,
        "root_topology_sign_change_count": 1,
        "selected_root_gate_passed": True,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise BoundedContinuationStop(
                f"Increment 9E summary mismatch for {key}: "
                f"{summary.get(key)!r}"
            )
    if not bool(
        summary.get("upper_boundary_local_admissibility_correction_applied")
    ):
        raise BoundedContinuationStop(
            "Increment 9E local-admissibility correction was not applied"
        )
    if not (
        base.WEAK_COMPRESSION_CHI_LIMIT
        < float(summary["selected_root_chi"])
        <= base.DIAGNOSTIC_CHI_CAP
    ):
        raise BoundedContinuationStop(
            "Increment 9E selected root is outside fixed chi scope"
        )
    with np.load(directory / "step605_state_identity.npz") as states:
        if not np.array_equal(states["U_before"], states["U_after"]):
            raise BoundedContinuationStop(
                "Increment 9E state identity is not exact"
            )
        if int(states["solver_step_before"][0]) != STARTING_STEP:
            raise BoundedContinuationStop(
                "Increment 9E solver-step identity mismatch"
            )
    return summary


def _verify_primary_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str], dict[str, str]]:
    summary, U, last_root = inc9e._verify_parent(
        directory,
        artifact_digest=artifact_digest,
    )
    step_rows = _read_csv(directory / "finite_compression_steps.csv")
    if len(step_rows) != 71:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9D accepted-step row count is not 71",
        )
    last_step = step_rows[-1]
    if int(last_step["solver_step_count"]) != STARTING_STEP:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9D last accepted step is not 605",
        )
    if float(last_step["time_after_s"]) != STARTING_TIME_S:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9D last accepted time mismatch",
        )
    if last_step.get("increment_9d_per_step_gate_passed") != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 9D last per-step gate did not pass",
        )
    return summary, U, last_step, last_root


def _is_local_inadmissible_success(row: dict[str, Any]) -> bool:
    return bool(
        row.get("evaluation_succeeded")
        and not row.get("local_candidate_admissible")
    )


def _is_excluded(row: dict[str, Any]) -> bool:
    return bool(inc8a._is_unavailable(row) or _is_local_inadmissible_success(row))


def _success_blocks(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        if inc8a._is_success(row):
            current.append(row)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _refine_lower_excluded_boundary(
    *,
    curve: Any,
    lower_excluded: dict[str, Any],
    upper_success: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    lower = dict(lower_excluded)
    upper = dict(upper_success)
    lower_chi = float(lower["requested_chi"])
    upper_chi = float(upper["requested_chi"])
    if not _is_excluded(lower) or not inc8a._is_success(upper):
        raise inc8a.DiagnosticStop(
            "UNEXPECTED_B1_FAILURE",
            "invalid initial bounded lower-boundary bracket",
        )
    rows: list[dict[str, Any]] = []
    for iteration in range(1, BOUNDARY_ITERATIONS + 1):
        mid_chi = float(0.5 * (lower_chi + upper_chi))
        if not lower_chi < mid_chi < upper_chi:
            raise inc8a.DiagnosticStop(
                "STATE_REPRODUCTION_MISMATCH",
                "bounded lower-boundary midpoint collapsed",
            )
        mid = curve.evaluate(mid_chi, "increment_9f_lower_boundary")
        if inc8a._is_success(mid):
            classification = "ADMISSIBLE_SUCCESS"
            upper_chi = mid_chi
            upper = dict(mid)
        elif _is_excluded(mid):
            classification = (
                "EXCLUDED_B1_UNAVAILABLE"
                if inc8a._is_unavailable(mid)
                else "EXCLUDED_LOCAL_INADMISSIBLE"
            )
            lower_chi = mid_chi
            lower = dict(mid)
        else:
            raise inc8a.DiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected bounded lower outcome: {mid.get('formal_outcome')} "
                f"{mid.get('formal_message')}",
            )
        rows.append(
            {
                **mid,
                "row_role": "LOWER_ADMISSIBLE_WINDOW_BOUNDARY",
                "guard_iteration": iteration,
                "guard_classification": classification,
                "lower_excluded_chi_after": lower_chi,
                "upper_admissible_chi_after": upper_chi,
                "guard_width_after": upper_chi - lower_chi,
                "root_topology_member": False,
                "root_topology_order": None,
                "selected_root_bracket_member": False,
            }
        )
    if not _is_excluded(lower) or not inc8a._is_success(upper):
        raise inc8a.DiagnosticStop(
            "UNEXPECTED_B1_FAILURE",
            "final bounded lower-boundary invariant failed",
        )
    return lower, upper, rows


def _bounded_dynamic_root_run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U: np.ndarray,
    parent_root: dict[str, str],
):
    del b1_contract
    if dyn._active_b1_contract is None:
        raise RuntimeError("authoritative B1 contract was not bound")

    provider = CoolPropB2StateProvider()
    hook = base.A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=dyn._active_b1_contract,
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
        raise inc8a.DiagnosticStop(
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
        curve.evaluate(float(chi), "increment_9f_fixed_scan")
        for chi in base.inc5_core.CHI_NODES
    ]
    fixed_rows: list[dict[str, Any]] = []
    for row in fixed_raw:
        if inc8a._is_success(row):
            classification = "ADMISSIBLE_SUCCESS"
        elif inc8a._is_unavailable(row):
            classification = "EXCLUDED_B1_UNAVAILABLE"
        elif _is_local_inadmissible_success(row):
            classification = "EXCLUDED_LOCAL_INADMISSIBLE"
        else:
            raise inc8a.DiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected fixed-scan outcome: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
            )
        fixed_rows.append(
            {
                **row,
                "row_role": "FIXED_SCAN",
                "bounded_window_classification": classification,
                "root_topology_member": False,
                "root_topology_order": None,
                "selected_root_bracket_member": False,
            }
        )

    blocks = _success_blocks(fixed_rows)
    if not blocks:
        raise inc8a.DiagnosticStop(
            "NO_SUCCESSFUL_DOMAIN", "fixed scan has no admissible-success window"
        )
    if len(blocks) != 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS",
            f"fixed scan has {len(blocks)} admissible-success windows",
        )
    success_block = blocks[0]
    first_index = fixed_rows.index(success_block[0])
    last_index = fixed_rows.index(success_block[-1])
    leading_excluded = fixed_rows[:first_index]
    trailing_excluded = fixed_rows[last_index + 1 :]
    if not all(_is_excluded(row) for row in leading_excluded + trailing_excluded):
        raise inc8a.DiagnosticStop(
            "UNEXPECTED_B1_FAILURE",
            "non-excluded state lies outside the single success window",
        )

    fixed_brackets = base.inc5_core._brackets(success_block)
    if len(fixed_brackets) > 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS",
            "multiple fixed roots inside bounded success window",
        )

    guard_rows: list[dict[str, Any]] = []
    selected_root: dict[str, Any] = {
        "selected_root_present": False,
        "diagnostic_classification": None,
    }
    topology_source: list[dict[str, Any]]
    classification: str

    if len(fixed_brackets) == 1:
        topology_source = success_block
        raw_root = base.inc5_core._bisect_compatibility_root(
            curve="GENERAL_EOS_HUGONIOT",
            bracket=fixed_brackets[0],
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
        selected_root = {**root, "selected_root_present": True}
    elif leading_excluded:
        _, refined_success, guard_rows = _refine_lower_excluded_boundary(
            curve=curve,
            lower_excluded=leading_excluded[-1],
            upper_success=success_block[0],
        )
        topology_source = [refined_success] + [
            row
            for row in success_block
            if float(row["requested_chi"])
            > float(refined_success["requested_chi"])
        ]
        topology_source = sorted(
            topology_source, key=lambda row: float(row["requested_chi"])
        )
        refined_residual = float(
            refined_success["compatibility_residual_kg_s"]
        )
        if refined_residual < -inc8a.ROOT_TOLERANCE:
            classification = inc8a.INSIDE_UNAVAILABLE
        else:
            brackets = base.inc5_core._brackets(topology_source)
            if len(brackets) > 1:
                raise inc8a.DiagnosticStop(
                    "MULTIPLE_COMPATIBILITY_ROOTS",
                    "multiple refined bounded-window roots",
                )
            if len(brackets) == 0:
                last_residual = float(
                    topology_source[-1]["compatibility_residual_kg_s"]
                )
                classification = (
                    inc8a.CAP_REQUIRED
                    if last_residual > inc8a.ROOT_TOLERANCE
                    else inc8a.WEAK_SCOPE
                )
            else:
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
                selected_root = {**root, "selected_root_present": True}
    else:
        topology_source = success_block
        first_residual = float(
            success_block[0]["compatibility_residual_kg_s"]
        )
        last_residual = float(
            success_block[-1]["compatibility_residual_kg_s"]
        )
        if first_residual < -inc8a.ROOT_TOLERANCE:
            classification = inc8a.WEAK_SCOPE
        elif last_residual > inc8a.ROOT_TOLERANCE:
            classification = inc8a.CAP_REQUIRED
        else:
            classification = inc8a.WEAK_SCOPE

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
        residuals and all(b <= a for a, b in zip(residuals, residuals[1:]))
    )
    if not monotone:
        raise inc8a.DiagnosticStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "bounded dynamic root topology is nonmonotone",
        )
    topology_brackets = base.inc5_core._brackets(topology_rows)
    if len(topology_brackets) > 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS",
            "multiple bounded dynamic topology roots",
        )

    summary = {
        "fixed_scan_node_count": len(fixed_rows),
        "fixed_unavailable_node_count": sum(
            inc8a._is_unavailable(row) for row in fixed_rows
        ),
        "fixed_success_node_count": len(success_block),
        "fixed_sign_change_count": len(fixed_brackets),
        "fixed_success_residual_monotone_nonincreasing": True,
        "guard_front_refinement_applied": bool(guard_rows),
        "guard_front_iterations": len(guard_rows),
        "root_topology_node_count": len(topology_rows),
        "root_topology_requested_chi": [
            float(row["requested_chi"]) for row in topology_rows
        ],
        "root_topology_residuals_kg_s": residuals,
        "root_topology_monotone_nonincreasing": monotone,
        "root_topology_sign_change_count": len(topology_brackets),
        "selected_root_present": bool(
            selected_root.get("selected_root_present")
        ),
        "selected_root_chi": selected_root.get("requested_chi"),
        "selected_root_residual_kg_s": selected_root.get(
            "root_mass_residual_kg_s"
        ),
        "selected_root_gate_passed": selected_root.get(
            "root_gate_passed", False
        ),
        "bounded_success_window_count": 1,
        "leading_excluded_node_count": len(leading_excluded),
        "trailing_excluded_node_count": len(trailing_excluded),
        "trailing_local_inadmissible_node_count": sum(
            _is_local_inadmissible_success(row) for row in trailing_excluded
        ),
        "outcome": classification,
        "diagnostic_classification_complete": classification
        in inc8a.CLASSIFIED,
        "actual_continuation_supported": classification == inc8a.SUPPORTED,
    }
    selected_root["diagnostic_classification"] = classification
    return (
        summary,
        fixed_rows,
        guard_rows,
        topology_rows,
        list(curve.density_search_rows),
        selected_root,
    )


def _postprocess(
    *,
    output: Path,
    diagnostic_summary: dict[str, Any],
) -> dict[str, Any]:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    original_gate = bool(summary.pop("increment_9d_full_horizon_gate_passed"))
    fixed_rows = _read_csv(output / "hugoniot_fixed_scans.csv")
    by_step: dict[str, list[dict[str, str]]] = {}
    for row in fixed_rows:
        by_step.setdefault(row["requested_solver_step"], []).append(row)
    bounded_steps = 0
    local_inadmissible_rows = 0
    trailing_excluded_rows = 0
    for rows in by_step.values():
        classifications = [
            row.get("bounded_window_classification") for row in rows
        ]
        success_indices = [
            index
            for index, value in enumerate(classifications)
            if value == "ADMISSIBLE_SUCCESS"
        ]
        if not success_indices:
            continue
        last_success = max(success_indices)
        trailing = classifications[last_success + 1 :]
        if trailing:
            bounded_steps += 1
            trailing_excluded_rows += len(trailing)
        local_inadmissible_rows += sum(
            value == "EXCLUDED_LOCAL_INADMISSIBLE"
            for value in classifications
        )

    gate = bool(
        original_gate
        and bounded_steps > 0
        and diagnostic_summary["increment_9e_rerun_gate_passed"]
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_finite_compression_increment_9f"
            ),
            "scope": "model_review_bounded_window_full_nominal_two_l_over_c0",
            "increment_9e_source_sha": DIAGNOSTIC_SOURCE_SHA,
            "increment_9e_run": DIAGNOSTIC_RUN,
            "increment_9e_job": DIAGNOSTIC_JOB,
            "increment_9e_artifact": DIAGNOSTIC_ARTIFACT,
            "increment_9e_artifact_name": DIAGNOSTIC_ARTIFACT_NAME,
            "increment_9e_artifact_sha256": DIAGNOSTIC_DIGEST,
            "increment_9e_outcome": diagnostic_summary["outcome"],
            "increment_9e_authority_verified": True,
            "bounded_success_window_step_count": bounded_steps,
            "bounded_window_trailing_excluded_row_count": (
                trailing_excluded_rows
            ),
            "bounded_window_local_inadmissible_fixed_row_count": (
                local_inadmissible_rows
            ),
            "original_increment_9d_gate_passed": original_gate,
            "increment_9f_full_horizon_gate_passed": gate,
            "outcome": OUTCOME if gate else "INCREMENT_9F_STOPPED",
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
        "primary_step605_state": {
            "source_sha": PRIMARY_SOURCE_SHA,
            "workflow_run": PRIMARY_RUN,
            "job": PRIMARY_JOB,
            "artifact": PRIMARY_ARTIFACT,
            "artifact_name": PRIMARY_ARTIFACT_NAME,
            "artifact_sha256": PRIMARY_DIGEST,
            "verified": True,
        },
        "increment_9e_diagnostic": {
            "source_sha": DIAGNOSTIC_SOURCE_SHA,
            "workflow_run": DIAGNOSTIC_RUN,
            "job": DIAGNOSTIC_JOB,
            "artifact": DIAGNOSTIC_ARTIFACT,
            "artifact_name": DIAGNOSTIC_ARTIFACT_NAME,
            "artifact_sha256": DIAGNOSTIC_DIGEST,
            "outcome": diagnostic_summary["outcome"],
            "verified": True,
        },
        "b1_behavior_changed": False,
        "local_admissibility_rule_changed": False,
        "excluded_state_used_as_root_endpoint": False,
        "excluded_state_used_to_construct_flux": False,
        "tolerance_or_scope_changed": False,
    }
    (output / "bounded_window_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9F bounded-window full-horizon attempt\n\n"
        "The exact accepted step-605 state and the independent Increment 9E "
        "bounded-window diagnostic were verified. Before every actual "
        "`FvmSolver` update, fixed Hugoniot candidates were separated into one "
        "locally admissible B1-success window and excluded states. Excluded "
        "states, including B1-success/local-inadmissible states, remained out "
        "of root topology and applied fluxes. The final accepted step was "
        "clipped to the fixed nominal `2L/c0` target. Formal project states "
        "remain false.\n\n"
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
        "bounded_window_authority.json",
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
    parser.add_argument("--primary-artifact-dir", type=Path, required=True)
    parser.add_argument("--primary-artifact-digest", required=True)
    parser.add_argument("--diagnostic-artifact-dir", type=Path, required=True)
    parser.add_argument("--diagnostic-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    diagnostic_summary = _verify_diagnostic_authority(
        args.diagnostic_artifact_dir,
        artifact_digest=args.diagnostic_artifact_digest,
    )

    runner.inc8a._run = _bounded_dynamic_root_run
    full.PARENT_SOURCE_SHA = PRIMARY_SOURCE_SHA
    full.PARENT_RUN = PRIMARY_RUN
    full.PARENT_JOB = PRIMARY_JOB
    full.PARENT_ARTIFACT = PRIMARY_ARTIFACT
    full.PARENT_ARTIFACT_NAME = PRIMARY_ARTIFACT_NAME
    full.PARENT_DIGEST = PRIMARY_DIGEST
    full.PARENT_OUTCOME = PRIMARY_OUTCOME
    full.STARTING_STEP = STARTING_STEP
    full.STARTING_TIME_S = STARTING_TIME_S
    full.MAXIMUM_OPERATIONAL_SOLVER_STEP = MAXIMUM_OPERATIONAL_SOLVER_STEP
    full.OUTCOME = OUTCOME
    full._verify_parent = _verify_primary_parent

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
            str(args.primary_artifact_dir),
            "--parent-artifact-digest",
            args.primary_artifact_digest,
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
        raise BoundedContinuationStop(
            "full-horizon base runner did not create summary evidence"
        )
    summary = _postprocess(
        output=args.output_dir,
        diagnostic_summary=diagnostic_summary,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9f_full_horizon_gate_passed"]:
        raise SystemExit(
            "Increment 9F full-horizon gate did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
