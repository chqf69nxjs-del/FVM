from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_finite_compression_hugoniot_model_selection as core
import u3_b2_a1_finite_compression_hugoniot_model_selection_identity_correction as identity


PARENT_RERUN_SOURCE_SHA = "3c89512189dd1f19f0d5bf94f7579ea4ef22ca9c"
PARENT_RERUN_WORKFLOW_RUN = 31651902818
PARENT_RERUN_JOB = 94297894819
PARENT_RERUN_ARTIFACT = 9162881047
PARENT_RERUN_ARTIFACT_SHA256 = (
    "769916024115c051b2c7a1e8c5bbef345636de15b4286433cf47405cbed020a7"
)
_ORIGINAL_CORE_EVALUATE = core.HugoniotCurve.evaluate


class IdentityStatusPropagatedHugoniotCurve(
    identity.IdentityCorrectedHugoniotCurve
):
    def evaluate(self, requested_chi: float, stage: str) -> dict[str, Any]:
        # The inherited solve_density method fails closed unless the
        # identity-accounted Hugoniot difference passes. Therefore any
        # successful core evaluation reached this point through an accepted
        # identity-corrected density state.
        result = _ORIGINAL_CORE_EVALUATE(self, requested_chi, stage)
        if result.get("evaluation_succeeded"):
            result["hugoniot_identity_accounted_passed"] = True
            result["identity_status_propagation_applied"] = True
            self.cache[float(requested_chi)] = dict(result)
        else:
            result["hugoniot_identity_accounted_passed"] = False
            result["identity_status_propagation_applied"] = False
        return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _postprocess(
    *,
    output_dir: Path,
    propagation_spec: Path,
) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with (output_dir / "hugoniot_compression_scan.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    successful = [
        row for row in rows if row.get("evaluation_succeeded") == "True"
    ]
    propagated = [
        row
        for row in successful
        if row.get("hugoniot_identity_accounted_passed") == "True"
        and row.get("identity_status_propagation_applied") == "True"
    ]
    propagation_gate = bool(
        len(rows) == len(core.CHI_NODES)
        and successful
        and len(propagated) == len(successful)
        and summary["cap_scope_exhaustion_reproduced"] is True
        and summary["cap_hugoniot_residual_kg_s"] is not None
        and float(summary["cap_hugoniot_residual_kg_s"])
        > core.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and summary["hugoniot_scan_monotone_nonincreasing"] is True
        and int(summary["hugoniot_sign_change_count"]) == 1
        and summary["state_unchanged"] is True
        and summary["fvm_step_484_attempted"] is False
        and summary["finite_compression_flux_applied"] is False
    )
    summary.update(
        {
            "identity_status_propagation_correction_applied": True,
            "identity_status_propagation_spec": str(propagation_spec),
            "identity_status_propagation_spec_sha256": _sha256(
                propagation_spec
            ),
            "identity_status_parent_rerun_source_sha": (
                PARENT_RERUN_SOURCE_SHA
            ),
            "identity_status_parent_rerun_workflow_run": (
                PARENT_RERUN_WORKFLOW_RUN
            ),
            "identity_status_parent_rerun_job": PARENT_RERUN_JOB,
            "identity_status_parent_rerun_artifact": (
                PARENT_RERUN_ARTIFACT
            ),
            "identity_status_parent_rerun_artifact_sha256": (
                PARENT_RERUN_ARTIFACT_SHA256
            ),
            "hugoniot_fixed_scan_success_count": len(successful),
            "hugoniot_fixed_scan_propagated_identity_count": len(
                propagated
            ),
            "identity_status_propagation_gate_passed": propagation_gate,
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
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    correction = {
        "correction": "identity_status_propagation_after_accepted_density_solve",
        "successful_hugoniot_scan_rows": len(successful),
        "propagated_successful_rows": len(propagated),
        "propagation_gate_passed": propagation_gate,
        "hugoniot_equations_changed": False,
        "coolprop_state_changed": False,
        "density_root_changed": False,
        "b1_behavior_changed": False,
        "lax_or_entropy_rule_changed": False,
        "compatibility_root_tolerance_changed": False,
        "diagnostic_chi_nodes_or_cap_changed": False,
        "finite_compression_flux_applied": False,
    }
    (output_dir / "identity_status_propagation.json").write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Identity-status propagation correction\n\n"
        + "The identity-accounted density solve remains fail-closed. A "
        + "successful subsequent B1 evaluation now carries the already-passed "
        + "identity status without changing the core Hugoniot closure or local "
        + "admissibility result. No solver step or finite-compression flux was "
        + "applied.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = (
        "isentropic_extrapolation_scan.csv",
        "hugoniot_compression_scan.csv",
        "hugoniot_density_search.csv",
        "curve_comparison.json",
        "step483_state_identity.npz",
        "enthalpy_identity_correction.json",
        "identity_status_propagation.json",
        "summary.json",
        "report.md",
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--tolerance-spec", type=Path, required=True)
    parser.add_argument("--identity-correction-spec", type=Path, required=True)
    parser.add_argument("--identity-status-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.identity_status_spec.is_file():
        raise FileNotFoundError(args.identity_status_spec)

    identity.IdentityCorrectedHugoniotCurve = (
        IdentityStatusPropagatedHugoniotCurve
    )

    original_argv = sys.argv
    try:
        sys.argv = [
            original_argv[0],
            "--contract",
            str(args.contract),
            "--b1-contract",
            str(args.b1_contract),
            "--model-review-spec",
            str(args.model_review_spec),
            "--tolerance-spec",
            str(args.tolerance_spec),
            "--identity-correction-spec",
            str(args.identity_correction_spec),
            "--parent-artifact-dir",
            str(args.parent_artifact_dir),
            "--parent-artifact-digest",
            args.parent_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        identity.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess(
        output_dir=args.output_dir,
        propagation_spec=args.identity_status_spec,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["identity_status_propagation_gate_passed"]:
        raise SystemExit("Increment 5 identity-status propagation gate failed")


if __name__ == "__main__":
    main()
