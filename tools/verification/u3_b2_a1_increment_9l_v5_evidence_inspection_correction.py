from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


SOURCE_RUN = 31690390529
SOURCE_JOB = 94416115006
SOURCE_GIT_SHA = "bdbbf88b240ff1b839d8a72fa898437efac1e7b8"
SOURCE_ARTIFACT = 9177683047
SOURCE_ARTIFACT_NAME = "u3-b2-a1-increment-9l-v5-31690390529"
SOURCE_ARTIFACT_SHA256 = (
    "0ff366738c855c83d9355c3e18b2cb54f640354a34b96211d85dd205269f6b32"
)
TARGET_TIME_S = 0.004285834855172021
EXPECTED_OUTCOME = (
    "INCREMENT_9L_PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE_PASS"
)
EXPECTED_WORKING_KIND = "PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE"
EXPECTED_FILES = {
    "artifact_sha256.txt",
    "authority_verification.json",
    "boundary_state_history.csv",
    "boundary_transition_events.csv",
    "finite_compression_bounded_window_fallback_correction.json",
    "finite_compression_bounded_window_fallback_events.csv",
    "guard_front_root_topology_correction.json",
    "guard_front_root_topology_correction_events.csv",
    "guard_front_topology_authority_binding_correction.json",
    "initial_and_final_states.npz",
    "initial_rarefaction_handoff_correction.json",
    "outward_model_transition_events.csv",
    "report.md",
    "step_metrics.csv",
    "summary.json",
    "technical_issue.json",
    "three_branch_algorithm_transition_events.csv",
}
FORMAL_FALSE = (
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


class Increment9LInspectionStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(U, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) == 1 and rows[0].get("no_rows_recorded") == "True":
        return []
    return rows


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _integer(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise Increment9LInspectionStop(f"invalid integer {name}: {value!r}") from exc


def _floating(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise Increment9LInspectionStop(f"invalid float {name}: {value!r}") from exc
    if not math.isfinite(result):
        raise Increment9LInspectionStop(f"nonfinite float {name}: {result!r}")
    return result


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Increment9LInspectionStop(message)


def _verify_source_artifact(
    directory: Path,
    *,
    artifact_digest: str,
) -> dict[str, str]:
    _require(
        artifact_digest == SOURCE_ARTIFACT_SHA256,
        "source GitHub artifact digest mismatch",
    )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    _require(actual == EXPECTED_FILES, f"unexpected source file set: {sorted(actual)}")

    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    _require(
        set(manifest) == EXPECTED_FILES - {"artifact_sha256.txt"},
        "source internal manifest names mismatch",
    )
    for name, digest in manifest.items():
        _require(
            _sha256(directory / name) == digest,
            f"source internal SHA256 mismatch for {name}",
        )
    return manifest


def _inspect(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _verify_source_artifact(
        directory,
        artifact_digest=artifact_digest,
    )
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    authority = json.loads(
        (directory / "authority_verification.json").read_text(encoding="utf-8")
    )
    handoff_correction = json.loads(
        (directory / "initial_rarefaction_handoff_correction.json").read_text(
            encoding="utf-8"
        )
    )
    topology_correction = json.loads(
        (directory / "guard_front_root_topology_correction.json").read_text(
            encoding="utf-8"
        )
    )
    topology_authority = json.loads(
        (
            directory
            / "guard_front_topology_authority_binding_correction.json"
        ).read_text(encoding="utf-8")
    )
    bounded_correction = json.loads(
        (
            directory
            / "finite_compression_bounded_window_fallback_correction.json"
        ).read_text(encoding="utf-8")
    )
    technical_issue = json.loads(
        (directory / "technical_issue.json").read_text(encoding="utf-8")
    )

    steps = _read_csv(directory / "step_metrics.csv")
    state_history = _read_csv(directory / "boundary_state_history.csv")
    boundary_events = _read_csv(directory / "boundary_transition_events.csv")
    outward_model_events = _read_csv(
        directory / "outward_model_transition_events.csv"
    )
    handoff_events = _read_csv(
        directory / "three_branch_algorithm_transition_events.csv"
    )
    topology_events = _read_csv(
        directory / "guard_front_root_topology_correction_events.csv"
    )
    bounded_events = _read_csv(
        directory / "finite_compression_bounded_window_fallback_events.csv"
    )

    _require(summary["source_git_sha"] == SOURCE_GIT_SHA, "source SHA mismatch")
    _require(summary["schema_version"].endswith("_v5"), "summary schema is not v5")
    _require(summary["source_starts_from_initial_state"] is True, "not initial-state run")
    _require(summary["checkpoint_artifact_used"] is False, "checkpoint artifact was used")
    _require(summary["single_fvm_solver_instance"] is True, "multiple solver path")
    _require(summary["solver_instance_count"] == 1, "solver instance count mismatch")
    _require(
        summary["absolute_step_number_transition_condition_used"] is False,
        "absolute step-number transition condition was used",
    )
    _require(summary["increment_9l_state_machine_gate_passed"] is True, "9L gate false")
    _require(summary["working_vertical_slice"] is True, "working slice false")
    _require(summary["working_vertical_slice_kind"] == EXPECTED_WORKING_KIND, "working kind mismatch")
    _require(summary["outcome"] == EXPECTED_OUTCOME, "outcome mismatch")
    _require(summary["target_horizon_reached"] is True, "target horizon not reached")
    _require(summary["final_step_clipped_to_target"] is True, "final target clip false")
    _require(summary["final_solver_step"] == 640, "final solver step mismatch")
    _require(summary["accepted_steps_completed"] == 640, "accepted-step count mismatch")
    _require(summary["final_solver_time_s"] == TARGET_TIME_S, "final time mismatch")
    _require(summary["target_two_l_over_c0_time_s"] == TARGET_TIME_S, "target time mismatch")
    _require(summary["horizon_time_error_s"] == 0.0, "horizon error is not exact zero")
    _require(summary["horizon_fraction_reached"] == 1.0, "horizon fraction mismatch")
    _require(summary["stop_classification"] is None, "unexpected stop classification")
    _require(summary["stop_reason"] is None, "unexpected stop reason")
    _require(all(summary[name] is False for name in FORMAL_FALSE), "formal boundary changed")

    _require(authority["execution_source_git_sha"] == SOURCE_GIT_SHA, "authority source mismatch")
    _require(authority["initial_state_built_from_locked_contract"] is True, "initial authority false")
    _require(authority["checkpoint_artifact_used"] is False, "authority checkpoint true")
    _require(authority["absolute_step_transition_condition_used"] is False, "authority step trigger true")
    _require(authority["b1_changed"] is False, "B1 changed")
    _require(authority["production_adapter_changed"] is False, "production adapter changed")
    _require(authority["fvm_solver_core_changed"] is False, "FvmSolver core changed")
    _require(authority["locked_b2_contract_changed"] is False, "locked contract changed")
    _require(authority["tolerances_changed"] is False, "tolerances changed")
    _require(authority["chi_cap_changed"] is False, "chi cap changed")

    _require(len(steps) == 640, "step_metrics row count mismatch")
    _require(len(state_history) == 640, "state-history row count mismatch")
    expected_step_ids = list(range(1, 641))
    _require(
        [_integer(row["requested_solver_step"], "requested_solver_step") for row in steps]
        == expected_step_ids,
        "requested-step sequence is not 1..640",
    )
    _require(
        [_integer(row["solver_step_count"], "solver_step_count") for row in steps]
        == expected_step_ids,
        "accepted solver-step sequence is not 1..640",
    )
    _require(
        [_integer(row["solver_step_count"], "state solver_step_count") for row in state_history]
        == expected_step_ids,
        "state-history solver-step sequence mismatch",
    )
    _require(
        all(_truth(row["increment_9l_per_step_engineering_gate_passed"]) for row in steps),
        "one or more per-step engineering gates failed",
    )
    for key in (
        "step_mass_passed",
        "step_momentum_passed",
        "step_energy_passed",
        "cumulative_mass_passed",
        "cumulative_momentum_passed",
        "cumulative_energy_passed",
        "all_conserved_finite",
        "all_phases_allowed",
        "rho_xv_exact_zero",
    ):
        _require(all(_truth(row[key]) for row in steps), f"per-step field {key} failed")
    _require(
        all(_floating(row["minimum_density_after_kg_m3"], "minimum density") > 0.0 for row in steps),
        "nonpositive density in accepted step",
    )
    _require(
        all(_floating(row["minimum_internal_energy_after_J_kg"], "minimum internal") > 0.0 for row in steps),
        "nonpositive internal energy in accepted step",
    )

    public_states = [row["public_boundary_state"] for row in steps]
    _require(public_states == ["OUTWARD_FLOW"] * 637 + ["ZERO_TRANSFER_CLOSED"] * 3, "public-state history mismatch")
    _require(summary["public_boundary_state_counts"] == {"OUTWARD_FLOW": 637, "ZERO_TRANSFER_CLOSED": 3}, "public counts mismatch")
    _require(summary["public_state_transition_count"] == 1, "public transition count mismatch")
    _require(summary["public_state_reentry_allowed"] is False, "public re-entry enabled")
    _require(summary["public_state_chatter_detected"] is False, "public-state chatter detected")
    _require(summary["reverse_mass_transfer_supported"] is False, "reverse mass transfer enabled")

    _require(len(handoff_events) == 1, "handoff event count mismatch")
    handoff = handoff_events[0]
    _require(_integer(handoff["requested_solver_step"], "handoff step") == 337, "handoff step mismatch")
    _require(handoff["from_algorithm"] == "CONNECTED_RAREFACTION", "handoff source mismatch")
    _require(handoff["to_algorithm"] == "GENERAL_THREE_BRANCH_CLASSIFICATION", "handoff target mismatch")
    _require(handoff["trigger_classification"] == "CONNECTED_ROOT_SIGN_CHANGES_ZERO", "handoff trigger mismatch")
    _require(not _truth(handoff["absolute_step_number_trigger_used"]), "handoff step trigger used")
    _require(not _truth(handoff["failed_candidate_used_as_root"]), "handoff failed candidate used as root")
    _require(not _truth(handoff["failed_candidate_used_as_flux"]), "handoff failed candidate used as flux")
    _require(not _truth(handoff["solver_state_mutated_before_handoff"]), "state mutated before handoff")
    _require(handoff_correction["handoff_gate_passed"] is True, "handoff correction gate false")

    _require(len(topology_events) == 24, "Guard-front topology event count mismatch")
    topology_steps = [_integer(row["requested_solver_step"], "topology step") for row in topology_events]
    _require(topology_steps[0] == 452 and topology_steps[-1] == 483, "topology corrected range mismatch")
    _require(all(_truth(row["root_topology_monotone_nonincreasing"]) for row in topology_events), "corrected topology nonmonotone")
    _require(all(_integer(row["root_topology_sign_change_count"], "topology sign changes") == 1 for row in topology_events), "topology sign-change count mismatch")
    _require(all(not _truth(row["intermediate_success_used_as_root_topology"]) for row in topology_events), "intermediate evidence used as topology")
    _require(all(not _truth(row["failed_b1_state_used_as_root_endpoint"]) for row in topology_events), "failed B1 state used as root endpoint")
    _require(all(not _truth(row["failed_b1_state_used_to_construct_flux"]) for row in topology_events), "failed B1 state used as flux")
    _require(topology_correction["root_topology_gate_passed"] is True, "topology correction gate false")
    _require(topology_authority["binding_correction_gate_passed"] is True, "topology authority gate false")

    _require(len(outward_model_events) == 1, "outward-model event count mismatch")
    model_event = outward_model_events[0]
    finite_model_step = _integer(model_event["requested_solver_step"], "finite model step")
    _require(finite_model_step == 484, "finite-compression model-transition step mismatch")
    _require(model_event["from_outward_model"] == "THREE_BRANCH_WAVE_MODEL", "finite model source mismatch")
    _require(model_event["to_outward_model"] == "GENERAL_EOS_FINITE_COMPRESSION", "finite model target mismatch")
    _require(model_event["trigger_classification"] == "FINITE_COMPRESSION_MODEL_REQUIRED", "finite model trigger mismatch")
    _require(not _truth(model_event["absolute_step_number_trigger_used"]), "finite-model step trigger used")

    _require(len(bounded_events) == 151, "bounded fallback event count mismatch")
    bounded_steps = [_integer(row["requested_solver_step"], "bounded step") for row in bounded_events]
    _require(bounded_steps == list(range(484, 635)), "bounded fallback steps are not contiguous 484..634")
    _require(bounded_steps[0] == finite_model_step, "first fallback does not equal finite model transition")
    _require(bounded_correction["first_fallback_requested_step"] == 484, "bounded correction first step mismatch")
    _require(bounded_correction["last_fallback_requested_step"] == 634, "bounded correction last step mismatch")
    _require(bounded_correction["fallback_event_count"] == 151, "bounded correction count mismatch")
    _require(bounded_correction["bounded_window_gate_passed"] is True, "bounded correction gate false")
    _require(all(row["seeded_trigger_classification"] == "SEEDED_INTERVAL_EDGE_CONTACT" for row in bounded_events), "unexpected bounded fallback trigger")
    _require(all(_integer(row["bounded_success_window_count"], "bounded window count") == 1 for row in bounded_events), "bounded success-window count mismatch")
    _require(all(_truth(row["root_topology_monotone_nonincreasing"]) for row in bounded_events), "bounded topology nonmonotone")
    _require(all(_integer(row["root_topology_sign_change_count"], "bounded sign changes") == 1 for row in bounded_events), "bounded sign-change count mismatch")
    _require(all(_truth(row["selected_root_gate_passed"]) for row in bounded_events), "bounded selected-root gate failed")
    _require(all(_truth(row["actual_continuation_supported"]) for row in bounded_events), "bounded continuation unsupported")
    _require(all(not _truth(row["excluded_candidate_used_as_root_endpoint"]) for row in bounded_events), "bounded excluded root endpoint used")
    _require(all(not _truth(row["excluded_candidate_used_to_construct_flux"]) for row in bounded_events), "bounded excluded flux used")
    _require(all(not _truth(row["absolute_step_number_trigger_used"]) for row in bounded_events), "bounded step trigger used")
    _require(all(not _truth(row["checkpoint_state_used"]) for row in bounded_events), "bounded checkpoint used")

    leading_steps = [
        _integer(row["requested_solver_step"], "leading excluded step")
        for row in bounded_events
        if _integer(row["leading_excluded_node_count"], "leading excluded count") > 0
    ]
    guard_steps = [
        _integer(row["requested_solver_step"], "guard refinement step")
        for row in bounded_events
        if _truth(row["guard_front_refinement_applied"])
    ]
    trailing_steps = [
        _integer(row["requested_solver_step"], "trailing excluded step")
        for row in bounded_events
        if _integer(row["trailing_excluded_node_count"], "trailing excluded count") > 0
    ]
    _require(leading_steps and leading_steps[0] == 489, "first leading-excluded step mismatch")
    _require(guard_steps and guard_steps[0] == 494, "first Guard-front refinement step mismatch")
    _require(trailing_steps and trailing_steps[0] == 606, "first trailing-excluded step mismatch")

    finite_rows = [row for row in steps if row["outward_internal_model"] == "GENERAL_EOS_FINITE_COMPRESSION"]
    finite_steps = [_integer(row["requested_solver_step"], "finite step") for row in finite_rows]
    _require(finite_steps == list(range(484, 638)), "finite-compression accepted steps mismatch")
    fallback_rows = [row for row in finite_rows if row["finite_compression_algorithm"] == "DYNAMIC_FIXED_GUARD_FRONT_FALLBACK"]
    seeded_rows = [row for row in finite_rows if row["finite_compression_algorithm"] == "DYNAMIC_SEEDED_257"]
    _require([_integer(row["requested_solver_step"], "fallback accepted step") for row in fallback_rows] == list(range(484, 635)), "accepted fallback step range mismatch")
    _require([_integer(row["requested_solver_step"], "seeded accepted step") for row in seeded_rows] == [635, 636, 637], "final seeded step range mismatch")

    _require(len(boundary_events) == 1, "boundary event count mismatch")
    boundary = boundary_events[0]
    _require(_integer(boundary["requested_solver_step"], "closure step") == 638, "closure step mismatch")
    _require(boundary["from_boundary_state"] == "OUTWARD_FLOW", "closure source mismatch")
    _require(boundary["to_boundary_state"] == "ZERO_TRANSFER_CLOSED", "closure target mismatch")
    _require(boundary["trigger_classification"] == "NO_ADMISSIBLE_ISLAND", "closure trigger mismatch")
    _require(not _truth(boundary["failed_candidate_used_as_root"]), "closure failed root used")
    _require(not _truth(boundary["failed_candidate_used_as_flux"]), "closure failed flux used")
    _require(not _truth(boundary["solver_state_mutated_before_transition"]), "state mutated before closure")
    _require(not _truth(boundary["absolute_step_number_trigger_used"]), "closure step trigger used")
    closed_rows = steps[637:]
    _require([_integer(row["requested_solver_step"], "closed step") for row in closed_rows] == [638, 639, 640], "closed accepted steps mismatch")
    _require(all(_floating(row["right_external_mass_flux_kg_m2_s"], "closed mass flux") == 0.0 for row in closed_rows), "closed mass flux nonzero")
    _require(all(_floating(row["right_external_energy_flux_W_m2"], "closed energy flux") == 0.0 for row in closed_rows), "closed energy flux nonzero")
    _require(all(_floating(row["right_external_vapor_flux_kg_m2_s"], "closed vapor flux") == 0.0 for row in closed_rows), "closed vapor flux nonzero")
    _require(all(_floating(row["wall_momentum_identity_residual_pa"], "wall residual") == 0.0 for row in closed_rows), "wall identity residual nonzero")

    with np.load(directory / "initial_and_final_states.npz") as states:
        _require(set(states.files) == {"U_initial", "U_final", "solver_step_initial", "solver_step_final", "solver_time_initial_s", "solver_time_final_s", "target_time_s"}, "state NPZ fields mismatch")
        U_initial = np.asarray(states["U_initial"], dtype=float)
        U_final = np.asarray(states["U_final"], dtype=float)
        _require(U_initial.shape == (32, 4) and U_final.shape == (32, 4), "state array shape mismatch")
        _require(int(states["solver_step_initial"][0]) == 0, "initial state step mismatch")
        _require(int(states["solver_step_final"][0]) == 640, "final state step mismatch")
        _require(float(states["solver_time_initial_s"][0]) == 0.0, "initial state time mismatch")
        _require(float(states["solver_time_final_s"][0]) == TARGET_TIME_S, "final state time mismatch")
        _require(float(states["target_time_s"][0]) == TARGET_TIME_S, "NPZ target mismatch")
        _require(_state_sha256(U_initial) == summary["starting_state_sha256"], "initial state SHA mismatch")
        _require(_state_sha256(U_final) == summary["final_state_sha256"], "final state SHA mismatch")
        _require(np.all(np.isfinite(U_initial)) and np.all(np.isfinite(U_final)), "nonfinite NPZ state")
        rho = U_final[:, 0]
        velocity = U_final[:, 1] / rho
        internal = U_final[:, 2] / rho - 0.5 * velocity * velocity
        _require(np.all(rho > 0.0), "final NPZ density nonpositive")
        _require(np.all(internal > 0.0), "final NPZ internal energy nonpositive")
        _require(np.all(U_final[:, 3] == 0.0), "final NPZ rho*xv not exact zero")

    _require(technical_issue["status"] == "OPEN_NONBLOCKING_TECHNICAL_DEBT", "technical issue status mismatch")
    _require(technical_issue["transition_generalized_without_absolute_step_number"] is True, "transition not generalized")
    _require(technical_issue["reentry_implemented"] is False, "reentry unexpectedly implemented")
    _require(technical_issue["reverse_flow_implemented"] is False, "reverse flow unexpectedly implemented")
    _require(technical_issue["physical_validation"] is False, "physical validation unexpectedly true")

    correction = {
        "correction": "increment_9l_v5_bounded_window_inspection_schema",
        "source_workflow_run": SOURCE_RUN,
        "source_job": SOURCE_JOB,
        "source_git_sha": SOURCE_GIT_SHA,
        "source_artifact": SOURCE_ARTIFACT,
        "source_artifact_name": SOURCE_ARTIFACT_NAME,
        "source_artifact_sha256": SOURCE_ARTIFACT_SHA256,
        "source_artifact_file_count": len(EXPECTED_FILES),
        "source_internal_manifest_verified": True,
        "source_internal_file_sha256_verified": True,
        "incorrect_fixed_assertion": "first_fallback_requested_step == 606",
        "correct_first_fallback_requested_step": 484,
        "correct_first_fallback_equals_finite_model_transition": True,
        "first_leading_excluded_requested_step": 489,
        "first_guard_front_refinement_requested_step": 494,
        "first_trailing_excluded_requested_step": 606,
        "last_fallback_requested_step": 634,
        "fallback_event_count": 151,
        "final_seeded_finite_compression_steps": [635, 636, 637],
        "public_closure_transition_requested_step": 638,
        "final_accepted_solver_step": 640,
        "accepted_step_count": 640,
        "target_time_s": TARGET_TIME_S,
        "target_horizon_reached": True,
        "source_runner_gate_passed": True,
        "corrected_inspection_gate_passed": True,
        "source_artifact_modified": False,
        "fvm_rerun_performed": False,
        "root_recomputed": False,
        "state_recomputed": False,
        "physics_changed": False,
        "state_machine_changed": False,
        "bounded_window_algorithm_changed": False,
        "b1_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "tolerances_changed": False,
        "chi_cap_changed": False,
        "formal_boundary_preserved": True,
    }
    inspection = {
        "schema_version": "stage7_u3_b2_a1_increment_9l_v5_evidence_inspection_correction_v1",
        "status": "IMMUTABLE_SOURCE_ARTIFACT_INSPECTED_PASS",
        "outcome": "INCREMENT_9L_V5_EVIDENCE_INSPECTION_CORRECTION_PASS",
        "source_summary_outcome": summary["outcome"],
        "source_working_vertical_slice_kind": summary["working_vertical_slice_kind"],
        "source_git_sha": SOURCE_GIT_SHA,
        "source_run": SOURCE_RUN,
        "source_job": SOURCE_JOB,
        "source_artifact": SOURCE_ARTIFACT,
        "source_artifact_name": SOURCE_ARTIFACT_NAME,
        "source_artifact_sha256": SOURCE_ARTIFACT_SHA256,
        "source_artifact_manifest": manifest,
        "accepted_steps": 640,
        "public_outward_steps": 637,
        "public_closed_steps": 3,
        "handoff_step": 337,
        "finite_model_transition_step": 484,
        "bounded_fallback_first_step": 484,
        "bounded_fallback_last_step": 634,
        "first_trailing_excluded_step": 606,
        "final_seeded_steps": [635, 636, 637],
        "closure_transition_step": 638,
        "final_solver_step": 640,
        "final_solver_time_s": TARGET_TIME_S,
        "maximum_absolute_step_mass_residual_kg": summary["maximum_absolute_step_mass_residual_kg"],
        "maximum_absolute_step_momentum_residual_kg_m_s": summary["maximum_absolute_step_momentum_residual_kg_m_s"],
        "maximum_absolute_step_energy_residual_J": summary["maximum_absolute_step_energy_residual_J"],
        "maximum_absolute_cumulative_mass_residual_kg": summary["maximum_absolute_cumulative_mass_residual_kg"],
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": summary["maximum_absolute_cumulative_momentum_residual_kg_m_s"],
        "maximum_absolute_cumulative_energy_residual_J": summary["maximum_absolute_cumulative_energy_residual_J"],
        "minimum_density_kg_m3": summary["minimum_density_kg_m3"],
        "minimum_internal_energy_J_kg": summary["minimum_internal_energy_J_kg"],
        "final_state_sha256": summary["final_state_sha256"],
        "all_source_per_step_gates_passed": True,
        "all_source_conservation_gates_passed": True,
        "all_source_phases_allowed": True,
        "source_rho_xv_exact_zero": True,
        "closed_transfer_identities_exact": True,
        "public_state_transition_count": 1,
        "public_state_chatter_detected": False,
        "public_state_reentry_allowed": False,
        "reverse_mass_transfer_supported": False,
        "corrected_inspection_gate_passed": True,
        **{name: False for name in FORMAL_FALSE},
    }
    return inspection, correction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact-dir", type=Path, required=True)
    parser.add_argument("--source-artifact-digest", required=True)
    parser.add_argument("--inspection-correction-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.inspection_correction_spec.is_file():
        raise FileNotFoundError(args.inspection_correction_spec)
    inspection, correction = _inspect(
        args.source_artifact_dir,
        artifact_digest=args.source_artifact_digest,
    )
    correction["inspection_correction_spec"] = str(args.inspection_correction_spec)
    correction["inspection_correction_spec_sha256"] = _sha256(
        args.inspection_correction_spec
    )
    correction["inspection_execution_source_git_sha"] = args.source_git_sha
    inspection["inspection_correction_spec"] = str(args.inspection_correction_spec)
    inspection["inspection_correction_spec_sha256"] = _sha256(
        args.inspection_correction_spec
    )
    inspection["inspection_execution_source_git_sha"] = args.source_git_sha

    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise Increment9LInspectionStop("inspection output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)
    (output / "inspection_summary.json").write_text(
        json.dumps(inspection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "inspection_correction.json").write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9L v5 immutable evidence inspection correction\n\n"
        "The exact successful v5 runner artifact was downloaded and inspected "
        "without FVM, root, flux, or state recomputation. The failed workflow "
        "inspection had conflated the first bounded-window fallback step (484) "
        "with the first trailing-excluded topology step (606). The corrected "
        "inspection verifies the contiguous fallback sequence 484-634, the "
        "first trailing excluded candidate at step 606, seeded continuation at "
        "steps 635-637, one public closure transition at step 638, and final "
        "accepted step 640 at exact nominal 2L/c0. All source per-step, "
        "conservation, positivity, phase, scalar, and closed-flux gates pass.\n\n"
        "```json\n"
        + json.dumps(inspection, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "inspection_summary.json",
        "inspection_correction.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(inspection, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
