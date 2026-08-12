from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from u3_b2_a1_neutral_endpoint_resume import _run_resume
from u3_b2_a1_post_endpoint_branch_classification import (
    A1PostEndpointBranchHook,
    _classification_diagnostics,
)
from u3_b2_a1_wave_curve_model import CASE_ID, _brackets, _scan_row


PARENT_SOURCE_SHA = "e3202ce2b886c0ff21893076d66c84dc9b275919"
STARTING_ACCEPTED_SOLVER_STEP = 337
CHI_MAX = 1.0e-6
FIRST_POSITIVE_SCAN_OFFSET_PA = 1.0e-4
MAX_BISECTION_ITERATIONS = 32
OUTCOME = "WEAK_COMPRESSION_INCREMENT_1_DIAGNOSTIC_PASS"
robustness = robustness_v4.robustness


class WeakCompressionDiagnosticStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sign(value: float) -> int:
    return -1 if value < 0.0 else 1 if value > 0.0 else 0


def _positive_scan_offsets(delta_p_max_pa: float) -> tuple[float, ...]:
    if not np.isfinite(delta_p_max_pa) or delta_p_max_pa <= 0.0:
        raise WeakCompressionDiagnosticStop(
            f"invalid weak-compression pressure scope: {delta_p_max_pa} Pa"
        )
    offsets = [0.0]
    value = FIRST_POSITIVE_SCAN_OFFSET_PA
    while value <= delta_p_max_pa:
        offsets.append(float(value))
        value *= 10.0
    if offsets[-1] < delta_p_max_pa:
        offsets.append(float(delta_p_max_pa))
    return tuple(sorted(set(offsets)))


def _annotate_row(
    row: dict[str, Any],
    *,
    interior_density_kg_m3: float,
    interior_sound_speed_m_s: float,
    selected_bracket: bool = False,
) -> dict[str, Any]:
    item = dict(row)
    offset = float(item["pressure_offset_pa"])
    denominator = float(
        interior_density_kg_m3 * interior_sound_speed_m_s**2
    )
    chi = float(offset / denominator)
    item.update(
        {
            "chi": chi,
            "chi_max": CHI_MAX,
            "within_weak_compression_scope": bool(
                offset == 0.0 or (0.0 < chi <= CHI_MAX)
            ),
            "selected_sign_change_bracket_member": selected_bracket,
            "positive_pressure_continuation_flux_applied": False,
            "fvm_step_338_attempted": False,
        }
    )
    return item


def _require_candidate(row: dict[str, Any], label: str) -> None:
    if not bool(row.get("evaluation_succeeded")):
        raise WeakCompressionDiagnosticStop(
            f"{label} evaluation failed: "
            f"{row.get('formal_outcome')} {row.get('formal_message')}"
        )
    if not bool(row.get("local_candidate_admissible")):
        raise WeakCompressionDiagnosticStop(
            f"{label} is outside the retained admissible branch"
        )
    residual = row.get("compatibility_residual_kg_s")
    if residual is None or not np.isfinite(float(residual)):
        raise WeakCompressionDiagnosticStop(
            f"{label} has a nonfinite compatibility residual"
        )


def _solve_first_bracket(
    *,
    bracket: dict[str, float | None],
    evaluate_offset: Callable[[float], dict[str, Any]],
    root_tolerance_kg_s: float,
) -> tuple[dict[str, Any], int, dict[str, float]]:
    lower_offset = float(bracket["lower_offset_pa"])
    upper_offset = float(bracket["upper_offset_pa"])
    lower = evaluate_offset(lower_offset)
    upper = evaluate_offset(upper_offset)
    _require_candidate(lower, "lower bracket endpoint")
    _require_candidate(upper, "upper bracket endpoint")
    lower_residual = float(lower["compatibility_residual_kg_s"])
    upper_residual = float(upper["compatibility_residual_kg_s"])

    if abs(lower_residual) <= root_tolerance_kg_s:
        return lower, 0, {
            "final_lower_offset_pa": lower_offset,
            "final_upper_offset_pa": upper_offset,
            "final_lower_residual_kg_s": lower_residual,
            "final_upper_residual_kg_s": upper_residual,
        }
    if abs(upper_residual) <= root_tolerance_kg_s:
        return upper, 0, {
            "final_lower_offset_pa": lower_offset,
            "final_upper_offset_pa": upper_offset,
            "final_lower_residual_kg_s": lower_residual,
            "final_upper_residual_kg_s": upper_residual,
        }
    if _sign(lower_residual) == _sign(upper_residual):
        raise WeakCompressionDiagnosticStop(
            "selected positive-pressure bracket does not retain a sign change"
        )

    midpoint = lower
    midpoint_offset = lower_offset
    midpoint_residual = lower_residual
    for iteration in range(1, MAX_BISECTION_ITERATIONS + 1):
        midpoint_offset = float(0.5 * (lower_offset + upper_offset))
        midpoint = evaluate_offset(midpoint_offset)
        _require_candidate(midpoint, f"bisection midpoint {iteration}")
        midpoint_residual = float(midpoint["compatibility_residual_kg_s"])
        if abs(midpoint_residual) <= root_tolerance_kg_s:
            return midpoint, iteration, {
                "final_lower_offset_pa": lower_offset,
                "final_upper_offset_pa": upper_offset,
                "final_lower_residual_kg_s": lower_residual,
                "final_upper_residual_kg_s": upper_residual,
            }
        if _sign(midpoint_residual) == _sign(lower_residual):
            lower_offset = midpoint_offset
            lower = midpoint
            lower_residual = midpoint_residual
        else:
            upper_offset = midpoint_offset
            upper = midpoint
            upper_residual = midpoint_residual

    best = min(
        (lower, upper, midpoint),
        key=lambda row: abs(float(row["compatibility_residual_kg_s"])),
    )
    if abs(float(best["compatibility_residual_kg_s"])) <= root_tolerance_kg_s:
        return best, MAX_BISECTION_ITERATIONS, {
            "final_lower_offset_pa": lower_offset,
            "final_upper_offset_pa": upper_offset,
            "final_lower_residual_kg_s": lower_residual,
            "final_upper_residual_kg_s": upper_residual,
        }
    raise WeakCompressionDiagnosticStop(
        "weak-compression root did not converge within 32 bisection iterations"
    )


def _run_increment_1(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    np.ndarray,
]:
    resume_row, resume_summary, _, U_step337 = _run_resume(
        contract,
        b1_contract,
    )
    if not bool(resume_summary["neutral_endpoint_one_step_gate_passed"]):
        raise WeakCompressionDiagnosticStop(
            "the parent neutral-endpoint step-337 reproduction did not pass"
        )
    if int(resume_summary["resumed_solver_step"]) != STARTING_ACCEPTED_SOLVER_STEP:
        raise WeakCompressionDiagnosticStop(
            "the reproduced accepted solver step is not 337"
        )

    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    provider = CoolPropB2StateProvider()
    hook = A1PostEndpointBranchHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(
        resume_summary["endpoint_pressure_pa"]
    )
    solver_time_s = float(resume_row["time_after_s"])
    U_before_diagnostic = np.asarray(U_step337, dtype=float).copy()

    details = _classification_diagnostics(
        hook=hook,
        U=U_before_diagnostic,
        solver_time_s=solver_time_s,
    )
    endpoint = dict(details["endpoint"])
    _require_candidate(endpoint, "neutral endpoint")
    root_tolerance = float(robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)
    endpoint_residual = float(endpoint["compatibility_residual_kg_s"])
    if abs(endpoint_residual) <= root_tolerance:
        raise WeakCompressionDiagnosticStop(
            "the reproduced endpoint is still inside the retained neutral tolerance"
        )

    connected = details["connected_rarefaction"]
    if not bool(connected["residual_monotone"]):
        raise WeakCompressionDiagnosticStop(
            "the approved connected rarefaction scan is not monotone"
        )
    if int(connected["sign_change_count"]) != 0:
        raise WeakCompressionDiagnosticStop(
            "an approved connected rarefaction root exists"
        )
    if int(details["rarefaction_side_local_sign_change_count"]) != 0:
        raise WeakCompressionDiagnosticStop(
            "a rarefaction-side local root requires branch review"
        )

    reconstruction = provider.reconstruct_from_conserved(U_before_diagnostic[-1])
    static = reconstruction.static
    interior_density = float(static.density_kg_m3)
    interior_sound_speed = float(static.sound_speed_m_s)
    delta_p_max = float(CHI_MAX * interior_density * interior_sound_speed**2)
    offsets = _positive_scan_offsets(delta_p_max)

    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))
    cache: dict[float, dict[str, Any]] = {}

    def evaluate_offset(offset_pa: float) -> dict[str, Any]:
        key = float(offset_pa)
        if key not in cache:
            raw = _scan_row(
                offset_pa=key,
                static=static,
                isentrope=isentrope,
                hook=hook,
                area_m2=hook.area_m2,
                allowed_phases=allowed_phases,
                velocity_tolerance=velocity_tolerance,
            )
            cache[key] = _annotate_row(
                raw,
                interior_density_kg_m3=interior_density,
                interior_sound_speed_m_s=interior_sound_speed,
            )
        return dict(cache[key])

    scan_rows = [evaluate_offset(offset) for offset in offsets]
    for index, row in enumerate(scan_rows):
        _require_candidate(row, f"positive-pressure scan node {index}")
        if not bool(row["within_weak_compression_scope"]):
            raise WeakCompressionDiagnosticStop(
                f"positive-pressure scan node {index} exceeds chi scope"
            )

    evaluable_brackets = _brackets(scan_rows, admissible_only=False)
    admissible_brackets = _brackets(scan_rows, admissible_only=True)
    if len(evaluable_brackets) != len(admissible_brackets):
        raise WeakCompressionDiagnosticStop(
            "an evaluable positive-pressure sign change is inadmissible"
        )
    if len(admissible_brackets) == 0:
        raise WeakCompressionDiagnosticStop(
            "no positive-pressure sign-change bracket exists within chi scope"
        )
    if len(admissible_brackets) > 1:
        raise WeakCompressionDiagnosticStop(
            "multiple positive-pressure sign-change brackets exist within chi scope"
        )

    selected_bracket = dict(admissible_brackets[0])
    selected_offsets = {
        float(selected_bracket["lower_offset_pa"]),
        float(selected_bracket["upper_offset_pa"]),
    }
    scan_rows = [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["pressure_offset_pa"]) in selected_offsets
            ),
        }
        for row in scan_rows
    ]

    root, iterations, final_bracket = _solve_first_bracket(
        bracket=selected_bracket,
        evaluate_offset=evaluate_offset,
        root_tolerance_kg_s=root_tolerance,
    )
    root_offset = float(root["pressure_offset_pa"])
    root_chi = float(root["chi"])
    root_residual = float(root["compatibility_residual_kg_s"])
    root_phase = normalize_phase(str(root["phase"]))
    state_unchanged = bool(
        np.array_equal(U_before_diagnostic, np.asarray(U_step337, dtype=float))
    )

    root_gate = bool(
        root_offset > 0.0
        and 0.0 < root_chi <= CHI_MAX
        and abs(root_residual) <= root_tolerance
        and bool(root["evaluation_succeeded"])
        and bool(root["local_candidate_admissible"])
        and bool(root["root_closure_passed"])
        and float(root["velocity_m_s"]) >= 0.0
        and 0.0 <= float(root["mach"]) < 1.0
        and root_phase == "liquid"
        and bool(root["phase_passed"])
        and bool(root["stagnation_pressure_above_back_pressure"])
        and bool(root["energy_ledger_passed"])
        and bool(root["reaction_ledger_passed"])
        and state_unchanged
    )
    if not root_gate:
        raise WeakCompressionDiagnosticStop(
            "the selected weak-compression root failed a fixed acceptance check"
        )

    root_row = dict(root)
    root_row.update(
        {
            "branch_classification": "WEAK_COMPRESSION",
            "p_P_minus_p_i_pa": root_offset,
            "chi": root_chi,
            "chi_max": CHI_MAX,
            "bisection_iterations": int(iterations),
            "selected_initial_bracket_lower_offset_pa": float(
                selected_bracket["lower_offset_pa"]
            ),
            "selected_initial_bracket_upper_offset_pa": float(
                selected_bracket["upper_offset_pa"]
            ),
            **final_bracket,
            "positive_pressure_continuation_flux_applied": False,
            "fvm_step_338_attempted": False,
            "solver_step_before_diagnostic": STARTING_ACCEPTED_SOLVER_STEP,
            "solver_step_after_diagnostic": STARTING_ACCEPTED_SOLVER_STEP,
            "solver_time_before_diagnostic_s": solver_time_s,
            "solver_time_after_diagnostic_s": solver_time_s,
            "state_unchanged_after_diagnostic": state_unchanged,
        }
    )

    gate_passed = bool(
        bool(resume_summary["checkpoint_reproduction_ok"])
        and bool(resume_summary["neutral_endpoint_one_step_gate_passed"])
        and abs(endpoint_residual) > root_tolerance
        and int(connected["sign_change_count"]) == 0
        and int(details["rarefaction_side_local_sign_change_count"]) == 0
        and len(admissible_brackets) == 1
        and root_gate
        and state_unchanged
    )
    summary = {
        "schema_version": "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_1",
        "scope": "model_review_working_vertical_slice_diagnostic_only",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "case_id": CASE_ID,
        "cells": int(contract["geometry"]["baseline_cells"]),
        "cfl": float(contract["geometry"]["baseline_cfl"]),
        "checkpoint_reproduction_ok": bool(
            resume_summary["checkpoint_reproduction_ok"]
        ),
        "neutral_endpoint_step337_gate_passed": bool(
            resume_summary["neutral_endpoint_one_step_gate_passed"]
        ),
        "solver_step_before_diagnostic": STARTING_ACCEPTED_SOLVER_STEP,
        "solver_step_after_diagnostic": STARTING_ACCEPTED_SOLVER_STEP,
        "solver_time_before_diagnostic_s": solver_time_s,
        "solver_time_after_diagnostic_s": solver_time_s,
        "state_unchanged_after_diagnostic": state_unchanged,
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_density_kg_m3": interior_density,
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": interior_sound_speed,
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_phase": str(static.phase),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "endpoint_residual_kg_s": endpoint_residual,
        "retained_root_mass_tolerance_kg_s": root_tolerance,
        "endpoint_within_retained_tolerance": bool(
            abs(endpoint_residual) <= root_tolerance
        ),
        "connected_rarefaction_sign_change_count": int(
            connected["sign_change_count"]
        ),
        "connected_rarefaction_residual_monotone": bool(
            connected["residual_monotone"]
        ),
        "rarefaction_side_local_sign_change_count": int(
            details["rarefaction_side_local_sign_change_count"]
        ),
        "parent_positive_side_local_sign_change_count": int(
            details["positive_side_local_sign_change_count"]
        ),
        "chi_max": CHI_MAX,
        "delta_p_max_pa": delta_p_max,
        "positive_scan_offsets_pa": list(offsets),
        "positive_scan_sign_change_count": len(admissible_brackets),
        "selected_initial_bracket": selected_bracket,
        "bisection_iterations": int(iterations),
        "branch_classification": "WEAK_COMPRESSION",
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_pressure_offset_pa": root_offset,
        "root_chi": root_chi,
        "root_density_kg_m3": float(root["density_kg_m3"]),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_sound_speed_m_s": float(root["sound_speed_m_s"]),
        "root_mach": float(root["mach"]),
        "root_phase": str(root["phase"]),
        "root_h0_J_kg": float(root["h0_J_kg"]),
        "root_pipe_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "root_b1_mass_rate_kg_s": float(root["b1_mass_rate_kg_s"]),
        "root_mass_residual_kg_s": root_residual,
        "root_b1_formal_outcome": root["formal_outcome"],
        "root_b1_formal_message": root["formal_message"],
        "root_stagnation_pressure_pa": float(root["stagnation_pressure_pa"]),
        "back_pressure_pa": float(root["back_pressure_pa"]),
        "root_pipe_momentum_port_N": float(root["pipe_momentum_port_N"]),
        "root_downstream_stream_pressure_port_N": float(
            root["downstream_stream_pressure_port_N"]
        ),
        "root_restriction_reaction_on_fluid_N": float(
            root["restriction_reaction_on_fluid_N"]
        ),
        "root_restriction_reaction_ledger_residual_N": float(
            root["restriction_reaction_ledger_residual_N"]
        ),
        "root_pipe_energy_rate_W": float(root["pipe_energy_rate_W"]),
        "root_b1_energy_rate_W": float(root["b1_energy_rate_W"]),
        "root_energy_port_residual_W": float(root["energy_port_residual_W"]),
        "root_stagnation_enthalpy_round_trip_residual_J_kg": float(
            root["stagnation_enthalpy_round_trip_residual_J_kg"]
        ),
        "root_energy_mass_consistency_residual_W": float(
            root["energy_mass_consistency_residual_W"]
        ),
        "outcome": OUTCOME,
        "increment_1_diagnostic_gate_passed": gate_passed,
        "positive_pressure_continuation_flux_applied": False,
        "fvm_step_338_attempted": False,
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
    return resume_row, scan_rows, root_row, summary, U_before_diagnostic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)

    resume_row, scan_rows, root_row, summary, U_step337 = _run_increment_1(
        contract,
        b1_contract,
    )
    summary["source_git_sha"] = args.source_git_sha
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "resume_step_337.csv", [resume_row])
    _write_csv(output / "weak_compression_positive_scan.csv", scan_rows)
    _write_csv(output / "weak_compression_root.csv", [root_row])
    np.savez_compressed(
        output / "step337_state.npz",
        U_step337_before=np.asarray(U_step337, dtype=float),
        U_step337_after=np.asarray(U_step337, dtype=float),
        solver_step_before=np.asarray(
            [STARTING_ACCEPTED_SOLVER_STEP], dtype=np.int64
        ),
        solver_step_after=np.asarray(
            [STARTING_ACCEPTED_SOLVER_STEP], dtype=np.int64
        ),
        solver_time_before_s=np.asarray(
            [summary["solver_time_before_diagnostic_s"]]
        ),
        solver_time_after_s=np.asarray(
            [summary["solver_time_after_diagnostic_s"]]
        ),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 1\n\n"
        "MODEL_REVIEW / WORKING_VERTICAL_SLICE evidence only. The exact "
        "step-337 state was reproduced, one local positive-pressure root was "
        "solved under the fixed weak-acoustic chi scope, and no FvmSolver "
        "step 338 was attempted. This does not approve a finite compression "
        "model, full-horizon passage, finite-pipe verification, benchmark "
        "acceptance, Physical Validation, design use, or production "
        "activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "resume_step_337.csv",
        "weak_compression_positive_scan.csv",
        "weak_compression_root.csv",
        "step337_state.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_1_diagnostic_gate_passed"]:
        raise SystemExit("Weak Compression Bridge Increment 1 did not pass")


if __name__ == "__main__":
    main()
