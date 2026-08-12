from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_full_horizon as full_horizon
import u3_b2_a1_weak_compression_bridge_one_step as one_step
import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase


INCREMENT_4A_SOURCE_SHA = "bee4b753bf6ab3563f57f82aceb9012fcfc82111"
INCREMENT_4A_WORKFLOW_RUN = 31614026739
INCREMENT_4A_JOB = 94172200536
INCREMENT_4A_ARTIFACT = 9148419818
INCREMENT_4A_ARTIFACT_SHA256 = (
    "0db60a1c3b3d0a3d42adf1627d170df6085267ac5ade484682e9925475e54cfe"
)
INCREMENT_4A_OUTCOME = (
    "BACK_PRESSURE_CROSSING_BRANCH_DOMAIN_CORRECTION_SUPPORTED"
)
FAILED_INCREMENT_4_SOURCE_SHA = "2e9e2c1c3d01fd66d82b3a2ecb036b811e0469b0"
FAILED_INCREMENT_4_WORKFLOW_RUN = 31606368597
FAILED_INCREMENT_4_JOB = 94146232478
FAILED_INCREMENT_4_ARTIFACT = 9145306448
FAILED_INCREMENT_4_ARTIFACT_SHA256 = (
    "633bffda60db2a886066772e693f83b5d1e4fd8887526d717637232ac7b3a35b"
)
FIRST_CORRECTION_REQUESTED_STEP = 444
OUTCOME = "WEAK_COMPRESSION_INCREMENT_4B_FULL_HORIZON_WORKING_SLICE_PASS"
robustness = robustness_v4.robustness

_ORIGINAL_BUILD_WEAK_COMPRESSION_CONTEXT = (
    short_run._build_weak_compression_context
)
_ORIGINAL_SOLVE_THREE_BRANCH_BOUNDARY = short_run._solve_three_branch_boundary
_ORIGINAL_ROOT_EVIDENCE_ROW = short_run._root_evidence_row


class BackPressureCrossingContinuationStop(
    short_run.WeakCompressionShortRunStop
):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_increment_4a_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    if artifact_digest != INCREMENT_4A_ARTIFACT_SHA256:
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            "Increment 4A GitHub artifact digest mismatch",
        )
    required = {
        "step443_local_wave_scans.csv",
        "step443_positive_pressure_scans.csv",
        "step443_weak_compression_root.csv",
        "step443_state_identity.npz",
        "summary.json",
        "report.md",
        "artifact_sha256.txt",
    }
    actual = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    if actual != required:
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            f"Increment 4A file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (artifact_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != required - {"artifact_sha256.txt"}:
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            "Increment 4A internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(artifact_dir / name) != digest:
            raise BackPressureCrossingContinuationStop(
                "INCREMENT_4A_AUTHORITY_MISMATCH",
                f"Increment 4A internal SHA256 mismatch for {name}",
            )
    summary = json.loads(
        (artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    if summary.get("source_git_sha") != INCREMENT_4A_SOURCE_SHA:
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            "Increment 4A source SHA mismatch",
        )
    if summary.get("outcome") != INCREMENT_4A_OUTCOME or not bool(
        summary.get("increment_4a_diagnostic_gate_passed")
    ):
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            "Increment 4A diagnostic outcome or gate mismatch",
        )
    if int(summary.get("solver_step_loaded", -1)) != 443:
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            "Increment 4A did not diagnose step 443",
        )
    if bool(summary.get("fvm_step_444_attempted")):
        raise BackPressureCrossingContinuationStop(
            "INCREMENT_4A_AUTHORITY_MISMATCH",
            "Increment 4A unexpectedly attempted step 444",
        )
    return summary


def _verify_failed_increment_4_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    if artifact_digest != FAILED_INCREMENT_4_ARTIFACT_SHA256:
        raise BackPressureCrossingContinuationStop(
            "FAILED_INCREMENT_4_AUTHORITY_MISMATCH",
            "failed Increment 4 GitHub artifact digest mismatch",
        )
    required = {
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
    actual = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    if actual != required:
        raise BackPressureCrossingContinuationStop(
            "FAILED_INCREMENT_4_AUTHORITY_MISMATCH",
            f"failed Increment 4 file set mismatch: {sorted(actual)}",
        )
    summary = json.loads(
        (artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    if summary.get("source_git_sha") != FAILED_INCREMENT_4_SOURCE_SHA:
        raise BackPressureCrossingContinuationStop(
            "FAILED_INCREMENT_4_AUTHORITY_MISMATCH",
            "failed Increment 4 source SHA mismatch",
        )
    if summary.get("outcome") != "INCREMENT_4_STOPPED":
        raise BackPressureCrossingContinuationStop(
            "FAILED_INCREMENT_4_AUTHORITY_MISMATCH",
            "failed Increment 4 outcome mismatch",
        )
    if int(summary.get("solver_step_after", -1)) != 443:
        raise BackPressureCrossingContinuationStop(
            "FAILED_INCREMENT_4_AUTHORITY_MISMATCH",
            "failed Increment 4 did not stop after step 443",
        )
    return summary


def _corrected_build_weak_compression_context(
    *,
    contract: dict[str, Any],
    state_id: str,
    provider: Any,
    hook: Any,
    outlet_conserved: np.ndarray,
    solver_time_s: float,
    increment_1_root: dict[str, Any],
    increment_1_scan_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reconstruction = provider.reconstruct_from_conserved(outlet_conserved)
    static = reconstruction.static
    back_pressure = float(hook.adapter.back_pressure_pa)
    if float(static.pressure_pa) > back_pressure:
        context = _ORIGINAL_BUILD_WEAK_COMPRESSION_CONTEXT(
            contract=contract,
            state_id=state_id,
            provider=provider,
            hook=hook,
            outlet_conserved=outlet_conserved,
            solver_time_s=solver_time_s,
            increment_1_root=increment_1_root,
            increment_1_scan_rows=increment_1_scan_rows,
        )
        context.update(
            {
                "back_pressure_crossing_correction_applied": False,
                "rarefaction_domain_available": True,
                "rarefaction_domain_reason": None,
                "interior_static_pressure_minus_back_pa": float(
                    static.pressure_pa - back_pressure
                ),
                "interior_stagnation_pressure_minus_back_pa": float(
                    reconstruction.stagnation_pressure_pa - back_pressure
                ),
                "root_static_pressure_minus_back_pa": float(
                    context["root"]["pressure_pa"] - back_pressure
                ),
            }
        )
        return context

    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if normalize_phase(static.phase) not in allowed_phases:
        raise one_step.WeakCompressionOneStepStop(
            f"interior phase {static.phase!r} is outside {sorted(allowed_phases)}"
        )
    if float(static.velocity_m_s) < -velocity_tolerance:
        raise one_step.WeakCompressionOneStepStop(
            f"interior outlet velocity is reverse-directed: {static.velocity_m_s}"
        )
    if not float(reconstruction.stagnation_pressure_pa) > back_pressure:
        raise one_step.WeakCompressionOneStepStop(
            "interior stagnation pressure is not above retained back pressure"
        )

    tolerances = contract["acceptance_tolerances"]
    if abs(float(reconstruction.enthalpy_round_trip_residual_J_kg)) > float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    ) or abs(float(reconstruction.entropy_round_trip_residual_J_kg_K)) > float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    ):
        raise one_step.WeakCompressionOneStepStop(
            "interior stagnation-state round trip exceeds locked tolerance"
        )

    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))

    def evaluate(pressure_pa: float) -> dict[str, Any]:
        return one_step._full_wave_row(
            pressure_pa=float(pressure_pa),
            static=static,
            isentrope=isentrope,
            hook=hook,
            area_m2=hook.area_m2,
            allowed_phases=allowed_phases,
            velocity_tolerance=velocity_tolerance,
            state_id=state_id,
        )

    root_pressure = float(increment_1_root["pressure_pa"])
    raw_root = evaluate(root_pressure)
    if not bool(raw_root.get("evaluation_succeeded")):
        raise one_step.WeakCompressionOneStepStop(
            "corrected Weak Compression root evaluation failed: "
            f"{raw_root.get('formal_outcome')} {raw_root.get('formal_message')}"
        )
    if not bool(raw_root.get("local_candidate_admissible")):
        raise one_step.WeakCompressionOneStepStop(
            "corrected Weak Compression root is inadmissible"
        )
    if not float(raw_root["pressure_pa"]) > back_pressure:
        raise one_step.WeakCompressionOneStepStop(
            "corrected Weak Compression root pressure is not above back pressure"
        )

    completed = horizon._complete_root_row_dynamic_v4(
        root=raw_root,
        evaluate=evaluate,
        adapter=hook.adapter,
        area_m2=hook.area_m2,
        quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
    )
    root = dict(raw_root)
    root.update(completed)
    root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    root_chi = float(root_offset / denominator)
    root.update(
        {
            "branch_classification": "WEAK_COMPRESSION",
            "p_P_minus_p_i_pa": root_offset,
            "chi": root_chi,
            "chi_max": short_run.CHI_MAX,
            "increment_1_bisection_iterations": int(
                increment_1_root["bisection_iterations"]
            ),
        }
    )

    if not root_offset > 0.0:
        raise one_step.WeakCompressionOneStepStop(
            "corrected Weak Compression root is not above the endpoint"
        )
    if not 0.0 < root_chi <= short_run.CHI_MAX:
        raise one_step.WeakCompressionOneStepStop(
            f"corrected Weak Compression root chi is outside scope: {root_chi}"
        )
    if abs(float(root["root_mass_residual_kg_s"])) > float(
        robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    ):
        raise one_step.WeakCompressionOneStepStop(
            "corrected root mass residual exceeds retained tolerance"
        )
    if float(root["local_residual_slope_kg_s_Pa"]) >= 0.0:
        raise one_step.WeakCompressionOneStepStop(
            "corrected root local residual slope is not negative"
        )
    if float(root["velocity_m_s"]) < -velocity_tolerance:
        raise one_step.WeakCompressionOneStepStop(
            "corrected root velocity is reverse-directed"
        )
    if not 0.0 <= float(root["mach"]) < 1.0:
        raise one_step.WeakCompressionOneStepStop(
            "corrected root is outside the subsonic branch"
        )
    if normalize_phase(str(root["phase"])) not in allowed_phases:
        raise one_step.WeakCompressionOneStepStop(
            "corrected root phase is outside the allowed liquid scope"
        )
    if not bool(root["stagnation_enthalpy_round_trip_passed"]):
        raise one_step.WeakCompressionOneStepStop(
            "corrected root stagnation-enthalpy round trip failed"
        )
    if not bool(root["energy_mass_consistency_passed"]):
        raise one_step.WeakCompressionOneStepStop(
            "corrected root energy/mass decomposition failed"
        )
    if not bool(root["energy_port_closure_passed"]):
        raise one_step.WeakCompressionOneStepStop(
            "corrected root energy-port closure failed"
        )
    if abs(float(root["momentum_ledger_residual_N"])) > float(
        robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    ):
        raise one_step.WeakCompressionOneStepStop(
            "corrected root restriction-reaction ledger failed"
        )

    mass_rate = float(root["pipe_mass_rate_kg_s"])
    velocity = float(root["velocity_m_s"])
    pressure = float(root["pressure_pa"])
    h0 = float(root["h0_J_kg"])
    flux = np.asarray(
        [
            mass_rate / hook.area_m2,
            (mass_rate * velocity + pressure * hook.area_m2) / hook.area_m2,
            mass_rate * h0 / hook.area_m2,
            0.0,
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(flux)):
        raise one_step.WeakCompressionOneStepStop(
            "corrected Weak Compression pipe-side flux is nonfinite"
        )

    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in increment_1_scan_rows
        if row.get("evaluation_succeeded")
    ]
    positive_residual_monotone = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    admissible_nodes = sum(
        bool(row.get("local_candidate_admissible"))
        for row in increment_1_scan_rows
    )
    return {
        "solver_time_s": float(solver_time_s),
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "interior_phase": static.phase,
        "interior_h0_round_trip_residual_J_kg": float(
            reconstruction.enthalpy_round_trip_residual_J_kg
        ),
        "interior_s0_round_trip_residual_J_kg_K": float(
            reconstruction.entropy_round_trip_residual_J_kg_K
        ),
        "connected_scan_base_node_count": len(increment_1_scan_rows),
        "connected_scan_requested_nodes": len(increment_1_scan_rows),
        "connected_scan_admissible_subsonic_nodes": int(admissible_nodes),
        "connected_scan_lowest_pressure_pa": float(static.pressure_pa),
        "connected_scan_stop_reason": None,
        "connected_scan_residual_monotone": positive_residual_monotone,
        "connected_scan_sign_change_count": 1,
        "root": root,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
        "branch_classification": "WEAK_COMPRESSION",
        "root_chi": root_chi,
        "positive_scan_sign_change_count": 1,
        "positive_pressure_continuation_flux_applied": True,
        "finite_compression_branch_approved": False,
        "back_pressure_crossing_correction_applied": True,
        "rarefaction_domain_available": False,
        "rarefaction_domain_reason": (
            "STATIC_PRESSURE_NOT_ABOVE_BACK_PRESSURE"
        ),
        "interior_static_pressure_minus_back_pa": float(
            static.pressure_pa - back_pressure
        ),
        "interior_stagnation_pressure_minus_back_pa": float(
            reconstruction.stagnation_pressure_pa - back_pressure
        ),
        "root_static_pressure_minus_back_pa": float(
            root["pressure_pa"] - back_pressure
        ),
    }


def _corrected_solve_three_branch_boundary(
    *,
    hook: Any,
    U: np.ndarray,
    solver_time_s: float,
) -> dict[str, Any]:
    details = short_run._classification_diagnostics(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
    )
    endpoint = dict(details["endpoint"])
    if not bool(endpoint.get("evaluation_succeeded")):
        raise BackPressureCrossingContinuationStop(
            "ENDPOINT_EVALUATION_FAILURE",
            "neutral endpoint evaluation did not succeed",
            details,
        )
    if not bool(endpoint.get("local_candidate_admissible")):
        raise BackPressureCrossingContinuationStop(
            "LOCAL_ROOT_INADMISSIBLE",
            "neutral endpoint is outside the retained admissible branch",
            details,
        )

    interior_pressure = float(details["interior_pressure_pa"])
    back_pressure = float(details["back_pressure_pa"])
    if interior_pressure > back_pressure:
        context = _ORIGINAL_SOLVE_THREE_BRANCH_BOUNDARY(
            hook=hook,
            U=U,
            solver_time_s=solver_time_s,
        )
        context.setdefault("back_pressure_crossing_correction_applied", False)
        context.setdefault("rarefaction_domain_available", True)
        context.setdefault("rarefaction_domain_reason", None)
        reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
        context.setdefault(
            "interior_static_pressure_minus_back_pa",
            float(interior_pressure - back_pressure),
        )
        context.setdefault(
            "interior_stagnation_pressure_minus_back_pa",
            float(reconstruction.stagnation_pressure_pa - back_pressure),
        )
        context.setdefault(
            "root_static_pressure_minus_back_pa",
            float(context["root"]["pressure_pa"] - back_pressure),
        )
        return context

    if bool(endpoint.get("root_closure_passed")):
        raise BackPressureCrossingContinuationStop(
            "BACK_PRESSURE_CROSSING_NEUTRAL_REQUIRES_REVIEW",
            "neutral endpoint is within tolerance after static-pressure crossing",
            details,
        )
    if not float(details["interior_stagnation_pressure_pa"]) > back_pressure:
        raise BackPressureCrossingContinuationStop(
            "STAGNATION_PRESSURE_NOT_ABOVE_BACK",
            "interior stagnation pressure is not above retained back pressure",
            details,
        )

    connected = dict(details["connected_rarefaction"])
    connected_stop = str(connected.get("stop_reason") or "")
    rarefaction_domain_unavailable = bool(
        int(connected.get("requested_nodes") or 0) == 0
        and int(connected.get("admissible_subsonic_nodes") or 0) == 0
        and int(connected.get("sign_change_count") or 0) == 0
        and "outlet pressure is not above retained back pressure"
        in connected_stop
    )
    if not rarefaction_domain_unavailable:
        raise BackPressureCrossingContinuationStop(
            "RAREFACTION_DOMAIN_CLASSIFICATION_FAILURE",
            "connected rarefaction domain did not match the fixed unavailable topology",
            details,
        )
    negative_local_count = int(
        details["rarefaction_side_local_sign_change_count"]
    )
    if negative_local_count != 0:
        raise BackPressureCrossingContinuationStop(
            "RAREFACTION_ROOT_PRESENT",
            "a local rarefaction-side root exists after static-pressure crossing",
            details,
        )

    positive = short_run._positive_pressure_scan(hook=hook, U=U)
    positive_count = int(positive["sign_change_count"])
    if positive_count > 1:
        raise BackPressureCrossingContinuationStop(
            "MULTIPLE_LOCAL_ROOTS",
            "multiple positive-pressure roots were observed",
            {**details, "positive_scan": positive},
        )
    if positive_count == 0:
        endpoint_residual = float(endpoint["compatibility_residual_kg_s"])
        scope_residual = float(positive["scope_limit_residual_kg_s"])
        if (
            endpoint_residual
            > float(robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)
            and scope_residual > 0.0
        ):
            raise BackPressureCrossingContinuationStop(
                "FINITE_COMPRESSION_MODEL_REQUIRED",
                "positive residual remained positive through the fixed chi scope",
                {**details, "positive_scan": positive},
            )
        raise BackPressureCrossingContinuationStop(
            "NO_UNIQUE_WEAK_COMPRESSION_ROOT",
            "no in-scope positive-pressure root was found",
            {**details, "positive_scan": positive},
        )

    context = short_run._solve_weak_compression(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
        positive=positive,
    )
    branch = "WEAK_COMPRESSION"
    if short_run._clear_branch_chatter(hook.accepted_branch_history, branch):
        raise BackPressureCrossingContinuationStop(
            "CLEAR_BRANCH_CHATTER",
            "candidate branch forms the fixed five-point chatter pattern",
            details,
        )

    root = context["root"]
    root_offset = float(root["pressure_pa"] - interior_pressure)
    denominator = float(
        context["interior_density_kg_m3"]
        * context["interior_sound_speed_m_s"] ** 2
    )
    root_chi = float(root_offset / denominator)
    if not 0.0 < root_chi <= short_run.CHI_MAX:
        raise BackPressureCrossingContinuationStop(
            "FINITE_COMPRESSION_MODEL_REQUIRED",
            f"Weak Compression root chi is outside scope: {root_chi}",
            details,
        )
    if not float(root["pressure_pa"]) > back_pressure:
        raise BackPressureCrossingContinuationStop(
            "ROOT_PRESSURE_NOT_ABOVE_BACK",
            "selected Weak Compression root pressure is not above back pressure",
            details,
        )

    context.update(
        {
            "branch_classification": branch,
            "endpoint_residual_kg_s": float(
                endpoint["compatibility_residual_kg_s"]
            ),
            "endpoint_within_locked_root_mass_tolerance": bool(
                endpoint["within_locked_root_mass_tolerance"]
            ),
            "endpoint_admissible": bool(
                endpoint["local_candidate_admissible"]
            ),
            "endpoint_root_closure_passed": bool(
                endpoint["root_closure_passed"]
            ),
            "retained_root_mass_tolerance_kg_s": float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            "rarefaction_side_local_sign_change_count": 0,
            "connected_rarefaction_sign_change_count": 0,
            "connected_rarefaction_residual_monotone": False,
            "connected_rarefaction_stop_reason": connected.get("stop_reason"),
            "positive_scan_sign_change_count": 1,
            "positive_scan_rows": list(positive["rows"]),
            "positive_scan_residual_monotone_nonincreasing": bool(
                positive["residual_monotone_nonincreasing"]
            ),
            "positive_scan_delta_p_max_pa": float(positive["delta_p_max_pa"]),
            "local_scan_rows": list(details["local_scan_rows"]),
            "p_P_minus_p_i_pa": root_offset,
            "root_chi": root_chi,
            "accepted_branch_history_before": list(
                hook.accepted_branch_history
            ),
            "clear_branch_chatter_detected": False,
            "positive_pressure_continuation_flux_applied": True,
            "finite_compression_branch_approved": False,
            "back_pressure_crossing_correction_applied": True,
            "rarefaction_domain_available": False,
            "rarefaction_domain_reason": (
                "STATIC_PRESSURE_NOT_ABOVE_BACK_PRESSURE"
            ),
            "interior_static_pressure_minus_back_pa": float(
                interior_pressure - back_pressure
            ),
            "interior_stagnation_pressure_minus_back_pa": float(
                details["interior_stagnation_pressure_pa"] - back_pressure
            ),
            "root_static_pressure_minus_back_pa": float(
                root["pressure_pa"] - back_pressure
            ),
        }
    )
    return context


def _corrected_root_evidence_row(
    *,
    context: dict[str, Any],
    requested_solver_step: int,
) -> dict[str, Any]:
    row = _ORIGINAL_ROOT_EVIDENCE_ROW(
        context=context,
        requested_solver_step=requested_solver_step,
    )
    row.update(
        {
            "back_pressure_crossing_correction_applied": bool(
                context.get("back_pressure_crossing_correction_applied", False)
            ),
            "rarefaction_domain_available": bool(
                context.get("rarefaction_domain_available", True)
            ),
            "rarefaction_domain_reason": context.get(
                "rarefaction_domain_reason"
            ),
            "interior_static_pressure_minus_back_pa": context.get(
                "interior_static_pressure_minus_back_pa"
            ),
            "interior_stagnation_pressure_minus_back_pa": context.get(
                "interior_stagnation_pressure_minus_back_pa"
            ),
            "root_static_pressure_minus_back_pa": context.get(
                "root_static_pressure_minus_back_pa"
            ),
        }
    )
    return row


def _compare_pre_crossing_steps(
    *,
    failed_artifact_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    previous = [
        row
        for row in _read_csv(
            failed_artifact_dir / "full_horizon_continuation_steps.csv"
        )
        if row.get("accepted_step") == "True"
    ]
    current = [
        row
        for row in _read_csv(
            output_dir / "full_horizon_continuation_steps.csv"
        )
        if row.get("accepted_step") == "True"
    ]
    if len(previous) != 74 or len(current) < 74:
        return {
            "passed": False,
            "previous_accepted_rows": len(previous),
            "current_accepted_rows": len(current),
            "mismatches": ["accepted row count mismatch"],
        }
    keys = (
        "requested_step",
        "accepted_step",
        "solver_step_count",
        "time_before_s",
        "time_after_s",
        "accepted_dt_s",
        "branch_classification",
        "interior_pressure_before_root_pa",
        "root_pressure_pa",
        "root_mass_residual_kg_s",
        "p_P_minus_p_i_pa",
        "root_chi",
        "outlet_pressure_after_step_pa",
        "outlet_velocity_after_step_m_s",
        "outlet_phase_after_step",
        "step_mass_residual_kg",
        "step_momentum_residual_kg_m_s",
        "step_energy_residual_J",
        "cumulative_mass_residual_kg",
        "cumulative_momentum_residual_kg_m_s",
        "cumulative_energy_residual_J",
        "step_passed",
        "increment_4_per_step_gate_passed",
    )
    mismatches: list[str] = []
    for index, (old, new) in enumerate(zip(previous, current[:74], strict=True)):
        for key in keys:
            if old.get(key) != new.get(key):
                mismatches.append(
                    f"row {index} step {old.get('solver_step_count')} key {key}: "
                    f"old={old.get(key)!r} new={new.get(key)!r}"
                )
                if len(mismatches) >= 20:
                    break
        if len(mismatches) >= 20:
            break
    return {
        "passed": not mismatches,
        "previous_accepted_rows": len(previous),
        "current_accepted_rows": len(current),
        "compared_rows": 74,
        "compared_keys": list(keys),
        "mismatches": mismatches,
    }


def _postprocess_output(
    *,
    output_dir: Path,
    increment_4a_summary: dict[str, Any],
    failed_increment_4_summary: dict[str, Any],
    failed_increment_4_artifact_dir: Path,
) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    roots = _read_csv(output_dir / "full_horizon_continuation_roots.csv")
    corrected = [
        row
        for row in roots
        if row.get("back_pressure_crossing_correction_applied") == "True"
    ]
    reproduction = _compare_pre_crossing_steps(
        failed_artifact_dir=failed_increment_4_artifact_dir,
        output_dir=output_dir,
    )
    first_correction_step = (
        min(int(row["requested_solver_step"]) for row in corrected)
        if corrected
        else None
    )
    correction_gate = bool(
        corrected
        and first_correction_step == FIRST_CORRECTION_REQUESTED_STEP
        and all(row["rarefaction_domain_available"] == "False" for row in corrected)
        and all(
            float(row["interior_static_pressure_minus_back_pa"]) <= 0.0
            for row in corrected
        )
        and all(
            float(row["interior_stagnation_pressure_minus_back_pa"]) > 0.0
            for row in corrected
        )
        and all(
            float(row["root_static_pressure_minus_back_pa"]) > 0.0
            for row in corrected
        )
    )
    gate_passed = bool(
        summary["working_vertical_slice_two_l_over_c0_passed"]
        and reproduction["passed"]
        and correction_gate
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4b"
            ),
            "scope": (
                "model_review_working_vertical_slice_back_pressure_crossing"
            ),
            "increment_4a_source_sha": INCREMENT_4A_SOURCE_SHA,
            "increment_4a_workflow_run": INCREMENT_4A_WORKFLOW_RUN,
            "increment_4a_job": INCREMENT_4A_JOB,
            "increment_4a_artifact": INCREMENT_4A_ARTIFACT,
            "increment_4a_artifact_sha256": INCREMENT_4A_ARTIFACT_SHA256,
            "increment_4a_outcome": increment_4a_summary["outcome"],
            "increment_4a_authority_verified": True,
            "failed_increment_4_source_sha": FAILED_INCREMENT_4_SOURCE_SHA,
            "failed_increment_4_workflow_run": FAILED_INCREMENT_4_WORKFLOW_RUN,
            "failed_increment_4_job": FAILED_INCREMENT_4_JOB,
            "failed_increment_4_artifact": FAILED_INCREMENT_4_ARTIFACT,
            "failed_increment_4_artifact_sha256": (
                FAILED_INCREMENT_4_ARTIFACT_SHA256
            ),
            "failed_increment_4_authority_verified": True,
            "pre_crossing_reproduction": reproduction,
            "pre_crossing_reproduction_passed": bool(reproduction["passed"]),
            "back_pressure_crossing_correction_count": len(corrected),
            "first_back_pressure_crossing_correction_step": first_correction_step,
            "minimum_corrected_static_pressure_margin_pa": (
                min(
                    float(row["interior_static_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "minimum_corrected_stagnation_pressure_margin_pa": (
                min(
                    float(row["interior_stagnation_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "minimum_corrected_root_pressure_margin_pa": (
                min(
                    float(row["root_static_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "back_pressure_crossing_correction_gate_passed": correction_gate,
            "outcome": OUTCOME if gate_passed else "INCREMENT_4B_STOPPED",
            "increment_4b_working_slice_gate_passed": gate_passed,
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

    authority = {
        "increment_4a": {
            "source_sha": INCREMENT_4A_SOURCE_SHA,
            "workflow_run": INCREMENT_4A_WORKFLOW_RUN,
            "job": INCREMENT_4A_JOB,
            "artifact": INCREMENT_4A_ARTIFACT,
            "artifact_sha256": INCREMENT_4A_ARTIFACT_SHA256,
            "outcome": increment_4a_summary["outcome"],
            "verified": True,
        },
        "failed_increment_4": {
            "source_sha": FAILED_INCREMENT_4_SOURCE_SHA,
            "workflow_run": FAILED_INCREMENT_4_WORKFLOW_RUN,
            "job": FAILED_INCREMENT_4_JOB,
            "artifact": FAILED_INCREMENT_4_ARTIFACT,
            "artifact_sha256": FAILED_INCREMENT_4_ARTIFACT_SHA256,
            "outcome": failed_increment_4_summary["outcome"],
            "verified": True,
        },
    }
    (output_dir / "increment_4b_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pre_crossing_reproduction.json").write_text(
        json.dumps(reproduction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Increment 4B branch-domain correction\n\n"
        + "The Increment 4A authority was verified. The first 74 continuation "
        + "steps through step 443 were compared with the prior failed "
        + "Increment 4 evidence. The correction was permitted only when outlet "
        + "static pressure was at or below back pressure while stagnation "
        + "pressure remained above back pressure, no rarefaction-side root was "
        + "present, and one in-scope positive-pressure root passed all retained "
        + "checks. Formal project states remain unchanged.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = (
        "full_horizon_continuation_steps.csv",
        "full_horizon_continuation_roots.csv",
        "local_wave_scans.csv",
        "positive_pressure_scans.csv",
        "branch_transitions.csv",
        "probe_series.csv",
        "full_horizon_states.npz",
        "parent_verification.json",
        "increment_4b_authority.json",
        "pre_crossing_reproduction.json",
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
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--increment-4a-artifact-dir", type=Path, required=True)
    parser.add_argument("--increment-4a-artifact-digest", required=True)
    parser.add_argument(
        "--failed-increment-4-artifact-dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--failed-increment-4-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    increment_4a_summary = _verify_increment_4a_artifact(
        args.increment_4a_artifact_dir,
        artifact_digest=args.increment_4a_artifact_digest,
    )
    failed_increment_4_summary = _verify_failed_increment_4_artifact(
        args.failed_increment_4_artifact_dir,
        artifact_digest=args.failed_increment_4_artifact_digest,
    )

    short_run._build_weak_compression_context = (
        _corrected_build_weak_compression_context
    )
    short_run._solve_three_branch_boundary = (
        _corrected_solve_three_branch_boundary
    )
    short_run._root_evidence_row = _corrected_root_evidence_row
    full_horizon.OUTCOME = OUTCOME

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
        full_horizon.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess_output(
        output_dir=args.output_dir,
        increment_4a_summary=increment_4a_summary,
        failed_increment_4_summary=failed_increment_4_summary,
        failed_increment_4_artifact_dir=args.failed_increment_4_artifact_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4b_working_slice_gate_passed"]:
        raise SystemExit(
            "Increment 4B back-pressure crossing continuation did not pass"
        )


if __name__ == "__main__":
    main()
