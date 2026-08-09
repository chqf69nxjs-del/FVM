"""Authoritative evidence writer for the U3 B2 FVM discharge-face Adapter.

This module compares the production-side Adapter with the independently
implemented U3 B2 Reference for the locked face and one-step scope.  It does
not implement finite-pipe execution and does not promote physical, design-use,
or production claims.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from . import u3_b1_critical_state_adapter as b1_adapter
from . import u3_b1_critical_state_reference as b1_reference
from . import u3_b2_fvm_discharge_reference as reference
from . import (
    u3_b2_fvm_discharge_reference_authoritative as reference_authoritative,
)
from .boundary import ReflectiveBoundary, TransmissiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .solver import FvmSolver
from .u3_b2_fvm_discharge_adapter import (
    ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
    BOUNDARY_UPDATE_POSITIVITY_FAILURE,
    INVENTORY_ORIENTATION_CONTRACT_MISMATCH,
    NONFINITE_INPUT,
    REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
    STAGNATION_RECONSTRUCTION_FAILURE,
    SUCCESS_ONE_STEP,
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    FaceEvaluation,
    U3B2FvmDischargeAdapter,
    adapter_for_case,
    build_uniform_initial_state,
    evaluate_face_case,
    evaluate_face_matrix,
    evaluate_inventory_orientation_guard,
    face_rows_as_dicts,
    load_b1_contract,
    load_contract,
    run_one_step_case,
)

SCHEMA_VERSION = "stage7_u3_b2_fvm_discharge_adapter_authority_v1"
REFERENCE_SOURCE_GIT_SHA = "0e2c8188961175b3c2cd56836296e713735bf8d9"
REFERENCE_ARTIFACT_ID = 9007750537
REFERENCE_ARTIFACT_ZIP_SHA256 = (
    "1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd"
)


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    payload = [dict(row) for row in rows]
    if not payload:
        raise ValueError(f"No rows supplied for {path.name}")
    fieldnames: list[str] = []
    for row in payload:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _allowed_error(expected: float, absolute: float, relative: float) -> float:
    return max(float(absolute), float(relative) * abs(float(expected)))


def _tracked_git_status() -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=no"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _junit_totals(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in ("tests", "skipped", "failures", "errors")
    }


def _adapter_imports_reference(adapter_source: Path) -> bool:
    tree = ast.parse(adapter_source.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    return any("u3_b2_fvm_discharge_reference" in name for name in imported)


def _reference_package(
    contract_path: Path,
    extension_path: Path,
    b1_contract_path: Path,
) -> reference.ReferencePackage:
    reference_authoritative.install_authoritative_interpretation()
    return reference.evaluate_reference(
        reference.load_contract(contract_path),
        reference.load_extension(extension_path),
        b1_reference.load_contract(b1_contract_path),
    )


def _compare_faces(
    contract: Mapping[str, Any],
    actual_rows: Sequence[FaceEvaluation],
    expected_rows: Sequence[reference.FaceReference],
) -> list[dict[str, Any]]:
    actual = {row.case_id: row for row in actual_rows}
    expected = {row.case_id: row for row in expected_rows}
    if set(actual) != set(expected):
        raise ValueError("Adapter and Reference face case sets differ")
    if len(actual) != 13:
        raise ValueError(f"Expected 13 face rows, received {len(actual)}")

    tolerances = contract["acceptance_tolerances"]
    measures = (
        (
            "F_rho_kg_m2_s",
            "reference_adapter_mass_flux_absolute_kg_m2_s",
            "reference_adapter_mass_flux_relative",
        ),
        (
            "F_rho_u_pa",
            "reference_adapter_momentum_flux_absolute_pa",
            "reference_adapter_momentum_flux_relative",
        ),
        (
            "F_rho_E_W_m2",
            "reference_adapter_energy_flux_absolute_W_m2",
            "reference_adapter_energy_flux_relative",
        ),
    )
    comparisons: list[dict[str, Any]] = []
    for case_id in sorted(expected):
        adapter_row = actual[case_id]
        reference_row = expected[case_id]
        if adapter_row.face is None:
            raise RuntimeError(f"{case_id}: Adapter face result is absent")
        outcome_match = adapter_row.formal_outcome == reference_row.formal_outcome
        for field, abs_key, rel_key in measures:
            adapter_value = float(getattr(adapter_row.face, field))
            reference_value = float(getattr(reference_row, field))
            error = abs(adapter_value - reference_value)
            allowed = _allowed_error(
                reference_value,
                float(tolerances[abs_key]),
                float(tolerances[rel_key]),
            )
            comparisons.append(
                {
                    "case_id": case_id,
                    "adapter_outcome": adapter_row.formal_outcome,
                    "reference_outcome": reference_row.formal_outcome,
                    "formal_outcome_match": outcome_match,
                    "measure": field,
                    "adapter_value": adapter_value,
                    "reference_value": reference_value,
                    "absolute_error": error,
                    "allowed_error": allowed,
                    "comparison_passed": outcome_match and error <= allowed,
                }
            )

        adapter_xv = float(adapter_row.face.F_rho_xv_kg_m2_s)
        reference_xv = float(reference_row.F_rho_xv_kg_m2_s)
        comparisons.append(
            {
                "case_id": case_id,
                "adapter_outcome": adapter_row.formal_outcome,
                "reference_outcome": reference_row.formal_outcome,
                "formal_outcome_match": outcome_match,
                "measure": "F_rho_xv_kg_m2_s",
                "adapter_value": adapter_xv,
                "reference_value": reference_xv,
                "absolute_error": abs(adapter_xv - reference_xv),
                "allowed_error": 0.0,
                "comparison_passed": (
                    outcome_match and adapter_xv == reference_xv == 0.0
                ),
            }
        )
    if len(comparisons) != 52:
        raise AssertionError(f"Expected 52 face comparisons, got {len(comparisons)}")
    return comparisons


def _one_step_comparison(
    contract: Mapping[str, Any],
    actual: Any,
    expected: reference.OneStepReference,
) -> tuple[dict[str, Any], bool]:
    tolerances = contract["acceptance_tolerances"]
    scale = max(
        abs(expected.U_after_rho),
        abs(expected.U_after_rho_u),
        abs(expected.U_after_rho_E),
        1.0,
    )
    normalized_state_error = max(
        abs(actual.U_after_rho - expected.U_after_rho),
        abs(actual.U_after_rho_u - expected.U_after_rho_u),
        abs(actual.U_after_rho_E - expected.U_after_rho_E),
        abs(actual.U_after_rho_xv - expected.U_after_rho_xv),
    ) / scale
    state_tolerance = float(tolerances["one_step_normalized_state_absolute"])
    formal_outcome_match = (
        actual.formal_outcome == expected.formal_outcome == SUCCESS_ONE_STEP
    )
    dt_constraints_passed = (
        actual.accepted_dt_s > 0.0
        and actual.accepted_dt_s <= actual.cfl_dt_s
        and actual.accepted_dt_s <= actual.mass_removal_dt_s
        and actual.accepted_dt_s <= actual.energy_removal_dt_s
    )
    mass_passed = abs(actual.mass_inventory_residual_kg) <= float(
        tolerances["mass_inventory_absolute_kg"]
    )
    momentum_passed = abs(actual.momentum_inventory_residual_kg_m_s) <= float(
        tolerances["momentum_inventory_absolute_kg_m_s"]
    )
    energy_passed = abs(actual.energy_inventory_residual_J) <= float(
        tolerances["energy_inventory_absolute_J"]
    )
    vapor_passed = (
        actual.vapor_inventory_residual_kg == 0.0
        and actual.U_after_rho_xv == 0.0
        and actual.right_F_rho_xv == 0.0
    )
    balance_passed = actual.normalized_balance_residual <= state_tolerance
    state_passed = normalized_state_error <= state_tolerance
    passed = all(
        (
            formal_outcome_match,
            dt_constraints_passed,
            state_passed,
            balance_passed,
            mass_passed,
            momentum_passed,
            energy_passed,
            vapor_passed,
        )
    )
    row = {
        **{f"adapter_{key}": value for key, value in asdict(actual).items()},
        **{f"reference_{key}": value for key, value in asdict(expected).items()},
        "formal_outcome_match": formal_outcome_match,
        "dt_constraints_passed": dt_constraints_passed,
        "normalized_state_error": normalized_state_error,
        "normalized_state_tolerance": state_tolerance,
        "state_comparison_passed": state_passed,
        "normalized_balance_passed": balance_passed,
        "mass_inventory_passed": mass_passed,
        "momentum_inventory_passed": momentum_passed,
        "energy_inventory_passed": energy_passed,
        "vapor_exact_zero_passed": vapor_passed,
        "one_step_comparison_passed": passed,
    }
    return row, passed


class _FailingStagnationProvider:
    def __init__(self) -> None:
        self._base = CoolPropB2StateProvider()
        self.version = self._base.version
        self.backend_name = self._base.backend_name

    def saturation_temperature(self, pressure_pa: float) -> float:
        return self._base.saturation_temperature(pressure_pa)

    def static_state_from_pT(
        self, pressure_pa: float, temperature_K: float, velocity_m_s: float
    ) -> Any:
        return self._base.static_state_from_pT(
            pressure_pa, temperature_K, velocity_m_s
        )

    def reconstruct_from_conserved(self, conserved: np.ndarray) -> Any:
        raise RuntimeError("synthetic HmassSmass inversion failure")


class _AlwaysRejectTrialAdapter(U3B2FvmDischargeAdapter):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.validation_calls = 0

    def validate_trial(self, **kwargs: Any) -> None:
        del kwargs
        self.validation_calls += 1
        raise ValueError("synthetic nonpositive internal energy")


def _positivity_guard_observation(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
) -> dict[str, Any]:
    case = next(
        row
        for row in contract["benchmark_cases"]
        if row["case_id"] == "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"
    )
    provider = CoolPropB2StateProvider()
    b1_provider = b1_adapter.CoolPropStateProvider()
    cells = int(case["cells"])
    geometry = contract["geometry"]
    grid = UniformGrid(
        PipeGeometry(
            length_m=float(geometry["pipe_length_m"]),
            diameter_m=float(geometry["pipe_diameter_m"]),
            roughness_m=float(geometry["roughness_m"]),
        ),
        cells,
    )
    U, static = build_uniform_initial_state(
        contract, provider, str(case["state_id"]), cells
    )
    eos = CoolPropSinglePhaseEOS(
        provider, boundary_temperature_K=static.temperature_K
    )
    base = adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=provider,
        b1_provider=b1_provider,
    )
    adapter = _AlwaysRejectTrialAdapter(
        contract=contract,
        b1_contract=b1_contract,
        state_id=base.state_id,
        back_pressure_pa=base.back_pressure_pa,
        opening_fraction=base.opening_fraction,
        discharge_coefficient=base.discharge_coefficient,
        case_id="G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE",
        provider=provider,
        b1_provider=b1_provider,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=float(case["cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=adapter,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    U_before = np.array(solver.U, copy=True)
    if solver.boundary_budget is None:
        raise AssertionError("positivity Guard requires boundary budget")
    left_before = np.array(solver.boundary_budget.cumulative_left, copy=True)
    right_before = np.array(solver.boundary_budget.cumulative_right, copy=True)
    formal_outcome = "UNEXPECTED_SUCCESS"
    formal_message = ""
    try:
        solver.step()
    except RuntimeError as exc:
        formal_message = str(exc)
        if BOUNDARY_UPDATE_POSITIVITY_FAILURE in formal_message:
            formal_outcome = BOUNDARY_UPDATE_POSITIVITY_FAILURE
    maximum_halvings = int(adapter.maximum_halvings)
    atomicity = (
        np.array_equal(solver.U, U_before)
        and solver.t == 0.0
        and solver.step_count == 0
        and np.array_equal(solver.boundary_budget.cumulative_left, left_before)
        and np.array_equal(solver.boundary_budget.cumulative_right, right_before)
        and solver.boundary_budget.last_dt_s == 0.0
    )
    attempts_passed = adapter.validation_calls == maximum_halvings + 1
    return {
        "case_id": "G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE",
        "formal_outcome": formal_outcome,
        "formal_message": formal_message,
        "guard_triggered_before_flux": atomicity,
        "guard_triggered_before_budget": atomicity,
        "guard_triggered_before_state_mutation": atomicity,
        "maximum_halvings": maximum_halvings,
        "trial_validation_calls": adapter.validation_calls,
        "halving_attempt_count_passed": attempts_passed,
        "atomicity_passed": atomicity and attempts_passed,
    }


def _evaluate_guards(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    expected_rows: Sequence[reference.GuardReference],
) -> list[dict[str, Any]]:
    cases = {str(row["case_id"]): row for row in contract["benchmark_cases"]}
    actual: dict[str, dict[str, Any]] = {}
    for case_id in (
        "G-01_REVERSE_PRESSURE",
        "G-02_REVERSE_ADJACENT_VELOCITY",
        "G-03_NONFINITE_ADJACENT_STATE",
        "G-04_SINGLE_PHASE_SCOPE_FAILURE",
    ):
        result = evaluate_face_case(contract, b1_contract, cases[case_id])
        actual[case_id] = {
            "case_id": case_id,
            "formal_outcome": result.formal_outcome,
            "formal_message": result.formal_message,
            "guard_triggered_before_flux": result.guard_triggered_before_flux,
            "guard_triggered_before_budget": result.guard_triggered_before_budget,
            "guard_triggered_before_state_mutation": (
                result.guard_triggered_before_state_mutation
            ),
            "atomicity_passed": all(
                (
                    result.guard_triggered_before_flux,
                    result.guard_triggered_before_budget,
                    result.guard_triggered_before_state_mutation,
                )
            ),
        }

    failing_case = cases["G-05_STAGNATION_RECONSTRUCTION_FAILURE"]
    failing_result = evaluate_face_case(
        contract,
        b1_contract,
        failing_case,
        provider=_FailingStagnationProvider(),
    )
    actual["G-05_STAGNATION_RECONSTRUCTION_FAILURE"] = {
        "case_id": "G-05_STAGNATION_RECONSTRUCTION_FAILURE",
        "formal_outcome": failing_result.formal_outcome,
        "formal_message": failing_result.formal_message,
        "guard_triggered_before_flux": failing_result.guard_triggered_before_flux,
        "guard_triggered_before_budget": failing_result.guard_triggered_before_budget,
        "guard_triggered_before_state_mutation": (
            failing_result.guard_triggered_before_state_mutation
        ),
        "atomicity_passed": all(
            (
                failing_result.guard_triggered_before_flux,
                failing_result.guard_triggered_before_budget,
                failing_result.guard_triggered_before_state_mutation,
            )
        ),
    }

    actual["G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE"] = (
        _positivity_guard_observation(contract, b1_contract)
    )
    orientation = evaluate_inventory_orientation_guard(right_outward_sign=-1)
    actual["G-07_INVENTORY_ORIENTATION_MISMATCH"] = {
        "case_id": "G-07_INVENTORY_ORIENTATION_MISMATCH",
        "formal_outcome": orientation.formal_outcome,
        "formal_message": orientation.formal_message,
        "guard_triggered_before_flux": orientation.guard_triggered_before_flux,
        "guard_triggered_before_budget": orientation.guard_triggered_before_budget,
        "guard_triggered_before_state_mutation": (
            orientation.guard_triggered_before_state_mutation
        ),
        "atomicity_passed": all(
            (
                orientation.guard_triggered_before_flux,
                orientation.guard_triggered_before_budget,
                orientation.guard_triggered_before_state_mutation,
            )
        ),
    }

    expected = {row.case_id: row for row in expected_rows}
    if set(actual) != set(expected):
        raise ValueError("Adapter and Reference Guard case sets differ")
    rows: list[dict[str, Any]] = []
    for case_id in sorted(expected):
        observed = actual[case_id]
        target = expected[case_id]
        outcome_match = observed["formal_outcome"] == target.formal_outcome
        atomicity_match = bool(observed["atomicity_passed"])
        rows.append(
            {
                **observed,
                "expected_outcome": target.formal_outcome,
                "reference_guard_triggered_before_flux": (
                    target.guard_triggered_before_flux
                ),
                "reference_guard_triggered_before_budget": (
                    target.guard_triggered_before_budget
                ),
                "reference_guard_triggered_before_state_mutation": (
                    target.guard_triggered_before_state_mutation
                ),
                "formal_outcome_match": outcome_match,
                "guard_comparison_passed": outcome_match and atomicity_match,
            }
        )
    if len(rows) != 7:
        raise AssertionError(f"Expected 7 Guard rows, got {len(rows)}")
    return rows


def _locked_checks(
    contract: Mapping[str, Any],
    adapter_source: Path,
    face_rows: Sequence[FaceEvaluation],
    face_comparisons: Sequence[Mapping[str, Any]],
    one_step_passed: bool,
    guard_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    face_by_id = {row.case_id: row for row in face_rows}
    exact_identities = True
    for case_id in (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
    ):
        face = face_by_id[case_id].face
        exact_identities = exact_identities and face is not None and (
            face.F_rho_kg_m2_s == 0.0
            and face.F_rho_u_pa == face.upstream_static_pressure_pa
            and face.F_rho_E_W_m2 == 0.0
            and face.F_rho_xv_kg_m2_s == 0.0
        )
    pressure_residual = max(
        abs(row.face.pressure_decomposition_residual_pa)
        for row in face_rows
        if row.face is not None
    )
    pressure_tolerance = float(
        contract["acceptance_tolerances"][
            "pressure_decomposition_reconstruction_absolute_pa"
        ]
    )
    vapor_exact = all(
        row.face is not None and row.face.F_rho_xv_kg_m2_s == 0.0
        for row in face_rows
    )
    imports_reference = _adapter_imports_reference(adapter_source)
    checks = [
        {
            "check": "adapter_imports_B2_reference",
            "value": imports_reference,
            "target": False,
            "passed": not imports_reference,
        },
        {
            "check": "face_row_count",
            "value": len(face_rows),
            "target": 13,
            "passed": len(face_rows) == 13,
        },
        {
            "check": "face_comparison_count",
            "value": len(face_comparisons),
            "target": 52,
            "passed": len(face_comparisons) == 52,
        },
        {
            "check": "all_face_comparisons",
            "value": sum(bool(row["comparison_passed"]) for row in face_comparisons),
            "target": 52,
            "passed": all(bool(row["comparison_passed"]) for row in face_comparisons),
        },
        {
            "check": "exact_closed_zero_drop_identities",
            "value": exact_identities,
            "target": True,
            "passed": exact_identities,
        },
        {
            "check": "pressure_decomposition_reconstruction",
            "value": pressure_residual,
            "target": pressure_tolerance,
            "passed": pressure_residual <= pressure_tolerance,
        },
        {
            "check": "one_step_conservative_parity",
            "value": one_step_passed,
            "target": True,
            "passed": one_step_passed,
        },
        {
            "check": "guard_row_count",
            "value": len(guard_rows),
            "target": 7,
            "passed": len(guard_rows) == 7,
        },
        {
            "check": "all_guard_outcomes_and_atomicity",
            "value": sum(bool(row["guard_comparison_passed"]) for row in guard_rows),
            "target": 7,
            "passed": all(bool(row["guard_comparison_passed"]) for row in guard_rows),
        },
        {
            "check": "single_phase_vapor_flux_exact_zero",
            "value": vapor_exact,
            "target": True,
            "passed": vapor_exact,
        },
    ]
    return checks


def _write_plot(
    output_dir: Path,
    comparisons: Sequence[Mapping[str, Any]],
    *,
    source_git_sha: str,
    backend_version: str,
) -> None:
    import matplotlib.pyplot as plt

    measures = (
        "F_rho_kg_m2_s",
        "F_rho_u_pa",
        "F_rho_E_W_m2",
    )
    figure, axes = plt.subplots(len(measures), 1, figsize=(12, 11))
    for axis, measure in zip(axes, measures, strict=True):
        rows = [row for row in comparisons if row["measure"] == measure]
        x = list(range(len(rows)))
        axis.plot(
            x,
            [float(row["reference_value"]) for row in rows],
            marker="o",
            label="Reference",
        )
        axis.plot(
            x,
            [float(row["adapter_value"]) for row in rows],
            marker="x",
            label="Adapter",
        )
        axis.set_ylabel(measure)
        axis.grid(True, alpha=0.3)
        axis.legend()
    axes[-1].set_xlabel("locked face-case row")
    description = (
        "case_or_matrix=U3_B2_13_FACE_52_COMPARISON_MATRIX | "
        "model=U3 B2 production-side FVM discharge Adapter | "
        "comparison=independent_reference | "
        "mapping=direct_external_face_flux_override | "
        f"backend=CoolProp {backend_version} | source={source_git_sha} | "
        f"run={os.environ.get('GITHUB_RUN_ID', 'local')}"
    )
    figure.suptitle("U3 B2 Reference–Adapter face-flux parity", fontsize=13)
    figure.text(0.01, 0.01, description, ha="left", va="bottom", fontsize=6)
    figure.tight_layout(rect=(0.0, 0.035, 1.0, 0.97))
    figure.savefig(
        output_dir / "reference_adapter_face_flux_parity.png",
        dpi=160,
        metadata={"Description": description},
    )
    plt.close(figure)


def write_artifact(
    *,
    contract_path: Path,
    extension_path: Path,
    b1_contract_path: Path,
    adapter_source: Path,
    output_dir: Path,
    source_git_sha: str,
    reference_source_git_sha: str,
    reference_artifact_id: int,
    reference_artifact_zip_sha256: str,
    dedicated_junit: Path,
    related_junit: Path,
    full_junit: Path,
) -> dict[str, Any]:
    if reference_source_git_sha != REFERENCE_SOURCE_GIT_SHA:
        raise ValueError("B2 Reference source SHA does not match the locked pin")
    if int(reference_artifact_id) != REFERENCE_ARTIFACT_ID:
        raise ValueError("B2 historical Reference Artifact ID changed")
    if reference_artifact_zip_sha256 != REFERENCE_ARTIFACT_ZIP_SHA256:
        raise ValueError("B2 historical Reference ZIP SHA256 changed")
    if not source_git_sha or source_git_sha == "UNKNOWN":
        raise ValueError("Exact Adapter source Git SHA is required")

    tracked_status = _tracked_git_status()
    if tracked_status:
        raise RuntimeError(f"Tracked checkout is not clean: {tracked_status!r}")

    contract = load_contract(contract_path)
    extension = reference.load_extension(extension_path)
    b1_contract = load_b1_contract(b1_contract_path)
    package = _reference_package(contract_path, extension_path, b1_contract_path)

    provider = CoolPropB2StateProvider()
    b1_provider = b1_adapter.CoolPropStateProvider()
    face_rows = evaluate_face_matrix(
        contract,
        b1_contract,
        provider=provider,
        b1_provider=b1_provider,
    )
    face_comparisons = _compare_faces(contract, face_rows, package.face_rows)
    one_step = run_one_step_case(
        contract,
        b1_contract,
        provider=provider,
        b1_provider=b1_provider,
    )
    one_step_row, one_step_passed = _one_step_comparison(
        contract, one_step, package.one_step
    )
    guard_rows = _evaluate_guards(contract, b1_contract, package.guard_rows)
    checks = _locked_checks(
        contract,
        adapter_source,
        face_rows,
        face_comparisons,
        one_step_passed,
        guard_rows,
    )
    if not all(bool(row["passed"]) for row in checks):
        failed = [row["check"] for row in checks if not bool(row["passed"])]
        raise RuntimeError(f"Locked Adapter authority checks failed: {failed}")

    junit_paths = {
        "dedicated_junit.xml": dedicated_junit,
        "related_junit.xml": related_junit,
        "full_repository_junit.xml": full_junit,
    }
    junit = {name: _junit_totals(path) for name, path in junit_paths.items()}
    for name, totals in junit.items():
        if totals["skipped"] or totals["failures"] or totals["errors"]:
            raise RuntimeError(f"Non-clean authoritative JUnit {name}: {totals}")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (output_dir / "event_provenance_contract.json").write_text(
        json.dumps(extension, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (output_dir / "b1_component_contract.json").write_text(
        json.dumps(b1_contract, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "adapter_face_results.csv", face_rows_as_dicts(face_rows))
    _write_csv(
        output_dir / "reference_adapter_face_flux_comparison.csv",
        face_comparisons,
    )
    _write_csv(
        output_dir / "one_step_conservative_update_comparison.csv",
        [one_step_row],
    )
    _write_csv(output_dir / "guard_outcomes.csv", guard_rows)
    _write_csv(output_dir / "locked_checks.csv", checks)
    _write_plot(
        output_dir,
        face_comparisons,
        source_git_sha=source_git_sha,
        backend_version=provider.version,
    )
    for target_name, source in junit_paths.items():
        shutil.copy2(source, output_dir / target_name)

    provenance: dict[str, Any] = {
        "source_git_sha": source_git_sha,
        "analysis_source_git_sha": source_git_sha,
        "reference_source_git_sha": reference_source_git_sha,
        "reference_resolution_mode": "regenerated_from_pinned_source_in_exact_checkout",
        "reference_historical_artifact_id": int(reference_artifact_id),
        "reference_historical_artifact_zip_sha256": (
            reference_artifact_zip_sha256
        ),
        "adapter_source_sha256": _sha256(adapter_source),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "property_backend": provider.backend_name,
        "property_backend_version": provider.version,
        "workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "workflow_run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        "runner_os": "ubuntu-24.04",
        "github_runner_os": os.environ.get("RUNNER_OS", "local"),
        "git_status_porcelain_tracked": tracked_status,
        "case_or_matrix_identifier": "U3_B2_13_FACE_52_COMPARISON_AND_ONE_STEP",
        "model": "U3 B2 production-side single-phase FVM discharge Adapter",
        "mapping_mode": "direct_external_face_flux_override",
        "adapter_imports_B2_reference": False,
        "reference_used_only_as_comparison_target": True,
    }
    (output_dir / "runtime_and_git_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "verification_only_single_phase_fvm_discharge_face_and_one_step",
        "issue": 135,
        "contract_schema_version": contract["schema_version"],
        "reference_schema_version": package.summary["schema_version"],
        "face_row_count": len(face_rows),
        "face_comparison_count": len(face_comparisons),
        "face_comparison_pass_count": sum(
            bool(row["comparison_passed"]) for row in face_comparisons
        ),
        "all_face_formal_outcomes_match": all(
            bool(row["formal_outcome_match"]) for row in face_comparisons
        ),
        "all_reference_adapter_face_comparisons_passed": all(
            bool(row["comparison_passed"]) for row in face_comparisons
        ),
        "one_step_case_count": 1,
        "one_step_comparison_passed": one_step_passed,
        "guard_row_count": len(guard_rows),
        "guard_comparison_pass_count": sum(
            bool(row["guard_comparison_passed"]) for row in guard_rows
        ),
        "all_guard_outcomes_and_atomicity_passed": all(
            bool(row["guard_comparison_passed"]) for row in guard_rows
        ),
        "all_locked_adapter_authority_checks_passed": all(
            bool(row["passed"]) for row in checks
        ),
        "junit": junit,
        "u3_b2_contract_locked": True,
        "u3_b2_reference_implemented": True,
        "candidate_u3_b2_fvm_adapter_implemented": True,
        "candidate_single_phase_fvm_discharge_mapping_verified": True,
        "u3_b2_fvm_adapter_implemented": False,
        "single_phase_fvm_discharge_mapping_verified": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_discharge_boundary_approved": False,
        "two_phase_critical_discharge_accuracy_approved": False,
        "integrated_blowdown_model_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "provenance": provenance,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = [
        "# Stage 7 U3 B2 — FVM流出面Adapter authority",
        "",
        "production側の単相Adapterを、固定sourceから再生成した独立U3 B2 Referenceと比較した。",
        "Adapter sourceはB2 Reference moduleをimportせず、B2固有のface mappingと",
        "one-step更新を別経路で実装している。本authorityの対象はface mappingと、",
        "32-cell配管における実際の保存形FVM 1 stepのみである。",
        "",
        "## 結果",
        "",
        f"- Adapter source SHA: `{source_git_sha}`",
        f"- pinned Reference source SHA: `{reference_source_git_sha}`",
        (
            "- historical Reference Artifact: "
            f"ID `{reference_artifact_id}` / ZIP SHA256 "
            f"`{reference_artifact_zip_sha256}`"
        ),
        f"- property backend: `{provider.backend_name} {provider.version}`",
        f"- face rows: `{len(face_rows)}`",
        f"- conserved-flux comparisons: `{len(face_comparisons)}` / 全件PASS",
        "- actual FvmSolver one-step comparison: `PASS`",
        f"- Guard rows: `{len(guard_rows)}` / outcome・atomicityとも全件PASS",
        f"- dedicated JUnit: `{junit['dedicated_junit.xml']}`",
        f"- related JUnit: `{junit['related_junit.xml']}`",
        f"- full JUnit: `{junit['full_repository_junit.xml']}`",
        "",
        "## merge後の昇格候補",
        "",
        "expected-head mergeとcentral record synchronizationの完了後に限り、",
        "本authorityは次のformal flag昇格を支持できる。",
        "",
        "```text",
        "u3_b2_fvm_adapter_implemented = true",
        "single_phase_fvm_discharge_mapping_verified = true",
        "```",
        "",
        "## 未承認の範囲",
        "",
        "次のformal flagはfalseのまま維持する。",
        "",
        "```text",
        "u3_b2_finite_pipe_execution_complete = false",
        "single_phase_finite_pipe_coupling_verified = false",
        "u3_b2_verification_benchmark_accepted = false",
        "physical_discharge_boundary_approved = false",
        "physical_validation = false",
        "design_use_acceptance = false",
        "production_hem_activation_approved = false",
        "```",
        "",
        "本結果はfinite-pipe応答、物理精度、設計利用またはproduction readinessを承認しない。",
        "",
    ]
    (output_dir / "report.md").write_text(
        "\n".join(report), encoding="utf-8"
    )

    names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file() and path.name != "artifact_sha256.txt"
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--extension-contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--adapter-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    parser.add_argument(
        "--reference-source-git-sha",
        default=REFERENCE_SOURCE_GIT_SHA,
    )
    parser.add_argument(
        "--reference-artifact-id",
        type=int,
        default=REFERENCE_ARTIFACT_ID,
    )
    parser.add_argument(
        "--reference-artifact-zip-sha256",
        default=REFERENCE_ARTIFACT_ZIP_SHA256,
    )
    parser.add_argument("--dedicated-junit", type=Path, required=True)
    parser.add_argument("--related-junit", type=Path, required=True)
    parser.add_argument("--full-junit", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    write_artifact(
        contract_path=args.contract,
        extension_path=args.extension_contract,
        b1_contract_path=args.b1_contract,
        adapter_source=args.adapter_source,
        output_dir=args.output_dir,
        source_git_sha=str(args.source_git_sha),
        reference_source_git_sha=str(args.reference_source_git_sha),
        reference_artifact_id=int(args.reference_artifact_id),
        reference_artifact_zip_sha256=str(
            args.reference_artifact_zip_sha256
        ),
        dedicated_junit=args.dedicated_junit,
        related_junit=args.related_junit,
        full_junit=args.full_junit,
    )


if __name__ == "__main__":
    main()
