from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_a1_weak_compression_bridge_stagnation_pressure_crossing_diagnostic as increment_4c
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


PARENT_SOURCE_SHA = "cb56cfa0f856dc8f1ebe1463eeb80f2a269aa2a8"
PARENT_WORKFLOW_RUN = 31616654684
PARENT_JOB = 94181021964
PARENT_ARTIFACT = 9149565073
PARENT_ARTIFACT_SHA256 = (
    "a24c491035bbe296b9ad2cc128fc98302025cc90a03f1bda190ee4d9cb5dbd0c"
)
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-weak-compression-bridge-increment-4d-31616654684"
)
EXPECTED_SOLVER_STEP = 451
EXPECTED_SOLVER_TIME_S = 0.003021957828880739
NEXT_REQUESTED_SOLVER_STEP = 452
EXPECTED_ENDPOINT_GUARD = "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"
GUARD_FRONT_BISECTION_ITERATIONS = 32
SUPPORTED_OUTCOME = "B1_GUARD_FRONT_REFINED_POSITIVE_ROOT_SUPPORTED"
ROOT_INSIDE_GUARD_OUTCOME = "ROOT_LIES_INSIDE_B1_GUARD_DOMAIN"
FINITE_COMPRESSION_OUTCOME = "FINITE_COMPRESSION_MODEL_REQUIRED"
UNEXPECTED_OUTCOME = "B1_GUARD_FRONT_DIAGNOSTIC_INCONCLUSIVE"
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


class GuardFrontDiagnosticStop(RuntimeError):
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
        raise GuardFrontDiagnosticStop(
            "parent GitHub artifact digest does not match the fixed Increment 4D "
            f"digest: {parent_artifact_digest}"
        )
    actual_files = {path.name for path in parent_dir.iterdir() if path.is_file()}
    if actual_files != PARENT_REQUIRED_FILES:
        raise GuardFrontDiagnosticStop(
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
        raise GuardFrontDiagnosticStop(
            "parent internal manifest names do not match the fixed file set"
        )
    for name, digest in manifest.items():
        actual = _sha256(parent_dir / name)
        if actual != digest:
            raise GuardFrontDiagnosticStop(
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
            "CandidateStateContinuationStop: no in-scope candidate-state "
            "positive root was found"
        ),
    }
    for key, expected in required_summary.items():
        if summary.get(key) != expected:
            raise GuardFrontDiagnosticStop(
                f"parent summary mismatch for {key}: {summary.get(key)!r}"
            )
    if int(summary.get("continuation_accepted_steps_completed", -1)) != 82:
        raise GuardFrontDiagnosticStop(
            "parent continuation accepted-step count is not 82"
        )
    if bool(summary.get("clear_branch_chatter_detected")):
        raise GuardFrontDiagnosticStop(
            "parent evidence reports clear branch chatter"
        )

    with np.load(parent_dir / "full_horizon_states.npz") as states:
        U_start = np.asarray(states["U_start"], dtype=float).copy()
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_start.shape != (32, 4) or U_final.shape != (32, 4):
        raise GuardFrontDiagnosticStop(
            "parent conserved-state shape is not (32, 4)"
        )
    if step_after != EXPECTED_SOLVER_STEP or time_after != EXPECTED_SOLVER_TIME_S:
        raise GuardFrontDiagnosticStop(
            "parent NPZ solver identity does not match step 451"
        )
    if not np.all(np.isfinite(U_final)):
        raise GuardFrontDiagnosticStop(
            "parent final conserved state contains nonfinite values"
        )
    rho = np.asarray(U_final[:, 0], dtype=float)
    velocity = np.asarray(U_final[:, 1] / rho, dtype=float)
    internal = np.asarray(U_final[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise GuardFrontDiagnosticStop(
            "parent final conserved state has nonpositive density or internal energy"
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise GuardFrontDiagnosticStop(
            "parent final rho*xv is not exact zero"
        )
    return summary, U_start, U_final


def _is_expected_guard(row: dict[str, Any]) -> bool:
    return bool(
        not row.get("evaluation_succeeded")
        and row.get("formal_outcome") == EXPECTED_ENDPOINT_GUARD
    )


def _require_success(row: dict[str, Any], label: str) -> None:
    if not bool(row.get("evaluation_succeeded")):
        raise GuardFrontDiagnosticStop(
            f"{label} did not succeed: "
            f"{row.get('formal_outcome')} {row.get('formal_message')}"
        )
    if not bool(row.get("local_candidate_admissible")):
        raise GuardFrontDiagnosticStop(
            f"{label} is not locally admissible"
        )
    residual = row.get("compatibility_residual_kg_s")
    if residual is None or not np.isfinite(float(residual)):
        raise GuardFrontDiagnosticStop(
            f"{label} does not have a finite compatibility residual"
        )


def _refine_guard_front(
    *,
    evaluate_offset,
    lower_guard_offset_pa: float,
    upper_success_offset_pa: float,
    back_pressure_pa: float,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
]:
    lower_offset = float(lower_guard_offset_pa)
    upper_offset = float(upper_success_offset_pa)
    lower = evaluate_offset(lower_offset)
    upper = evaluate_offset(upper_offset)
    if not _is_expected_guard(lower):
        raise GuardFrontDiagnosticStop(
            "initial lower Guard-front endpoint is not the exact retained B1 Guard"
        )
    _require_success(upper, "initial upper Guard-front endpoint")
    initial_lower = lower_offset
    initial_upper = upper_offset
    rows: list[dict[str, Any]] = []

    for iteration in range(1, GUARD_FRONT_BISECTION_ITERATIONS + 1):
        before_lower = lower_offset
        before_upper = upper_offset
        midpoint_offset = float(0.5 * (before_lower + before_upper))
        if not before_lower < midpoint_offset < before_upper:
            raise GuardFrontDiagnosticStop(
                "Guard-front midpoint did not lie strictly inside the bracket"
            )
        midpoint = evaluate_offset(midpoint_offset)
        if _is_expected_guard(midpoint):
            classification = "B1_GUARD"
            lower_offset = midpoint_offset
            lower = midpoint
        elif bool(midpoint.get("evaluation_succeeded")):
            _require_success(midpoint, f"Guard-front midpoint {iteration}")
            classification = "B1_SUCCESS"
            upper_offset = midpoint_offset
            upper = midpoint
        else:
            raise GuardFrontDiagnosticStop(
                "unexpected Guard-front midpoint result at iteration "
                f"{iteration}: {midpoint.get('formal_outcome')} "
                f"{midpoint.get('formal_message')}"
            )
        rows.append(
            {
                "iteration": iteration,
                "lower_guard_offset_before_pa": before_lower,
                "upper_success_offset_before_pa": before_upper,
                "midpoint_offset_pa": midpoint_offset,
                "midpoint_classification": classification,
                "midpoint_evaluation_succeeded": bool(
                    midpoint.get("evaluation_succeeded")
                ),
                "midpoint_formal_outcome": midpoint.get("formal_outcome"),
                "midpoint_formal_message": midpoint.get("formal_message"),
                "midpoint_stagnation_pressure_pa": midpoint.get(
                    "stagnation_pressure_pa"
                ),
                "midpoint_stagnation_pressure_margin_above_back_pa": (
                    None
                    if midpoint.get("stagnation_pressure_pa") is None
                    else float(midpoint["stagnation_pressure_pa"])
                    - back_pressure_pa
                ),
                "midpoint_compatibility_residual_kg_s": midpoint.get(
                    "compatibility_residual_kg_s"
                ),
                "lower_guard_offset_after_pa": lower_offset,
                "upper_success_offset_after_pa": upper_offset,
                "bracket_width_after_pa": float(upper_offset - lower_offset),
            }
        )

    if not _is_expected_guard(lower):
        raise GuardFrontDiagnosticStop(
            "final lower Guard-front endpoint lost the exact retained B1 Guard"
        )
    _require_success(upper, "refined first-success endpoint")
    final = {
        "initial_lower_guard_offset_pa": initial_lower,
        "initial_upper_success_offset_pa": initial_upper,
        "final_lower_guard_offset_pa": lower_offset,
        "final_upper_success_offset_pa": upper_offset,
        "final_bracket_width_pa": float(upper_offset - lower_offset),
        "refined_first_success_stagnation_pressure_pa": float(
            upper["stagnation_pressure_pa"]
        ),
        "refined_first_success_stagnation_pressure_margin_above_back_pa": float(
            upper["stagnation_pressure_pa"] - back_pressure_pa
        ),
        "refined_first_success_residual_kg_s": float(
            upper["compatibility_residual_kg_s"]
        ),
    }
    return lower, upper, rows, final


def _complete_root(
    *,
    positive: dict[str, Any],
    hook: Any,
    interior_pressure_pa: float,
    lower_success: dict[str, Any],
    upper_success: dict[str, Any],
) -> tuple[dict[str, Any], int, dict[str, float]]:
    lower_offset = float(lower_success["pressure_offset_pa"])
    upper_offset = float(upper_success["pressure_offset_pa"])
    lower_residual = float(lower_success["compatibility_residual_kg_s"])
    upper_residual = float(upper_success["compatibility_residual_kg_s"])
    bracket = {
        "lower_offset_pa": lower_offset,
        "upper_offset_pa": upper_offset,
        "lower_residual_kg_s": lower_residual,
        "upper_residual_kg_s": upper_residual,
        "linear_root_offset_estimate_pa": (
            None
            if upper_residual == lower_residual
            else float(
                lower_offset
                - lower_residual
                * (upper_offset - lower_offset)
                / (upper_residual - lower_residual)
            )
        ),
    }
    try:
        root, iterations, final_bracket = short_run._solve_first_bracket(
            bracket=bracket,
            evaluate_offset=positive["evaluate_offset"],
            root_tolerance_kg_s=float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
        )
    except Exception as exc:
        raise GuardFrontDiagnosticStop(
            f"successful-domain root bisection failed: {type(exc).__name__}: {exc}"
        ) from exc

    def evaluate_pressure(pressure_pa: float) -> dict[str, Any]:
        return positive["evaluate_offset"](
            float(pressure_pa) - float(interior_pressure_pa)
        )

    try:
        completed = horizon._complete_root_row_dynamic_v4(
            root=root,
            evaluate=evaluate_pressure,
            adapter=hook.adapter,
            area_m2=hook.area_m2,
            quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
        )
    except Exception as exc:
        raise GuardFrontDiagnosticStop(
            f"successful-domain root completion failed: {type(exc).__name__}: {exc}"
        ) from exc
    merged = dict(root)
    merged.update(completed)
    merged.update(
        {
            "bisection_iterations": int(iterations),
            "selected_initial_bracket_lower_offset_pa": lower_offset,
            "selected_initial_bracket_upper_offset_pa": upper_offset,
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
    allowed_phases = {
        normalize_phase(value)
        for value in short_run.diagnostic._family(
            contract,
            hook.state_id,
        )["allowed_normalized_phases"]
    }

    details = short_run._classification_diagnostics(
        hook=hook,
        U=U_before,
        solver_time_s=EXPECTED_SOLVER_TIME_S,
    )
    endpoint = dict(details["endpoint"])
    connected = dict(details["connected_rarefaction"])
    positive = increment_4c._permissive_positive_pressure_scan(
        hook=hook,
        U=U_before,
    )
    fixed_guard_rows = list(positive["guard_rows"])
    fixed_success_rows = list(positive["successful_rows"])
    if not fixed_guard_rows or not fixed_success_rows:
        raise GuardFrontDiagnosticStop(
            "fixed scan did not retain both Guard and successful domains"
        )
    last_fixed_guard = fixed_guard_rows[-1]
    first_fixed_success = fixed_success_rows[0]
    lower_guard, refined_success, guard_front_rows, guard_front = (
        _refine_guard_front(
            evaluate_offset=positive["evaluate_offset"],
            lower_guard_offset_pa=float(
                last_fixed_guard["pressure_offset_pa"]
            ),
            upper_success_offset_pa=float(
                first_fixed_success["pressure_offset_pa"]
            ),
            back_pressure_pa=back_pressure,
        )
    )

    refined_residual = float(
        refined_success["compatibility_residual_kg_s"]
    )
    higher_success: dict[str, Any] | None = None
    for row in fixed_success_rows:
        if float(row["pressure_offset_pa"]) <= float(
            refined_success["pressure_offset_pa"]
        ):
            continue
        residual = float(row["compatibility_residual_kg_s"])
        if residual <= root_tolerance:
            higher_success = row
            break

    root: dict[str, Any] | None = None
    root_iterations: int | None = None
    final_root_bracket: dict[str, float] = {}
    if refined_residual < -root_tolerance:
        outcome = ROOT_INSIDE_GUARD_OUTCOME
    elif higher_success is None:
        scope_residual = float(positive["scope_limit_residual_kg_s"])
        outcome = (
            FINITE_COMPRESSION_OUTCOME
            if scope_residual > root_tolerance
            else UNEXPECTED_OUTCOME
        )
    else:
        root, root_iterations, final_root_bracket = _complete_root(
            positive=positive,
            hook=hook,
            interior_pressure_pa=float(static.pressure_pa),
            lower_success=refined_success,
            upper_success=higher_success,
        )
        outcome = SUPPORTED_OUTCOME

    rho = np.asarray(U_before[:, 0], dtype=float)
    velocity = np.asarray(U_before[:, 1] / rho, dtype=float)
    internal = np.asarray(U_before[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    state_sha256_after = _array_sha256(U_before)
    state_unchanged = bool(
        np.array_equal(U_before, U_final)
        and state_sha256_before == state_sha256_after
    )
    static_pressure_margin = float(static.pressure_pa - back_pressure)
    stagnation_pressure_margin = float(
        reconstruction.stagnation_pressure_pa - back_pressure
    )
    connected_stop_reason = str(connected.get("stop_reason") or "")

    root_offset: float | None = None
    root_chi: float | None = None
    root_gate = False
    if root is not None:
        root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
        denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
        root_chi = float(root_offset / denominator)
        root_gate = bool(
            float(root["pressure_pa"]) > back_pressure
            and float(root["stagnation_pressure_pa"]) > back_pressure
            and root_offset > 0.0
            and 0.0 < root_chi <= short_run.CHI_MAX
            and abs(float(root["root_mass_residual_kg_s"])) <= root_tolerance
            and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
            and float(root["velocity_m_s"]) >= -velocity_tolerance
            and 0.0 <= float(root["mach"]) < 1.0
            and normalize_phase(str(root["phase"])) in allowed_phases
            and bool(root["stagnation_enthalpy_round_trip_passed"])
            and bool(root["energy_mass_consistency_passed"])
            and bool(root["energy_port_closure_passed"])
            and abs(float(root["momentum_ledger_residual_N"]))
            <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
        )

    checks = {
        "parent_increment_4d_stop_verified": bool(
            parent_summary["solver_step_after"] == EXPECTED_SOLVER_STEP
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
        "all_density_positive": bool(np.all(rho > 0.0)),
        "all_internal_energy_positive": bool(np.all(internal > 0.0)),
        "endpoint_exact_reverse_pressure_guard": bool(
            not endpoint.get("evaluation_succeeded")
            and endpoint.get("formal_outcome") == EXPECTED_ENDPOINT_GUARD
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
        "fixed_scan_has_guard_and_success_domains": bool(
            fixed_guard_rows and fixed_success_rows
        ),
        "guard_front_bisection_completed": bool(
            len(guard_front_rows) == GUARD_FRONT_BISECTION_ITERATIONS
        ),
        "final_guard_endpoint_retained": bool(
            _is_expected_guard(lower_guard)
        ),
        "refined_success_endpoint_valid": bool(
            refined_success.get("evaluation_succeeded")
            and refined_success.get("local_candidate_admissible")
        ),
        "refined_success_stagnation_pressure_above_back": bool(
            float(refined_success["stagnation_pressure_pa"]) > back_pressure
        ),
        "refined_success_residual_not_negative_beyond_tolerance": bool(
            refined_residual >= -root_tolerance
        ),
        "higher_success_negative_or_within_tolerance": bool(
            higher_success is not None
            and float(higher_success["compatibility_residual_kg_s"])
            <= root_tolerance
        ),
        "root_gate_passed": bool(root_gate),
        "state_unchanged": state_unchanged,
        "fvm_step_452_attempted": False,
    }
    supported_gate = bool(
        outcome == SUPPORTED_OUTCOME
        and all(
            value
            for key, value in checks.items()
            if key != "fvm_step_452_attempted"
        )
        and checks["fvm_step_452_attempted"] is False
    )

    if root is None:
        root_row: dict[str, Any] = {
            "requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
            "solver_time_s": EXPECTED_SOLVER_TIME_S,
            "diagnostic_outcome": outcome,
            "refined_first_success_offset_pa": float(
                refined_success["pressure_offset_pa"]
            ),
            "refined_first_success_residual_kg_s": refined_residual,
            "higher_success_offset_pa": (
                None
                if higher_success is None
                else float(higher_success["pressure_offset_pa"])
            ),
            "higher_success_residual_kg_s": (
                None
                if higher_success is None
                else float(higher_success["compatibility_residual_kg_s"])
            ),
            "fvm_step_452_attempted": False,
            "state_unchanged": state_unchanged,
        }
    else:
        root_row = dict(root)
        root_row.update(
            {
                "requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
                "solver_time_s": EXPECTED_SOLVER_TIME_S,
                "diagnostic_outcome": outcome,
                "interior_pressure_pa": float(static.pressure_pa),
                "interior_stagnation_pressure_pa": float(
                    reconstruction.stagnation_pressure_pa
                ),
                "back_pressure_pa": back_pressure,
                "p_P_minus_p_i_pa": root_offset,
                "root_chi": root_chi,
                "chi_max": short_run.CHI_MAX,
                "bisection_iterations": root_iterations,
                **final_root_bracket,
                "fvm_step_452_attempted": False,
                "state_unchanged": state_unchanged,
            }
        )

    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4e"
        ),
        "scope": "model_review_diagnostic_only_b1_guard_front_root",
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
        "minimum_density_kg_m3": float(np.min(rho)),
        "minimum_internal_energy_J_kg": float(np.min(internal)),
        "endpoint_evaluation_succeeded": bool(
            endpoint.get("evaluation_succeeded")
        ),
        "endpoint_formal_outcome": endpoint.get("formal_outcome"),
        "endpoint_formal_message": endpoint.get("formal_message"),
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
        "fixed_positive_scan_guard_node_count": len(fixed_guard_rows),
        "fixed_positive_scan_success_node_count": len(fixed_success_rows),
        "last_fixed_guard_offset_pa": float(
            last_fixed_guard["pressure_offset_pa"]
        ),
        "first_fixed_success_offset_pa": float(
            first_fixed_success["pressure_offset_pa"]
        ),
        "guard_front_bisection_iterations": GUARD_FRONT_BISECTION_ITERATIONS,
        **guard_front,
        "refined_first_success_offset_pa": float(
            refined_success["pressure_offset_pa"]
        ),
        "refined_first_success_residual_kg_s": refined_residual,
        "higher_success_offset_pa": (
            None
            if higher_success is None
            else float(higher_success["pressure_offset_pa"])
        ),
        "higher_success_residual_kg_s": (
            None
            if higher_success is None
            else float(higher_success["compatibility_residual_kg_s"])
        ),
        "successful_domain_sign_change_count": (
            1 if root is not None else 0
        ),
        "positive_scan_delta_p_max_pa": float(positive["delta_p_max_pa"]),
        "positive_scan_scope_limit_residual_kg_s": float(
            positive["scope_limit_residual_kg_s"]
        ),
        "root_pressure_pa": None if root is None else float(root["pressure_pa"]),
        "root_pressure_offset_pa": root_offset,
        "root_chi": root_chi,
        "chi_max": short_run.CHI_MAX,
        "root_mass_residual_kg_s": (
            None if root is None else float(root["root_mass_residual_kg_s"])
        ),
        "root_local_slope_kg_s_Pa": (
            None
            if root is None
            else float(root["local_residual_slope_kg_s_Pa"])
        ),
        "root_velocity_m_s": (
            None if root is None else float(root["velocity_m_s"])
        ),
        "root_mach": None if root is None else float(root["mach"]),
        "root_phase": None if root is None else str(root["phase"]),
        "root_b1_formal_outcome": (
            None if root is None else root["formal_outcome"]
        ),
        "root_stagnation_pressure_pa": (
            None if root is None else float(root["stagnation_pressure_pa"])
        ),
        "root_stagnation_pressure_margin_above_back_pa": (
            None
            if root is None
            else float(root["stagnation_pressure_pa"] - back_pressure)
        ),
        "root_restriction_reaction_ledger_residual_N": (
            None
            if root is None
            else float(root["momentum_ledger_residual_N"])
        ),
        "root_energy_port_residual_W": (
            None if root is None else float(root["energy_port_residual_W"])
        ),
        "root_bisection_iterations": root_iterations,
        "checks": checks,
        "outcome": outcome,
        "increment_4e_continuation_supported": supported_gate,
        "increment_4e_diagnostic_classification_complete": bool(
            outcome
            in {
                SUPPORTED_OUTCOME,
                ROOT_INSIDE_GUARD_OUTCOME,
                FINITE_COMPRESSION_OUTCOME,
            }
        ),
        "fvm_step_452_attempted": False,
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
    return (
        summary,
        list(details["local_scan_rows"]),
        list(positive["rows"]),
        guard_front_rows,
        root_row,
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

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    parent_summary, _, U_final = _verify_parent_artifact(
        args.parent_artifact_dir,
        parent_artifact_digest=args.parent_artifact_digest,
    )
    summary, local_rows, positive_rows, guard_rows, root_row = _run_diagnostic(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_final=U_final,
    )
    summary["source_git_sha"] = args.source_git_sha

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "step451_local_wave_scans.csv", local_rows)
    _write_csv(output / "step451_fixed_positive_pressure_scans.csv", positive_rows)
    _write_csv(output / "step451_guard_front_bisection.csv", guard_rows)
    _write_csv(output / "step451_refined_success_root.csv", [root_row])
    np.savez_compressed(
        output / "step451_state_identity.npz",
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
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 4E\n\n"
        "MODEL_REVIEW / DIAGNOSTIC_ONLY evidence. The authoritative step-451 "
        "state was loaded without mutation. The unchanged fixed scan was "
        "retained, the exact B1 Guard-to-success front was categorically "
        "refined for 32 iterations, and only successful B1 states were used "
        "to test the compatibility-root bracket. FvmSolver step 452 was not "
        "attempted. Formal project states remain unchanged.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step451_local_wave_scans.csv",
        "step451_fixed_positive_pressure_scans.csv",
        "step451_guard_front_bisection.csv",
        "step451_refined_success_root.csv",
        "step451_state_identity.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4e_diagnostic_classification_complete"]:
        raise SystemExit("Increment 4E diagnostic classification was inconclusive")
    if not summary["increment_4e_continuation_supported"]:
        raise SystemExit(
            "Increment 4E did not support continuation: "
            f"{summary['outcome']}"
        )


if __name__ == "__main__":
    main()
