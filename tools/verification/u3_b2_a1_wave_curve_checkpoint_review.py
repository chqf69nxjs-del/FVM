from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from u3_b2_a1_wave_curve_model import (
    CASE_ID,
    EXPECTED_ACCEPTED_STEPS,
    EXPECTED_STOP_TOKEN,
    PARENT_NUMERICAL_SOURCE_SHA,
    PRESSURE_OFFSETS_PA,
    _brackets,
    _inventory_array,
    _scan_row,
    _sha256,
    _write_csv,
)
from u3_b2_characteristic_port_dynamic_short_metrics import inventory


def _capture_checkpoint(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> dict[str, Any]:
    capture: dict[str, Any] = {}
    original = horizon.A1TwoLOverC0Hook._ensure_root

    def wrapped(self: Any, U: np.ndarray, t: float) -> None:
        try:
            original(self, U, t)
        except Exception as exc:
            capture.update(
                U=np.array(U, dtype=float, copy=True),
                time_s=float(t),
                hook=self,
                previous_root_pressure_pa=getattr(
                    self,
                    "_previous_root_pressure_pa",
                    None,
                ),
                exception_type=type(exc).__name__,
                exception_message=str(exc),
            )
            raise

    horizon.A1TwoLOverC0Hook._ensure_root = wrapped
    try:
        rows, case_summary = horizon._run_case(
            contract=contract,
            b1_contract=b1_contract,
        )
    finally:
        horizon.A1TwoLOverC0Hook._ensure_root = original

    if "U" not in capture:
        raise RuntimeError(
            "the expected next-step root stop was not captured"
        )
    complete = [
        row
        for row in rows
        if row.get("accepted_step") is True and "root_mach" in row
    ]
    capture["rows"] = rows
    capture["case_summary"] = case_summary
    capture["reproduction_ok"] = bool(
        int(case_summary["accepted_steps_completed"])
        == EXPECTED_ACCEPTED_STEPS
        and EXPECTED_STOP_TOKEN in str(case_summary["stop_reason"])
        and int(case_summary["accepted_steps_completed"]) == len(complete)
    )
    return capture


def _classify(
    reproduction_ok: bool,
    rows: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    endpoint = next(
        row
        for row in rows
        if float(row["pressure_offset_pa"]) == 0.0
    )
    evaluable = _brackets(rows, admissible_only=False)
    admissible = _brackets(rows, admissible_only=True)
    negative = [
        row
        for row in admissible
        if float(row["upper_offset_pa"]) <= 0.0
    ]
    positive = [
        row
        for row in admissible
        if float(row["lower_offset_pa"]) >= 0.0
    ]
    details = {
        "endpoint_residual_kg_s": endpoint.get(
            "compatibility_residual_kg_s"
        ),
        "endpoint_within_locked_root_mass_tolerance": endpoint.get(
            "within_locked_root_mass_tolerance"
        ),
        "endpoint_admissible": endpoint.get(
            "local_candidate_admissible"
        ),
        "endpoint_root_closure_passed": endpoint.get(
            "root_closure_passed"
        ),
        "evaluable_sign_change_brackets": evaluable,
        "admissible_sign_change_brackets": admissible,
        "negative_side_admissible_sign_change_count": len(negative),
        "positive_side_admissible_sign_change_count": len(positive),
    }
    if not reproduction_ok:
        return "CHECKPOINT_REPRODUCTION_MISMATCH", details
    if endpoint.get("root_closure_passed"):
        return "NEUTRAL_ENDPOINT_WITHIN_LOCKED_TOLERANCE", details
    if len(admissible) > 1:
        return "MULTIPLE_LOCAL_ROOT_BRANCHES", details
    if len(positive) == 1 and not negative:
        return "LOCAL_COMPRESSION_CONTINUATION_ROOT_SUPPORTED", details
    if len(negative) == 1 and not positive:
        return "RAREFACTION_ROOT_RETAINED", details
    if evaluable and not admissible:
        return "LOCAL_ROOT_INADMISSIBLE", details
    return "NO_LOCAL_COMPATIBLE_ROOT", details


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

    capture = _capture_checkpoint(contract, b1_contract)
    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = capture["hook"].provider
    U_initial, _ = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    initial_inventory = inventory(
        U_initial,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current_inventory = inventory(
        capture["U"],
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    reconstruction = provider.reconstruct_from_conserved(
        capture["U"][-1]
    )
    static = reconstruction.static
    diagnostic.QUADRATURE_ORDER = 32
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(
            contract,
            state_id,
        )["allowed_normalized_phases"]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    scan_rows = [
        _scan_row(
            offset_pa=offset,
            static=static,
            isentrope=isentrope,
            hook=capture["hook"],
            area_m2=float(grid.geometry.area_m2),
            allowed_phases=allowed_phases,
            velocity_tolerance=velocity_tolerance,
        )
        for offset in PRESSURE_OFFSETS_PA
    ]
    classification, details = _classify(
        bool(capture["reproduction_ok"]),
        scan_rows,
    )
    evidence_gate = bool(
        capture["reproduction_ok"]
        and len(scan_rows) == len(PRESSURE_OFFSETS_PA)
        and all(row.get("evaluation_succeeded") for row in scan_rows)
    )
    continuation_supported = classification in {
        "NEUTRAL_ENDPOINT_WITHIN_LOCKED_TOLERANCE",
        "LOCAL_COMPRESSION_CONTINUATION_ROOT_SUPPORTED",
        "RAREFACTION_ROOT_RETAINED",
    }
    previous_root = capture["previous_root_pressure_pa"]
    previous_root_value = (
        math.nan if previous_root is None else float(previous_root)
    )
    current_minus_initial = (
        _inventory_array(current_inventory)
        - _inventory_array(initial_inventory)
    )
    complete_rows = [
        row
        for row in capture["rows"]
        if row.get("accepted_step") is True and "root_mach" in row
    ]
    last_complete = complete_rows[-1]
    cumulative_expected_delta = np.asarray(
        [
            current_minus_initial[0]
            - float(last_complete["cumulative_mass_residual_kg"]),
            current_minus_initial[1]
            - float(
                last_complete[
                    "cumulative_momentum_residual_kg_m_s"
                ]
            ),
            current_minus_initial[2]
            - float(last_complete["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )

    checkpoint = {
        "schema_version": "stage7_u3_b2_a1_wave_curve_checkpoint_v1",
        "source_git_sha": args.source_git_sha,
        "parent_numerical_source_sha": PARENT_NUMERICAL_SOURCE_SHA,
        "case_id": CASE_ID,
        "state_id": state_id,
        "reproduction_ok": bool(capture["reproduction_ok"]),
        "expected_accepted_steps": EXPECTED_ACCEPTED_STEPS,
        "accepted_steps": int(
            capture["case_summary"]["accepted_steps_completed"]
        ),
        "solver_time_s": float(capture["time_s"]),
        "stop_exception_type": capture["exception_type"],
        "stop_reason": (
            f'{capture["exception_type"]}: '
            f'{capture["exception_message"]}'
        ),
        "previous_root_pressure_pa": (
            None
            if math.isnan(previous_root_value)
            else previous_root_value
        ),
        "cells": int(grid.n_cells),
        "dx_m": float(grid.dx),
        "cfl": float(geometry["baseline_cfl"]),
        "outlet_static": {
            "pressure_pa": float(static.pressure_pa),
            "temperature_K": float(static.temperature_K),
            "density_kg_m3": float(static.density_kg_m3),
            "internal_energy_J_kg": float(
                static.internal_energy_J_kg
            ),
            "enthalpy_J_kg": float(static.enthalpy_J_kg),
            "entropy_J_kg_K": float(static.entropy_J_kg_K),
            "sound_speed_m_s": float(static.sound_speed_m_s),
            "phase": static.phase,
            "velocity_m_s": float(static.velocity_m_s),
        },
        "outlet_stagnation": {
            "pressure_pa": float(
                reconstruction.stagnation_pressure_pa
            ),
            "temperature_K": float(
                reconstruction.stagnation_temperature_K
            ),
            "enthalpy_J_kg": float(
                reconstruction.stagnation_enthalpy_J_kg
            ),
            "entropy_J_kg_K": float(
                reconstruction.stagnation_entropy_J_kg_K
            ),
        },
        "initial_inventory": initial_inventory,
        "current_inventory": current_inventory,
        "cumulative_expected_delta": [
            float(value) for value in cumulative_expected_delta
        ],
        "runtime": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "CoolProp": importlib.metadata.version("CoolProp"),
        },
    }
    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_wave_curve_checkpoint_review_v1"
        ),
        "scope": (
            "model_review_only_checkpoint_and_local_wave_curve_scan"
        ),
        "source_git_sha": args.source_git_sha,
        "parent_numerical_source_sha": PARENT_NUMERICAL_SOURCE_SHA,
        "model_review_spec": str(args.model_review_spec),
        "fixed_pressure_offsets_pa": list(PRESSURE_OFFSETS_PA),
        "checkpoint": checkpoint,
        "classification": classification,
        "classification_details": details,
        "wave_curve_checkpoint_evidence_gate_passed": evidence_gate,
        "local_continuation_supported": continuation_supported,
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

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output / "checkpoint.npz",
        U=np.asarray(capture["U"], dtype=float),
        U_initial=np.asarray(U_initial, dtype=float),
        solver_time_s=np.asarray([float(capture["time_s"])]),
        solver_step_count=np.asarray(
            [
                int(
                    capture["case_summary"][
                        "accepted_steps_completed"
                    ]
                )
            ],
            dtype=np.int64,
        ),
        previous_root_pressure_pa=np.asarray(
            [previous_root_value]
        ),
        initial_inventory=_inventory_array(initial_inventory),
        current_inventory=_inventory_array(current_inventory),
        current_minus_initial_inventory=current_minus_initial,
        cumulative_expected_delta=cumulative_expected_delta,
    )
    (output / "checkpoint_summary.json").write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(output / "pressure_scan.csv", scan_rows)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 checkpoint and local wave-curve review\n\n"
        "MODEL_REVIEW_ONLY. The B2-10A rarefaction-side A1 run "
        "was replayed to its first next-step root stop. The "
        "captured conservative checkpoint was scanned at the "
        "fixed pressure offsets on both sides of `p_P = p_i`. "
        "Positive offsets are local isentropic continuation "
        "observations only; no finite compression branch, "
        "Contract revision, production Adapter, solver change, "
        "Physical Validation, design use, or production "
        "activation is approved.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        f"classification: `{classification}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "checkpoint.npz",
        "checkpoint_summary.json",
        "pressure_scan.csv",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n"
            for name in names
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not evidence_gate:
        raise SystemExit(
            "A1 wave-curve checkpoint evidence gate did not pass"
        )


if __name__ == "__main__":
    main()
