from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_model_selection as inc5_core
import u3_b2_a1_finite_compression_hugoniot_model_selection_identity_status as inc5_final
import u3_b2_a1_weak_compression_bridge_one_step as weak_one_step
import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
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
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_hook import A1DynamicShortHook
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
)


CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
PARENT_SOURCE_SHA = "2c1e1e26138b7d3bd3cf0e7f1d2f7a2c11b443c1"
PARENT_WORKFLOW_RUN = 31650819553
PARENT_JOB = 94294552017
PARENT_ARTIFACT = 9162559698
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-weak-compression-bridge-increment-4f-root-topology-31650819553"
)
PARENT_ARTIFACT_SHA256 = (
    "6f611e1935d2680a04046d1fc7fbb595f19bc99d12ccc274700fd92c086ddb93"
)
INCREMENT_5_SOURCE_SHA = "c4a0f92e4b418c2cc91c53639bff50b8d3af69b5"
INCREMENT_5_WORKFLOW_RUN = 31652171734
INCREMENT_5_JOB = 94298712101
INCREMENT_5_ARTIFACT = 9162985187
INCREMENT_5_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-5-rerun-2-31652171734"
)
INCREMENT_5_ARTIFACT_SHA256 = (
    "80051eedde6b5a9ea92938d9700ad5fa03eaa5ff3cd54dae3964bb12c1fb1781"
)
INCREMENT_5_OUTCOME = (
    "FINITE_COMPRESSION_HUGONIOT_ROOT_SUPPORTED_FOR_ONE_STEP_REVIEW"
)
STARTING_SOLVER_STEP = 483
TARGET_SOLVER_STEP = 484
STARTING_SOLVER_TIME_S = 0.0032365792102672024
OUTCOME = "FINITE_COMPRESSION_INCREMENT_6_HUGONIOT_ONE_STEP_PASS"
WEAK_COMPRESSION_CHI_LIMIT = 1.0e-6
DIAGNOSTIC_CHI_CAP = 1.0e-4
ROOT_REPRODUCTION_TOLERANCES = {
    "requested_chi": 1.0e-12,
    "pressure_pa": 1.0e-6,
    "pressure_offset_pa": 1.0e-6,
    "density_kg_m3": 1.0e-9,
    "velocity_m_s": 1.0e-9,
    "compatibility_residual_kg_s": 1.0e-8,
}
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
    "increment_4f_authority.json",
    "pre_guard_front_reproduction.json",
    "refinement_evidence_gate_correction.json",
    "root_topology_correction.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}

INCREMENT_5_REQUIRED_FILES = {
    "isentropic_extrapolation_scan.csv",
    "hugoniot_compression_scan.csv",
    "hugoniot_density_search.csv",
    "curve_comparison.json",
    "step483_state_identity.npz",
    "enthalpy_identity_correction.json",
    "identity_status_propagation.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


class FiniteCompressionOneStepStop(RuntimeError):
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def _verify_manifest(
    directory: Path,
    required_files: set[str],
    *,
    label: str,
) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != required_files:
        raise FiniteCompressionOneStepStop(
            f"{label} file set mismatch: {sorted(actual)}"
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    expected_names = required_files - {"artifact_sha256.txt"}
    if set(manifest) != expected_names:
        raise FiniteCompressionOneStepStop(
            f"{label} internal manifest names mismatch"
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise FiniteCompressionOneStepStop(
                f"{label} internal SHA256 mismatch for {name}"
            )


def _verify_parent_artifact(
    parent_dir: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str]]:
    if artifact_digest != PARENT_ARTIFACT_SHA256:
        raise FiniteCompressionOneStepStop(
            "accepted-state parent GitHub artifact digest mismatch"
        )
    _verify_manifest(parent_dir, PARENT_REQUIRED_FILES, label="parent")
    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "solver_step_after": STARTING_SOLVER_STEP,
        "solver_time_after_s": STARTING_SOLVER_TIME_S,
        "outcome": "INCREMENT_4F_STOPPED",
        "stop_classification": "GuardFrontContinuationStop",
        "stop_reason": (
            "GuardFrontContinuationStop: successful residual remains positive "
            "through the fixed chi scope"
        ),
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise FiniteCompressionOneStepStop(
                f"accepted-state parent summary mismatch for {key}: "
                f"{summary.get(key)!r}"
            )
    if not bool(summary.get("pre_guard_front_reproduction_passed")):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent pre-Guard reproduction did not pass"
        )
    if not bool(summary.get("guard_front_refinement_gate_passed")):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent Guard-front gate did not pass"
        )
    if not bool(summary.get("guard_front_root_topology_gate_passed")):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent root-topology gate did not pass"
        )

    with np.load(parent_dir / "full_horizon_states.npz") as states:
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_final.shape != (32, 4):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent final state shape is not (32, 4)"
        )
    if step_after != STARTING_SOLVER_STEP or time_after != STARTING_SOLVER_TIME_S:
        raise FiniteCompressionOneStepStop(
            "accepted-state parent NPZ solver identity mismatch"
        )
    if not np.all(np.isfinite(U_final)):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent contains nonfinite values"
        )
    rho = U_final[:, 0]
    velocity = U_final[:, 1] / rho
    internal = U_final[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent has nonpositive density or internal energy"
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise FiniteCompressionOneStepStop(
            "accepted-state parent rho*xv is not exact zero"
        )

    accepted_rows = [
        row
        for row in _read_csv(
            parent_dir / "full_horizon_continuation_steps.csv"
        )
        if row.get("accepted_step") == "True"
    ]
    if not accepted_rows:
        raise FiniteCompressionOneStepStop(
            "accepted-state parent has no accepted continuation row"
        )
    resume_row = accepted_rows[-1]
    if int(resume_row["solver_step_count"]) != STARTING_SOLVER_STEP:
        raise FiniteCompressionOneStepStop(
            "accepted-state parent last accepted row is not step 483"
        )
    if float(resume_row["time_after_s"]) != STARTING_SOLVER_TIME_S:
        raise FiniteCompressionOneStepStop(
            "accepted-state parent last accepted time mismatch"
        )
    return summary, U_final, resume_row


def _verify_increment_5_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
    parent_U: np.ndarray,
) -> dict[str, Any]:
    if artifact_digest != INCREMENT_5_ARTIFACT_SHA256:
        raise FiniteCompressionOneStepStop(
            "Increment 5 GitHub artifact digest mismatch"
        )
    _verify_manifest(
        artifact_dir,
        INCREMENT_5_REQUIRED_FILES,
        label="Increment 5",
    )
    summary = json.loads(
        (artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    if summary.get("source_git_sha") != INCREMENT_5_SOURCE_SHA:
        raise FiniteCompressionOneStepStop(
            "Increment 5 source SHA mismatch"
        )
    if summary.get("outcome") != INCREMENT_5_OUTCOME:
        raise FiniteCompressionOneStepStop(
            f"Increment 5 outcome mismatch: {summary.get('outcome')!r}"
        )
    if not bool(summary.get("diagnostic_classification_complete")):
        raise FiniteCompressionOneStepStop(
            "Increment 5 diagnostic classification is incomplete"
        )
    if not bool(summary.get("enthalpy_identity_correction_gate_passed")):
        raise FiniteCompressionOneStepStop(
            "Increment 5 enthalpy-identity correction gate did not pass"
        )
    if not bool(summary.get("identity_status_propagation_gate_passed")):
        raise FiniteCompressionOneStepStop(
            "Increment 5 identity-status propagation gate did not pass"
        )
    if not bool(summary.get("hugoniot_root_gate_passed")):
        raise FiniteCompressionOneStepStop(
            "Increment 5 Hugoniot root gate did not pass"
        )
    if summary.get("hugoniot_root") is None:
        raise FiniteCompressionOneStepStop(
            "Increment 5 artifact has no Hugoniot root"
        )
    if bool(summary.get("fvm_step_484_attempted")):
        raise FiniteCompressionOneStepStop(
            "Increment 5 unexpectedly attempted solver step 484"
        )
    if bool(summary.get("finite_compression_flux_applied")):
        raise FiniteCompressionOneStepStop(
            "Increment 5 unexpectedly applied a finite-compression flux"
        )
    with np.load(artifact_dir / "step483_state_identity.npz") as states:
        before = np.asarray(states["U_before"], dtype=float)
        after = np.asarray(states["U_after"], dtype=float)
        step_before = int(states["solver_step_before"][0])
        step_after = int(states["solver_step_after"][0])
    if before.shape != (32, 4) or not np.array_equal(before, after):
        raise FiniteCompressionOneStepStop(
            "Increment 5 state identity evidence mismatch"
        )
    if step_before != STARTING_SOLVER_STEP or step_after != STARTING_SOLVER_STEP:
        raise FiniteCompressionOneStepStop(
            "Increment 5 state identity step mismatch"
        )
    if not np.array_equal(before, parent_U):
        raise FiniteCompressionOneStepStop(
            "Increment 5 state does not exactly match accepted-state parent"
        )
    return summary


def _root_comparison(
    authority: dict[str, Any],
    recomputed: dict[str, Any],
) -> dict[str, Any]:
    pairs = {
        "requested_chi": (
            float(authority["requested_chi"]),
            float(recomputed["requested_chi"]),
        ),
        "pressure_pa": (
            float(authority["pressure_pa"]),
            float(recomputed["pressure_pa"]),
        ),
        "pressure_offset_pa": (
            float(authority["pressure_offset_pa"]),
            float(recomputed["pressure_offset_pa"]),
        ),
        "density_kg_m3": (
            float(authority["density_kg_m3"]),
            float(recomputed["density_kg_m3"]),
        ),
        "velocity_m_s": (
            float(authority["velocity_m_s"]),
            float(recomputed["velocity_m_s"]),
        ),
        "compatibility_residual_kg_s": (
            float(authority["compatibility_residual_kg_s"]),
            float(recomputed["compatibility_residual_kg_s"]),
        ),
    }
    checks: dict[str, Any] = {}
    for key, (expected, actual) in pairs.items():
        difference = float(actual - expected)
        tolerance = float(ROOT_REPRODUCTION_TOLERANCES[key])
        checks[key] = {
            "authority": expected,
            "recomputed": actual,
            "difference": difference,
            "absolute_difference": abs(difference),
            "tolerance": tolerance,
            "passed": bool(abs(difference) <= tolerance),
        }
    return {
        "checks": checks,
        "passed": bool(all(item["passed"] for item in checks.values())),
    }


def _augment_candidate_for_completion(
    *,
    candidate: dict[str, Any],
    hook: A1DynamicShortHook,
    state_id: str,
) -> dict[str, Any]:
    result = dict(candidate)
    result["case_id"] = CASE_ID
    result["state_id"] = state_id
    result["residual_kg_s"] = result.get(
        "compatibility_residual_kg_s"
    )
    if not result.get("evaluation_succeeded"):
        return result
    rho = float(result["density_kg_m3"])
    velocity = float(result["velocity_m_s"])
    internal = float(result["internal_energy_J_kg"])
    conserved = np.asarray(
        [
            rho,
            rho * velocity,
            rho * (internal + 0.5 * velocity * velocity),
            0.0,
        ],
        dtype=float,
    )
    evaluation = hook.adapter.evaluate(conserved, hook.area_m2)
    if not evaluation.succeeded or evaluation.face is None:
        result.update(
            evaluation_succeeded=False,
            formal_outcome=evaluation.formal_outcome,
            formal_message=evaluation.formal_message,
            local_candidate_admissible=False,
            residual_kg_s=None,
        )
        return result
    face = evaluation.face
    result.update(
        {
            "formal_outcome": evaluation.formal_outcome,
            "formal_message": evaluation.formal_message,
            "h0_J_kg": float(
                result["enthalpy_J_kg"] + 0.5 * velocity * velocity
            ),
            "b1_effective_velocity_m_s": float(
                face.effective_velocity_m_s
            ),
            "b1_discharge_state_pressure_pa": float(
                face.discharge_state_pressure_pa
            ),
            "b1_critical_pressure_pa": (
                None
                if face.critical_pressure_pa is None
                else float(face.critical_pressure_pa)
            ),
        }
    )
    return result


def _prepare_root_context(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U_step483: np.ndarray,
    increment_5_summary: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    provider = CoolPropB2StateProvider()
    preparation_hook = A1DynamicShortHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    inc5_core.HugoniotCurve = (
        inc5_final.IdentityStatusPropagatedHugoniotCurve
    )
    (
        reproduction_summary,
        isentropic_rows,
        hugoniot_rows,
        density_rows,
        curve_comparison,
    ) = inc5_core._run(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary={
            "outcome": "INCREMENT_4F_STOPPED",
        },
        U_final=U_step483,
    )
    if reproduction_summary["outcome"] != INCREMENT_5_OUTCOME:
        raise FiniteCompressionOneStepStop(
            "independent Increment 5 reproduction did not support one-step review: "
            f"{reproduction_summary['outcome']}"
        )
    recomputed_root = reproduction_summary.get("hugoniot_root")
    if recomputed_root is None:
        raise FiniteCompressionOneStepStop(
            "independent Increment 5 reproduction returned no Hugoniot root"
        )
    comparison = _root_comparison(
        increment_5_summary["hugoniot_root"],
        recomputed_root,
    )
    if not comparison["passed"]:
        raise FiniteCompressionOneStepStop(
            "independently recomputed Hugoniot root does not match Increment 5 authority"
        )

    reconstruction = provider.reconstruct_from_conserved(U_step483[-1])
    static = reconstruction.static
    state_id = str(diagnostic._case(contract, CASE_ID)["state_id"])
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    denominator = float(
        static.density_kg_m3 * static.sound_speed_m_s**2
    )
    curve = inc5_final.IdentityStatusPropagatedHugoniotCurve(
        static=static,
        hook=preparation_hook,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_tolerance,
        pressure_denominator_pa=denominator,
    )

    def evaluate_pressure(pressure_pa: float) -> dict[str, Any]:
        chi = float(
            (float(pressure_pa) - float(static.pressure_pa)) / denominator
        )
        candidate = curve.evaluate(chi, "increment_6_root_completion")
        return _augment_candidate_for_completion(
            candidate=candidate,
            hook=preparation_hook,
            state_id=state_id,
        )

    raw_root = evaluate_pressure(float(recomputed_root["pressure_pa"]))
    if not raw_root.get("evaluation_succeeded") or not raw_root.get(
        "local_candidate_admissible"
    ):
        raise FiniteCompressionOneStepStop(
            "recomputed Hugoniot root failed B1/local admissibility during one-step preparation"
        )
    completed = horizon._complete_root_row_dynamic_v4(
        root=raw_root,
        evaluate=evaluate_pressure,
        adapter=preparation_hook.adapter,
        area_m2=preparation_hook.area_m2,
        quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
    )
    root = dict(raw_root)
    root.update(completed)
    root.update(
        {
            "branch_classification": "FINITE_COMPRESSION_HUGONIOT",
            "p_P_minus_p_i_pa": float(
                root["pressure_pa"] - static.pressure_pa
            ),
            "requested_chi": float(recomputed_root["requested_chi"]),
            "realized_chi": float(
                (root["pressure_pa"] - static.pressure_pa) / denominator
            ),
            "chi": float(recomputed_root["requested_chi"]),
            "approved_weak_compression_chi_limit": (
                WEAK_COMPRESSION_CHI_LIMIT
            ),
            "diagnostic_chi_cap": DIAGNOSTIC_CHI_CAP,
            "finite_compression_model": "GENERAL_EOS_HUGONIOT",
            "finite_compression_branch_approved": False,
        }
    )

    mass_rate = float(root["pipe_mass_rate_kg_s"])
    velocity = float(root["velocity_m_s"])
    pressure = float(root["pressure_pa"])
    h0 = float(root["h0_J_kg"])
    flux = np.asarray(
        [
            mass_rate / preparation_hook.area_m2,
            (
                mass_rate * velocity
                + pressure * preparation_hook.area_m2
            )
            / preparation_hook.area_m2,
            mass_rate * h0 / preparation_hook.area_m2,
            0.0,
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(flux)):
        raise FiniteCompressionOneStepStop(
            "prepared Hugoniot Euler flux contains nonfinite values"
        )

    admissible_hugoniot_rows = [
        row
        for row in hugoniot_rows
        if row.get("evaluation_succeeded")
        and row.get("local_candidate_admissible")
    ]
    context = {
        "solver_time_s": STARTING_SOLVER_TIME_S,
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(
            static.velocity_m_s / static.sound_speed_m_s
        ),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "interior_phase": str(static.phase),
        "interior_h0_round_trip_residual_J_kg": float(
            reconstruction.enthalpy_round_trip_residual_J_kg
        ),
        "interior_s0_round_trip_residual_J_kg_K": float(
            reconstruction.entropy_round_trip_residual_J_kg_K
        ),
        "connected_scan_base_node_count": len(inc5_core.CHI_NODES),
        "connected_scan_requested_nodes": len(inc5_core.CHI_NODES),
        "connected_scan_admissible_subsonic_nodes": len(
            admissible_hugoniot_rows
        ),
        "connected_scan_lowest_pressure_pa": float(
            hugoniot_rows[0]["pressure_pa"]
        ),
        "connected_scan_stop_reason": None,
        "connected_scan_residual_monotone": bool(
            reproduction_summary[
                "hugoniot_scan_monotone_nonincreasing"
            ]
        ),
        "connected_scan_sign_change_count": int(
            reproduction_summary["hugoniot_sign_change_count"]
        ),
        "root": root,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
        "branch_classification": "FINITE_COMPRESSION_HUGONIOT",
        "root_chi": float(root["requested_chi"]),
        "positive_scan_sign_change_count": 1,
        "positive_pressure_continuation_flux_applied": True,
        "finite_compression_flux_applied": True,
        "finite_compression_branch_approved": False,
    }
    return (
        context,
        reproduction_summary,
        isentropic_rows,
        hugoniot_rows,
        density_rows,
        comparison,
    )


def _run_one_step(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    parent_summary: dict[str, Any],
    U_step483: np.ndarray,
    resume_row: dict[str, str],
    increment_5_summary: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    np.ndarray,
    np.ndarray,
]:
    (
        prepared_context,
        reproduction_summary,
        isentropic_rows,
        hugoniot_rows,
        density_rows,
        authority_comparison,
    ) = _prepare_root_context(
        contract=contract,
        b1_contract=b1_contract,
        U_step483=U_step483,
        increment_5_summary=increment_5_summary,
    )
    root = prepared_context["root"]

    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = CoolPropB2StateProvider()
    U_initial, initial_static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    hook = weak_one_step.A1WeakCompressionOneStepHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
        prepared_context=prepared_context,
        expected_outlet=np.asarray(U_step483[-1], dtype=float),
        expected_time_s=STARTING_SOLVER_TIME_S,
    )
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=np.asarray(U_step483, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=STARTING_SOLVER_TIME_S,
        step_count=STARTING_SOLVER_STEP,
    )

    initial = inventory(
        U_initial,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    before = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current_minus_initial = _inventory_array(before) - _inventory_array(
        initial
    )
    cumulative_expected_delta = np.asarray(
        [
            current_minus_initial[0]
            - float(resume_row["cumulative_mass_residual_kg"]),
            current_minus_initial[1]
            - float(
                resume_row["cumulative_momentum_residual_kg_m_s"]
            ),
            current_minus_initial[2]
            - float(resume_row["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )

    candidate_dt = float(solver.compute_dt())
    dt_limits = dict(hook.last_dt_limits)
    if hook.root_context is None:
        raise FiniteCompressionOneStepStop(
            "Hugoniot root was not prepared by compute_dt"
        )
    root_context = hook.root_context
    if root_context["branch_classification"] != (
        "FINITE_COMPRESSION_HUGONIOT"
    ):
        raise FiniteCompressionOneStepStop(
            "prepared one-step branch is not FINITE_COMPRESSION_HUGONIOT"
        )
    flux_left, _ = solver._base_fluxes()
    left_flux = np.asarray(flux_left[0], dtype=float)
    right_flux = np.asarray(hook.flux, dtype=float)
    U_before = np.asarray(solver.U, dtype=float).copy()
    accepted_dt = float(solver.step(candidate_dt))
    hook.accept_current_root()
    U_after = np.asarray(solver.U, dtype=float).copy()

    after = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    expected_step_delta = accepted_dt * grid.geometry.area_m2 * (
        left_flux - right_flux
    )
    cumulative_expected_delta += expected_step_delta
    primitive_after = solver.primitive()
    post_reconstruction = provider.reconstruct_from_conserved(
        solver.U[-1]
    )
    row = build_step_row(
        case_id=CASE_ID,
        state_id=state_id,
        requested_step=TARGET_SOLVER_STEP,
        solver=solver,
        hook=hook,
        root_context=root_context,
        dt_limits=dt_limits,
        candidate_dt=candidate_dt,
        accepted_dt=accepted_dt,
        before=before,
        after=after,
        initial=initial,
        expected_step_delta=expected_step_delta,
        cumulative_expected_delta=cumulative_expected_delta,
        left_flux=left_flux,
        right_flux=right_flux,
        post_reconstruction=post_reconstruction,
        primitive_after=primitive_after,
        tolerances=contract["acceptance_tolerances"],
    )
    rho_after = U_after[:, 0]
    velocity_after = U_after[:, 1] / rho_after
    internal_after = U_after[:, 2] / rho_after - 0.5 * velocity_after**2
    outlet_after = post_reconstruction.static
    row.update(
        {
            "branch_classification": "FINITE_COMPRESSION_HUGONIOT",
            "finite_compression_model": "GENERAL_EOS_HUGONIOT",
            "root_requested_chi": float(root["requested_chi"]),
            "root_realized_chi": float(root["realized_chi"]),
            "approved_weak_compression_chi_limit": (
                WEAK_COMPRESSION_CHI_LIMIT
            ),
            "diagnostic_chi_cap": DIAGNOSTIC_CHI_CAP,
            "root_pressure_offset_pa": float(root["p_P_minus_p_i_pa"]),
            "root_density_kg_m3": float(root["density_kg_m3"]),
            "root_temperature_K": float(root["temperature_K"]),
            "root_entropy_delta_J_kg_K": float(
                root["entropy_delta_J_kg_K"]
            ),
            "root_hugoniot_energy_residual_J_kg": float(
                root["hugoniot_energy_residual_J_kg"]
            ),
            "root_hugoniot_enthalpy_residual_J_kg": float(
                root["hugoniot_enthalpy_residual_J_kg"]
            ),
            "root_hugoniot_identity_accounted_passed": bool(
                root["hugoniot_identity_accounted_passed"]
            ),
            "root_lax_1_shock_passed": bool(
                root["lax_1_shock_passed"]
            ),
            "root_shock_speed_m_s": float(root["shock_speed_m_s"]),
            "root_lambda_1_candidate_m_s": float(
                root["lambda_1_candidate_m_s"]
            ),
            "root_lambda_1_interior_m_s": float(
                root["lambda_1_interior_m_s"]
            ),
            "root_authority_comparison_passed": bool(
                authority_comparison["passed"]
            ),
            "all_conserved_finite_after_step": bool(
                np.all(np.isfinite(U_after))
            ),
            "minimum_density_after_step_kg_m3": float(
                np.min(rho_after)
            ),
            "minimum_internal_energy_after_step_J_kg": float(
                np.min(internal_after)
            ),
            "outlet_mach_after_step": float(
                outlet_after.velocity_m_s / outlet_after.sound_speed_m_s
            ),
            "finite_compression_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
    )

    pre_step_gate = bool(
        increment_5_summary["outcome"] == INCREMENT_5_OUTCOME
        and reproduction_summary["outcome"] == INCREMENT_5_OUTCOME
        and authority_comparison["passed"]
        and float(root["requested_chi"]) > WEAK_COMPRESSION_CHI_LIMIT
        and float(root["requested_chi"]) <= DIAGNOSTIC_CHI_CAP
        and abs(float(root["root_mass_residual_kg_s"]))
        <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
        and float(root["pressure_pa"]) > float(
            root_context["interior_pressure_pa"]
        )
        and float(root["density_kg_m3"]) > float(
            root_context["interior_density_kg_m3"]
        )
        and float(root["velocity_m_s"]) >= 0.0
        and 0.0 <= float(root["mach"]) < 1.0
        and normalize_phase(str(root["phase"])) in hook.allowed_phases
        and bool(root["hugoniot_closure_passed"])
        and bool(root["hugoniot_identity_accounted_passed"])
        and bool(root["lax_1_shock_passed"])
        and bool(root["entropy_bound_passed"])
        and bool(root["stagnation_enthalpy_round_trip_passed"])
        and bool(root["energy_mass_consistency_passed"])
        and bool(root["energy_port_closure_passed"])
        and abs(float(root["momentum_ledger_residual_N"]))
        <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    )
    post_step_gate = bool(
        accepted_dt > 0.0
        and int(solver.step_count) == TARGET_SOLVER_STEP
        and float(solver.t) == STARTING_SOLVER_TIME_S + accepted_dt
        and bool(row["accepted_step"])
        and bool(row["step_passed"])
        and bool(row["all_conserved_finite_after_step"])
        and float(row["minimum_density_after_step_kg_m3"]) > 0.0
        and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
        and not bool(row["reverse_flow_guard_triggered"])
        and not bool(row["reverse_velocity_detected"])
        and float(row["outlet_velocity_after_step_m_s"]) >= 0.0
        and 0.0 <= float(row["outlet_mach_after_step"]) < 1.0
        and bool(row["outlet_phase_passed"])
        and bool(row["rho_xv_exact_zero"])
        and bool(row["step_mass_passed"])
        and bool(row["step_momentum_passed"])
        and bool(row["step_energy_passed"])
        and bool(row["cumulative_mass_passed"])
        and bool(row["cumulative_momentum_passed"])
        and bool(row["cumulative_energy_passed"])
    )
    gate = bool(pre_step_gate and post_step_gate)

    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_6",
        "scope": "model_review_one_actual_fvm_step_general_eos_hugoniot",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_artifact_verified": True,
        "parent_outcome": parent_summary["outcome"],
        "increment_5_source_sha": INCREMENT_5_SOURCE_SHA,
        "increment_5_workflow_run": INCREMENT_5_WORKFLOW_RUN,
        "increment_5_job": INCREMENT_5_JOB,
        "increment_5_artifact": INCREMENT_5_ARTIFACT,
        "increment_5_artifact_name": INCREMENT_5_ARTIFACT_NAME,
        "increment_5_artifact_sha256": INCREMENT_5_ARTIFACT_SHA256,
        "increment_5_artifact_verified": True,
        "increment_5_outcome": increment_5_summary["outcome"],
        "increment_5_reproduction_outcome": reproduction_summary[
            "outcome"
        ],
        "root_authority_comparison": authority_comparison,
        "root_authority_comparison_passed": bool(
            authority_comparison["passed"]
        ),
        "case_id": CASE_ID,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "solver_step_before": STARTING_SOLVER_STEP,
        "solver_step_after": int(solver.step_count),
        "solver_time_before_s": STARTING_SOLVER_TIME_S,
        "solver_time_after_s": float(solver.t),
        "candidate_dt_s": candidate_dt,
        "accepted_dt_s": accepted_dt,
        "halving_count": int(row["halving_count"]),
        "trial_dts_s": row["trial_dts_s"],
        "branch_classification": "FINITE_COMPRESSION_HUGONIOT",
        "finite_compression_model": "GENERAL_EOS_HUGONIOT",
        "root_requested_chi": float(root["requested_chi"]),
        "root_realized_chi": float(root["realized_chi"]),
        "approved_weak_compression_chi_limit": WEAK_COMPRESSION_CHI_LIMIT,
        "diagnostic_chi_cap": DIAGNOSTIC_CHI_CAP,
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_pressure_offset_pa": float(root["p_P_minus_p_i_pa"]),
        "root_density_kg_m3": float(root["density_kg_m3"]),
        "root_temperature_K": float(root["temperature_K"]),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_mass_residual_kg_s": float(
            root["root_mass_residual_kg_s"]
        ),
        "root_local_slope_kg_s_Pa": float(
            root["local_residual_slope_kg_s_Pa"]
        ),
        "root_b1_outcome": root["formal_outcome"],
        "root_entropy_delta_J_kg_K": float(
            root["entropy_delta_J_kg_K"]
        ),
        "root_hugoniot_energy_residual_J_kg": float(
            root["hugoniot_energy_residual_J_kg"]
        ),
        "root_hugoniot_enthalpy_residual_J_kg": float(
            root["hugoniot_enthalpy_residual_J_kg"]
        ),
        "root_hugoniot_identity_accounted_passed": bool(
            root["hugoniot_identity_accounted_passed"]
        ),
        "root_lax_1_shock_passed": bool(
            root["lax_1_shock_passed"]
        ),
        "root_shock_speed_m_s": float(root["shock_speed_m_s"]),
        "root_lambda_1_candidate_m_s": float(
            root["lambda_1_candidate_m_s"]
        ),
        "root_lambda_1_interior_m_s": float(
            root["lambda_1_interior_m_s"]
        ),
        "pre_step_gate_passed": pre_step_gate,
        "post_step_gate_passed": post_step_gate,
        "increment_6_one_step_gate_passed": gate,
        "outcome": OUTCOME if gate else "INCREMENT_6_ONE_STEP_FAILED",
        "outlet_pressure_after_step_pa": float(
            row["outlet_pressure_after_step_pa"]
        ),
        "outlet_velocity_after_step_m_s": float(
            row["outlet_velocity_after_step_m_s"]
        ),
        "outlet_mach_after_step": float(row["outlet_mach_after_step"]),
        "outlet_phase_after_step": row["outlet_phase_after_step"],
        "minimum_density_after_step_kg_m3": float(
            row["minimum_density_after_step_kg_m3"]
        ),
        "minimum_internal_energy_after_step_J_kg": float(
            row["minimum_internal_energy_after_step_J_kg"]
        ),
        "rho_xv_exact_zero_after_step": bool(row["rho_xv_exact_zero"]),
        "step_mass_residual_kg": float(row["step_mass_residual_kg"]),
        "step_momentum_residual_kg_m_s": float(
            row["step_momentum_residual_kg_m_s"]
        ),
        "step_energy_residual_J": float(row["step_energy_residual_J"]),
        "cumulative_mass_residual_kg": float(
            row["cumulative_mass_residual_kg"]
        ),
        "cumulative_momentum_residual_kg_m_s": float(
            row["cumulative_momentum_residual_kg_m_s"]
        ),
        "cumulative_energy_residual_J": float(
            row["cumulative_energy_residual_J"]
        ),
        "finite_compression_flux_applied": True,
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
    return (
        summary,
        row,
        reproduction_summary,
        isentropic_rows,
        hugoniot_rows,
        density_rows,
        authority_comparison,
        U_before,
        U_after,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--increment-5-artifact-dir", type=Path, required=True)
    parser.add_argument("--increment-5-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_step483, resume_row = _verify_parent_artifact(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    increment_5_summary = _verify_increment_5_artifact(
        args.increment_5_artifact_dir,
        artifact_digest=args.increment_5_artifact_digest,
        parent_U=U_step483,
    )
    (
        summary,
        step_row,
        reproduction_summary,
        isentropic_rows,
        hugoniot_rows,
        density_rows,
        authority_comparison,
        U_before,
        U_after,
    ) = _run_one_step(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_step483=U_step483,
        resume_row=resume_row,
        increment_5_summary=increment_5_summary,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "recomputed_isentropic_scan.csv", isentropic_rows)
    _write_csv(output / "recomputed_hugoniot_scan.csv", hugoniot_rows)
    _write_csv(output / "recomputed_hugoniot_density_search.csv", density_rows)
    _write_csv(
        output / "hugoniot_root_evidence.csv",
        [
            {
                **reproduction_summary["hugoniot_root"],
                "authority_comparison_passed": authority_comparison["passed"],
            }
        ],
    )
    _write_csv(output / "finite_compression_one_step.csv", [step_row])
    authority = {
        "accepted_state_parent": {
            "source_sha": PARENT_SOURCE_SHA,
            "workflow_run": PARENT_WORKFLOW_RUN,
            "job": PARENT_JOB,
            "artifact": PARENT_ARTIFACT,
            "artifact_sha256": PARENT_ARTIFACT_SHA256,
            "verified": True,
        },
        "increment_5": {
            "source_sha": INCREMENT_5_SOURCE_SHA,
            "workflow_run": INCREMENT_5_WORKFLOW_RUN,
            "job": INCREMENT_5_JOB,
            "artifact": INCREMENT_5_ARTIFACT,
            "artifact_sha256": INCREMENT_5_ARTIFACT_SHA256,
            "outcome": increment_5_summary["outcome"],
            "verified": True,
        },
    }
    (output / "authority_verification.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "root_authority_comparison.json").write_text(
        json.dumps(authority_comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        output / "finite_compression_one_step_states.npz",
        U_before=np.asarray(U_before, dtype=float),
        U_after=np.asarray(U_after, dtype=float),
        solver_step_before=np.asarray([STARTING_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["solver_step_after"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([summary["solver_time_after_s"]]),
        accepted_dt_s=np.asarray([summary["accepted_dt_s"]]),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 finite-compression Increment 6\n\n"
        "MODEL_REVIEW / ONE_ACTUAL_FVM_STEP evidence. The exact accepted "
        "step-483 state and authoritative Increment 5 result were independently "
        "verified. The general-EOS Hugoniot root was recomputed, compared with "
        "the authority, converted to the existing pipe-side Euler flux, and "
        "applied to exactly one actual FvmSolver update. A pass does not "
        "authorize step 485, multi-step continuation, formal Verification, "
        "benchmark acceptance, Physical Validation, design use, or production "
        "activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "recomputed_isentropic_scan.csv",
        "recomputed_hugoniot_scan.csv",
        "recomputed_hugoniot_density_search.csv",
        "hugoniot_root_evidence.csv",
        "finite_compression_one_step.csv",
        "authority_verification.json",
        "root_authority_comparison.json",
        "finite_compression_one_step_states.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_6_one_step_gate_passed"]:
        raise SystemExit("Increment 6 Hugoniot one-step gate did not pass")


if __name__ == "__main__":
    main()
