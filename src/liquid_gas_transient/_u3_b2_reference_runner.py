"""Artifact assembly for the independent U3 B2 Reference."""
from __future__ import annotations
import hashlib
import json
import math
import os
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Any
from ._u3_b2_reference_acoustic import acoustic_arrival_rows, mesh_cfl_reference_rows
from ._u3_b2_reference_b1 import RepositoryB1Authority
from ._u3_b2_reference_balance import build_inventory_ledger, one_step_reference
from ._u3_b2_reference_checks import locked_checks
from ._u3_b2_reference_contract import SCHEMA_VERSION, load_contracts
from ._u3_b2_reference_face import evaluate_face_reference
from ._u3_b2_reference_io import artifact_manifest, write_csv, write_plots
from ._u3_b2_reference_properties import CoolPropPropertyProvider

def write_artifact(
    contract_path: Path,
    extension_path: Path,
    b1_contract_path: Path,
    output_dir: Path,
    *,
    source_git_sha: str,
) -> dict[str, Any]:
    contract, extension = load_contracts(contract_path, extension_path)
    provider = CoolPropPropertyProvider()
    b1_authority = RepositoryB1Authority(
        b1_contract_path,
        b1_source_sha=contract["depends_on"]["u3_b1"]["reference_source_sha"],
    )
    results = [
        evaluate_face_reference(contract, extension, row, provider, b1_authority)
        for row in contract["benchmark_cases"]
    ]
    by_id = {row.case_id: row for row in results}
    one_step = one_step_reference(
        contract,
        by_id["B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"],
    )
    ledger = build_inventory_ledger(
        by_id["B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"], one_step
    )
    liquid_sound_speed = float(
        by_id["B2-04_SMALL_DROP_RECOVERS_B0_FACE_LIMIT"].adjacent_sound_speed_m_s
        or math.nan
    )
    acoustic = acoustic_arrival_rows(
        contract, extension, liquid_sound_speed
    )
    matrix_rows = mesh_cfl_reference_rows(contract, acoustic)
    check_rows, checks = locked_checks(
        contract, extension, results, one_step, acoustic
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "benchmark_contract.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "event_provenance_contract.json").write_text(
        json.dumps(extension, indent=2) + "\n", encoding="utf-8"
    )

    state_rows = []
    seen_states: set[str] = set()
    for result in results:
        if not result.succeeded or result.state_id in seen_states:
            continue
        seen_states.add(result.state_id)
        state_rows.append(
            {
                "state_id": result.state_id,
                "pressure_pa": result.adjacent_pressure_pa,
                "temperature_K": result.adjacent_temperature_K,
                "density_kg_m3": result.adjacent_density_kg_m3,
                "internal_energy_J_kg": result.adjacent_internal_energy_J_kg,
                "enthalpy_J_kg": result.adjacent_enthalpy_J_kg,
                "entropy_J_kg_K": result.adjacent_entropy_J_kg_K,
                "sound_speed_m_s": result.adjacent_sound_speed_m_s,
                "phase": result.adjacent_phase,
                "stagnation_pressure_pa": result.stagnation_pressure_pa,
                "stagnation_temperature_K": result.stagnation_temperature_K,
            }
        )
    write_csv(output_dir / "state_family_properties.csv", state_rows)
    write_csv(
        output_dir / "face_state_and_choking_adoption.csv",
        [
            {
                "case_id": row.case_id,
                "state_id": row.state_id,
                "formal_outcome": row.formal_outcome,
                "external_back_pressure_pa": row.external_back_pressure_pa,
                "adjacent_pressure_pa": row.adjacent_pressure_pa,
                "stagnation_pressure_pa": row.stagnation_pressure_pa,
                "b1_formal_outcome": row.b1_formal_outcome,
                "discharge_evaluation_pressure_pa": row.discharge_evaluation_pressure_pa,
                "critical_pressure_pa": row.critical_pressure_pa,
                "critical_pressure_ratio": row.critical_pressure_ratio,
                "reference_status": row.reference_status,
            }
            for row in results
        ],
    )
    write_csv(output_dir / "face_flux_reference.csv", [asdict(row) for row in results])
    write_csv(output_dir / "one_step_balance_reference.csv", [asdict(one_step)])
    write_csv(output_dir / "inventory_ledger_reference.csv", [asdict(row) for row in ledger])
    write_csv(output_dir / "acoustic_arrival_reference.csv", [asdict(row) for row in acoustic])
    write_csv(
        output_dir / "probe_mapping_reference.csv",
        [
            {
                "cells": row.cells,
                "requested_x_over_L": row.probe_x_over_L,
                "left_cell_index_zero_based": row.left_cell_index_zero_based,
                "right_cell_index_zero_based": row.right_cell_index_zero_based,
                "left_center_x_over_L": row.left_center_x_over_L,
                "right_center_x_over_L": row.right_center_x_over_L,
                "interpolation_weight_right": row.interpolation_weight_right,
                "arrival_reference_coordinate": row.probe_x_over_L,
            }
            for row in acoustic
        ],
    )
    write_csv(output_dir / "mesh_cfl_reference.csv", matrix_rows)
    write_csv(
        output_dir / "guard_outcomes.csv",
        [asdict(row) for row in results if not row.succeeded],
    )
    write_csv(output_dir / "locked_checks.csv", check_rows)

    workflow_run_id = os.environ.get("GITHUB_RUN_ID", "local")
    write_plots(
        output_dir,
        results,
        one_step,
        acoustic,
        backend_version=provider.version,
        source_git_sha=source_git_sha,
        workflow_run_id=workflow_run_id,
    )

    contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    extension_sha = hashlib.sha256(extension_path.read_bytes()).hexdigest()
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": "verification_only_u3_b2_independent_reference",
        "issue": contract["issue"],
        "case_count": len(results),
        "physical_case_count": sum(row.succeeded for row in results),
        "guard_case_count": sum(not row.succeeded for row in results),
        "formal_outcome_match_count": sum(
            row.formal_outcome == row.expected_outcome for row in results
        ),
        "reference_layers": [
            "face_flux_algebra",
            "one_step_finite_volume_balance",
            "mass_energy_inventory_ledger",
            "linear_acoustic_MOC_arrival_reference",
            "fixed_probe_interpolation",
            "formal_guard_outcomes",
        ],
        **checks,
        "contract_sha256": contract_sha,
        "event_provenance_contract_sha256": extension_sha,
        "u3_b2_contract_locked": True,
        "u3_b2_reference_implemented": True,
        "u3_b2_fvm_adapter_implemented": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "u3_b2_verification_benchmark_accepted": False,
        "single_phase_fvm_discharge_mapping_verified": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "physical_discharge_boundary_approved": False,
        "two_phase_critical_discharge_accuracy_approved": False,
        "integrated_blowdown_model_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "provenance": {
            "analysis_source_git_sha": source_git_sha,
            "checkout_git_sha": os.environ.get("GITHUB_SHA", ""),
            "workflow_run_id": workflow_run_id,
            "property_backend": contract["property_backend"]["name"],
            "property_backend_version": provider.version,
            "python_version": platform.python_version(),
            "b1_reference_source_sha": contract["depends_on"]["u3_b1"][
                "reference_source_sha"
            ],
            "tracked_git_status": "",
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = [
        "# Stage 7 U3 B2 independent FVM discharge-coupling reference",
        "",
        f"- fixed cases: {summary['case_count']}",
        f"- physical / Guard: {summary['physical_case_count']} / {summary['guard_case_count']}",
        f"- formal outcomes matched: {summary['formal_outcome_match_count']} / {summary['case_count']}",
        f"- all locked checks passed: {summary['all_locked_checks_passed']}",
        "",
        "## Implemented reference layers",
        "",
    ]
    report.extend(f"- {layer}" for layer in summary["reference_layers"])
    report.extend(
        [
            "",
            "## One-step balance",
            "",
            f"- accepted dt: {one_step.accepted_dt_s:.12g} s",
            f"- mass residual: {one_step.mass_inventory_residual_kg:.12g} kg",
            f"- energy residual: {one_step.energy_inventory_residual_J:.12g} J",
            f"- momentum residual: {one_step.momentum_inventory_residual_kg_m_s:.12g} kg m/s",
            "",
            "## Approval boundary",
            "",
            "This artifact implements the independent B2 Reference only. The FVM "
            "Adapter, finite-pipe execution, physical discharge-boundary approval, "
            "physical validation, design use, and production activation remain false.",
            "",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    artifact_manifest(output_dir)
    return summary
