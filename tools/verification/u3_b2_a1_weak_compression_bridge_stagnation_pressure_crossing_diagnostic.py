from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


PARENT_SOURCE_SHA = "532ba7388915e8d484aae5a65de87dc760c200aa"
PARENT_WORKFLOW_RUN = 31614869209
PARENT_JOB = 94175042813
PARENT_ARTIFACT = 9148819125
PARENT_ARTIFACT_SHA256 = (
    "71f1e2bfa2959f526466a0effbfd8daaa50e56d416f37697679d829b69c26437"
)
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-weak-compression-bridge-increment-4b-31614869209"
)
EXPECTED_SOLVER_STEP = 447
EXPECTED_SOLVER_TIME_S = 0.002995130267713174
NEXT_REQUESTED_SOLVER_STEP = 448
EXPECTED_ENDPOINT_GUARD = "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"
PASS_OUTCOME = "STAGNATION_PRESSURE_CROSSING_POSITIVE_ROOT_SUPPORTED"
FAIL_OUTCOME = "STAGNATION_PRESSURE_CROSSING_REQUIRES_PHYSICS_REVIEW"
SCAN_CORRECTION = (
    "requested_scan_coordinate_authoritative_expected_leading_b1_guards"
)
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


class StagnationPressureCrossingDiagnosticStop(RuntimeError):
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
        raise StagnationPressureCrossingDiagnosticStop(
            "parent GitHub artifact digest does not match the fixed Increment 4B "
            f"digest: {parent_artifact_digest}"
        )
    actual_files = {path.name for path in parent_dir.iterdir() if path.is_file()}
    if actual_files != PARENT_REQUIRED_FILES:
        raise StagnationPressureCrossingDiagnosticStop(
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
        raise StagnationPressureCrossingDiagnosticStop(
            "parent internal manifest names do not match the fixed file set"
        )
    for name, digest in manifest.items():
        actual = _sha256(parent_dir / name)
        if actual != digest:
            raise StagnationPressureCrossingDiagnosticStop(
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
            "BackPressureCrossingContinuationStop: neutral endpoint evaluation "
            "did not succeed"
        ),
    }
    for key, expected in required_summary.items():
        if summary.get(key) != expected:
            raise StagnationPressureCrossingDiagnosticStop(
                f"parent summary mismatch for {key}: {summary.get(key)!r}"
            )
    if int(summary.get("continuation_accepted_steps_completed", -1)) != 78:
        raise StagnationPressureCrossingDiagnosticStop(
            "parent continuation accepted-step count is not 78"
        )
    if bool(summary.get("clear_branch_chatter_detected")):
        raise StagnationPressureCrossingDiagnosticStop(
            "parent evidence reports clear branch chatter"
        )

    with np.load(parent_dir / "full_horizon_states.npz") as states:
        U_start = np.asarray(states["U_start"], dtype=float).copy()
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_start.shape != (32, 4) or U_final.shape != (32, 4):
        raise StagnationPressureCrossingDiagnosticStop(
            "parent conserved-state shape is not (32, 4)"
        )
    if step_after != EXPECTED_SOLVER_STEP or time_after != EXPECTED_SOLVER_TIME_S:
        raise StagnationPressureCrossingDiagnosticStop(
            "parent NPZ solver identity does not match step 447"
        )
    if not np.all(np.isfinite(U_final)):
        raise StagnationPressureCrossingDiagnosticStop(
            "parent final conserved state contains nonfinite values"
        )
    rho = np.asarray(U_final[:, 0], dtype=float)
    velocity = np.asarray(U_final[:, 1] / rho, dtype=float)
    internal = np.asarray(U_final[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise StagnationPressureCrossingDiagnosticStop(
            "parent final conserved state has nonpositive density or internal energy"
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise StagnationPressureCrossingDiagnosticStop(
            "parent final rho*xv is not exact zero"
        )
    return summary, U_start, U_final


def _permissive_positive_pressure_scan(
    *,
    hook: Any,
    U: np.ndarray,
) -> dict[str, Any]:
    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    allowed_phases = {
        normalize_phase(value)
        for value in short_run.diagnostic._family(
            hook.contract,
            hook.state_id,
        )["allowed_normalized_phases"]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    short_run.diagnostic.QUADRATURE_ORDER = (
        short_run.horizon.ROOT_QUADRATURE_ORDER
    )
    isentrope = short_run.diagnostic.Isentrope(
        float(static.entropy_J_kg_K)
    )
    density = float(static.density_kg_m3)
    sound_speed = float(static.sound_speed_m_s)
    denominator = float(density * sound_speed**2)
    delta_p_max = float(denominator * short_run.CHI_MAX)
    offsets = short_run._positive_scan_offsets(delta_p_max)
    cache: dict[float, dict[str, Any]] = {}

    def evaluate_offset(offset_pa: float) -> dict[str, Any]:
        key = float(offset_pa)
        if key not in cache:
            candidate_pressure = float(static.pressure_pa + key)
            raw = short_run._full_wave_row(
                pressure_pa=candidate_pressure,
                static=static,
                isentrope=isentrope,
                hook=hook,
                area_m2=hook.area_m2,
                allowed_phases=allowed_phases,
                velocity_tolerance=velocity_tolerance,
                state_id=hook.state_id,
            )
            realized_offset = float(raw["pressure_offset_pa"])
            requested_chi = float(
                short_run.CHI_MAX
                if key == delta_p_max
                else key / denominator
            )
            realized_chi = float(realized_offset / denominator)
            expected_guard = bool(
                not raw.get("evaluation_succeeded")
                and raw.get("formal_outcome") == EXPECTED_ENDPOINT_GUARD
            )
            item = dict(raw)
            item.update(
                {
                    "pressure_offset_pa": key,
                    "requested_pressure_offset_pa": key,
                    "realized_pressure_offset_pa": realized_offset,
                    "requested_pressure_pa": candidate_pressure,
                    "realized_pressure_pa": float(raw["pressure_pa"]),
                    "chi": requested_chi,
                    "requested_chi": requested_chi,
                    "realized_chi": realized_chi,
                    "chi_max": short_run.CHI_MAX,
                    "within_weak_compression_scope": bool(
                        key == 0.0 or 0.0 < key <= delta_p_max
                    ),
                    "expected_leading_b1_guard": expected_guard,
                    "scan_coordinate_correction": SCAN_CORRECTION,
                    "selected_sign_change_bracket_member": False,
                }
            )
            cache[key] = item
        return dict(cache[key])

    rows = [evaluate_offset(offset) for offset in offsets]
    success_seen = False
    guard_rows: list[dict[str, Any]] = []
    successful_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not bool(row["within_weak_compression_scope"]):
            raise StagnationPressureCrossingDiagnosticStop(
                f"positive-pressure scan node {index} exceeds fixed chi scope"
            )
        if bool(row.get("evaluation_succeeded")):
            success_seen = True
            if not bool(row.get("local_candidate_admissible")):
                raise StagnationPressureCrossingDiagnosticStop(
                    f"successful positive-pressure scan node {index} is inadmissible"
                )
            residual = row.get("compatibility_residual_kg_s")
            if residual is None or not np.isfinite(float(residual)):
                raise StagnationPressureCrossingDiagnosticStop(
                    f"successful positive-pressure scan node {index} has no finite residual"
                )
            successful_rows.append(row)
            continue
        if not bool(row.get("expected_leading_b1_guard")):
            raise StagnationPressureCrossingDiagnosticStop(
                "unexpected positive-pressure scan failure at node "
                f"{index}: {row.get('formal_outcome')} {row.get('formal_message')}"
            )
        if success_seen:
            raise StagnationPressureCrossingDiagnosticStop(
                "a B1 Guard node occurred after the positive scan became successful"
            )
        guard_rows.append(row)

    if not guard_rows:
        raise StagnationPressureCrossingDiagnosticStop(
            "the positive scan did not begin with the expected B1 Guard domain"
        )
    if len(successful_rows) < 2:
        raise StagnationPressureCrossingDiagnosticStop(
            "positive scan has fewer than two successful admissible nodes"
        )
    if not float(successful_rows[0]["stagnation_pressure_pa"]) > float(
        hook.adapter.back_pressure_pa
    ):
        raise StagnationPressureCrossingDiagnosticStop(
            "first successful positive scan node does not have stagnation pressure above back"
        )

    evaluable = short_run._brackets(successful_rows, admissible_only=False)
    admissible = short_run._brackets(successful_rows, admissible_only=True)
    if len(evaluable) != len(admissible):
        raise StagnationPressureCrossingDiagnosticStop(
            "a successful positive-pressure root bracket is inadmissible"
        )
    if len(admissible) > 1:
        raise StagnationPressureCrossingDiagnosticStop(
            "multiple positive-pressure root brackets were observed"
        )

    selected_offsets: set[float] = set()
    if admissible:
        selected_offsets = {
            float(admissible[0]["lower_offset_pa"]),
            float(admissible[0]["upper_offset_pa"]),
        }
    annotated = [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["pressure_offset_pa"]) in selected_offsets
            ),
        }
        for row in rows
    ]
    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in successful_rows
    ]
    monotone_nonincreasing = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    return {
        "static": static,
        "rows": annotated,
        "guard_rows": guard_rows,
        "successful_rows": successful_rows,
        "evaluate_offset": evaluate_offset,
        "evaluable_brackets": evaluable,
        "admissible_brackets": admissible,
        "sign_change_count": len(admissible),
        "residual_monotone_nonincreasing": monotone_nonincreasing,
        "delta_p_max_pa": delta_p_max,
        "guard_node_count": len(guard_rows),
        "first_guard_offset_pa": float(guard_rows[0]["pressure_offset_pa"]),
        "last_guard_offset_pa": float(guard_rows[-1]["pressure_offset_pa"]),
        "first_success_offset_pa": float(
            successful_rows[0]["pressure_offset_pa"]
        ),
        "first_success_stagnation_pressure_pa": float(
            successful_rows[0]["stagnation_pressure_pa"]
        ),
        "scope_limit_residual_kg_s": float(residuals[-1]),
        "scan_coordinate_correction": SCAN_CORRECTION,
    }


def _complete_root(
    *,
    positive: dict[str, Any],
    hook: Any,
    interior_pressure_pa: float,
) -> tuple[dict[str, Any], int, dict[str, float]]:
    brackets = list(positive["admissible_brackets"])
    if len(brackets) != 1:
        raise StagnationPressureCrossingDiagnosticStop(
            "positive-pressure diagnostic did not retain exactly one root bracket"
        )
    try:
        root, iterations, final_bracket = short_run._solve_first_bracket(
            bracket=brackets[0],
            evaluate_offset=positive["evaluate_offset"],
            root_tolerance_kg_s=float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
        )
    except Exception as exc:
        raise StagnationPressureCrossingDiagnosticStop(
            f"positive-pressure root bisection failed: {type(exc).__name__}: {exc}"
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
        raise StagnationPressureCrossingDiagnosticStop(
            f"positive-pressure root completion failed: {type(exc).__name__}: {exc}"
        ) from exc
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
    positive = _permissive_positive_pressure_scan(hook=hook, U=U_before)

    root: dict[str, Any] | None = None
    iterations: int | None = None
    final_bracket: dict[str, float] = {}
    if int(positive["sign_change_count"]) == 1:
        root, iterations, final_bracket = _complete_root(
            positive=positive,
            hook=hook,
            interior_pressure_pa=float(static.pressure_pa),
        )

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
    root_phase_allowed = False
    root_gate = False
    if root is not None:
        root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
        denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
        root_chi = float(root_offset / denominator)
        root_phase_allowed = bool(
            normalize_phase(str(root["phase"])) in allowed_phases
        )
        root_gate = bool(
            float(root["pressure_pa"]) > back_pressure
            and float(root["stagnation_pressure_pa"]) > back_pressure
            and root_offset > 0.0
            and 0.0 < root_chi <= short_run.CHI_MAX
            and abs(float(root["root_mass_residual_kg_s"])) <= root_tolerance
            and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
            and float(root["velocity_m_s"]) >= -velocity_tolerance
            and 0.0 <= float(root["mach"]) < 1.0
            and root_phase_allowed
            and bool(root["stagnation_enthalpy_round_trip_passed"])
            and bool(root["energy_mass_consistency_passed"])
            and bool(root["energy_port_closure_passed"])
            and abs(float(root["momentum_ledger_residual_N"]))
            <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
        )

    checks = {
        "parent_increment_4b_stop_verified": bool(
            parent_summary["solver_step_after"] == EXPECTED_SOLVER_STEP
        ),
        "static_pressure_at_or_below_back": bool(
            float(static.pressure_pa) <= back_pressure
        ),
        "stagnation_pressure_at_or_below_back": bool(
            float(reconstruction.stagnation_pressure_pa) <= back_pressure
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
        "endpoint_evaluation_failed": bool(
            not endpoint.get("evaluation_succeeded")
        ),
        "endpoint_exact_reverse_pressure_guard": bool(
            endpoint.get("formal_outcome") == EXPECTED_ENDPOINT_GUARD
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
        "positive_scan_has_leading_guard_nodes": bool(
            int(positive["guard_node_count"]) > 0
        ),
        "positive_scan_has_success_domain": bool(
            len(positive["successful_rows"]) >= 2
        ),
        "positive_scan_unique_root": bool(
            int(positive["sign_change_count"]) == 1
        ),
        "positive_scan_monotone": bool(
            positive["residual_monotone_nonincreasing"]
        ),
        "first_success_stagnation_pressure_above_back": bool(
            float(positive["first_success_stagnation_pressure_pa"])
            > back_pressure
        ),
        "root_gate_passed": root_gate,
        "state_unchanged": state_unchanged,
        "fvm_step_448_attempted": False,
    }
    gate_passed = bool(
        all(
            value
            for key, value in checks.items()
            if key != "fvm_step_448_attempted"
        )
        and checks["fvm_step_448_attempted"] is False
    )
    outcome = PASS_OUTCOME if gate_passed else FAIL_OUTCOME

    root_row: dict[str, Any]
    if root is None:
        root_row = {
            "requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
            "solver_time_s": EXPECTED_SOLVER_TIME_S,
            "branch_classification": "NO_ROOT_DIAGNOSTIC_STOP",
            "fvm_step_448_attempted": False,
            "state_unchanged": state_unchanged,
        }
    else:
        root_row = dict(root)
        root_row.update(
            {
                "requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
                "solver_time_s": EXPECTED_SOLVER_TIME_S,
                "branch_classification": (
                    "WEAK_COMPRESSION_CANDIDATE_DIAGNOSTIC_ONLY"
                ),
                "interior_pressure_pa": float(static.pressure_pa),
                "interior_stagnation_pressure_pa": float(
                    reconstruction.stagnation_pressure_pa
                ),
                "back_pressure_pa": back_pressure,
                "p_P_minus_p_i_pa": root_offset,
                "root_chi": root_chi,
                "chi_max": short_run.CHI_MAX,
                "bisection_iterations": iterations,
                **final_bracket,
                "fvm_step_448_attempted": False,
                "state_unchanged": state_unchanged,
            }
        )

    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4c"
        ),
        "scope": "model_review_diagnostic_only_stagnation_pressure_crossing",
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
        "positive_scan_guard_node_count": int(positive["guard_node_count"]),
        "positive_scan_first_guard_offset_pa": float(
            positive["first_guard_offset_pa"]
        ),
        "positive_scan_last_guard_offset_pa": float(
            positive["last_guard_offset_pa"]
        ),
        "positive_scan_first_success_offset_pa": float(
            positive["first_success_offset_pa"]
        ),
        "positive_scan_first_success_stagnation_pressure_pa": float(
            positive["first_success_stagnation_pressure_pa"]
        ),
        "positive_scan_successful_node_count": len(
            positive["successful_rows"]
        ),
        "positive_scan_sign_change_count": int(
            positive["sign_change_count"]
        ),
        "positive_scan_residual_monotone_nonincreasing": bool(
            positive["residual_monotone_nonincreasing"]
        ),
        "positive_scan_delta_p_max_pa": float(positive["delta_p_max_pa"]),
        "scan_coordinate_correction": positive["scan_coordinate_correction"],
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
        "bisection_iterations": iterations,
        "checks": checks,
        "outcome": outcome,
        "increment_4c_diagnostic_gate_passed": gate_passed,
        "fvm_step_448_attempted": False,
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
    _write_csv(output / "step447_local_wave_scans.csv", local_rows)
    _write_csv(output / "step447_positive_pressure_scans.csv", positive_rows)
    _write_csv(output / "step447_weak_compression_root.csv", [root_row])
    np.savez_compressed(
        output / "step447_state_identity.npz",
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
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 4C\n\n"
        "MODEL_REVIEW / DIAGNOSTIC_ONLY evidence. The authoritative step-447 "
        "state was loaded without mutation. Leading positive-pressure states "
        "refused by the unchanged B1 reverse-pressure Guard were recorded, "
        "and the later admissible positive-pressure domain was inspected for "
        "one in-scope Weak Compression root. FvmSolver step 448 was not "
        "attempted. A passing result does not authorize continuation, verify "
        "finite-pipe coupling, accept a benchmark, perform Physical Validation, "
        "approve design use, or activate production behavior.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step447_local_wave_scans.csv",
        "step447_positive_pressure_scans.csv",
        "step447_weak_compression_root.csv",
        "step447_state_identity.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4c_diagnostic_gate_passed"]:
        raise SystemExit(
            "Increment 4C stagnation-pressure crossing diagnostic did not pass"
        )


if __name__ == "__main__":
    main()
