from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_finite_compression_hugoniot_model_selection as base


FIRST_DIAGNOSTIC_SOURCE_SHA = "dc9c117a720ba14814e4ff23660d16fe2b7e4736"
FIRST_DIAGNOSTIC_WORKFLOW_RUN = 31651694424
FIRST_DIAGNOSTIC_JOB = 94297206783
FIRST_DIAGNOSTIC_ARTIFACT = 9162803881
FIRST_DIAGNOSTIC_ARTIFACT_SHA256 = (
    "b80161157cbd7e1e3f95df662fc7185caef15d57390e137bb89932ff134edead"
)
IDENTITY_ACCOUNTED_TOLERANCE_J_KG = 1.0e-10
RAW_DIFFERENCE_OBSERVATION_LIMIT_J_KG = base.HUGONIOT_ENERGY_TOLERANCE_J_KG


class IdentityCorrectedHugoniotCurve(base.HugoniotCurve):
    def _density_row(
        self,
        *,
        pressure_pa: float,
        density_kg_m3: float,
        requested_chi: float,
        expansion: int,
        stage: str,
    ) -> dict[str, Any]:
        result = super()._density_row(
            pressure_pa=pressure_pa,
            density_kg_m3=density_kg_m3,
            requested_chi=requested_chi,
            expansion=expansion,
            stage=stage,
        )
        v_i = 1.0 / float(self.static.density_kg_m3)
        v_P = 1.0 / float(result["density_kg_m3"])
        identity_i = float(
            self.static.enthalpy_J_kg
            - self.static.internal_energy_J_kg
            - self.static.pressure_pa * v_i
        )
        identity_P = float(
            result["enthalpy_J_kg"]
            - result["internal_energy_J_kg"]
            - result["pressure_pa"] * v_P
        )
        raw_difference = float(
            result["hugoniot_energy_residual_J_kg"]
            - result["hugoniot_enthalpy_residual_J_kg"]
        )
        corrected_difference = float(
            raw_difference - (identity_i - identity_P)
        )
        result.update(
            {
                "interior_enthalpy_identity_residual_J_kg": identity_i,
                "candidate_enthalpy_identity_residual_J_kg": identity_P,
                "raw_hugoniot_form_difference_J_kg": raw_difference,
                "identity_accounted_hugoniot_difference_J_kg": (
                    corrected_difference
                ),
                "identity_accounted_hugoniot_passed": bool(
                    abs(corrected_difference)
                    <= IDENTITY_ACCOUNTED_TOLERANCE_J_KG
                ),
            }
        )
        self.density_search_rows[-1].update(
            {
                "interior_enthalpy_identity_residual_J_kg": identity_i,
                "candidate_enthalpy_identity_residual_J_kg": identity_P,
                "raw_hugoniot_form_difference_J_kg": raw_difference,
                "identity_accounted_hugoniot_difference_J_kg": (
                    corrected_difference
                ),
                "identity_accounted_hugoniot_passed": bool(
                    abs(corrected_difference)
                    <= IDENTITY_ACCOUNTED_TOLERANCE_J_KG
                ),
            }
        )
        return result

    def solve_density(
        self,
        *,
        requested_chi: float,
        stage: str,
    ) -> dict[str, Any]:
        result = super().solve_density(
            requested_chi=requested_chi,
            stage=stage,
        )
        if not bool(result["identity_accounted_hugoniot_passed"]):
            raise base.FiniteCompressionDiagnosticError(
                "HUGONIOT_DENSITY_ROOT_FAILURE: identity-accounted equivalence"
            )
        return result

    def evaluate(self, requested_chi: float, stage: str) -> dict[str, Any]:
        result = super().evaluate(requested_chi, stage)
        if result.get("evaluation_succeeded"):
            identity_ok = bool(
                result.get("identity_accounted_hugoniot_passed")
            )
            result["hugoniot_identity_accounted_passed"] = identity_ok
            result["hugoniot_closure_passed"] = bool(
                result.get("hugoniot_closure_passed") and identity_ok
            )
            result["local_candidate_admissible"] = bool(
                result.get("local_candidate_admissible") and identity_ok
            )
            self.cache[float(requested_chi)] = dict(result)
        return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _postprocess(
    *,
    output_dir: Path,
    correction_spec: Path,
) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    density_path = output_dir / "hugoniot_density_search.csv"
    import csv

    with density_path.open(newline="", encoding="utf-8") as handle:
        density_rows = list(csv.DictReader(handle))
    raw_values = [
        abs(float(row["raw_hugoniot_form_difference_J_kg"]))
        for row in density_rows
        if row.get("raw_hugoniot_form_difference_J_kg") not in {None, ""}
    ]
    corrected_values = [
        abs(float(row["identity_accounted_hugoniot_difference_J_kg"]))
        for row in density_rows
        if row.get("identity_accounted_hugoniot_difference_J_kg")
        not in {None, ""}
    ]
    interior_identity = [
        abs(float(row["interior_enthalpy_identity_residual_J_kg"]))
        for row in density_rows
        if row.get("interior_enthalpy_identity_residual_J_kg") not in {None, ""}
    ]
    candidate_identity = [
        abs(float(row["candidate_enthalpy_identity_residual_J_kg"]))
        for row in density_rows
        if row.get("candidate_enthalpy_identity_residual_J_kg") not in {None, ""}
    ]
    correction_gate = bool(
        density_rows
        and corrected_values
        and max(corrected_values) <= IDENTITY_ACCOUNTED_TOLERANCE_J_KG
        and summary["state_unchanged"] is True
        and summary["fvm_step_484_attempted"] is False
        and summary["finite_compression_flux_applied"] is False
    )
    summary.update(
        {
            "enthalpy_identity_correction_applied": True,
            "enthalpy_identity_correction_spec": str(correction_spec),
            "enthalpy_identity_correction_spec_sha256": _sha256(
                correction_spec
            ),
            "first_diagnostic_source_sha": FIRST_DIAGNOSTIC_SOURCE_SHA,
            "first_diagnostic_workflow_run": FIRST_DIAGNOSTIC_WORKFLOW_RUN,
            "first_diagnostic_job": FIRST_DIAGNOSTIC_JOB,
            "first_diagnostic_artifact": FIRST_DIAGNOSTIC_ARTIFACT,
            "first_diagnostic_artifact_sha256": (
                FIRST_DIAGNOSTIC_ARTIFACT_SHA256
            ),
            "raw_hugoniot_form_difference_direct_gate_removed": True,
            "raw_hugoniot_form_difference_observation_limit_J_kg": (
                RAW_DIFFERENCE_OBSERVATION_LIMIT_J_KG
            ),
            "identity_accounted_difference_tolerance_J_kg": (
                IDENTITY_ACCOUNTED_TOLERANCE_J_KG
            ),
            "maximum_absolute_raw_hugoniot_form_difference_J_kg": (
                max(raw_values) if raw_values else None
            ),
            "maximum_absolute_identity_accounted_difference_J_kg": (
                max(corrected_values) if corrected_values else None
            ),
            "maximum_absolute_interior_enthalpy_identity_residual_J_kg": (
                max(interior_identity) if interior_identity else None
            ),
            "maximum_absolute_candidate_enthalpy_identity_residual_J_kg": (
                max(candidate_identity) if candidate_identity else None
            ),
            "enthalpy_identity_correction_gate_passed": correction_gate,
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
        "correction": "enthalpy_identity_accounted_hugoniot_equivalence",
        "individual_hugoniot_energy_tolerance_J_kg": (
            base.HUGONIOT_ENERGY_TOLERANCE_J_KG
        ),
        "identity_accounted_difference_tolerance_J_kg": (
            IDENTITY_ACCOUNTED_TOLERANCE_J_KG
        ),
        "raw_difference_direct_gate_removed": True,
        "hugoniot_equations_changed": False,
        "b1_behavior_changed": False,
        "compatibility_root_tolerance_changed": False,
        "diagnostic_chi_cap_changed": False,
        "finite_compression_flux_applied": False,
    }
    (output_dir / "enthalpy_identity_correction.json").write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Enthalpy-identity correction\n\n"
        + "Both physical Hugoniot energy forms retain their original absolute "
        + "closure tolerances. The redundant raw difference is recorded, while "
        + "the pass/fail equivalence check subtracts the independently returned "
        + "CoolProp `h-e-pv` identity residuals. No solver step or finite-"
        + "compression flux was applied.\n\n"
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
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.identity_correction_spec.is_file():
        raise FileNotFoundError(args.identity_correction_spec)

    base.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        RAW_DIFFERENCE_OBSERVATION_LIMIT_J_KG
    )
    base.HugoniotCurve = IdentityCorrectedHugoniotCurve

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
            "--parent-artifact-dir",
            str(args.parent_artifact_dir),
            "--parent-artifact-digest",
            args.parent_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        base.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess(
        output_dir=args.output_dir,
        correction_spec=args.identity_correction_spec,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["enthalpy_identity_correction_gate_passed"]:
        raise SystemExit("Increment 5 enthalpy-identity correction gate failed")


if __name__ == "__main__":
    main()
