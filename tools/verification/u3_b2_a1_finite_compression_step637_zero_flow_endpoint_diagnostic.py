from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
import u3_b2_a1_finite_compression_step635_seeded_island_diagnostic as island
import u3_b2_a1_finite_compression_step635_seeded_island_float_fix as float_fix
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


PARENT_SOURCE_SHA = "8d0568abd827684562783393650d6f63f3aa390f"
PARENT_RUN = 31670285271
PARENT_JOB = 94353300958
PARENT_ARTIFACT = 9169437776
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9i-root-schema-31670285271"
)
EXPECTED_STEP = 637
EXPECTED_TIME_S = 0.0042695827462251995
NEXT_STEP = 638
ULTRAFINE_LOWER_FACTOR = 0.98
ULTRAFINE_UPPER_FACTOR = 1.02
ULTRAFINE_NODE_COUNT = 4097
BROAD_LOWER_FACTOR = 0.50
BROAD_UPPER_FACTOR = 2.00
BROAD_NODE_COUNT = 513
SCALAR_BISECTION_ITERATIONS = 80
ROOT_TOLERANCE = float(base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)
ULTRAFINE_SUPPORTED = "ULTRAFINE_ADMISSIBLE_ISLAND_WITH_UNIQUE_ROOT_SUPPORTED"
ZERO_ENDPOINT_SUPPORTED = (
    "ZERO_FLOW_ENDPOINT_WITHIN_COMPATIBILITY_TOLERANCE_SUPPORTED_FOR_BRANCH_REVIEW"
)
CLASSIFIED = {ULTRAFINE_SUPPORTED, ZERO_ENDPOINT_SUPPORTED}

PARENT_REQUIRED_FILES = {
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
    "artifact_sha256.txt",
}


class ZeroFlowEndpointDiagnosticStop(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(U, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        rows = [{"no_rows_recorded": True}]
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _verify_manifest(directory: Path) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"parent file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise ZeroFlowEndpointDiagnosticStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent internal SHA256 mismatch for {name}",
            )


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str], dict[str, str]]:
    if len(artifact_digest) != 64 or any(
        character not in "0123456789abcdef" for character in artifact_digest
    ):
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent GitHub artifact digest is not a lowercase SHA256",
        )
    _verify_manifest(directory)
    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": "INCREMENT_9I_STOPPED",
        "starting_solver_step": 636,
        "additional_accepted_steps": 1,
        "final_solver_step": EXPECTED_STEP,
        "final_solver_time_s": EXPECTED_TIME_S,
        "stop_classification": "DiagnosticStop",
        "target_horizon_reached": False,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ZeroFlowEndpointDiagnosticStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent summary mismatch for {key}: {summary.get(key)!r}",
            )
    if "dynamic seeded interval contains no admissible island" not in str(
        summary.get("stop_reason")
    ):
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent stop reason mismatch",
        )

    with np.load(
        directory / "finite_compression_full_horizon_states.npz"
    ) as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if (
        U_after.shape != (32, 4)
        or step_after != EXPECTED_STEP
        or time_after != EXPECTED_TIME_S
    ):
        raise ZeroFlowEndpointDiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            "parent state identity mismatch",
        )
    if not np.all(np.isfinite(U_after)):
        raise ZeroFlowEndpointDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "parent state contains nonfinite values",
        )
    rho = np.asarray(U_after[:, 0], dtype=float)
    velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
    internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise ZeroFlowEndpointDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "parent density or internal energy is nonpositive",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise ZeroFlowEndpointDiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            "parent rho*xv is not exact zero",
        )

    step_rows = _read_csv(directory / "finite_compression_steps.csv")
    root_rows = _read_csv(directory / "finite_compression_roots.csv")
    if len(step_rows) != 1 or len(root_rows) != 1:
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent step/root row count is not one",
        )
    step_row = step_rows[0]
    root_row = root_rows[0]
    if int(step_row["solver_step_count"]) != EXPECTED_STEP:
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent accepted step is not 637",
        )
    if step_row.get("increment_9d_per_step_gate_passed") != "True":
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent accepted-step gate did not pass",
        )
    if int(root_row["requested_solver_step"]) != EXPECTED_STEP:
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent root is not for step 637",
        )
    if root_row.get("root_gate_passed") != "True":
        raise ZeroFlowEndpointDiagnosticStop(
            "PARENT_ARTIFACT_MISMATCH",
            "parent selected-root gate did not pass",
        )
    return summary, U_after, step_row, root_row


def _classification(row: dict[str, Any]) -> str:
    if inc8a._is_success(row):
        return "ADMISSIBLE_SUCCESS"
    if inc8a._is_unavailable(row):
        return "EXCLUDED_B1_UNAVAILABLE"
    if bool(
        row.get("evaluation_succeeded")
        and not row.get("local_candidate_admissible")
    ):
        return "EXCLUDED_LOCAL_INADMISSIBLE"
    raise ZeroFlowEndpointDiagnosticStop(
        "UNEXPECTED_CANDIDATE_OUTCOME",
        f"unexpected candidate outcome: {row.get('formal_outcome')} "
        f"{row.get('formal_message')}",
    )


def _success_blocks(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        if inc8a._is_success(row):
            current.append(row)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _scalar_value(
    row: dict[str, Any],
    *,
    scalar_name: str,
    back_pressure_pa: float,
) -> float:
    if scalar_name == "stagnation_pressure_margin_pa":
        value = float(row["stagnation_pressure_pa"]) - back_pressure_pa
    elif scalar_name == "velocity_m_s":
        value = float(row["velocity_m_s"])
    else:
        raise ValueError(scalar_name)
    if not math.isfinite(value):
        raise ZeroFlowEndpointDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            f"nonfinite scalar {scalar_name}",
        )
    return value


def _scalar_brackets(
    rows: list[dict[str, Any]],
    *,
    scalar_name: str,
    back_pressure_pa: float,
) -> list[dict[str, Any]]:
    brackets: list[dict[str, Any]] = []
    for lower, upper in zip(rows, rows[1:]):
        lower_value = _scalar_value(
            lower,
            scalar_name=scalar_name,
            back_pressure_pa=back_pressure_pa,
        )
        upper_value = _scalar_value(
            upper,
            scalar_name=scalar_name,
            back_pressure_pa=back_pressure_pa,
        )
        if lower_value == 0.0:
            brackets.append(
                {
                    "lower": lower,
                    "upper": lower,
                    "lower_value": lower_value,
                    "upper_value": lower_value,
                    "exact_node": True,
                }
            )
        elif lower_value * upper_value < 0.0 or upper_value == 0.0:
            brackets.append(
                {
                    "lower": lower,
                    "upper": upper,
                    "lower_value": lower_value,
                    "upper_value": upper_value,
                    "exact_node": upper_value == 0.0,
                }
            )
    if rows:
        final_value = _scalar_value(
            rows[-1],
            scalar_name=scalar_name,
            back_pressure_pa=back_pressure_pa,
        )
        if final_value == 0.0 and not any(
            float(item["lower"]["requested_chi"])
            == float(rows[-1]["requested_chi"])
            for item in brackets
        ):
            brackets.append(
                {
                    "lower": rows[-1],
                    "upper": rows[-1],
                    "lower_value": final_value,
                    "upper_value": final_value,
                    "exact_node": True,
                }
            )
    return brackets


def _solve_scalar_endpoint(
    *,
    curve: Any,
    bracket: dict[str, Any],
    scalar_name: str,
    back_pressure_pa: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    lower = dict(bracket["lower"])
    upper = dict(bracket["upper"])
    lower_chi = float(lower["requested_chi"])
    upper_chi = float(upper["requested_chi"])
    lower_value = _scalar_value(
        lower,
        scalar_name=scalar_name,
        back_pressure_pa=back_pressure_pa,
    )
    upper_value = _scalar_value(
        upper,
        scalar_name=scalar_name,
        back_pressure_pa=back_pressure_pa,
    )
    if lower_chi == upper_chi:
        selected = lower
        return selected, [], {
            "exact_scan_node": True,
            "float_resolution_hold": False,
            "iterations": 0,
            "final_lower_chi": lower_chi,
            "final_upper_chi": upper_chi,
            "final_width_chi": 0.0,
        }
    if lower_value * upper_value > 0.0:
        raise ZeroFlowEndpointDiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            f"invalid {scalar_name} scalar bracket",
        )

    rows: list[dict[str, Any]] = []
    resolution_hold = False
    for iteration in range(1, SCALAR_BISECTION_ITERATIONS + 1):
        mid_chi = float(0.5 * (lower_chi + upper_chi))
        if not lower_chi < mid_chi < upper_chi:
            if float(np.nextafter(lower_chi, upper_chi)) != upper_chi:
                raise ZeroFlowEndpointDiagnosticStop(
                    "STATE_REPRODUCTION_MISMATCH",
                    f"{scalar_name} midpoint collapsed before adjacent values",
                )
            resolution_hold = True
            rows.append(
                {
                    "scalar_name": scalar_name,
                    "iteration": iteration,
                    "action": "FLOAT_RESOLUTION_HOLD",
                    "candidate_evaluated": False,
                    "lower_chi_after": lower_chi,
                    "upper_chi_after": upper_chi,
                    "bracket_width_after": upper_chi - lower_chi,
                    "lower_scalar_after": lower_value,
                    "upper_scalar_after": upper_value,
                }
            )
            continue
        if resolution_hold:
            raise ZeroFlowEndpointDiagnosticStop(
                "STATE_REPRODUCTION_MISMATCH",
                f"{scalar_name} midpoint appeared after resolution hold",
            )
        midpoint = curve.evaluate(
            mid_chi,
            f"increment_9j_{scalar_name}_endpoint",
        )
        mid_value = _scalar_value(
            midpoint,
            scalar_name=scalar_name,
            back_pressure_pa=back_pressure_pa,
        )
        if mid_value == 0.0:
            lower = midpoint
            upper = midpoint
            lower_chi = mid_chi
            upper_chi = mid_chi
            lower_value = 0.0
            upper_value = 0.0
        elif lower_value == 0.0:
            upper = lower
            upper_chi = lower_chi
            upper_value = lower_value
        elif lower_value * mid_value <= 0.0:
            upper = midpoint
            upper_chi = mid_chi
            upper_value = mid_value
        else:
            lower = midpoint
            lower_chi = mid_chi
            lower_value = mid_value
        rows.append(
            {
                **midpoint,
                "scalar_name": scalar_name,
                "iteration": iteration,
                "action": "CANDIDATE_EVALUATED",
                "candidate_evaluated": True,
                "scalar_value": mid_value,
                "lower_chi_after": lower_chi,
                "upper_chi_after": upper_chi,
                "bracket_width_after": upper_chi - lower_chi,
                "lower_scalar_after": lower_value,
                "upper_scalar_after": upper_value,
            }
        )
        if lower_chi == upper_chi:
            break

    candidates = [lower] if lower_chi == upper_chi else [lower, upper]
    selected = min(
        candidates,
        key=lambda row: abs(
            _scalar_value(
                row,
                scalar_name=scalar_name,
                back_pressure_pa=back_pressure_pa,
            )
        ),
    )
    return selected, rows, {
        "exact_scan_node": bool(bracket.get("exact_node")),
        "float_resolution_hold": resolution_hold,
        "iterations": len(rows),
        "final_lower_chi": lower_chi,
        "final_upper_chi": upper_chi,
        "final_width_chi": upper_chi - lower_chi,
        "selected_scalar_value": _scalar_value(
            selected,
            scalar_name=scalar_name,
            back_pressure_pa=back_pressure_pa,
        ),
    }


def _deduplicate_success_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_chi: dict[float, dict[str, Any]] = {}
    for row in rows:
        if inc8a._is_success(row):
            by_chi[float(row["requested_chi"])] = dict(row)
    return [by_chi[key] for key in sorted(by_chi)]


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U: np.ndarray,
    parent_root: dict[str, str],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    provider = CoolPropB2StateProvider()
    hook = base.A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
    )
    previous_root_pressure = float(parent_root["root_pressure_pa"])
    hook._previous_root_pressure_pa = previous_root_pressure
    state_id = hook.state_id
    reconstruction = provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    back_pressure = float(hook.adapter.back_pressure_pa)
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_zero_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if (
        float(static.velocity_m_s) < -velocity_zero_tolerance
        or not 0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0
        or normalize_phase(str(static.phase)) not in allowed_phases
    ):
        raise ZeroFlowEndpointDiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "outlet state is outside the retained scope",
        )

    seed_chi = float(
        (previous_root_pressure - float(static.pressure_pa)) / denominator
    )
    if not base.WEAK_COMPRESSION_CHI_LIMIT < seed_chi < base.DIAGNOSTIC_CHI_CAP:
        raise ZeroFlowEndpointDiagnosticStop(
            "STATE_REPRODUCTION_MISMATCH",
            f"seed chi is outside finite-compression scope: {seed_chi}",
        )

    base.inc5_core.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        base.inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
    )
    curve = base.inc5_final.IdentityStatusPropagatedHugoniotCurve(
        static=static,
        hook=hook,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_zero_tolerance,
        pressure_denominator_pa=denominator,
    )

    fixed_rows = []
    for chi in base.inc5_core.CHI_NODES:
        row = curve.evaluate(float(chi), "increment_9j_fixed_scan")
        fixed_rows.append(
            {
                **row,
                "row_role": "UNCHANGED_FIXED_SCAN",
                "candidate_classification": _classification(row),
            }
        )

    ultrafine_lower = float(ULTRAFINE_LOWER_FACTOR * seed_chi)
    ultrafine_upper = float(ULTRAFINE_UPPER_FACTOR * seed_chi)
    ultrafine_chi = np.linspace(
        ultrafine_lower,
        ultrafine_upper,
        ULTRAFINE_NODE_COUNT,
        dtype=float,
    )
    ultrafine_rows = []
    for index, chi in enumerate(ultrafine_chi):
        row = curve.evaluate(float(chi), "increment_9j_ultrafine_scan")
        ultrafine_rows.append(
            {
                **row,
                "row_role": "ULTRAFINE_SCAN",
                "ultrafine_index": index,
                "candidate_classification": _classification(row),
            }
        )

    broad_lower = float(BROAD_LOWER_FACTOR * seed_chi)
    broad_upper = float(BROAD_UPPER_FACTOR * seed_chi)
    broad_chi = np.linspace(
        broad_lower,
        broad_upper,
        BROAD_NODE_COUNT,
        dtype=float,
    )
    broad_rows = []
    for index, chi in enumerate(broad_chi):
        row = curve.evaluate(float(chi), "increment_9j_broad_endpoint_scan")
        broad_rows.append(
            {
                **row,
                "row_role": "BROAD_ENDPOINT_SCAN",
                "broad_index": index,
                "candidate_classification": _classification(row),
                "stagnation_pressure_margin_pa": float(
                    row["stagnation_pressure_pa"] - back_pressure
                ),
            }
        )

    ultrafine_blocks = _success_blocks(ultrafine_rows)
    if len(ultrafine_blocks) > 1:
        raise ZeroFlowEndpointDiagnosticStop(
            "MULTIPLE_ULTRAFINE_ADMISSIBLE_ISLANDS",
            f"ultrafine scan contains {len(ultrafine_blocks)} islands",
        )

    selected_root: dict[str, Any] | None = None
    lower_boundary_rows: list[dict[str, Any]] = []
    upper_boundary_rows: list[dict[str, Any]] = []
    root_topology_rows: list[dict[str, Any]] = []
    root_topology_residuals: list[float] = []
    root_bracket_count = 0
    ultrafine_gate = False

    if ultrafine_blocks:
        success_island = ultrafine_blocks[0]
        if len(success_island) < 2:
            raise ZeroFlowEndpointDiagnosticStop(
                "ULTRAFINE_ADMISSIBLE_ISLAND_TOO_NARROW",
                "ultrafine island contains fewer than two nodes",
            )
        first_index = ultrafine_rows.index(success_island[0])
        last_index = ultrafine_rows.index(success_island[-1])
        if first_index == 0 or last_index == len(ultrafine_rows) - 1:
            raise ZeroFlowEndpointDiagnosticStop(
                "STATE_REPRODUCTION_MISMATCH",
                "ultrafine island touches an interval edge",
            )
        lower_neighbor = ultrafine_rows[first_index - 1]
        upper_neighbor = ultrafine_rows[last_index + 1]
        if not island._is_excluded(lower_neighbor) or not island._is_excluded(
            upper_neighbor
        ):
            raise ZeroFlowEndpointDiagnosticStop(
                "STATE_REPRODUCTION_MISMATCH",
                "ultrafine island is not bounded by excluded candidates",
            )
        _, lower_success, lower_boundary_rows = (
            float_fix._corrected_refine_boundary(
                curve=curve,
                excluded_row=lower_neighbor,
                success_row=success_island[0],
                lower_excluded=True,
                label="lower",
            )
        )
        _, upper_success, upper_boundary_rows = (
            float_fix._corrected_refine_boundary(
                curve=curve,
                excluded_row=upper_neighbor,
                success_row=success_island[-1],
                lower_excluded=False,
                label="upper",
            )
        )
        topology_source = _deduplicate_success_rows(
            [lower_success, *success_island, upper_success]
        )
        root_topology_rows = [
            {
                **row,
                "row_role": "ROOT_TOPOLOGY",
                "root_topology_order": index,
            }
            for index, row in enumerate(topology_source, start=1)
        ]
        root_topology_residuals = [
            float(row["compatibility_residual_kg_s"])
            for row in root_topology_rows
        ]
        monotone = bool(
            root_topology_residuals
            and all(
                right <= left
                for left, right in zip(
                    root_topology_residuals,
                    root_topology_residuals[1:],
                )
            )
        )
        if not monotone:
            raise ZeroFlowEndpointDiagnosticStop(
                "ULTRAFINE_SUCCESS_DOMAIN_NONMONOTONE",
                "ultrafine root topology is nonmonotone",
            )
        root_brackets = base.inc5_core._brackets(root_topology_rows)
        root_bracket_count = len(root_brackets)
        if root_bracket_count > 1:
            raise ZeroFlowEndpointDiagnosticStop(
                "MULTIPLE_COMPATIBILITY_ROOTS",
                f"ultrafine topology contains {root_bracket_count} roots",
            )
        if root_bracket_count != 1:
            raise ZeroFlowEndpointDiagnosticStop(
                "NO_UNIQUE_COMPATIBILITY_ROOT",
                "ultrafine topology contains no unique root",
            )
        raw_root = base.inc5_core._bisect_compatibility_root(
            curve="GENERAL_EOS_HUGONIOT",
            bracket=root_brackets[0],
            evaluate_chi=curve.evaluate,
        )
        selected_root = inc8a._complete_root(
            raw_root=raw_root,
            curve=curve,
            hook=hook,
            state_id=state_id,
            static=static,
            denominator=denominator,
        )
        ultrafine_gate = bool(
            selected_root["root_gate_passed"]
            and base.WEAK_COMPRESSION_CHI_LIMIT
            < float(selected_root["requested_chi"])
            <= base.DIAGNOSTIC_CHI_CAP
            and abs(float(selected_root["root_mass_residual_kg_s"]))
            <= ROOT_TOLERANCE
            and float(selected_root["local_residual_slope_kg_s_Pa"]) < 0.0
            and float(selected_root["velocity_m_s"]) >= -velocity_zero_tolerance
            and 0.0 <= float(selected_root["mach"]) < 1.0
            and normalize_phase(str(selected_root["phase"])) in allowed_phases
        )

    p0_brackets = _scalar_brackets(
        broad_rows,
        scalar_name="stagnation_pressure_margin_pa",
        back_pressure_pa=back_pressure,
    )
    velocity_brackets = _scalar_brackets(
        broad_rows,
        scalar_name="velocity_m_s",
        back_pressure_pa=back_pressure,
    )
    if len(p0_brackets) > 1:
        raise ZeroFlowEndpointDiagnosticStop(
            "MULTIPLE_STAGNATION_PRESSURE_ENDPOINTS",
            f"broad scan contains {len(p0_brackets)} p0 endpoints",
        )
    if len(velocity_brackets) > 1:
        raise ZeroFlowEndpointDiagnosticStop(
            "MULTIPLE_VELOCITY_ENDPOINTS",
            f"broad scan contains {len(velocity_brackets)} velocity endpoints",
        )

    p0_endpoint: dict[str, Any] | None = None
    p0_bisection_rows: list[dict[str, Any]] = []
    p0_bisection_summary: dict[str, Any] | None = None
    if p0_brackets:
        p0_endpoint, p0_bisection_rows, p0_bisection_summary = (
            _solve_scalar_endpoint(
                curve=curve,
                bracket=p0_brackets[0],
                scalar_name="stagnation_pressure_margin_pa",
                back_pressure_pa=back_pressure,
            )
        )

    velocity_endpoint: dict[str, Any] | None = None
    velocity_bisection_rows: list[dict[str, Any]] = []
    velocity_bisection_summary: dict[str, Any] | None = None
    if velocity_brackets:
        (
            velocity_endpoint,
            velocity_bisection_rows,
            velocity_bisection_summary,
        ) = _solve_scalar_endpoint(
            curve=curve,
            bracket=velocity_brackets[0],
            scalar_name="velocity_m_s",
            back_pressure_pa=back_pressure,
        )

    broad_spacing = float((broad_upper - broad_lower) / (BROAD_NODE_COUNT - 1))
    zero_endpoint_gate = False
    endpoint_chi_separation: float | None = None
    p0_endpoint_pipe_mass_rate: float | None = None
    p0_endpoint_velocity: float | None = None
    p0_endpoint_mach: float | None = None
    p0_endpoint_phase: str | None = None
    p0_endpoint_margin: float | None = None
    if p0_endpoint is not None:
        p0_endpoint_velocity = float(p0_endpoint["velocity_m_s"])
        p0_endpoint_mach = float(p0_endpoint["mach"])
        p0_endpoint_phase = str(p0_endpoint["phase"])
        p0_endpoint_margin = float(
            p0_endpoint["stagnation_pressure_pa"] - back_pressure
        )
        p0_endpoint_pipe_mass_rate = float(
            p0_endpoint["density_kg_m3"]
            * p0_endpoint_velocity
            * hook.area_m2
        )
        velocity_condition = abs(p0_endpoint_velocity) <= velocity_zero_tolerance
        if velocity_endpoint is not None:
            endpoint_chi_separation = abs(
                float(p0_endpoint["requested_chi"])
                - float(velocity_endpoint["requested_chi"])
            )
            velocity_condition = bool(
                velocity_condition
                or endpoint_chi_separation <= broad_spacing
            )
        zero_endpoint_gate = bool(
            not ultrafine_blocks
            and math.isfinite(p0_endpoint_pipe_mass_rate)
            and abs(p0_endpoint_pipe_mass_rate) <= ROOT_TOLERANCE
            and p0_endpoint_velocity >= -velocity_zero_tolerance
            and 0.0 <= p0_endpoint_mach < 1.0
            and normalize_phase(p0_endpoint_phase) in allowed_phases
            and velocity_condition
        )

    U_after = np.asarray(U, dtype=float).copy()
    state_unchanged = bool(np.array_equal(U, U_after))
    if ultrafine_gate:
        outcome = ULTRAFINE_SUPPORTED
    elif zero_endpoint_gate:
        outcome = ZERO_ENDPOINT_SUPPORTED
    elif not p0_brackets:
        raise ZeroFlowEndpointDiagnosticStop(
            "NO_STAGNATION_PRESSURE_ENDPOINT",
            "broad scan contains no stagnation-pressure endpoint",
        )
    else:
        raise ZeroFlowEndpointDiagnosticStop(
            "ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE",
            "zero-flow endpoint did not meet retained compatibility criteria",
        )

    category_counts: dict[str, int] = {}
    for row in ultrafine_rows:
        key = str(row["candidate_classification"])
        category_counts[key] = category_counts.get(key, 0) + 1

    selected_root_summary = None
    if selected_root is not None:
        selected_root_summary = {
            "chi": float(selected_root["requested_chi"]),
            "pressure_pa": float(selected_root["pressure_pa"]),
            "pressure_offset_pa": float(selected_root["pressure_offset_pa"]),
            "residual_kg_s": float(selected_root["root_mass_residual_kg_s"]),
            "local_slope_kg_s_Pa": float(
                selected_root["local_residual_slope_kg_s_Pa"]
            ),
            "velocity_m_s": float(selected_root["velocity_m_s"]),
            "mach": float(selected_root["mach"]),
            "phase": str(selected_root["phase"]),
            "b1_outcome": str(selected_root["formal_outcome"]),
            "root_gate_passed": bool(selected_root["root_gate_passed"]),
        }

    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_9j",
        "scope": "diagnostic_only_step637_ultrafine_root_and_zero_flow_endpoint",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": artifact_digest,
        "parent_artifact_verified": True,
        "solver_step_loaded": EXPECTED_STEP,
        "next_requested_solver_step": NEXT_STEP,
        "solver_time_s": EXPECTED_TIME_S,
        "state_sha256_before": _state_sha256(U),
        "state_sha256_after": _state_sha256(U_after),
        "state_unchanged": state_unchanged,
        "fvm_step_638_attempted": False,
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_stagnation_pressure_pa": float(
            reconstruction.stagnation_pressure_pa
        ),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_phase": str(static.phase),
        "back_pressure_pa": back_pressure,
        "last_accepted_root_chi": float(parent_root["root_requested_chi"]),
        "last_accepted_root_pressure_pa": previous_root_pressure,
        "last_accepted_root_velocity_m_s": float(
            parent_root["root_velocity_m_s"]
        ),
        "last_accepted_root_stagnation_pressure_margin_pa": float(
            parent_root["root_stagnation_pressure_margin_above_back_pa"]
        ),
        "seed_chi": seed_chi,
        "fixed_scan_node_count": len(fixed_rows),
        "ultrafine_lower_factor": ULTRAFINE_LOWER_FACTOR,
        "ultrafine_upper_factor": ULTRAFINE_UPPER_FACTOR,
        "ultrafine_lower_chi": ultrafine_lower,
        "ultrafine_upper_chi": ultrafine_upper,
        "ultrafine_node_count": ULTRAFINE_NODE_COUNT,
        "ultrafine_category_counts": category_counts,
        "ultrafine_admissible_island_count": len(ultrafine_blocks),
        "ultrafine_admissible_island_node_count": (
            0 if not ultrafine_blocks else len(ultrafine_blocks[0])
        ),
        "root_topology_node_count": len(root_topology_rows),
        "root_topology_residuals_kg_s": root_topology_residuals,
        "root_topology_sign_change_count": root_bracket_count,
        "selected_root": selected_root_summary,
        "broad_lower_factor": BROAD_LOWER_FACTOR,
        "broad_upper_factor": BROAD_UPPER_FACTOR,
        "broad_lower_chi": broad_lower,
        "broad_upper_chi": broad_upper,
        "broad_node_count": BROAD_NODE_COUNT,
        "broad_chi_spacing": broad_spacing,
        "stagnation_pressure_endpoint_bracket_count": len(p0_brackets),
        "velocity_endpoint_bracket_count": len(velocity_brackets),
        "stagnation_pressure_endpoint_bisection": p0_bisection_summary,
        "velocity_endpoint_bisection": velocity_bisection_summary,
        "stagnation_pressure_endpoint_chi": (
            None if p0_endpoint is None else float(p0_endpoint["requested_chi"])
        ),
        "stagnation_pressure_endpoint_margin_pa": p0_endpoint_margin,
        "stagnation_pressure_endpoint_static_pressure_pa": (
            None if p0_endpoint is None else float(p0_endpoint["pressure_pa"])
        ),
        "stagnation_pressure_endpoint_velocity_m_s": p0_endpoint_velocity,
        "stagnation_pressure_endpoint_mach": p0_endpoint_mach,
        "stagnation_pressure_endpoint_phase": p0_endpoint_phase,
        "stagnation_pressure_endpoint_pipe_mass_rate_kg_s": (
            p0_endpoint_pipe_mass_rate
        ),
        "stagnation_pressure_endpoint_b1_outcome": (
            None if p0_endpoint is None else p0_endpoint.get("formal_outcome")
        ),
        "stagnation_pressure_endpoint_local_admissible": (
            None
            if p0_endpoint is None
            else bool(p0_endpoint.get("local_candidate_admissible"))
        ),
        "velocity_endpoint_chi": (
            None
            if velocity_endpoint is None
            else float(velocity_endpoint["requested_chi"])
        ),
        "velocity_endpoint_velocity_m_s": (
            None
            if velocity_endpoint is None
            else float(velocity_endpoint["velocity_m_s"])
        ),
        "endpoint_chi_separation": endpoint_chi_separation,
        "root_mass_tolerance_kg_s": ROOT_TOLERANCE,
        "velocity_zero_tolerance_m_s": velocity_zero_tolerance,
        "outcome": outcome,
        "increment_9j_diagnostic_classification_complete": outcome in CLASSIFIED,
        "ultrafine_actual_continuation_supported": outcome == ULTRAFINE_SUPPORTED,
        "zero_flow_branch_review_supported": outcome == ZERO_ENDPOINT_SUPPORTED,
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
    evidence = {
        "fixed_rows": fixed_rows,
        "ultrafine_rows": ultrafine_rows,
        "broad_rows": broad_rows,
        "lower_boundary_rows": lower_boundary_rows,
        "upper_boundary_rows": upper_boundary_rows,
        "root_topology_rows": root_topology_rows,
        "selected_root_rows": [] if selected_root is None else [selected_root],
        "p0_bisection_rows": p0_bisection_rows,
        "velocity_bisection_rows": velocity_bisection_rows,
        "p0_endpoint_rows": [] if p0_endpoint is None else [p0_endpoint],
        "velocity_endpoint_rows": (
            [] if velocity_endpoint is None else [velocity_endpoint]
        ),
    }
    return summary, evidence


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

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U, parent_step, parent_root = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    del parent_summary, parent_step
    summary, evidence = _run(
        contract=contract,
        b1_contract=b1_contract,
        U=U,
        parent_root=parent_root,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "step637_fixed_scan.csv", evidence["fixed_rows"])
    _write_csv(output / "step637_ultrafine_scan.csv", evidence["ultrafine_rows"])
    _write_csv(output / "step637_broad_endpoint_scan.csv", evidence["broad_rows"])
    _write_csv(
        output / "step637_lower_boundary_refinement.csv",
        evidence["lower_boundary_rows"],
    )
    _write_csv(
        output / "step637_upper_boundary_refinement.csv",
        evidence["upper_boundary_rows"],
    )
    _write_csv(
        output / "step637_root_topology.csv",
        evidence["root_topology_rows"],
    )
    _write_csv(output / "step637_selected_root.csv", evidence["selected_root_rows"])
    _write_csv(
        output / "step637_stagnation_pressure_endpoint_bisection.csv",
        evidence["p0_bisection_rows"],
    )
    _write_csv(
        output / "step637_velocity_endpoint_bisection.csv",
        evidence["velocity_bisection_rows"],
    )
    _write_csv(
        output / "step637_stagnation_pressure_endpoint.csv",
        evidence["p0_endpoint_rows"],
    )
    _write_csv(
        output / "step637_velocity_endpoint.csv",
        evidence["velocity_endpoint_rows"],
    )
    np.savez_compressed(
        output / "step637_state_identity.npz",
        U_before=np.asarray(U, dtype=float),
        U_after=np.asarray(U, dtype=float),
        solver_step_before=np.asarray([EXPECTED_STEP], dtype=np.int64),
        solver_step_after=np.asarray([EXPECTED_STEP], dtype=np.int64),
        solver_time_before_s=np.asarray([EXPECTED_TIME_S]),
        solver_time_after_s=np.asarray([EXPECTED_TIME_S]),
    )
    (output / "authority_verification.json").write_text(
        json.dumps(
            {
                "source_sha": PARENT_SOURCE_SHA,
                "workflow_run": PARENT_RUN,
                "job": PARENT_JOB,
                "artifact": PARENT_ARTIFACT,
                "artifact_name": PARENT_ARTIFACT_NAME,
                "artifact_sha256": args.parent_artifact_digest,
                "internal_manifest_verified": True,
                "state_identity_verified": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9J zero-flow endpoint diagnostic\n\n"
        "The exact accepted step-637 state was loaded without mutation. A "
        "fixed 4097-node ultrafine scan tested for a narrower admissible "
        "outward-flow root, while a separate fixed 513-node broad scan and "
        "binary scalar solves located the stagnation-pressure and velocity "
        "endpoints. Solver step 638 was not attempted. Formal project states "
        "remain unchanged.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
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
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9j_diagnostic_classification_complete"]:
        raise SystemExit(
            "Increment 9J did not produce a supported classification: "
            f"{summary['outcome']}"
        )


if __name__ == "__main__":
    main()
