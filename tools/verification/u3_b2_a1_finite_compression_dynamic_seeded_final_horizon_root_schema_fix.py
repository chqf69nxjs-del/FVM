from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_finite_compression_dynamic_seeded_final_horizon as runner


CORRECTION_PARENT_SOURCE_SHA = "825210c4b11850278c44d094486abbd89b170996"
CORRECTION_PARENT_RUN = 31670007778
CORRECTION_PARENT_JOB = 94352512260
CORRECTION_SCOPE = "map_verified_selected_root_pressure_pa_to_parent_root_pressure_pa"

_ORIGINAL_VERIFY_PARENT = runner._verify_parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corrected_verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], Any, dict[str, str], dict[str, str]]:
    summary, state, step_row, root_row = _ORIGINAL_VERIFY_PARENT(
        directory,
        artifact_digest=artifact_digest,
    )
    corrected_root = dict(root_row)
    if "root_pressure_pa" in corrected_root:
        source_key = "root_pressure_pa"
    elif "pressure_pa" in corrected_root:
        corrected_root["root_pressure_pa"] = corrected_root["pressure_pa"]
        source_key = "pressure_pa"
    else:
        raise KeyError(
            "verified Increment 9H selected root has neither pressure_pa nor "
            "root_pressure_pa"
        )
    corrected_root["parent_root_pressure_source_key"] = source_key
    corrected_root["parent_root_schema_correction_applied"] = (
        source_key == "pressure_pa"
    )
    return summary, state, step_row, corrected_root


def _argument_path(flag: str) -> Path:
    try:
        index = sys.argv.index(flag)
    except ValueError as exc:
        raise RuntimeError(f"required argument {flag!r} is missing") from exc
    if index + 1 >= len(sys.argv):
        raise RuntimeError(f"required argument {flag!r} has no value")
    return Path(sys.argv[index + 1])


def _postprocess(output: Path) -> dict[str, Any]:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(
        {
            "parent_root_schema_correction_applied": True,
            "parent_root_schema_source_key": "pressure_pa",
            "parent_root_schema_target_key": "root_pressure_pa",
            "parent_root_schema_value_changed": False,
            "parent_root_schema_correction_scope": CORRECTION_SCOPE,
            "parent_root_schema_correction_parent_source_sha": (
                CORRECTION_PARENT_SOURCE_SHA
            ),
            "parent_root_schema_correction_parent_run": CORRECTION_PARENT_RUN,
            "parent_root_schema_correction_parent_job": CORRECTION_PARENT_JOB,
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
        "scope": CORRECTION_SCOPE,
        "failed_parent_run": {
            "source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "workflow_run": CORRECTION_PARENT_RUN,
            "job": CORRECTION_PARENT_JOB,
            "failure": "KeyError: root_pressure_pa",
            "artifact": None,
        },
        "source_key": "pressure_pa",
        "target_key": "root_pressure_pa",
        "numerical_value_changed": False,
        "accepted_state_changed": False,
        "root_changed": False,
        "b1_behavior_changed": False,
        "local_admissibility_rule_changed": False,
        "dynamic_seeded_interval_rule_changed": False,
        "root_tolerance_or_chi_scope_changed": False,
        "flux_or_solver_update_changed": False,
    }
    (output / "parent_root_schema_correction.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Parent-root schema correction\n\n"
        + "The verified Increment 9H selected-root value stored as "
        + "`pressure_pa` was exposed to the shared continuation engine under "
        + "its expected alias `root_pressure_pa`. The numerical value, root, "
        + "state, seeded interval rule, flux, solver update and all gates were "
        + "unchanged.\n\n"
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
        "parent_root_schema_correction.json",
        "stop_evidence.json",
        "summary.json",
        "report.md",
    )
    missing = [name for name in names if not (output / name).is_file()]
    if missing:
        summary["parent_root_schema_postprocess_missing_files"] = missing
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n"
            for name in names
            if (output / name).is_file()
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    output = _argument_path("--output-dir")
    runner._verify_parent = _corrected_verify_parent
    base_exit: SystemExit | None = None
    try:
        runner.main()
    except SystemExit as exc:
        base_exit = exc

    if not (output / "summary.json").is_file():
        if base_exit is not None:
            raise base_exit
        raise RuntimeError(
            "Increment 9I corrected runner did not create summary evidence"
        )

    summary = _postprocess(output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if base_exit is not None:
        raise base_exit


if __name__ == "__main__":
    main()
