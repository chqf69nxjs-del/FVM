from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_step637_zero_flow_endpoint_diagnostic_v2 as increment_9j
import u3_b2_a1_finite_compression_step637_zero_flow_endpoint_diagnostic_v3 as authority_correction


FAILED_SCHEMA_RUN = 31675938522
FAILED_SCHEMA_JOB = 94370412069
FAILED_SCHEMA_SOURCE_SHA = "6b554899b7b7d1147de3bef99a952f7a9ca23b3b"
FAILED_SCHEMA_EXCEPTION = "KeyError: 'stagnation_pressure_pa'"

B1_FACE_SOURCE = "B1_FACE_RECONSTRUCTION"
CANDIDATE_SOURCE = "CANDIDATE_CONSERVED_COOLPROP_RECONSTRUCTION"
ENDPOINT_STAGES = {
    "increment_9j_broad_endpoint_scan",
    "increment_9j_stagnation_pressure_margin_pa_endpoint",
    "increment_9j_velocity_m_s_endpoint",
}
CORRECTION_FILE = "broad_candidate_stagnation_schema_correction.json"

BASE_OUTPUT_FILES = {
    "step637_fixed_scan.csv",
    "step637_ultrafine_scan.csv",
    "step637_broad_endpoint_scan.csv",
    "step637_lower_boundary_refinement.csv",
    "step637_upper_boundary_refinement.csv",
    "step637_root_topology.csv",
    "step637_selected_root.csv",
    "step637_stagnation_pressure_endpoint_bisection.csv",
    "step637_velocity_endpoint_bisection.csv",
    "step637_stagnation_pressure_endpoint.csv",
    "step637_velocity_endpoint.csv",
    "step637_state_identity.npz",
    "authority_verification.json",
    "summary.json",
    "report.md",
}

_ORIGINAL_EVALUATE = (
    increment_9j.base.inc5_final.IdentityStatusPropagatedHugoniotCurve.evaluate
)
_ENDPOINT_EVENTS: list[dict[str, Any]] = []


class BroadCandidateStagnationSchemaStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) == 1 and rows[0].get("no_rows_recorded") == "True":
        return []
    return rows


def _finite_float(row: dict[str, Any], key: str) -> float:
    if key not in row or row[key] is None:
        raise BroadCandidateStagnationSchemaStop(
            f"missing candidate thermodynamic field {key!r}"
        )
    value = float(row[key])
    if not math.isfinite(value):
        raise BroadCandidateStagnationSchemaStop(
            f"nonfinite candidate thermodynamic field {key!r}"
        )
    return value


def _invariant_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "evaluation_succeeded",
            "formal_outcome",
            "formal_message",
            "local_candidate_admissible",
            "compatibility_residual_kg_s",
            "pressure_pa",
            "density_kg_m3",
            "internal_energy_J_kg",
            "enthalpy_J_kg",
            "entropy_J_kg_K",
            "velocity_m_s",
            "mach",
            "phase",
        )
    }


def _endpoint_schema_evaluate(
    self: Any,
    requested_chi: float,
    stage: str,
) -> dict[str, Any]:
    row = dict(_ORIGINAL_EVALUATE(self, requested_chi, stage))
    if stage not in ENDPOINT_STAGES:
        return row

    before = _invariant_snapshot(row)
    category = increment_9j._classification(row)
    existing_p0 = row.get("stagnation_pressure_pa")
    schema_completed = False

    if existing_p0 is not None:
        if not bool(row.get("evaluation_succeeded")):
            raise BroadCandidateStagnationSchemaStop(
                "an excluded B1 candidate unexpectedly contains a successful-face "
                "stagnation-pressure field"
            )
        p0 = float(existing_p0)
        if not math.isfinite(p0) or p0 <= 0.0:
            raise BroadCandidateStagnationSchemaStop(
                "successful-face stagnation pressure is nonfinite or nonpositive"
            )
        source = B1_FACE_SOURCE
        row["candidate_stagnation_pressure_pa"] = p0
        row["endpoint_stagnation_temperature_K"] = None
        row["endpoint_stagnation_enthalpy_J_kg"] = None
        row["endpoint_stagnation_entropy_J_kg_K"] = None
        row["endpoint_stagnation_enthalpy_round_trip_residual_J_kg"] = None
        row["endpoint_stagnation_entropy_round_trip_residual_J_kg_K"] = None
        row["endpoint_static_pressure_reconstruction_residual_pa"] = None
        row["endpoint_static_density_reconstruction_residual_kg_m3"] = None
        row["endpoint_static_internal_energy_reconstruction_residual_J_kg"] = None
        row["endpoint_static_velocity_reconstruction_residual_m_s"] = None
        row["endpoint_reconstructed_phase"] = None
        row["endpoint_candidate_conserved_rho_xv_exact_zero"] = True
    else:
        if category != "EXCLUDED_B1_UNAVAILABLE":
            raise BroadCandidateStagnationSchemaStop(
                "only an expected EXCLUDED_B1_UNAVAILABLE candidate may receive "
                "diagnostic stagnation schema completion"
            )

        rho = _finite_float(row, "density_kg_m3")
        velocity = _finite_float(row, "velocity_m_s")
        internal = _finite_float(row, "internal_energy_J_kg")
        pressure = _finite_float(row, "pressure_pa")
        if rho <= 0.0 or internal <= 0.0:
            raise BroadCandidateStagnationSchemaStop(
                "candidate density/internal energy is nonpositive"
            )

        conserved = np.asarray(
            [
                rho,
                rho * velocity,
                rho * (internal + 0.5 * velocity * velocity),
                0.0,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(conserved)) or conserved[3] != 0.0:
            raise BroadCandidateStagnationSchemaStop(
                "diagnostic candidate conserved state is invalid"
            )

        provider = getattr(self, "_increment_9j_endpoint_state_provider", None)
        if provider is None:
            provider = increment_9j.CoolPropB2StateProvider()
            setattr(self, "_increment_9j_endpoint_state_provider", provider)
        try:
            reconstruction = provider.reconstruct_from_conserved(conserved)
        except Exception as exc:
            raise BroadCandidateStagnationSchemaStop(
                "candidate conserved-state stagnation reconstruction failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        reconstructed_phase = increment_9j.normalize_phase(
            str(reconstruction.static.phase)
        )
        original_phase = increment_9j.normalize_phase(str(row.get("phase")))
        if (
            reconstructed_phase not in self.allowed_phases
            or original_phase not in self.allowed_phases
            or reconstructed_phase != original_phase
        ):
            raise BroadCandidateStagnationSchemaStop(
                "candidate stagnation reconstruction phase mismatch"
            )

        tolerances = self.hook.contract["acceptance_tolerances"]
        h_residual = float(reconstruction.enthalpy_round_trip_residual_J_kg)
        s_residual = float(reconstruction.entropy_round_trip_residual_J_kg_K)
        h_tolerance = float(
            tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
        )
        s_tolerance = float(
            tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
        )
        if abs(h_residual) > h_tolerance or abs(s_residual) > s_tolerance:
            raise BroadCandidateStagnationSchemaStop(
                "candidate stagnation reconstruction exceeds the locked B2 "
                "round-trip tolerance"
            )

        p0 = float(reconstruction.stagnation_pressure_pa)
        if not math.isfinite(p0) or p0 <= 0.0:
            raise BroadCandidateStagnationSchemaStop(
                "diagnostic candidate stagnation pressure is nonfinite or "
                "nonpositive"
            )
        source = CANDIDATE_SOURCE
        schema_completed = True
        row.update(
            {
                "stagnation_pressure_pa": p0,
                "candidate_stagnation_pressure_pa": p0,
                "endpoint_stagnation_temperature_K": float(
                    reconstruction.stagnation_temperature_K
                ),
                "endpoint_stagnation_enthalpy_J_kg": float(
                    reconstruction.stagnation_enthalpy_J_kg
                ),
                "endpoint_stagnation_entropy_J_kg_K": float(
                    reconstruction.stagnation_entropy_J_kg_K
                ),
                "endpoint_stagnation_enthalpy_round_trip_residual_J_kg": (
                    h_residual
                ),
                "endpoint_stagnation_entropy_round_trip_residual_J_kg_K": (
                    s_residual
                ),
                "endpoint_static_pressure_reconstruction_residual_pa": float(
                    reconstruction.static.pressure_pa - pressure
                ),
                "endpoint_static_density_reconstruction_residual_kg_m3": float(
                    reconstruction.static.density_kg_m3 - rho
                ),
                "endpoint_static_internal_energy_reconstruction_residual_J_kg": (
                    float(reconstruction.static.internal_energy_J_kg - internal)
                ),
                "endpoint_static_velocity_reconstruction_residual_m_s": float(
                    reconstruction.static.velocity_m_s - velocity
                ),
                "endpoint_reconstructed_phase": str(reconstruction.static.phase),
                "endpoint_candidate_conserved_rho_xv_exact_zero": True,
            }
        )

    back_pressure = float(self.hook.adapter.back_pressure_pa)
    row.update(
        {
            "endpoint_stagnation_schema_completed": schema_completed,
            "endpoint_stagnation_pressure_source": source,
            "endpoint_scalar_diagnostic_only": True,
            "endpoint_stagnation_pressure_margin_pa": p0 - back_pressure,
            "excluded_candidate_used_as_compatibility_root_endpoint": False,
            "excluded_candidate_used_to_construct_flux": False,
        }
    )

    after = _invariant_snapshot(row)
    if after != before:
        raise BroadCandidateStagnationSchemaStop(
            "schema completion altered a frozen candidate outcome/admissibility/"
            "thermodynamic field"
        )

    _ENDPOINT_EVENTS.append(
        {
            "evaluation_stage": stage,
            "requested_chi": float(requested_chi),
            "candidate_classification": category,
            "formal_outcome": row.get("formal_outcome"),
            "evaluation_succeeded": bool(row.get("evaluation_succeeded")),
            "local_candidate_admissible": bool(
                row.get("local_candidate_admissible")
            ),
            "compatibility_residual_kg_s": row.get(
                "compatibility_residual_kg_s"
            ),
            "stagnation_pressure_pa": p0,
            "stagnation_pressure_source": source,
            "schema_completed": schema_completed,
            "invariant_snapshot_preserved": True,
            "excluded_candidate_used_as_compatibility_root_endpoint": False,
            "excluded_candidate_used_to_construct_flux": False,
        }
    )
    return row


def _install_patch() -> None:
    curve = increment_9j.base.inc5_final.IdentityStatusPropagatedHugoniotCurve
    if curve.evaluate is not _ORIGINAL_EVALUATE:
        raise BroadCandidateStagnationSchemaStop(
            "Increment 9J Hugoniot evaluate method changed before schema correction"
        )
    curve.evaluate = _endpoint_schema_evaluate


def _restore_patch() -> None:
    increment_9j.base.inc5_final.IdentityStatusPropagatedHugoniotCurve.evaluate = (
        _ORIGINAL_EVALUATE
    )


def _postprocess(
    *,
    output_dir: Path,
    contract_path: Path,
    model_review_spec: Path,
    authority_correction_spec: Path,
    schema_correction_spec: Path,
) -> dict[str, Any]:
    expected_before = BASE_OUTPUT_FILES | {"artifact_sha256.txt"}
    actual_before = {path.name for path in output_dir.iterdir() if path.is_file()}
    if actual_before != expected_before:
        raise BroadCandidateStagnationSchemaStop(
            f"unexpected pre-correction evidence file set: {sorted(actual_before)}"
        )

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    tolerances = contract["acceptance_tolerances"]
    h_tolerance = float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    )
    s_tolerance = float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    )

    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    broad_rows = _read_csv(output_dir / "step637_broad_endpoint_scan.csv")
    root_rows = _read_csv(output_dir / "step637_root_topology.csv")
    selected_root_rows = _read_csv(output_dir / "step637_selected_root.csv")

    broad_sources = Counter(
        row.get("endpoint_stagnation_pressure_source") for row in broad_rows
    )
    broad_classifications = Counter(
        row.get("candidate_classification") for row in broad_rows
    )
    completed_rows = [
        row for row in broad_rows if _truth(row.get("endpoint_stagnation_schema_completed"))
    ]
    retained_face_rows = [
        row
        for row in broad_rows
        if row.get("endpoint_stagnation_pressure_source") == B1_FACE_SOURCE
    ]

    broad_scalar_complete = bool(
        len(broad_rows) == increment_9j.BROAD_NODE_COUNT
        and all(
            math.isfinite(float(row["stagnation_pressure_pa"]))
            and float(row["stagnation_pressure_pa"]) > 0.0
            and math.isfinite(float(row["stagnation_pressure_margin_pa"]))
            and row.get("endpoint_stagnation_pressure_source")
            in {B1_FACE_SOURCE, CANDIDATE_SOURCE}
            for row in broad_rows
        )
    )
    completed_rows_valid = bool(
        completed_rows
        and all(
            row.get("endpoint_stagnation_pressure_source") == CANDIDATE_SOURCE
            and row.get("candidate_classification") == "EXCLUDED_B1_UNAVAILABLE"
            and not _truth(row.get("evaluation_succeeded"))
            and not _truth(row.get("local_candidate_admissible"))
            and row.get("compatibility_residual_kg_s") in {None, ""}
            and _truth(row.get("endpoint_candidate_conserved_rho_xv_exact_zero"))
            and abs(
                float(
                    row[
                        "endpoint_stagnation_enthalpy_round_trip_residual_J_kg"
                    ]
                )
            )
            <= h_tolerance
            and abs(
                float(
                    row[
                        "endpoint_stagnation_entropy_round_trip_residual_J_kg_K"
                    ]
                )
            )
            <= s_tolerance
            for row in completed_rows
        )
    )
    retained_face_rows_valid = bool(
        retained_face_rows
        and all(
            not _truth(row.get("endpoint_stagnation_schema_completed"))
            and _truth(row.get("evaluation_succeeded"))
            and row.get("candidate_classification")
            in {"ADMISSIBLE_SUCCESS", "EXCLUDED_LOCAL_INADMISSIBLE"}
            for row in retained_face_rows
        )
    )

    root_topology_admissible_only = all(
        _truth(row.get("evaluation_succeeded"))
        and _truth(row.get("local_candidate_admissible"))
        and row.get("compatibility_residual_kg_s") not in {None, ""}
        and not _truth(row.get("endpoint_stagnation_schema_completed"))
        for row in root_rows
    )
    selected_root_admissible_only = all(
        _truth(row.get("evaluation_succeeded"))
        and _truth(row.get("local_candidate_admissible"))
        and _truth(row.get("root_gate_passed"))
        and not _truth(row.get("endpoint_stagnation_schema_completed"))
        for row in selected_root_rows
    )

    event_stage_counts = Counter(
        str(row["evaluation_stage"]) for row in _ENDPOINT_EVENTS
    )
    event_completion_stage_counts = Counter(
        str(row["evaluation_stage"])
        for row in _ENDPOINT_EVENTS
        if bool(row["schema_completed"])
    )
    event_source_counts = Counter(
        str(row["stagnation_pressure_source"]) for row in _ENDPOINT_EVENTS
    )
    events_preserved = bool(
        _ENDPOINT_EVENTS
        and all(
            bool(row["invariant_snapshot_preserved"])
            and row["excluded_candidate_used_as_compatibility_root_endpoint"]
            is False
            and row["excluded_candidate_used_to_construct_flux"] is False
            for row in _ENDPOINT_EVENTS
        )
    )

    formal_false = (
        "finite_compression_branch_approved",
        "multi_step_finite_compression_continuation_authorized",
        "full_two_l_over_c0_passed",
        "formal_state_promoted",
        "u3_b2_finite_pipe_execution_complete",
        "single_phase_finite_pipe_coupling_verified",
        "u3_b2_verification_benchmark_accepted",
        "physical_validation",
        "design_use_acceptance",
        "production_hem_activation_approved",
    )
    formal_boundary_preserved = all(summary[name] is False for name in formal_false)

    correction_gate = bool(
        broad_scalar_complete
        and completed_rows_valid
        and retained_face_rows_valid
        and root_topology_admissible_only
        and selected_root_admissible_only
        and events_preserved
        and summary["state_unchanged"] is True
        and summary["fvm_step_638_attempted"] is False
        and formal_boundary_preserved
    )

    correction = {
        "correction": "increment_9j_broad_candidate_stagnation_schema_completion",
        "failed_workflow_run": FAILED_SCHEMA_RUN,
        "failed_job": FAILED_SCHEMA_JOB,
        "failed_source_git_sha": FAILED_SCHEMA_SOURCE_SHA,
        "failed_exception": FAILED_SCHEMA_EXCEPTION,
        "original_increment_9j_spec": str(model_review_spec),
        "original_increment_9j_spec_sha256": _sha256(model_review_spec),
        "authority_correction_spec": str(authority_correction_spec),
        "authority_correction_spec_sha256": _sha256(authority_correction_spec),
        "schema_correction_spec": str(schema_correction_spec),
        "schema_correction_spec_sha256": _sha256(schema_correction_spec),
        "broad_node_count": len(broad_rows),
        "broad_source_counts": dict(sorted(broad_sources.items())),
        "broad_candidate_classification_counts": dict(
            sorted(broad_classifications.items())
        ),
        "broad_schema_completed_count": len(completed_rows),
        "broad_b1_face_stagnation_count": len(retained_face_rows),
        "endpoint_event_count": len(_ENDPOINT_EVENTS),
        "endpoint_event_stage_counts": dict(sorted(event_stage_counts.items())),
        "endpoint_completion_stage_counts": dict(
            sorted(event_completion_stage_counts.items())
        ),
        "endpoint_event_source_counts": dict(sorted(event_source_counts.items())),
        "maximum_completed_enthalpy_round_trip_residual_J_kg": max(
            abs(
                float(
                    row[
                        "endpoint_stagnation_enthalpy_round_trip_residual_J_kg"
                    ]
                )
            )
            for row in completed_rows
        ),
        "maximum_completed_entropy_round_trip_residual_J_kg_K": max(
            abs(
                float(
                    row[
                        "endpoint_stagnation_entropy_round_trip_residual_J_kg_K"
                    ]
                )
            )
            for row in completed_rows
        ),
        "locked_enthalpy_round_trip_tolerance_J_kg": h_tolerance,
        "locked_entropy_round_trip_tolerance_J_kg_K": s_tolerance,
        "broad_scalar_schema_complete": broad_scalar_complete,
        "completed_rows_retain_b1_unavailable_status": completed_rows_valid,
        "successful_face_stagnation_fields_retained": retained_face_rows_valid,
        "candidate_outcome_and_admissibility_fields_unchanged": events_preserved,
        "compatibility_root_topology_uses_only_admissible_success": (
            root_topology_admissible_only
        ),
        "selected_root_uses_only_admissible_success": (
            selected_root_admissible_only
        ),
        "excluded_candidate_used_only_for_scalar_topology": bool(completed_rows),
        "failed_b1_state_used_as_compatibility_root_endpoint": False,
        "failed_b1_state_used_to_construct_flux": False,
        "fvm_step_638_attempted": summary["fvm_step_638_attempted"],
        "state_unchanged": summary["state_unchanged"],
        "formal_boundary_preserved": formal_boundary_preserved,
        "hugoniot_equations_changed": False,
        "b1_behavior_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "root_tolerance_changed": False,
        "velocity_tolerance_changed": False,
        "chi_scope_changed": False,
        "scan_node_counts_changed": False,
        "correction_gate_passed": correction_gate,
    }

    correction_path = output_dir / CORRECTION_FILE
    correction_path.write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary.update(
        {
            "broad_candidate_stagnation_schema_correction_applied": True,
            "broad_candidate_stagnation_schema_correction_spec": str(
                schema_correction_spec
            ),
            "broad_candidate_stagnation_schema_correction_spec_sha256": (
                _sha256(schema_correction_spec)
            ),
            "failed_schema_workflow_run": FAILED_SCHEMA_RUN,
            "failed_schema_job": FAILED_SCHEMA_JOB,
            "broad_candidate_stagnation_schema_completed_count": len(
                completed_rows
            ),
            "broad_b1_face_stagnation_count": len(retained_face_rows),
            "compatibility_root_topology_uses_only_admissible_success": (
                root_topology_admissible_only
            ),
            "failed_b1_state_used_as_compatibility_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
            "excluded_candidate_used_only_for_scalar_topology": bool(
                completed_rows
            ),
            "broad_candidate_stagnation_schema_correction_gate_passed": (
                correction_gate
            ),
        }
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Broad-candidate stagnation schema correction\n\n"
        + "Expected B1-unavailable Hugoniot candidates retained their original "
        + "failure and inadmissibility status. Only the scalar endpoint "
        + "diagnostic received candidate stagnation pressure reconstructed from "
        + "the unchanged candidate conserved state through the locked "
        + "CoolPropB2StateProvider path. No excluded candidate became a "
        + "compatibility root, flux state, or solver-step authority.\n\n"
        + "```json\n"
        + json.dumps(correction, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    manifest_names = sorted(BASE_OUTPUT_FILES | {CORRECTION_FILE})
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output_dir / name)}  {name}\n" for name in manifest_names
        ),
        encoding="utf-8",
    )

    final_files = {path.name for path in output_dir.iterdir() if path.is_file()}
    expected_final = BASE_OUTPUT_FILES | {
        CORRECTION_FILE,
        "artifact_sha256.txt",
    }
    if final_files != expected_final:
        raise BroadCandidateStagnationSchemaStop(
            f"unexpected final evidence file set: {sorted(final_files)}"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--authority-correction-spec", type=Path, required=True)
    parser.add_argument("--schema-correction-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.contract,
        args.b1_contract,
        args.model_review_spec,
        args.authority_correction_spec,
        args.schema_correction_spec,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    if authority_correction.AUTHORITATIVE_PARENT_SOURCE_SHA != (
        "c89a992d69c2985fc081fe3750c5b27136d3941e"
    ) or authority_correction.AUTHORITATIVE_EXPECTED_TIME_S != (
        0.004269583083221582
    ):
        raise BroadCandidateStagnationSchemaStop(
            "Increment 9J authority correction constants changed"
        )

    _ENDPOINT_EVENTS.clear()
    _install_patch()
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
            "--parent-artifact-dir",
            str(args.parent_artifact_dir),
            "--parent-artifact-digest",
            args.parent_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        authority_correction.main()
    finally:
        sys.argv = original_argv
        _restore_patch()

    summary = _postprocess(
        output_dir=args.output_dir,
        contract_path=args.contract,
        model_review_spec=args.model_review_spec,
        authority_correction_spec=args.authority_correction_spec,
        schema_correction_spec=args.schema_correction_spec,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["broad_candidate_stagnation_schema_correction_gate_passed"]:
        raise SystemExit(
            "Increment 9J broad-candidate stagnation schema correction gate failed"
        )


if __name__ == "__main__":
    main()
