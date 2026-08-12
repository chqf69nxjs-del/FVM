from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_a1_weak_compression_bridge_short_run_scope_roundoff as scope_roundoff
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


PARENT_SOURCE_SHA = "2e9e2c1c3d01fd66d82b3a2ecb036b811e0469b0"
PARENT_WORKFLOW_RUN = 31606368597
PARENT_JOB = 94146232478
PARENT_ARTIFACT = 9145306448
PARENT_ARTIFACT_SHA256 = (
    "633bffda60db2a886066772e693f83b5d1e4fd8887526d717637232ac7b3a35b"
)
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-weak-compression-bridge-increment-4-31606368597"
)
EXPECTED_SOLVER_STEP = 443
EXPECTED_SOLVER_TIME_S = 0.0029683027202354953
NEXT_REQUESTED_SOLVER_STEP = 444
PASS_OUTCOME = "BACK_PRESSURE_CROSSING_BRANCH_DOMAIN_CORRECTION_SUPPORTED"
FAIL_OUTCOME = "BACK_PRESSURE_CROSSING_REQUIRES_PHYSICS_REVIEW"
robustness = robustness_v4.robustness

PARENT_REQUIRED_FILES = {
    "full_horizon_continuation_steps.csv",
    "full_horizon_continuation_roots.csv",
    "local_wave_scans.csv",
    "positive_pressure_scans.csv",
    "branch_transitions.csv",
    "probe_series.csv",
    "full_horizon_states.npz",
    "parent_verification.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


class BackPressureCrossingDiagnosticStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _verify_parent_artifact(
    parent_dir: Path,
    *,
    parent_artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    if parent_artifact_digest != PARENT_ARTIFACT_SHA256:
        raise BackPressureCrossingDiagnosticStop(
            "parent GitHub artifact digest does not match the fixed Increment 4 "
            f"digest: {parent_artifact_digest}"
        )
    actual_files = {path.name for path in parent_dir.iterdir() if path.is_file()}
    if actual_files != PARENT_REQUIRED_FILES:
        raise BackPressureCrossingDiagnosticStop(
            "parent artifact file set mismatch: "
            f"actual={sorted(actual_files)}"
        )

    manifest: dict[str, str] = {}
    for line in (parent_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    expected_names = PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}
    if set(manifest) != expected_names:
        raise BackPressureCrossingDiagnosticStop(
            "parent internal manifest names do not match the fixed file set"
        )
    for name, digest in manifest.items():
        actual = _sha256(parent_dir / name)
        if actual != digest:
            raise BackPressureCrossingDiagnosticStop(
                f"parent internal SHA256 mismatch for {name}: {actual}"
            )

    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    required_summary = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "solver_step_after": EXPECTED_SOLVER_STEP,
        "solver_time_after_s": EXPECTED_SOLVER_TIME_S,
        "outcome": "INCREMENT_4_STOPPED",
        "stop_reason": (
            "WeakCompressionShortRunStop: connected rarefaction scan has "
            "fewer than two admissible subsonic nodes"
        ),
    }
    for key, expected in required_summary.items():
        if summary.get(key) != expected:
            raise BackPressureCrossingDiagnosticStop(
                f"parent summary mismatch for {key}: {summary.get(key)!r}"
            )
    if int(summary.get("continuation_accepted_steps_completed", -1)) != 74:
        raise BackPressureCrossingDiagnosticStop(
            "parent continuation accepted-step count is not 74"
        )
    if bool(summary.get("clear_branch_chatter_detected")):
        raise BackPressureCrossingDiagnosticStop(
            "parent evidence reports clear branch chatter"
        )

    with np.load(parent_dir / "full_horizon_states.npz") as states:
        U_start = np.asarray(states["U_start"], dtype=float).copy()
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_start.shape != (32, 4) or U_final.shape != (32, 4):
        raise BackPressureCrossingDiagnosticStop(
            "parent conserved-state shape is not (32, 4)"
        )
    if step_after != EXPECTED_SOLVER_STEP or time_after != EXPECTED_SOLVER_TIME_S:
        raise BackPressureCrossingDiagnosticStop(
            "parent NPZ solver identity does not match step 443"
        )
    if not np.all(np.isfinite(U_final)):
        raise BackPressureCrossingDiagnosticStop(
            "parent final conserved state contains nonfinite values"
        )
    if not np.all(U_final[:, 0] > 0.0):
        raise BackPressureCrossingDiagnosticStop(
            "parent final conserved state contains nonpositive density"
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise BackPressureCrossingDiagnosticStop(
            "parent final rho*xv is not exact zero"
        )
    return summary, U_start, U_final


def _root_completion(
    *,
    positive: dict[str, Any],
    hook: Any,
    interior_pressure_pa: float,
) -> tuple[dict[str, Any], int, dict[str, float]]:
    brackets = list(positive["admissible_brackets"])
    if len(brackets) != 1:
        raise BackPressureCrossingDiagnosticStop(
            "positive-pressure diagnostic did not retain exactly one root bracket"
        )
    root, iterations, final_bracket = short_run._solve_first_bracket(
        bracket=brackets[0],
        evaluate_offset=positive["evaluate_offset"],
        root_tolerance_kg_s=float(
            robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        ),
    )

    def evaluate_pressure(pressure_pa: float) -> dict[str, Any]:
        return positive["evaluate_offset"](
            float(pressure_pa) - float(interior_pressure_pa)
        )

    completed = horizon._complete_root_row_dynamic_v4(
        root=root,
        evaluate=evaluate_pressure,
        adapter=hook.adapter,
        area_m2=hook.area_m2,
        quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
    )
    merged = dict(root)
    merged.update(completed)
    merged.update(
        {
            "bisection_iterations": int(iterations),
            "selected_initial_bracket_lower_offset_pa": float(
                brackets[0]["lower_offset_pa"]
            ),
            "selected_initial_bracket_upper_offset_pa": float(
                brackets[0]["upper_offset_pa"]
            ),
            **final_bracket,
        }
    )
    return merged, int(iterations), final_bracket


def _run_diagnostic(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    parent_summary: dict[str, Any],
    U_final: np.ndarray,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    provider = CoolPropB2StateProvider()
    hook = short_run.A1WeakCompressionBridgeShortRunHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=short_run.CASE_ID,
        provider=provider,
    )
    U_before = np.asarray(U_final, dtype=float).copy()
    state_sha256_before = _array_sha256(U_before)
    reconstruction = provider.reconstruct_from_conserved(U_before[-1])
    static = reconstruction.static
    back_pressure = float(hook.adapter.back_pressure_pa)
    velocity_tolerance = float(
        contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    root_tolerance = float(robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)

    details = short_run._classification_diagnostics(
        hook=hook,
        U=U_before,
        solver_time_s=EXPECTED_SOLVER_TIME_S,
    )
    endpoint = dict(details["endpoint"])
    connected = dict(details["connected_rarefaction"])

    positive = scope_roundoff._corrected_positive_pressure_scan(
        hook=hook,
        U=U_before,
    )
    root, iterations, final_bracket = _root_completion(
        positive=positive,
        hook=hook,
        interior_pressure_pa=float(static.pressure_pa),
    )

    root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    root_chi = float(root_offset / denominator)
    normalized_root_phase = normalize_phase(str(root["phase"]))
    allowed_phases = {
        normalize_phase(value)
        for value in short_run.diagnostic._family(
            contract,
            hook.state_id,
        )["allowed_normalized_phases"]
    }
    state_sha256_after = _array_sha256(U_before)
    state_unchanged = bool(
        np.array_equal(U_before, U_final)
        and state_sha256_before == state_sha256_after
    )

    static_pressure_margin = float(static.pressure_pa - back_pressure)
    stagnation_pressure_margin = float(
        reconstruction.stagnation_pressure_pa - back_pressure
    )
    endpoint_residual = float(endpoint["compatibility_residual_kg_s"])
    connected_stop_reason = str(connected.get("stop_reason") or "")

    checks = {
        "parent_increment_4_stop_verified": bool(
            parent_summary["solver_step_after"] == EXPECTED_SOLVER_STEP
        ),
        "static_pressure_at_or_below_back": bool(
            float(static.pressure_pa) <= back_pressure
        ),
        "stagnation_pressure_above_back": bool(
            float(reconstruction.stagnation_pressure_pa) > back_pressure
        ),
        "outlet_velocity_outward": bool(
            float(static.velocity_m_s) >= -velocity_tolerance
        ),
        "outlet_subsonic": bool(
            0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0
        ),
        "outlet_phase_allowed": bool(
            normalize_phase(str(static.phase)) in allowed_phases
        ),
        "endpoint_evaluation_succeeded": bool(
            endpoint.get("evaluation_succeeded")
        ),
        "endpoint_locally_admissible": bool(
            endpoint.get("local_candidate_admissible")
        ),
        "endpoint_outside_root_tolerance": bool(
            abs(endpoint_residual) > root_tolerance
        ),
        "connected_rarefaction_domain_empty": bool(
            int(connected.get("requested_nodes") or 0) == 0
            and int(connected.get("admissible_subsonic_nodes") or 0) == 0
            and int(connected.get("sign_change_count") or 0) == 0
            and "outlet pressure is not above retained back pressure"
            in connected_stop_reason
        ),
        "local_rarefaction_root_absent": bool(
            int(details["rarefaction_side_local_sign_change_count"]) == 0
        ),
        "positive_scan_unique_root": bool(
            int(positive["sign_change_count"]) == 1
        ),
        "positive_scan_monotone": bool(
            positive["residual_monotone_nonincreasing"]
        ),
        "root_pressure_above_interior": bool(root_offset > 0.0),
        "root_chi_in_scope": bool(0.0 < root_chi <= short_run.CHI_MAX),
        "root_mass_residual_passed": bool(
            abs(float(root["root_mass_residual_kg_s"])) <= root_tolerance
        ),
        "root_slope_negative": bool(
            float(root["local_residual_slope_kg_s_Pa"]) < 0.0
        ),
        "root_velocity_outward": bool(
            float(root["velocity_m_s"]) >= -velocity_tolerance
        ),
        "root_subsonic": bool(0.0 <= float(root["mach"]) < 1.0),
        "root_phase_allowed": bool(normalized_root_phase in allowed_phases),
        "root_b1_succeeded": bool(
            root.get("evaluation_succeeded")
            and root.get("formal_outcome")
            not in {None, "", "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"}
        ),
        "root_stagnation_enthalpy_round_trip_passed": bool(
            root["stagnation_enthalpy_round_trip_passed"]
        ),
        "root_energy_mass_consistency_passed": bool(
            root["energy_mass_consistency_passed"]
        ),
        "root_energy_port_closure_passed": bool(
            root["energy_port_closure_passed"]
        ),
        "root_reaction_ledger_passed": bool(
            abs(float(root["momentum_ledger_residual_N"]))
            <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
        ),
        "state_unchanged": state_unchanged,
        "fvm_step_444_attempted": False,
    }
    gate_passed = bool(
        all(
            value
            for key, value in checks.items()
            if key != "fvm_step_444_attempted"
        )
        and checks["fvm_step_444_attempted"] is False
    )
    outcome = PASS_OUTCOME if gate_passed else FAIL_OUTCOME

    root_row = dict(root)
    root_row.update(
        {
            "requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
            "solver_time_s": EXPECTED_SOLVER_TIME_S,
            "branch_classification": "WEAK_COMPRESSION_CANDIDATE_DIAGNOSTIC_ONLY",
            "interior_pressure_pa": float(static.pressure_pa),
            "back_pressure_pa": back_pressure,
            "p_P_minus_p_i_pa": root_offset,
            "root_chi": root_chi,
            "chi_max": short_run.CHI_MAX,
            "bisection_iterations": iterations,
            **final_bracket,
            "fvm_step_444_attempted": False,
            "state_unchanged": state_unchanged,
        }
    )

    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4a"
        ),
        "scope": "model_review_diagnostic_only_back_pressure_crossing",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_artifact_verified": True,
        "case_id": short_run.CASE_ID,
        "solver_step_loaded": EXPECTED_SOLVER_STEP,
        "next_requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
        "solver_time_s": EXPECTED_SOLVER_TIME_S,
        "state_sha256_before": state_sha256_before,
        "state_sha256_after": state_sha256_after,
        "state_unchanged": state_unchanged,
        "interior_pressure_pa": float(static.pressure_pa),
        "back_pressure_pa": back_pressure,
        "static_pressure_margin_above_back_pa": static_pressure_margin,
        "interior_stagnation_pressure_pa": float(
            reconstruction.stagnation_pressure_pa
        ),
        "stagnation_pressure_margin_above_back_pa": stagnation_pressure_margin,
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_phase": str(static.phase),
        "endpoint_residual_kg_s": endpoint_residual,
        "retained_root_mass_tolerance_kg_s": root_tolerance,
        "endpoint_within_retained_tolerance": bool(
            abs(endpoint_residual) <= root_tolerance
        ),
        "endpoint_locally_admissible": bool(
            endpoint.get("local_candidate_admissible")
        ),
        "connected_rarefaction_requested_nodes": int(
            connected.get("requested_nodes") or 0
        ),
        "connected_rarefaction_admissible_subsonic_nodes": int(
            connected.get("admissible_subsonic_nodes") or 0
        ),
        "connected_rarefaction_sign_change_count": int(
            connected.get("sign_change_count") or 0
        ),
        "connected_rarefaction_stop_reason": connected.get("stop_reason"),
        "rarefaction_side_local_sign_change_count": int(
            details["rarefaction_side_local_sign_change_count"]
        ),
        "positive_scan_sign_change_count": int(
            positive["sign_change_count"]
        ),
        "positive_scan_residual_monotone_nonincreasing": bool(
            positive["residual_monotone_nonincreasing"]
        ),
        "positive_scan_delta_p_max_pa": float(positive["delta_p_max_pa"]),
        "scan_coordinate_correction": positive["scan_coordinate_correction"],
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_pressure_offset_pa": root_offset,
        "root_chi": root_chi,
        "chi_max": short_run.CHI_MAX,
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(
            root["local_residual_slope_kg_s_Pa"]
        ),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_phase": str(root["phase"]),
        "root_b1_formal_outcome": root["formal_outcome"],
        "root_stagnation_pressure_pa": float(root["stagnation_pressure_pa"]),
        "root_stagnation_pressure_margin_above_back_pa": float(
            root["stagnation_pressure_pa"] - back_pressure
        ),
        "root_restriction_reaction_ledger_residual_N": float(
            root["momentum_ledger_residual_N"]
        ),
        "root_energy_port_residual_W": float(root["energy_port_residual_W"]),
        "bisection_iterations": iterations,
        "checks": checks,
        "outcome": outcome,
        "increment_4a_diagnostic_gate_passed": gate_passed,
        "fvm_step_444_attempted": False,
        "positive_pressure_continuation_flux_applied": False,
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
    return summary, list(details["local_scan_rows"]), list(positive["rows"]), root_row


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

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    parent_summary, _, U_final = _verify_parent_artifact(
        args.parent_artifact_dir,
        parent_artifact_digest=args.parent_artifact_digest,
    )
    summary, local_rows, positive_rows, root_row = _run_diagnostic(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_final=U_final,
    )
    summary["source_git_sha"] = args.source_git_sha

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "step443_local_wave_scans.csv", local_rows)
    _write_csv(output / "step443_positive_pressure_scans.csv", positive_rows)
    _write_csv(output / "step443_weak_compression_root.csv", [root_row])
    np.savez_compressed(
        output / "step443_state_identity.npz",
        U_before=np.asarray(U_final, dtype=float),
        U_after=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray([EXPECTED_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray([EXPECTED_SOLVER_STEP], dtype=np.int64),
        solver_time_before_s=np.asarray([EXPECTED_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([EXPECTED_SOLVER_TIME_S]),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 4A\n\n"
        "MODEL_REVIEW / DIAGNOSTIC_ONLY evidence. The authoritative step-443 "
        "state was loaded without mutation, the rarefaction-domain stop was "
        "classified, and the unchanged positive-pressure root construction "
        "was evaluated without attempting FvmSolver step 444. A passing result "
        "does not authorize continuation, verify finite-pipe coupling, accept "
        "a benchmark, perform Physical Validation, approve design use, or "
        "activate production behavior.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step443_local_wave_scans.csv",
        "step443_positive_pressure_scans.csv",
        "step443_weak_compression_root.csv",
        "step443_state_identity.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4a_diagnostic_gate_passed"]:
        raise SystemExit(
            "Increment 4A back-pressure crossing diagnostic did not pass"
        )


if __name__ == "__main__":
    main()
