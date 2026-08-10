from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.u3_b2_fvm_discharge_finite_pipe import (
    ACOUSTIC_EVENT_NOT_RESOLVED,
    BASELINE_CASE_IDS,
    SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING,
    FinitePipePackage,
    FinitePipeRun,
    detect_acoustic_event,
    sample_locked_probes,
    write_preflight_package,
)

SOURCE = Path(
    "src/liquid_gas_transient/u3_b2_fvm_discharge_finite_pipe.py"
)


def _extension() -> dict:
    return {
        "acoustic_event_detection": {
            "spatial_probe_sampling": {
                "fixed_mesh_probe_map": [
                    {
                        "cells": 4,
                        "entries": [
                            {
                                "xi_probe": 0.25,
                                "left_internal_index": 0,
                                "left_center_xi": 0.125,
                                "right_internal_index": 1,
                                "right_center_xi": 0.375,
                                "lambda": 0.5,
                            },
                            {
                                "xi_probe": 0.5,
                                "left_internal_index": 1,
                                "left_center_xi": 0.375,
                                "right_internal_index": 2,
                                "right_center_xi": 0.625,
                                "lambda": 0.5,
                            },
                            {
                                "xi_probe": 0.75,
                                "left_internal_index": 2,
                                "left_center_xi": 0.625,
                                "right_internal_index": 3,
                                "right_center_xi": 0.875,
                                "lambda": 0.5,
                            },
                        ],
                    }
                ]
            }
        }
    }


def test_finite_pipe_module_does_not_import_b2_reference() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("u3_b2_fvm_discharge_reference" in name for name in imported)


def test_locked_baseline_case_order_is_stable() -> None:
    assert BASELINE_CASE_IDS == (
        "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE",
        "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT",
        "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT",
    )


def test_locked_probe_interpolation_uses_declared_brackets() -> None:
    primitive = SimpleNamespace(
        p=np.asarray([10.0, 20.0, 30.0, 40.0]),
        u=np.asarray([1.0, 2.0, 3.0, 4.0]),
    )
    rows = sample_locked_probes(
        primitive=primitive,
        extension=_extension(),
        run_id="RUN",
        case_id="CASE",
        state_id="LIQUID_SMALL_DROP",
        cells=4,
        cfl=0.1,
        step=2,
        time_s=0.5,
    )
    assert [row["probe_normalized_position"] for row in rows] == [0.25, 0.5, 0.75]
    assert [row["pressure_pa"] for row in rows] == [15.0, 25.0, 35.0]
    assert [row["axial_velocity_m_s"] for row in rows] == [1.5, 2.5, 3.5]


def test_direct_event_uses_minimum_centered_pressure_slope() -> None:
    rows = [
        {"time_s": 0.0, "pressure_pa": 0.0, "axial_velocity_m_s": 0.0},
        {"time_s": 1.0, "pressure_pa": 0.0, "axial_velocity_m_s": 0.0},
        {"time_s": 2.0, "pressure_pa": -1.0, "axial_velocity_m_s": 1.0},
        {"time_s": 3.0, "pressure_pa": -4.0, "axial_velocity_m_s": 3.0},
        {"time_s": 4.0, "pressure_pa": -4.0, "axial_velocity_m_s": 3.0},
    ]
    event = detect_acoustic_event(
        rows,
        event_kind="direct",
        reference_time_s=2.0,
        window_half_width_s=1.5,
        relative_tolerance=0.1,
    )
    assert event["formal_outcome"] == SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
    assert event["detected_time_s"] == 2.0
    assert event["pressure_sign_passed"] is True
    assert event["velocity_sign_passed"] is True
    assert event["arrival_tolerance_passed"] is True


def test_reflected_event_requires_negative_velocity_change() -> None:
    rows = [
        {"time_s": 2.0, "pressure_pa": 0.0, "axial_velocity_m_s": 2.0},
        {"time_s": 3.0, "pressure_pa": 0.0, "axial_velocity_m_s": 2.0},
        {"time_s": 4.0, "pressure_pa": -1.0, "axial_velocity_m_s": 1.0},
        {"time_s": 5.0, "pressure_pa": -4.0, "axial_velocity_m_s": -1.0},
        {"time_s": 6.0, "pressure_pa": -4.0, "axial_velocity_m_s": -1.0},
    ]
    event = detect_acoustic_event(
        rows,
        event_kind="reflected",
        reference_time_s=4.0,
        window_half_width_s=1.5,
        relative_tolerance=0.1,
    )
    assert event["formal_outcome"] == SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
    assert event["detected_time_s"] == 4.0
    assert event["velocity_delta_m_s"] < 0.0


def test_event_without_centered_candidate_is_unresolved() -> None:
    event = detect_acoustic_event(
        [{"time_s": 0.0, "pressure_pa": 0.0, "axial_velocity_m_s": 0.0}],
        event_kind="direct",
        reference_time_s=1.0,
        window_half_width_s=0.1,
        relative_tolerance=0.1,
    )
    assert event["formal_outcome"] == ACOUSTIC_EVENT_NOT_RESOLVED
    assert event["candidate_count"] == 0


def test_preflight_writer_retains_false_formal_flags(tmp_path: Path) -> None:
    run = FinitePipeRun(
        summary={
            "run_id": "R",
            "case_id": "C",
            "formal_outcome": SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING,
        },
        step_history=({"run_id": "R", "step": 1},),
        probe_history=({"run_id": "R", "time_s": 0.0},),
        acoustic_events=({"run_id": "R", "event_kind": "direct"},),
    )
    package = FinitePipePackage(
        runs=(run,),
        summary={
            "run_count": 1,
            "all_baseline_runs_passed": True,
            "total_accepted_steps": 1,
            "total_probe_rows": 1,
            "total_acoustic_event_rows": 1,
            "u3_b2_finite_pipe_execution_complete": False,
            "single_phase_finite_pipe_coupling_verified": False,
            "u3_b2_verification_benchmark_accepted": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        },
    )
    contract = tmp_path / "contract.json"
    extension = tmp_path / "extension.json"
    b1_contract = tmp_path / "b1.json"
    for path in (contract, extension, b1_contract):
        path.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "artifact"
    write_preflight_package(
        package,
        output_dir=output,
        contract_path=contract,
        extension_path=extension,
        b1_contract_path=b1_contract,
        source_git_sha="abc",
    )
    summary = __import__("json").loads((output / "summary.json").read_text())
    assert summary["u3_b2_finite_pipe_execution_complete"] is False
    assert summary["single_phase_finite_pipe_coupling_verified"] is False
    assert summary["u3_b2_verification_benchmark_accepted"] is False
    assert "physical_validation = false" in (output / "report.md").read_text()
    manifest = (output / "artifact_sha256.txt").read_text().splitlines()
    assert manifest
