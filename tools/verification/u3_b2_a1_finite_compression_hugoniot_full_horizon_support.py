from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
)
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
)


PARENT_SOURCE_SHA = "55d414ac82b63ae93ce2866148af363dc76fa2cb"
PARENT_WORKFLOW_RUN = 31654235903
PARENT_JOB = 94304991819
PARENT_ARTIFACT = 9163799106
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-8-31654235903"
)
PARENT_ARTIFACT_SHA256 = (
    "45d726b422090c8ce00becb7d66a7a44b309678c0a7cb61b4f842dd08086be8b"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_8_HUGONIOT_32_STEP_PASS"
STARTING_SOLVER_STEP = 524
STARTING_SOLVER_TIME_S = 0.003511644475195471
TARGET_TIME_S = 0.004285834855172021
HORIZON_ROUNDOFF_TOLERANCE_S = 8.0 * float(np.spacing(TARGET_TIME_S))
MAXIMUM_OPERATIONAL_SOLVER_STEP = 1000
OUTCOME = "FINITE_COMPRESSION_INCREMENT_9_FULL_HORIZON_WORKING_SLICE_PASS"

PARENT_REQUIRED_FILES = {
    "finite_compression_steps.csv",
    "finite_compression_roots.csv",
    "hugoniot_fixed_scans.csv",
    "hugoniot_density_search.csv",
    "branch_sequence.csv",
    "finite_compression_32_step_states.npz",
    "authority_verification.json",
    "stop_evidence.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_manifest(directory: Path) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"Increment 8 file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise base.FiniteCompressionShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 8 internal SHA256 mismatch for {name}",
            )


def _verify_parent(
    parent_dir: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str]]:
    if artifact_digest != PARENT_ARTIFACT_SHA256:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 GitHub artifact digest mismatch",
        )
    _verify_manifest(parent_dir)
    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "increment_8_32_step_gate_passed": True,
        "accepted_steps_completed": 32,
        "final_solver_step": STARTING_SOLVER_STEP,
        "final_solver_time_s": STARTING_SOLVER_TIME_S,
        "branch_transition_count": 0,
        "clear_branch_chatter_detected": False,
        "stop_classification": None,
        "stop_reason": None,
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise base.FiniteCompressionShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 8 summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(parent_dir / "finite_compression_32_step_states.npz") as states:
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_final.shape != (32, 4):
        raise base.FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8 final state shape is not (32, 4)",
        )
    if step_after != STARTING_SOLVER_STEP or time_after != STARTING_SOLVER_TIME_S:
        raise base.FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8 solver identity mismatch",
        )
    if not np.all(np.isfinite(U_final)):
        raise base.FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 8 final state contains nonfinite values",
        )
    rho = U_final[:, 0]
    velocity = U_final[:, 1] / rho
    internal = U_final[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise base.FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 8 final state has nonpositive density or internal energy",
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise base.FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8 final rho*xv is not exact zero",
        )

    step_rows = _read_csv(parent_dir / "finite_compression_steps.csv")
    root_rows = _read_csv(parent_dir / "finite_compression_roots.csv")
    if len(step_rows) != 32 or len(root_rows) != 32:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 does not contain 32 step/root rows",
        )
    last_step = step_rows[-1]
    last_root = root_rows[-1]
    if int(last_step["solver_step_count"]) != STARTING_SOLVER_STEP:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 last step is not solver step 524",
        )
    if float(last_step["time_after_s"]) != STARTING_SOLVER_TIME_S:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 last-step time mismatch",
        )
    if last_step.get("accepted_step") != "True" or last_step.get(
        "increment_7_per_step_gate_passed"
    ) != "True":
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 last step did not pass",
        )
    if int(last_root["requested_solver_step"]) != STARTING_SOLVER_STEP:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 last root is not for step 524",
        )
    if last_root.get("root_gate_passed") != "True":
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8 last root gate did not pass",
        )
    summary = dict(summary)
    summary["root_pressure_pa"] = float(last_root["root_pressure_pa"])
    return summary, U_final, last_step


def _inventory_array(values: dict[str, float]) -> np.ndarray:
    return np.asarray(
        [
            values["mass_kg"],
            values["momentum_kg_m_s"],
            values["energy_J"],
            values["vapor_mass_kg"],
        ],
        dtype=float,
    )
