from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_model_selection as inc5_core
import u3_b2_a1_finite_compression_hugoniot_model_selection_identity_status as inc5_final
import u3_b2_a1_finite_compression_hugoniot_one_step as inc6
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
PARENT_SOURCE_SHA = "821bac91c6c9b9bdd991ab54a845ec3a311c4b48"
PARENT_WORKFLOW_RUN = 31652814648
PARENT_JOB = 94300642258
PARENT_ARTIFACT = 9163222601
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-6-rerun-31652814648"
)
PARENT_ARTIFACT_SHA256 = (
    "db671e3b9c7f8f7b52b88d3f0d44a279496546cd2777a683538451f2efe71fe7"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_6_HUGONIOT_ONE_STEP_PASS"
STARTING_SOLVER_STEP = 484
REQUESTED_ACCEPTED_STEPS = 8
FINAL_SOLVER_STEP = 492
STARTING_SOLVER_TIME_S = 0.0032432861683330846
WEAK_COMPRESSION_CHI_LIMIT = 1.0e-6
DIAGNOSTIC_CHI_CAP = 1.0e-4
OUTCOME = "FINITE_COMPRESSION_INCREMENT_7_HUGONIOT_8_STEP_PASS"
BRANCH = "FINITE_COMPRESSION_HUGONIOT"
robustness = robustness_v4.robustness

PARENT_REQUIRED_FILES = {
    "recomputed_isentropic_scan.csv",
    "recomputed_hugoniot_scan.csv",
    "recomputed_hugoniot_density_search.csv",
    "hugoniot_root_evidence.csv",
    "finite_compression_one_step.csv",
    "authority_verification.json",
    "root_authority_comparison.json",
    "finite_compression_one_step_states.npz",
    "identity_reproduction_correction.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


class FiniteCompressionShortRunStop(RuntimeError):
    def __init__(
        self,
        classification: str,
        message: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.diagnostics = diagnostics or {}


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


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _verify_manifest(
    directory: Path,
    required_files: set[str],
    *,
    label: str,
) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != required_files:
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"{label} file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    expected_names = required_files - {"artifact_sha256.txt"}
    if set(manifest) != expected_names:
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"{label} internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise FiniteCompressionShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"{label} internal SHA256 mismatch for {name}",
            )


def _verify_parent(
    parent_dir: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str]]:
    if artifact_digest != PARENT_ARTIFACT_SHA256:
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 6 GitHub artifact digest mismatch",
        )
    _verify_manifest(parent_dir, PARENT_REQUIRED_FILES, label="Increment 6")
    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "solver_step_after": STARTING_SOLVER_STEP,
        "solver_time_after_s": STARTING_SOLVER_TIME_S,
        "increment_6_one_step_gate_passed": True,
        "pre_step_gate_passed": True,
        "post_step_gate_passed": True,
        "root_authority_comparison_passed": True,
        "identity_correction_reproduction_applied": True,
        "finite_compression_flux_applied": True,
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise FiniteCompressionShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 6 summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(parent_dir / "finite_compression_one_step_states.npz") as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_after.shape != (32, 4):
        raise FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 6 final state shape is not (32, 4)",
        )
    if step_after != STARTING_SOLVER_STEP or time_after != STARTING_SOLVER_TIME_S:
        raise FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 6 solver identity mismatch",
        )
    if not np.all(np.isfinite(U_after)):
        raise FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 6 final state contains nonfinite values",
        )
    rho = U_after[:, 0]
    velocity = U_after[:, 1] / rho
    internal = U_after[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 6 final state has nonpositive density or internal energy",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 6 final rho*xv is not exact zero",
        )

    rows = _read_csv(parent_dir / "finite_compression_one_step.csv")
    if len(rows) != 1:
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 6 step evidence does not contain exactly one row",
        )
    row = rows[0]
    if row.get("accepted_step") != "True" or row.get("step_passed") != "True":
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 6 step evidence did not pass",
        )
    if int(row["solver_step_count"]) != STARTING_SOLVER_STEP:
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 6 step row is not solver step 484",
        )
    if float(row["time_after_s"]) != STARTING_SOLVER_TIME_S:
        raise FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 6 step-row time mismatch",
        )
    return summary, U_after, row


def _annotate_scan_rows(
    rows: list[dict[str, Any]],
    *,
    bracket: dict[str, float],
) -> list[dict[str, Any]]:
    selected = {
        float(bracket["lower_chi"]),
        float(bracket["upper_chi"]),
    }
    return [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["requested_chi"]) in selected
            ),
        }
        for row in rows
    ]


def _solve_hugoniot_context(
    *,
    hook: Any,
    U: np.ndarray,
    solver_time_s: float,
) -> dict[str, Any]:
    inc5_core.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
    )
    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    if not all(
        np.isfinite(value)
        for value in (
            static.pressure_pa,
            static.temperature_K,
            static.density_kg_m3,
            static.velocity_m_s,
            static.internal_energy_J_kg,
            static.sound_speed_m_s,
            static.entropy_J_kg_K,
        )
    ):
        raise FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "outlet reconstruction contains nonfinite values",
        )
    if (
        float(static.density_kg_m3) <= 0.0
        or float(static.internal_energy_J_kg) <= 0.0
        or float(static.sound_speed_m_s) <= 0.0
    ):
        raise FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "outlet reconstruction contains nonpositive density, internal energy or sound speed",
        )
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(hook.contract, hook.state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    interior_mach = float(static.velocity_m_s / static.sound_speed_m_s)
    if float(static.velocity_m_s) < -velocity_tolerance:
        raise FiniteCompressionShortRunStop(
            "REVERSE_VELOCITY",
            "interior outlet velocity is reverse-directed",
        )
    if not 0.0 <= interior_mach < 1.0:
        raise FiniteCompressionShortRunStop(
            "SUBSONIC_SCOPE_DEPARTURE",
            "interior outlet state is outside the subsonic branch",
        )
    if normalize_phase(str(static.phase)) not in allowed_phases:
        raise FiniteCompressionShortRunStop(
            "PHASE_SCOPE_DEPARTURE",
            f"interior phase {static.phase!r} is outside {sorted(allowed_phases)}",
        )

    denominator = float(
        static.density_kg_m3 * static.sound_speed_m_s**2
    )
    curve = inc5_final.IdentityStatusPropagatedHugoniotCurve(
        static=static,
        hook=hook,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_tolerance,
        pressure_denominator_pa=denominator,
    )
    fixed_rows = [
        curve.evaluate(float(chi), "increment_7_fixed_scan")
        for chi in inc5_core.CHI_NODES
    ]
    successful = [
        row
        for row in fixed_rows
        if row.get("evaluation_succeeded")
        and row.get("local_candidate_admissible")
    ]
    if len(successful) < 2:
        raise FiniteCompressionShortRunStop(
            "B1_ADMISSIBLE_DOMAIN_FAILURE",
            "Hugoniot fixed scan has fewer than two successful admissible nodes",
            {"hugoniot_scan_rows": fixed_rows},
        )
    monotone = inc5_core._monotone_nonincreasing(fixed_rows)
    if not monotone:
        raise FiniteCompressionShortRunStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "Hugoniot compatibility residual is not monotone nonincreasing",
            {"hugoniot_scan_rows": fixed_rows},
        )
    brackets = inc5_core._brackets(fixed_rows)
    if len(brackets) > 1:
        raise FiniteCompressionShortRunStop(
            "MULTIPLE_COMPATIBILITY_ROOTS",
            "multiple Hugoniot compatibility-root brackets were observed",
            {"hugoniot_scan_rows": fixed_rows, "brackets": brackets},
        )
    if len(brackets) == 0:
        last_success = successful[-1]
        classification = (
            "FINITE_COMPRESSION_DIAGNOSTIC_CAP_REQUIRED"
            if float(last_success["compatibility_residual_kg_s"])
            > robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            else "NO_UNIQUE_HUGONIOT_ROOT"
        )
        raise FiniteCompressionShortRunStop(
            classification,
            "no unique Hugoniot compatibility root exists inside the fixed diagnostic cap",
            {"hugoniot_scan_rows": fixed_rows},
        )

    bracket = brackets[0]
    annotated_scan = _annotate_scan_rows(fixed_rows, bracket=bracket)
    try:
        raw_root = inc5_core._bisect_compatibility_root(
            curve="GENERAL_EOS_HUGONIOT",
            bracket=bracket,
            evaluate_chi=curve.evaluate,
        )
    except Exception as exc:
        raise FiniteCompressionShortRunStop(
            "COMPATIBILITY_ROOT_FAILURE",
            f"Hugoniot compatibility-root bisection failed: {type(exc).__name__}: {exc}",
            {"hugoniot_scan_rows": annotated_scan},
        ) from exc

    requested_chi = float(raw_root["requested_chi"])
    if not requested_chi > WEAK_COMPRESSION_CHI_LIMIT:
        raise FiniteCompressionShortRunStop(
            "ROOT_RETURNED_TO_WEAK_COMPRESSION_SCOPE",
            f"Hugoniot root chi is not above the Weak Compression limit: {requested_chi}",
            {"hugoniot_scan_rows": annotated_scan, "raw_root": raw_root},
        )
    if requested_chi > DIAGNOSTIC_CHI_CAP:
        raise FiniteCompressionShortRunStop(
            "FINITE_COMPRESSION_DIAGNOSTIC_CAP_REQUIRED",
            f"Hugoniot root chi exceeds the fixed diagnostic cap: {requested_chi}",
            {"hugoniot_scan_rows": annotated_scan, "raw_root": raw_root},
        )

    def evaluate_pressure(pressure_pa: float) -> dict[str, Any]:
        chi = float(
            (float(pressure_pa) - float(static.pressure_pa)) / denominator
        )
        candidate = curve.evaluate(chi, "increment_7_root_completion")
        return inc6._augment_candidate_for_completion(
            candidate=candidate,
            hook=hook,
            state_id=hook.state_id,
        )

    completed_candidate = evaluate_pressure(float(raw_root["pressure_pa"]))
    if not completed_candidate.get("evaluation_succeeded") or not completed_candidate.get(
        "local_candidate_admissible"
    ):
        raise FiniteCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE",
            "selected Hugoniot root failed completion B1/local admissibility",
            {"hugoniot_scan_rows": annotated_scan, "raw_root": raw_root},
        )
    try:
        completed = horizon._complete_root_row_dynamic_v4(
            root=completed_candidate,
            evaluate=evaluate_pressure,
            adapter=hook.adapter,
            area_m2=hook.area_m2,
            quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
        )
    except Exception as exc:
        raise FiniteCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE",
            f"selected Hugoniot root ledger completion failed: {type(exc).__name__}: {exc}",
            {"hugoniot_scan_rows": annotated_scan, "raw_root": raw_root},
        ) from exc

    root = dict(completed_candidate)
    root.update(completed)
    root.update(
        {
            "curve": "GENERAL_EOS_HUGONIOT",
            "branch_classification": BRANCH,
            "requested_chi": requested_chi,
            "realized_chi": float(
                (float(root["pressure_pa"]) - float(static.pressure_pa))
                / denominator
            ),
            "p_P_minus_p_i_pa": float(
                float(root["pressure_pa"]) - float(static.pressure_pa)
            ),
            "chi": requested_chi,
            "approved_weak_compression_chi_limit": WEAK_COMPRESSION_CHI_LIMIT,
            "diagnostic_chi_cap": DIAGNOSTIC_CHI_CAP,
            "finite_compression_model": "GENERAL_EOS_HUGONIOT",
            "finite_compression_branch_approved": False,
            "compatibility_bisection_iterations": int(
                raw_root["compatibility_bisection_iterations"]
            ),
            "final_lower_chi": float(raw_root["final_lower_chi"]),
            "final_upper_chi": float(raw_root["final_upper_chi"]),
            "final_lower_residual_kg_s": float(
                raw_root["final_lower_residual_kg_s"]
            ),
            "final_upper_residual_kg_s": float(
                raw_root["final_upper_residual_kg_s"]
            ),
        }
    )

    root_gate = bool(
        requested_chi > WEAK_COMPRESSION_CHI_LIMIT
        and requested_chi <= DIAGNOSTIC_CHI_CAP
        and float(root["pressure_pa"]) > float(static.pressure_pa)
        and float(root["density_kg_m3"]) > float(static.density_kg_m3)
        and abs(float(root["root_mass_residual_kg_s"]))
        <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and float(root["local_residual_slope_kg_s_Pa"]) < 0.0
        and float(root["velocity_m_s"]) >= -velocity_tolerance
        and 0.0 <= float(root["mach"]) < 1.0
        and normalize_phase(str(root["phase"])) in allowed_phases
        and bool(root["hugoniot_closure_passed"])
        and bool(root["hugoniot_identity_accounted_passed"])
        and bool(root["lax_1_shock_passed"])
        and bool(root["entropy_bound_passed"])
        and float(root["stagnation_pressure_pa"])
        > float(hook.adapter.back_pressure_pa)
        and bool(root["stagnation_enthalpy_round_trip_passed"])
        and bool(root["energy_mass_consistency_passed"])
        and bool(root["energy_port_closure_passed"])
        and abs(float(root["momentum_ledger_residual_N"]))
        <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    )
    if not root_gate:
        raise FiniteCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE",
            "selected Hugoniot root did not pass all fixed physical/root/ledger gates",
            {"hugoniot_scan_rows": annotated_scan, "root": root},
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
        raise FiniteCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE",
            "selected Hugoniot Euler flux contains nonfinite values",
            {"root": root},
        )

    successful_pressures = [
        float(row["pressure_pa"])
        for row in annotated_scan
        if row.get("evaluation_succeeded")
        and row.get("local_candidate_admissible")
    ]
    context = {
        "solver_time_s": float(solver_time_s),
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": interior_mach,
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
        "connected_scan_admissible_subsonic_nodes": len(successful),
        "connected_scan_lowest_pressure_pa": min(successful_pressures),
        "connected_scan_stop_reason": None,
        "connected_scan_residual_monotone": monotone,
        "connected_scan_sign_change_count": 1,
        "root": root,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
        "branch_classification": BRANCH,
        "root_chi": requested_chi,
        "root_gate_passed": root_gate,
        "hugoniot_scan_rows": annotated_scan,
        "hugoniot_density_search_rows": list(curve.density_search_rows),
        "hugoniot_scan_monotone_nonincreasing": monotone,
        "hugoniot_scan_sign_change_count": 1,
        "positive_pressure_continuation_flux_applied": True,
        "finite_compression_flux_applied": True,
        "finite_compression_branch_approved": False,
    }
    return context


class A1FiniteCompressionHugoniotShortHook(A1DynamicShortHook):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.accepted_branch_history: list[str] = [BRANCH]
        self.pending_branch: str | None = None

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        context = _solve_hugoniot_context(
            hook=self,
            U=U,
            solver_time_s=t,
        )
        self.root_context = context
        self.flux = np.asarray(context["flux"], dtype=float).copy()
        self.pending_branch = str(context["branch_classification"])
        self._cache_t = float(t)
        self._cache_outlet = np.asarray(U[-1], dtype=float).copy()
        self.trial_dts_s = []

    def accept_current_root(self) -> None:
        if self.pending_branch != BRANCH:
            raise AssertionError("no pending finite-compression Hugoniot branch")
        super().accept_current_root()
        self.accepted_branch_history.append(self.pending_branch)
        self.pending_branch = None


def _flatten_rows(
    *,
    rows: list[dict[str, Any]],
    requested_solver_step: int,
    solver_time_s: float,
    row_kind: str,
) -> list[dict[str, Any]]:
    return [
        {
            "requested_solver_step": requested_solver_step,
            "solver_time_s": solver_time_s,
            "row_kind": row_kind,
            **row,
        }
        for row in rows
    ]


def _root_evidence_row(
    *,
    context: dict[str, Any],
    requested_solver_step: int,
) -> dict[str, Any]:
    root = context["root"]
    return {
        "requested_solver_step": requested_solver_step,
        "solver_time_s": float(context["solver_time_s"]),
        "branch_classification": BRANCH,
        "finite_compression_model": "GENERAL_EOS_HUGONIOT",
        "interior_pressure_pa": float(context["interior_pressure_pa"]),
        "interior_density_kg_m3": float(context["interior_density_kg_m3"]),
        "interior_velocity_m_s": float(context["interior_velocity_m_s"]),
        "interior_sound_speed_m_s": float(context["interior_sound_speed_m_s"]),
        "interior_mach": float(context["interior_mach"]),
        "interior_phase": context["interior_phase"],
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
        "root_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(root["local_residual_slope_kg_s_Pa"]),
        "root_b1_formal_outcome": root["formal_outcome"],
        "root_stagnation_pressure_pa": float(root["stagnation_pressure_pa"]),
        "root_stagnation_pressure_margin_above_back_pa": float(
            root["stagnation_pressure_pa"] - root["back_pressure_pa"]
        ),
        "root_entropy_delta_J_kg_K": float(root["entropy_delta_J_kg_K"]),
        "root_hugoniot_energy_residual_J_kg": float(
            root["hugoniot_energy_residual_J_kg"]
        ),
        "root_hugoniot_enthalpy_residual_J_kg": float(
            root["hugoniot_enthalpy_residual_J_kg"]
        ),
        "root_hugoniot_identity_accounted_passed": bool(
            root["hugoniot_identity_accounted_passed"]
        ),
        "root_lax_1_shock_passed": bool(root["lax_1_shock_passed"]),
        "root_shock_speed_m_s": float(root["shock_speed_m_s"]),
        "root_lambda_1_candidate_m_s": float(root["lambda_1_candidate_m_s"]),
        "root_lambda_1_interior_m_s": float(root["lambda_1_interior_m_s"]),
        "compatibility_bisection_iterations": int(
            root["compatibility_bisection_iterations"]
        ),
        "hugoniot_scan_sign_change_count": int(
            context["hugoniot_scan_sign_change_count"]
        ),
        "hugoniot_scan_monotone_nonincreasing": bool(
            context["hugoniot_scan_monotone_nonincreasing"]
        ),
        "root_restriction_reaction_ledger_residual_N": float(
            root["momentum_ledger_residual_N"]
        ),
        "root_energy_port_residual_W": float(root["energy_port_residual_W"]),
        "stagnation_enthalpy_round_trip_passed": bool(
            root["stagnation_enthalpy_round_trip_passed"]
        ),
        "energy_mass_consistency_passed": bool(
            root["energy_mass_consistency_passed"]
        ),
        "energy_port_closure_passed": bool(root["energy_port_closure_passed"]),
        "root_gate_passed": bool(context["root_gate_passed"]),
        "finite_compression_flux_applied": True,
        "finite_compression_branch_approved": False,
    }


def _run_short(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    parent_summary: dict[str, Any],
    U_step484: np.ndarray,
    parent_step_row: dict[str, str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    np.ndarray,
    np.ndarray,
]:
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
    hook = A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(parent_summary["root_pressure_pa"])
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=np.asarray(U_step484, dtype=float),
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
    starting = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current_minus_initial = _inventory_array(starting) - _inventory_array(initial)
    cumulative_residual = np.asarray(
        [
            float(parent_step_row["cumulative_mass_residual_kg"]),
            float(parent_step_row["cumulative_momentum_residual_kg_m_s"]),
            float(parent_step_row["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )
    cumulative_expected_delta = current_minus_initial - cumulative_residual

    U_start = np.asarray(solver.U, dtype=float).copy()
    step_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []
    density_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None
    stop_diagnostics: dict[str, Any] = {}

    for index in range(1, REQUESTED_ACCEPTED_STEPS + 1):
        requested_step = STARTING_SOLVER_STEP + index
        try:
            before = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            candidate_dt = float(solver.compute_dt())
            dt_limits = dict(hook.last_dt_limits)
            if hook.root_context is None:
                raise FiniteCompressionShortRunStop(
                    "ROOT_OR_LEDGER_FAILURE",
                    "Hugoniot root was not prepared by compute_dt",
                )
            context = hook.root_context
            if context["branch_classification"] != BRANCH:
                raise FiniteCompressionShortRunStop(
                    "UNAPPROVED_BRANCH",
                    f"unexpected branch {context['branch_classification']!r}",
                )
            root_rows.append(
                _root_evidence_row(
                    context=context,
                    requested_solver_step=requested_step,
                )
            )
            scan_rows.extend(
                _flatten_rows(
                    rows=list(context["hugoniot_scan_rows"]),
                    requested_solver_step=requested_step,
                    solver_time_s=float(context["solver_time_s"]),
                    row_kind="HUGONIOT_FIXED_SCAN",
                )
            )
            density_rows.extend(
                _flatten_rows(
                    rows=list(context["hugoniot_density_search_rows"]),
                    requested_solver_step=requested_step,
                    solver_time_s=float(context["solver_time_s"]),
                    row_kind="HUGONIOT_DENSITY_SEARCH",
                )
            )

            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)
            accepted_dt = float(solver.step(candidate_dt))
            hook.accept_current_root()

            after = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            expected_step_delta = (
                accepted_dt
                * grid.geometry.area_m2
                * (left_flux - right_flux)
            )
            cumulative_expected_delta += expected_step_delta
            primitive_after = solver.primitive()
            post_reconstruction = provider.reconstruct_from_conserved(
                solver.U[-1]
            )
            row = build_step_row(
                case_id=CASE_ID,
                state_id=state_id,
                requested_step=requested_step,
                solver=solver,
                hook=hook,
                root_context=context,
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
            rho_after = np.asarray(solver.U[:, 0], dtype=float)
            velocity_after = np.asarray(
                solver.U[:, 1] / rho_after,
                dtype=float,
            )
            internal_after = np.asarray(
                solver.U[:, 2] / rho_after - 0.5 * velocity_after**2,
                dtype=float,
            )
            outlet_after = post_reconstruction.static
            root = context["root"]
            row.update(
                {
                    "branch_classification": BRANCH,
                    "finite_compression_model": "GENERAL_EOS_HUGONIOT",
                    "root_requested_chi": float(root["requested_chi"]),
                    "root_realized_chi": float(root["realized_chi"]),
                    "approved_weak_compression_chi_limit": WEAK_COMPRESSION_CHI_LIMIT,
                    "diagnostic_chi_cap": DIAGNOSTIC_CHI_CAP,
                    "root_pressure_offset_pa": float(root["p_P_minus_p_i_pa"]),
                    "root_density_kg_m3": float(root["density_kg_m3"]),
                    "root_temperature_K": float(root["temperature_K"]),
                    "root_entropy_delta_J_kg_K": float(root["entropy_delta_J_kg_K"]),
                    "root_hugoniot_energy_residual_J_kg": float(
                        root["hugoniot_energy_residual_J_kg"]
                    ),
                    "root_hugoniot_enthalpy_residual_J_kg": float(
                        root["hugoniot_enthalpy_residual_J_kg"]
                    ),
                    "root_hugoniot_identity_accounted_passed": bool(
                        root["hugoniot_identity_accounted_passed"]
                    ),
                    "root_lax_1_shock_passed": bool(root["lax_1_shock_passed"]),
                    "root_shock_speed_m_s": float(root["shock_speed_m_s"]),
                    "root_lambda_1_candidate_m_s": float(
                        root["lambda_1_candidate_m_s"]
                    ),
                    "root_lambda_1_interior_m_s": float(
                        root["lambda_1_interior_m_s"]
                    ),
                    "hugoniot_scan_monotone_nonincreasing": bool(
                        context["hugoniot_scan_monotone_nonincreasing"]
                    ),
                    "hugoniot_scan_sign_change_count": int(
                        context["hugoniot_scan_sign_change_count"]
                    ),
                    "root_gate_passed": bool(context["root_gate_passed"]),
                    "all_conserved_finite_after_step": bool(
                        np.all(np.isfinite(solver.U))
                    ),
                    "minimum_density_after_step_kg_m3": float(np.min(rho_after)),
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
            per_step_gate = bool(
                bool(context["root_gate_passed"])
                and bool(row["step_passed"])
                and accepted_dt > 0.0
                and int(solver.step_count) == requested_step
                and bool(row["all_conserved_finite_after_step"])
                and float(row["minimum_density_after_step_kg_m3"]) > 0.0
                and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
                and not bool(row["reverse_flow_guard_triggered"])
                and not bool(row["reverse_velocity_detected"])
                and float(row["outlet_velocity_after_step_m_s"]) >= 0.0
                and 0.0 <= float(row["outlet_mach_after_step"]) < 1.0
                and bool(row["outlet_phase_passed"])
                and bool(row["rho_xv_exact_zero"])
                and float(root["requested_chi"]) > WEAK_COMPRESSION_CHI_LIMIT
                and float(root["requested_chi"]) <= DIAGNOSTIC_CHI_CAP
            )
            row["increment_7_per_step_gate_passed"] = per_step_gate
            step_rows.append(row)
            branch_rows.append(
                {
                    "requested_solver_step": requested_step,
                    "solver_step_count": int(solver.step_count),
                    "time_after_s": float(solver.t),
                    "branch_classification": BRANCH,
                    "accepted": True,
                }
            )
            if not per_step_gate:
                raise FiniteCompressionShortRunStop(
                    "POST_STEP_GATE_FAILURE",
                    f"accepted solver step {requested_step} failed the Increment 7 per-step gate",
                    {"step_row": row},
                )
        except FiniteCompressionShortRunStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{type(exc).__name__}: {exc}"
            stop_diagnostics = dict(exc.diagnostics)
            break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            stop_diagnostics = {}
            break

    U_final = np.asarray(solver.U, dtype=float).copy()
    branch_sequence = [row["branch_classification"] for row in branch_rows]
    branch_transitions = sum(
        left != right
        for left, right in zip(branch_sequence, branch_sequence[1:])
    )
    clear_chatter = bool(
        any(
            sequence[0] == sequence[2] == sequence[4]
            and sequence[1] == sequence[3]
            and sequence[0] != sequence[1]
            for sequence in (
                branch_sequence[index : index + 5]
                for index in range(max(len(branch_sequence) - 4, 0))
            )
            if len(sequence) == 5
        )
    )
    pass_gate = bool(
        stop_reason is None
        and len(step_rows) == REQUESTED_ACCEPTED_STEPS
        and len(root_rows) == REQUESTED_ACCEPTED_STEPS
        and int(solver.step_count) == FINAL_SOLVER_STEP
        and all(row["increment_7_per_step_gate_passed"] for row in step_rows)
        and all(branch == BRANCH for branch in branch_sequence)
        and branch_transitions == 0
        and not clear_chatter
        and all(
            WEAK_COMPRESSION_CHI_LIMIT
            < float(row["root_requested_chi"])
            <= DIAGNOSTIC_CHI_CAP
            for row in step_rows
        )
    )
    final_reconstruction = provider.reconstruct_from_conserved(U_final[-1])
    rho_final = U_final[:, 0]
    velocity_final = U_final[:, 1] / rho_final
    internal_final = U_final[:, 2] / rho_final - 0.5 * velocity_final**2
    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_7",
        "scope": "model_review_eight_actual_fvm_steps_general_eos_hugoniot",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_artifact_verified": True,
        "parent_outcome": parent_summary["outcome"],
        "case_id": CASE_ID,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "starting_solver_step": STARTING_SOLVER_STEP,
        "requested_accepted_steps": REQUESTED_ACCEPTED_STEPS,
        "accepted_steps_completed": len(step_rows),
        "final_solver_step": int(solver.step_count),
        "starting_solver_time_s": STARTING_SOLVER_TIME_S,
        "final_solver_time_s": float(solver.t),
        "branch_sequence": branch_sequence,
        "branch_counts": dict(Counter(branch_sequence)),
        "branch_transition_count": branch_transitions,
        "clear_branch_chatter_detected": clear_chatter,
        "maximum_root_requested_chi": _maximum(step_rows, "root_requested_chi"),
        "minimum_root_requested_chi": _minimum(step_rows, "root_requested_chi"),
        "maximum_root_pressure_offset_pa": _maximum(
            step_rows, "root_pressure_offset_pa"
        ),
        "minimum_root_pressure_offset_pa": _minimum(
            step_rows, "root_pressure_offset_pa"
        ),
        "maximum_absolute_root_mass_residual_kg_s": _max_abs(
            step_rows, "root_mass_residual_kg_s"
        ),
        "minimum_root_local_slope_kg_s_Pa": _minimum(
            step_rows, "root_local_slope_kg_s_Pa"
        ),
        "maximum_root_mach": _maximum(step_rows, "root_mach"),
        "minimum_root_velocity_m_s": _minimum(step_rows, "root_velocity_m_s"),
        "minimum_root_entropy_delta_J_kg_K": _minimum(
            step_rows, "root_entropy_delta_J_kg_K"
        ),
        "minimum_root_stagnation_pressure_margin_above_back_pa": _minimum(
            root_rows, "root_stagnation_pressure_margin_above_back_pa"
        ),
        "minimum_root_shock_speed_m_s": _minimum(
            step_rows, "root_shock_speed_m_s"
        ),
        "maximum_halving_count": _maximum(step_rows, "halving_count"),
        "minimum_accepted_dt_s": _minimum(step_rows, "accepted_dt_s"),
        "maximum_accepted_dt_s": _maximum(step_rows, "accepted_dt_s"),
        "maximum_absolute_step_mass_residual_kg": _max_abs(
            step_rows, "step_mass_residual_kg"
        ),
        "maximum_absolute_step_momentum_residual_kg_m_s": _max_abs(
            step_rows, "step_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_step_energy_residual_J": _max_abs(
            step_rows, "step_energy_residual_J"
        ),
        "maximum_absolute_cumulative_mass_residual_kg": _max_abs(
            step_rows, "cumulative_mass_residual_kg"
        ),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": _max_abs(
            step_rows, "cumulative_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_cumulative_energy_residual_J": _max_abs(
            step_rows, "cumulative_energy_residual_J"
        ),
        "final_outlet_pressure_pa": float(final_reconstruction.static.pressure_pa),
        "final_outlet_velocity_m_s": float(final_reconstruction.static.velocity_m_s),
        "final_outlet_mach": float(
            final_reconstruction.static.velocity_m_s
            / final_reconstruction.static.sound_speed_m_s
        ),
        "final_outlet_phase": str(final_reconstruction.static.phase),
        "final_minimum_density_kg_m3": float(np.min(rho_final)),
        "final_minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "final_rho_xv_exact_zero": bool(np.all(U_final[:, 3] == 0.0)),
        "starting_state_sha256": _array_sha256(U_start),
        "final_state_sha256": _array_sha256(U_final),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "stop_diagnostics_keys": sorted(stop_diagnostics),
        "increment_7_eight_step_gate_passed": pass_gate,
        "outcome": OUTCOME if pass_gate else "INCREMENT_7_STOPPED",
        "finite_compression_flux_applied": bool(step_rows),
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
        "solver_step_493_authorized": False,
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
        step_rows,
        root_rows,
        scan_rows,
        density_rows,
        branch_rows,
        U_start,
        U_final,
    )


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
    parent_summary, U_step484, parent_step_row = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    (
        summary,
        step_rows,
        root_rows,
        scan_rows,
        density_rows,
        branch_rows,
        U_start,
        U_final,
    ) = _run_short(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_step484=U_step484,
        parent_step_row=parent_step_row,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "finite_compression_steps.csv", step_rows)
    _write_csv(output / "finite_compression_roots.csv", root_rows)
    _write_csv(output / "hugoniot_fixed_scans.csv", scan_rows)
    _write_csv(output / "hugoniot_density_search.csv", density_rows)
    _write_csv(output / "branch_sequence.csv", branch_rows)
    np.savez_compressed(
        output / "finite_compression_8_step_states.npz",
        U_start=np.asarray(U_start, dtype=float),
        U_final=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray([STARTING_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
    )
    authority = {
        "increment_6_parent": {
            "source_sha": PARENT_SOURCE_SHA,
            "workflow_run": PARENT_WORKFLOW_RUN,
            "job": PARENT_JOB,
            "artifact": PARENT_ARTIFACT,
            "artifact_name": PARENT_ARTIFACT_NAME,
            "artifact_sha256": PARENT_ARTIFACT_SHA256,
            "outcome": parent_summary["outcome"],
            "verified": True,
        }
    }
    (output / "authority_verification.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stop = {
        "classification": summary["stop_classification"],
        "reason": summary["stop_reason"],
        "diagnostic_keys": summary["stop_diagnostics_keys"],
    }
    (output / "stop_evidence.json").write_text(
        json.dumps(stop, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 finite-compression Increment 7\n\n"
        "MODEL_REVIEW / EIGHT_ACTUAL_FVM_STEPS evidence. The authoritative "
        "Increment 6 step-484 state was loaded and independently verified. A "
        "new general-EOS Hugoniot and unchanged B1-compatible root were solved "
        "at every requested step. No result authorizes step 493, formal "
        "finite-compression approval, benchmark acceptance, Physical "
        "Validation, design use, or production activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "finite_compression_steps.csv",
        "finite_compression_roots.csv",
        "hugoniot_fixed_scans.csv",
        "hugoniot_density_search.csv",
        "branch_sequence.csv",
        "finite_compression_8_step_states.npz",
        "authority_verification.json",
        "stop_evidence.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_7_eight_step_gate_passed"]:
        raise SystemExit(
            "Increment 7 Hugoniot 8-step gate did not pass: "
            f"{summary['stop_classification']} {summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
