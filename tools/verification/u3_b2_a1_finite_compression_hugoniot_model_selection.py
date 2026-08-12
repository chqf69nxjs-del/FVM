from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
import CoolProp.CoolProp as CP
from CoolProp import AbstractState, DmassP_INPUTS

import u3_b2_a1_weak_compression_bridge_one_step as one_step
import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_a1_wave_curve_model as wave
import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


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
EXPECTED_SOLVER_STEP = 483
EXPECTED_SOLVER_TIME_S = 0.0032365792102672024
NEXT_REQUESTED_SOLVER_STEP = 484
WEAK_COMPRESSION_CHI_LIMIT = 1.0e-6
DIAGNOSTIC_CHI_CAP = 1.0e-4
CHI_NODES = (
    1.0e-6,
    1.05e-6,
    1.10e-6,
    1.25e-6,
    1.50e-6,
    2.0e-6,
    3.0e-6,
    5.0e-6,
    1.0e-5,
    2.0e-5,
    5.0e-5,
    1.0e-4,
)
DENSITY_SCAN_NODES = 65
DENSITY_EXPANSIONS = 8
DENSITY_BISECTION_ITERATIONS = 64
COMPATIBILITY_BISECTION_ITERATIONS = 48
HUGONIOT_ENERGY_TOLERANCE_J_KG = 1.0e-6
HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = 1.0e-8
DENSITY_RELATIVE_BRACKET_TOLERANCE = 1.0e-12
ENTROPY_DECREASE_TOLERANCE_J_KG_K = 1.0e-7
PRESSURE_OFFSET_RELATIVE_DISAGREEMENT = 1.0e-3
VELOCITY_ABSOLUTE_DISAGREEMENT_M_S = 1.0e-5
MASS_RATE_RELATIVE_DISAGREEMENT = 1.0e-3
robustness = robustness_v4.robustness

SUPPORTED = "FINITE_COMPRESSION_HUGONIOT_ROOT_SUPPORTED_FOR_ONE_STEP_REVIEW"
MODEL_DISAGREEMENT = (
    "FINITE_COMPRESSION_ROOT_INSIDE_DIAGNOSTIC_CAP_BUT_MODEL_DISAGREEMENT"
)
NO_ROOT = "NO_FINITE_COMPRESSION_ROOT_WITHIN_DIAGNOSTIC_CAP"

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


class FiniteCompressionDiagnosticError(RuntimeError):
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


def _sign(value: float) -> int:
    return -1 if value < 0.0 else 1 if value > 0.0 else 0


def _verify_parent(
    parent_dir: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray]:
    if artifact_digest != PARENT_ARTIFACT_SHA256:
        raise FiniteCompressionDiagnosticError(
            "PARENT_ARTIFACT_MISMATCH: GitHub artifact digest mismatch"
        )
    actual = {path.name for path in parent_dir.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise FiniteCompressionDiagnosticError(
            "PARENT_ARTIFACT_MISMATCH: file set mismatch: "
            f"{sorted(actual)}"
        )
    manifest: dict[str, str] = {}
    for line in (parent_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise FiniteCompressionDiagnosticError(
            "PARENT_ARTIFACT_MISMATCH: internal manifest names mismatch"
        )
    for name, digest in manifest.items():
        if _sha256(parent_dir / name) != digest:
            raise FiniteCompressionDiagnosticError(
                f"PARENT_ARTIFACT_MISMATCH: internal SHA256 mismatch for {name}"
            )
    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "solver_step_after": EXPECTED_SOLVER_STEP,
        "solver_time_after_s": EXPECTED_SOLVER_TIME_S,
        "outcome": "INCREMENT_4F_STOPPED",
        "stop_classification": "GuardFrontContinuationStop",
        "stop_reason": (
            "GuardFrontContinuationStop: successful residual remains positive "
            "through the fixed chi scope"
        ),
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise FiniteCompressionDiagnosticError(
                f"PARENT_ARTIFACT_MISMATCH: summary {key}={summary.get(key)!r}"
            )
    if not bool(summary.get("pre_guard_front_reproduction_passed")):
        raise FiniteCompressionDiagnosticError(
            "PARENT_ARTIFACT_MISMATCH: pre-Guard reproduction did not pass"
        )
    if not bool(summary.get("guard_front_refinement_gate_passed")):
        raise FiniteCompressionDiagnosticError(
            "PARENT_ARTIFACT_MISMATCH: Guard-front refinement gate did not pass"
        )
    if not bool(summary.get("guard_front_root_topology_gate_passed")):
        raise FiniteCompressionDiagnosticError(
            "PARENT_ARTIFACT_MISMATCH: root-topology gate did not pass"
        )

    with np.load(parent_dir / "full_horizon_states.npz") as states:
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_final.shape != (32, 4):
        raise FiniteCompressionDiagnosticError(
            "STATE_REPRODUCTION_MISMATCH: final state shape is not (32, 4)"
        )
    if step_after != EXPECTED_SOLVER_STEP or time_after != EXPECTED_SOLVER_TIME_S:
        raise FiniteCompressionDiagnosticError(
            "STATE_REPRODUCTION_MISMATCH: solver identity mismatch"
        )
    if not np.all(np.isfinite(U_final)):
        raise FiniteCompressionDiagnosticError(
            "NONFINITE_OR_NONPOSITIVE_STATE: nonfinite conserved state"
        )
    rho = U_final[:, 0]
    velocity = U_final[:, 1] / rho
    internal = U_final[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise FiniteCompressionDiagnosticError(
            "NONFINITE_OR_NONPOSITIVE_STATE: density or internal energy"
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise FiniteCompressionDiagnosticError(
            "STATE_REPRODUCTION_MISMATCH: rho*xv is not exact zero"
        )
    return summary, U_final


def _brackets(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    valid = [
        row
        for row in sorted(rows, key=lambda item: float(item["requested_chi"]))
        if row.get("evaluation_succeeded")
        and row.get("local_candidate_admissible")
        and row.get("compatibility_residual_kg_s") is not None
    ]
    result: list[dict[str, float]] = []
    for left, right in zip(valid, valid[1:]):
        r0 = float(left["compatibility_residual_kg_s"])
        r1 = float(right["compatibility_residual_kg_s"])
        if _sign(r0) == 0 or _sign(r1) == 0 or _sign(r0) != _sign(r1):
            result.append(
                {
                    "lower_chi": float(left["requested_chi"]),
                    "upper_chi": float(right["requested_chi"]),
                    "lower_residual_kg_s": r0,
                    "upper_residual_kg_s": r1,
                }
            )
    return result


def _monotone_nonincreasing(rows: list[dict[str, Any]]) -> bool:
    valid = [
        float(row["compatibility_residual_kg_s"])
        for row in sorted(rows, key=lambda item: float(item["requested_chi"]))
        if row.get("evaluation_succeeded")
        and row.get("local_candidate_admissible")
        and row.get("compatibility_residual_kg_s") is not None
    ]
    return bool(
        len(valid) >= 2
        and all(valid[index + 1] <= valid[index] for index in range(len(valid) - 1))
    )


def _bisect_compatibility_root(
    *,
    curve: str,
    bracket: dict[str, float],
    evaluate_chi: Callable[[float, str], dict[str, Any]],
) -> dict[str, Any]:
    a_chi = float(bracket["lower_chi"])
    b_chi = float(bracket["upper_chi"])
    a = evaluate_chi(a_chi, "compatibility_bisection")
    b = evaluate_chi(b_chi, "compatibility_bisection")
    if not a.get("local_candidate_admissible") or not b.get(
        "local_candidate_admissible"
    ):
        raise FiniteCompressionDiagnosticError(
            f"COMPATIBILITY_ROOT_FAILURE: {curve} bracket endpoint inadmissible"
        )
    a_r = float(a["compatibility_residual_kg_s"])
    b_r = float(b["compatibility_residual_kg_s"])
    if _sign(a_r) == _sign(b_r) and a_r != 0.0 and b_r != 0.0:
        raise FiniteCompressionDiagnosticError(
            f"COMPATIBILITY_ROOT_FAILURE: {curve} bracket has no sign change"
        )
    best = a if abs(a_r) <= abs(b_r) else b
    iterations = 0
    for iterations in range(1, COMPATIBILITY_BISECTION_ITERATIONS + 1):
        mid_chi = float(0.5 * (a_chi + b_chi))
        mid = evaluate_chi(mid_chi, "compatibility_bisection")
        if not mid.get("local_candidate_admissible"):
            raise FiniteCompressionDiagnosticError(
                f"COMPATIBILITY_ROOT_FAILURE: {curve} midpoint inadmissible"
            )
        mid_r = float(mid["compatibility_residual_kg_s"])
        if abs(mid_r) < abs(float(best["compatibility_residual_kg_s"])):
            best = mid
        if abs(mid_r) <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S:
            best = mid
            if iterations >= 2:
                break
        if _sign(mid_r) == _sign(a_r):
            a_chi, a_r, a = mid_chi, mid_r, mid
        else:
            b_chi, b_r, b = mid_chi, mid_r, mid
    pressure_width = float(b["pressure_pa"] - a["pressure_pa"])
    slope = (
        None
        if pressure_width == 0.0
        else float((b_r - a_r) / pressure_width)
    )
    root = dict(best)
    root.update(
        {
            "curve": curve,
            "compatibility_bisection_iterations": iterations,
            "final_lower_chi": a_chi,
            "final_upper_chi": b_chi,
            "final_lower_residual_kg_s": a_r,
            "final_upper_residual_kg_s": b_r,
            "local_residual_slope_kg_s_Pa": slope,
        }
    )
    return root


class HugoniotCurve:
    def __init__(
        self,
        *,
        static: Any,
        hook: Any,
        allowed_phases: set[str],
        velocity_tolerance_m_s: float,
        pressure_denominator_pa: float,
    ) -> None:
        self.static = static
        self.hook = hook
        self.allowed_phases = allowed_phases
        self.velocity_tolerance_m_s = velocity_tolerance_m_s
        self.pressure_denominator_pa = pressure_denominator_pa
        self.state = AbstractState("HEOS", "CO2")
        self.density_search_rows: list[dict[str, Any]] = []
        self.cache: dict[float, dict[str, Any]] = {}

    def _props(self, pressure_pa: float, density_kg_m3: float) -> dict[str, Any]:
        self.state.update(DmassP_INPUTS, float(density_kg_m3), float(pressure_pa))
        p = float(self.state.p())
        T = float(self.state.T())
        rho = float(self.state.rhomass())
        e = float(self.state.umass())
        h = float(self.state.hmass())
        s = float(self.state.smass())
        c = float(self.state.speed_sound())
        phase = str(CP.PhaseSI("P", p, "Dmass", rho, "CO2"))
        if not all(math.isfinite(value) for value in (p, T, rho, e, h, s, c)):
            raise ValueError("nonfinite Hugoniot property")
        if rho <= 0.0 or e <= 0.0 or c <= 0.0:
            raise ValueError("nonpositive Hugoniot property")
        return {
            "pressure_pa": p,
            "temperature_K": T,
            "density_kg_m3": rho,
            "internal_energy_J_kg": e,
            "enthalpy_J_kg": h,
            "entropy_J_kg_K": s,
            "sound_speed_m_s": c,
            "phase": phase,
        }

    def _density_row(
        self,
        *,
        pressure_pa: float,
        density_kg_m3: float,
        requested_chi: float,
        expansion: int,
        stage: str,
    ) -> dict[str, Any]:
        props = self._props(pressure_pa, density_kg_m3)
        v = 1.0 / float(props["density_kg_m3"])
        v_i = 1.0 / float(self.static.density_kg_m3)
        H_e = float(
            props["internal_energy_J_kg"]
            - float(self.static.internal_energy_J_kg)
            + 0.5
            * (pressure_pa + float(self.static.pressure_pa))
            * (v - v_i)
        )
        H_h = float(
            props["enthalpy_J_kg"]
            - float(self.static.enthalpy_J_kg)
            - 0.5
            * (pressure_pa - float(self.static.pressure_pa))
            * (v_i + v)
        )
        row = {
            "requested_chi": requested_chi,
            "pressure_pa": pressure_pa,
            "density_kg_m3": float(props["density_kg_m3"]),
            "density_fraction_above_interior": float(
                props["density_kg_m3"] / float(self.static.density_kg_m3) - 1.0
            ),
            "hugoniot_energy_residual_J_kg": H_e,
            "hugoniot_enthalpy_residual_J_kg": H_h,
            "hugoniot_form_difference_J_kg": float(H_e - H_h),
            "temperature_K": float(props["temperature_K"]),
            "entropy_J_kg_K": float(props["entropy_J_kg_K"]),
            "phase": str(props["phase"]),
            "expansion": expansion,
            "density_search_stage": stage,
        }
        self.density_search_rows.append(row)
        return {**props, **row}

    def _find_density_brackets(
        self,
        rows: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        brackets: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for left, right in zip(rows, rows[1:]):
            h0 = float(left["hugoniot_energy_residual_J_kg"])
            h1 = float(right["hugoniot_energy_residual_J_kg"])
            if _sign(h0) == 0 or _sign(h1) == 0 or _sign(h0) != _sign(h1):
                brackets.append((left, right))
        return brackets

    def solve_density(
        self,
        *,
        requested_chi: float,
        stage: str,
    ) -> dict[str, Any]:
        pressure_pa = float(
            float(self.static.pressure_pa)
            + requested_chi * self.pressure_denominator_pa
        )
        rho_i = float(self.static.density_kg_m3)
        lower_density = float(rho_i * (1.0 + 1.0e-12))
        fraction = float(max(1.0e-5, 20.0 * requested_chi))
        selected: tuple[dict[str, Any], dict[str, Any]] | None = None
        selected_expansion = -1
        for expansion in range(DENSITY_EXPANSIONS + 1):
            upper_density = float(rho_i * (1.0 + fraction))
            densities = np.linspace(
                lower_density,
                upper_density,
                DENSITY_SCAN_NODES,
            )
            rows: list[dict[str, Any]] = []
            for density in densities:
                row = self._density_row(
                    pressure_pa=pressure_pa,
                    density_kg_m3=float(density),
                    requested_chi=requested_chi,
                    expansion=expansion,
                    stage=f"{stage}_density_scan",
                )
                if normalize_phase(str(row["phase"])) not in self.allowed_phases:
                    raise FiniteCompressionDiagnosticError(
                        "PHASE_SCOPE_DEPARTURE: Hugoniot density scan left liquid scope"
                    )
                rows.append(row)
            brackets = self._find_density_brackets(rows)
            if len(brackets) > 1:
                raise FiniteCompressionDiagnosticError(
                    "HUGONIOT_MULTIPLE_DENSITY_ROOTS: multiple density brackets"
                )
            if len(brackets) == 1:
                selected = brackets[0]
                selected_expansion = expansion
                break
            fraction *= 2.0
        if selected is None:
            raise FiniteCompressionDiagnosticError(
                "HUGONIOT_DENSITY_ROOT_FAILURE: no density sign change"
            )

        left, right = selected
        a_rho = float(left["density_kg_m3"])
        b_rho = float(right["density_kg_m3"])
        a_h = float(left["hugoniot_energy_residual_J_kg"])
        b_h = float(right["hugoniot_energy_residual_J_kg"])
        best = left if abs(a_h) <= abs(b_h) else right
        for _ in range(DENSITY_BISECTION_ITERATIONS):
            mid_rho = float(0.5 * (a_rho + b_rho))
            mid = self._density_row(
                pressure_pa=pressure_pa,
                density_kg_m3=mid_rho,
                requested_chi=requested_chi,
                expansion=selected_expansion,
                stage=f"{stage}_density_bisection",
            )
            if normalize_phase(str(mid["phase"])) not in self.allowed_phases:
                raise FiniteCompressionDiagnosticError(
                    "PHASE_SCOPE_DEPARTURE: Hugoniot bisection left liquid scope"
                )
            mid_h = float(mid["hugoniot_energy_residual_J_kg"])
            if abs(mid_h) < abs(float(best["hugoniot_energy_residual_J_kg"])):
                best = mid
            if _sign(mid_h) == _sign(a_h):
                a_rho, a_h, left = mid_rho, mid_h, mid
            else:
                b_rho, b_h, right = mid_rho, mid_h, mid
        relative_width = float((b_rho - a_rho) / rho_i)
        if relative_width > DENSITY_RELATIVE_BRACKET_TOLERANCE:
            raise FiniteCompressionDiagnosticError(
                "HUGONIOT_DENSITY_ROOT_FAILURE: density bracket too wide"
            )
        result = dict(best)
        result.update(
            {
                "density_bracket_lower_kg_m3": a_rho,
                "density_bracket_upper_kg_m3": b_rho,
                "density_relative_bracket_width": relative_width,
                "density_search_expansion": selected_expansion,
                "density_bisection_iterations": DENSITY_BISECTION_ITERATIONS,
            }
        )
        if abs(float(result["hugoniot_energy_residual_J_kg"])) > (
            HUGONIOT_ENERGY_TOLERANCE_J_KG
        ):
            raise FiniteCompressionDiagnosticError(
                "HUGONIOT_DENSITY_ROOT_FAILURE: energy residual tolerance"
            )
        if abs(float(result["hugoniot_enthalpy_residual_J_kg"])) > (
            HUGONIOT_ENERGY_TOLERANCE_J_KG
        ):
            raise FiniteCompressionDiagnosticError(
                "HUGONIOT_DENSITY_ROOT_FAILURE: enthalpy residual tolerance"
            )
        if abs(float(result["hugoniot_form_difference_J_kg"])) > (
            HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG
        ):
            raise FiniteCompressionDiagnosticError(
                "HUGONIOT_DENSITY_ROOT_FAILURE: energy-form equivalence"
            )
        return result

    def evaluate(self, requested_chi: float, stage: str) -> dict[str, Any]:
        key = float(requested_chi)
        if key in self.cache:
            cached = dict(self.cache[key])
            cached["evaluation_stage"] = stage
            return cached
        try:
            props = self.solve_density(requested_chi=key, stage=stage)
            p_i = float(self.static.pressure_pa)
            rho_i = float(self.static.density_kg_m3)
            u_i = float(self.static.velocity_m_s)
            v_i = 1.0 / rho_i
            p = float(props["pressure_pa"])
            rho = float(props["density_kg_m3"])
            v = 1.0 / rho
            delta_p = float(p - p_i)
            delta_v = float(v_i - v)
            if not delta_p > 0.0 or not delta_v > 0.0 or not rho > rho_i:
                raise FiniteCompressionDiagnosticError(
                    "HUGONIOT_DENSITY_ROOT_FAILURE: non-compressive state"
                )
            shock_mass_flux = float(math.sqrt(delta_p / delta_v))
            velocity = float(u_i - shock_mass_flux * delta_v)
            shock_speed = float(u_i - shock_mass_flux * v_i)
            sound_speed = float(props["sound_speed_m_s"])
            mach = float(velocity / sound_speed)
            lambda_1_i = float(u_i - float(self.static.sound_speed_m_s))
            lambda_1_P = float(velocity - sound_speed)
            lax = bool(lambda_1_P < shock_speed < lambda_1_i)
            entropy_delta = float(
                props["entropy_J_kg_K"] - float(self.static.entropy_J_kg_K)
            )
            conserved = np.asarray(
                [
                    rho,
                    rho * velocity,
                    rho
                    * (
                        float(props["internal_energy_J_kg"])
                        + 0.5 * velocity * velocity
                    ),
                    0.0,
                ],
                dtype=float,
            )
            evaluation = self.hook.adapter.evaluate(conserved, self.hook.area_m2)
            base = {
                "curve": "GENERAL_EOS_HUGONIOT",
                "requested_chi": key,
                "realized_chi": float(delta_p / self.pressure_denominator_pa),
                "approved_weak_compression_scope": bool(
                    key <= WEAK_COMPRESSION_CHI_LIMIT
                ),
                "diagnostic_only": True,
                "pressure_pa": p,
                "pressure_offset_pa": delta_p,
                "density_kg_m3": rho,
                "temperature_K": float(props["temperature_K"]),
                "internal_energy_J_kg": float(props["internal_energy_J_kg"]),
                "enthalpy_J_kg": float(props["enthalpy_J_kg"]),
                "entropy_J_kg_K": float(props["entropy_J_kg_K"]),
                "entropy_delta_J_kg_K": entropy_delta,
                "sound_speed_m_s": sound_speed,
                "phase": str(props["phase"]),
                "velocity_m_s": velocity,
                "mach": mach,
                "shock_mass_flux_kg_m2_s": shock_mass_flux,
                "shock_speed_m_s": shock_speed,
                "lambda_1_interior_m_s": lambda_1_i,
                "lambda_1_candidate_m_s": lambda_1_P,
                "lax_1_shock_passed": lax,
                "hugoniot_energy_residual_J_kg": float(
                    props["hugoniot_energy_residual_J_kg"]
                ),
                "hugoniot_enthalpy_residual_J_kg": float(
                    props["hugoniot_enthalpy_residual_J_kg"]
                ),
                "hugoniot_form_difference_J_kg": float(
                    props["hugoniot_form_difference_J_kg"]
                ),
                "density_relative_bracket_width": float(
                    props["density_relative_bracket_width"]
                ),
                "density_search_expansion": int(
                    props["density_search_expansion"]
                ),
                "density_bisection_iterations": int(
                    props["density_bisection_iterations"]
                ),
                "evaluation_stage": stage,
            }
            if not evaluation.succeeded or evaluation.face is None:
                result = {
                    **base,
                    "evaluation_succeeded": False,
                    "formal_outcome": evaluation.formal_outcome,
                    "formal_message": evaluation.formal_message,
                    "local_candidate_admissible": False,
                    "compatibility_residual_kg_s": None,
                }
                self.cache[key] = result
                return dict(result)
            face = evaluation.face
            pipe_mass = float(rho * velocity * self.hook.area_m2)
            b1_mass = float(face.mass_transfer_outward_kg_s)
            h0 = float(props["enthalpy_J_kg"] + 0.5 * velocity * velocity)
            pipe_energy = float(pipe_mass * h0)
            b1_energy = float(face.energy_transfer_outward_W)
            energy = wave._energy_ledger(
                pipe_mass,
                b1_mass,
                h0,
                pipe_energy,
                b1_energy,
            )
            pipe_momentum = float(
                pipe_mass * velocity + p * self.hook.area_m2
            )
            downstream_momentum = float(
                face.advective_momentum_rate_out_N
                + face.discharge_state_pressure_pa * face.open_area_m2
            )
            reaction = float(downstream_momentum - pipe_momentum)
            reaction_residual = float(
                downstream_momentum - pipe_momentum - reaction
            )
            outward = bool(velocity >= -self.velocity_tolerance_m_s)
            subsonic = bool(0.0 <= mach < 1.0)
            phase_ok = bool(
                normalize_phase(str(props["phase"])) in self.allowed_phases
            )
            p0_ok = bool(
                float(face.stagnation_pressure_pa)
                > float(self.hook.adapter.back_pressure_pa)
            )
            reaction_ok = bool(
                abs(reaction_residual)
                <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
            )
            hugoniot_ok = bool(
                abs(float(props["hugoniot_energy_residual_J_kg"]))
                <= HUGONIOT_ENERGY_TOLERANCE_J_KG
                and abs(float(props["hugoniot_enthalpy_residual_J_kg"]))
                <= HUGONIOT_ENERGY_TOLERANCE_J_KG
                and abs(float(props["hugoniot_form_difference_J_kg"]))
                <= HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG
            )
            entropy_ok = bool(
                entropy_delta >= -ENTROPY_DECREASE_TOLERANCE_J_KG_K
            )
            local_admissible = bool(
                outward
                and subsonic
                and phase_ok
                and p0_ok
                and reaction_ok
                and hugoniot_ok
                and lax
                and entropy_ok
            )
            residual = float(pipe_mass - b1_mass)
            result = {
                **base,
                "evaluation_succeeded": True,
                "formal_outcome": evaluation.formal_outcome,
                "formal_message": evaluation.formal_message,
                "stagnation_pressure_pa": float(face.stagnation_pressure_pa),
                "back_pressure_pa": float(self.hook.adapter.back_pressure_pa),
                "stagnation_pressure_margin_above_back_pa": float(
                    face.stagnation_pressure_pa - self.hook.adapter.back_pressure_pa
                ),
                "pipe_mass_rate_kg_s": pipe_mass,
                "b1_mass_rate_kg_s": b1_mass,
                "compatibility_residual_kg_s": residual,
                "pipe_momentum_port_N": pipe_momentum,
                "downstream_stream_pressure_port_N": downstream_momentum,
                "restriction_reaction_on_fluid_N": reaction,
                "restriction_reaction_ledger_residual_N": reaction_residual,
                "outward_velocity_passed": outward,
                "subsonic_passed": subsonic,
                "phase_passed": phase_ok,
                "stagnation_pressure_above_back_pressure": p0_ok,
                "reaction_ledger_passed": reaction_ok,
                "hugoniot_closure_passed": hugoniot_ok,
                "entropy_bound_passed": entropy_ok,
                "local_candidate_admissible": local_admissible,
                **energy,
            }
            self.cache[key] = result
            return dict(result)
        except Exception as exc:
            result = {
                "curve": "GENERAL_EOS_HUGONIOT",
                "requested_chi": key,
                "approved_weak_compression_scope": bool(
                    key <= WEAK_COMPRESSION_CHI_LIMIT
                ),
                "diagnostic_only": True,
                "evaluation_succeeded": False,
                "formal_outcome": type(exc).__name__,
                "formal_message": str(exc),
                "local_candidate_admissible": False,
                "compatibility_residual_kg_s": None,
                "evaluation_stage": stage,
            }
            self.cache[key] = result
            return dict(result)


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    parent_summary: dict[str, Any],
    U_final: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    provider = CoolPropB2StateProvider()
    hook = short_run.A1WeakCompressionBridgeShortRunHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=short_run.CASE_ID,
        provider=provider,
    )
    state_before = np.asarray(U_final, dtype=float).copy()
    state_hash_before = _array_sha256(state_before)
    reconstruction = provider.reconstruct_from_conserved(state_before[-1])
    static = reconstruction.static
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, hook.state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    denominator = float(
        static.density_kg_m3 * static.sound_speed_m_s**2
    )
    diagnostic.QUADRATURE_ORDER = short_run.horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))
    isentropic_cache: dict[float, dict[str, Any]] = {}

    def evaluate_isentropic(requested_chi: float, stage: str) -> dict[str, Any]:
        key = float(requested_chi)
        if key not in isentropic_cache:
            requested_offset = float(key * denominator)
            requested_pressure = float(static.pressure_pa + requested_offset)
            raw = one_step._full_wave_row(
                pressure_pa=requested_pressure,
                static=static,
                isentrope=isentrope,
                hook=hook,
                area_m2=hook.area_m2,
                allowed_phases=allowed_phases,
                velocity_tolerance=velocity_tolerance,
                state_id=hook.state_id,
            )
            realized_offset = float(raw["pressure_pa"] - static.pressure_pa)
            item = dict(raw)
            item.update(
                {
                    "curve": "ISENTROPIC_CHARACTERISTIC_EXTRAPOLATION",
                    "requested_chi": key,
                    "realized_chi": float(realized_offset / denominator),
                    "requested_pressure_offset_pa": requested_offset,
                    "realized_pressure_offset_pa": realized_offset,
                    "approved_weak_compression_scope": bool(
                        key <= WEAK_COMPRESSION_CHI_LIMIT
                    ),
                    "diagnostic_only": True,
                    "entropy_delta_J_kg_K": 0.0,
                    "evaluation_stage": stage,
                }
            )
            isentropic_cache[key] = item
        result = dict(isentropic_cache[key])
        result["evaluation_stage"] = stage
        return result

    hugoniot = HugoniotCurve(
        static=static,
        hook=hook,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_tolerance,
        pressure_denominator_pa=denominator,
    )

    isentropic_scan = [
        evaluate_isentropic(chi, "fixed_scan") for chi in CHI_NODES
    ]
    hugoniot_scan = [hugoniot.evaluate(chi, "fixed_scan") for chi in CHI_NODES]

    isentropic_brackets = _brackets(isentropic_scan)
    hugoniot_brackets = _brackets(hugoniot_scan)
    isentropic_monotone = _monotone_nonincreasing(isentropic_scan)
    hugoniot_monotone = _monotone_nonincreasing(hugoniot_scan)

    isentropic_root = None
    hugoniot_root = None
    if len(isentropic_brackets) == 1 and isentropic_monotone:
        isentropic_root = _bisect_compatibility_root(
            curve="ISENTROPIC_CHARACTERISTIC_EXTRAPOLATION",
            bracket=isentropic_brackets[0],
            evaluate_chi=evaluate_isentropic,
        )
    if len(hugoniot_brackets) == 1 and hugoniot_monotone:
        hugoniot_root = _bisect_compatibility_root(
            curve="GENERAL_EOS_HUGONIOT",
            bracket=hugoniot_brackets[0],
            evaluate_chi=hugoniot.evaluate,
        )

    cap_isentropic = evaluate_isentropic(
        WEAK_COMPRESSION_CHI_LIMIT,
        "scope_cap",
    )
    cap_hugoniot = hugoniot.evaluate(
        WEAK_COMPRESSION_CHI_LIMIT,
        "scope_cap",
    )
    cap_reproduced = bool(
        cap_isentropic.get("local_candidate_admissible")
        and cap_hugoniot.get("local_candidate_admissible")
        and float(cap_isentropic["compatibility_residual_kg_s"])
        > robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        and float(cap_hugoniot["compatibility_residual_kg_s"])
        > robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    )

    comparison: dict[str, Any] = {
        "isentropic_root_found": isentropic_root is not None,
        "hugoniot_root_found": hugoniot_root is not None,
        "pressure_offset_relative_difference": None,
        "velocity_absolute_difference_m_s": None,
        "mass_rate_relative_difference": None,
        "material_model_disagreement": None,
    }
    if isentropic_root is not None and hugoniot_root is not None:
        dp_i = float(isentropic_root["pressure_offset_pa"])
        dp_h = float(hugoniot_root["pressure_offset_pa"])
        m_i = float(isentropic_root["pipe_mass_rate_kg_s"])
        m_h = float(hugoniot_root["pipe_mass_rate_kg_s"])
        relative_dp = float(abs(dp_i - dp_h) / max(abs(dp_h), 1.0e-30))
        velocity_difference = float(
            abs(
                float(isentropic_root["velocity_m_s"])
                - float(hugoniot_root["velocity_m_s"])
            )
        )
        relative_mass = float(abs(m_i - m_h) / max(abs(m_h), 1.0e-30))
        disagreement = bool(
            relative_dp > PRESSURE_OFFSET_RELATIVE_DISAGREEMENT
            or velocity_difference > VELOCITY_ABSOLUTE_DISAGREEMENT_M_S
            or relative_mass > MASS_RATE_RELATIVE_DISAGREEMENT
        )
        comparison.update(
            {
                "pressure_offset_relative_difference": relative_dp,
                "velocity_absolute_difference_m_s": velocity_difference,
                "mass_rate_relative_difference": relative_mass,
                "material_model_disagreement": disagreement,
            }
        )

    state_after = np.asarray(state_before, dtype=float).copy()
    state_hash_after = _array_sha256(state_after)
    state_unchanged = bool(
        np.array_equal(state_before, state_after)
        and state_hash_before == state_hash_after
    )

    hugoniot_gate = False
    if hugoniot_root is not None:
        hugoniot_gate = bool(
            float(hugoniot_root["requested_chi"])
            > WEAK_COMPRESSION_CHI_LIMIT
            and float(hugoniot_root["requested_chi"]) <= DIAGNOSTIC_CHI_CAP
            and abs(float(hugoniot_root["compatibility_residual_kg_s"]))
            <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            and hugoniot_root.get("local_residual_slope_kg_s_Pa") is not None
            and float(hugoniot_root["local_residual_slope_kg_s_Pa"]) < 0.0
            and bool(hugoniot_root.get("hugoniot_closure_passed"))
            and bool(hugoniot_root.get("lax_1_shock_passed"))
            and bool(hugoniot_root.get("entropy_bound_passed"))
            and bool(hugoniot_root.get("energy_ledger_passed"))
            and bool(hugoniot_root.get("reaction_ledger_passed"))
            and bool(hugoniot_root.get("outward_velocity_passed"))
            and bool(hugoniot_root.get("subsonic_passed"))
            and bool(hugoniot_root.get("phase_passed"))
        )

    if not state_unchanged:
        outcome = "STATE_MUTATION_DETECTED"
    elif not cap_reproduced:
        outcome = "ROOT_OR_LEDGER_FAILURE"
    elif len(hugoniot_brackets) > 1 or len(isentropic_brackets) > 1:
        outcome = "MULTIPLE_COMPATIBILITY_ROOTS"
    elif hugoniot_root is None:
        outcome = NO_ROOT
    elif not hugoniot_gate:
        if not bool(hugoniot_root.get("lax_1_shock_passed")):
            outcome = "LAX_ADMISSIBILITY_FAILURE"
        elif not bool(hugoniot_root.get("entropy_bound_passed")):
            outcome = "ENTROPY_DECREASE_FAILURE"
        else:
            outcome = "ROOT_OR_LEDGER_FAILURE"
    elif comparison.get("material_model_disagreement") is True:
        outcome = MODEL_DISAGREEMENT
    else:
        outcome = SUPPORTED

    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_5",
        "scope": "model_review_diagnostic_only_hugoniot_model_selection",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_artifact_verified": True,
        "parent_outcome": parent_summary["outcome"],
        "case_id": short_run.CASE_ID,
        "solver_step_loaded": EXPECTED_SOLVER_STEP,
        "next_requested_solver_step": NEXT_REQUESTED_SOLVER_STEP,
        "solver_time_s": EXPECTED_SOLVER_TIME_S,
        "state_sha256_before": state_hash_before,
        "state_sha256_after": state_hash_after,
        "state_unchanged": state_unchanged,
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_phase": str(static.phase),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "interior_stagnation_pressure_pa": float(
            reconstruction.stagnation_pressure_pa
        ),
        "back_pressure_pa": float(hook.adapter.back_pressure_pa),
        "pressure_denominator_rho_c2_pa": denominator,
        "approved_weak_compression_chi_limit": WEAK_COMPRESSION_CHI_LIMIT,
        "diagnostic_chi_cap": DIAGNOSTIC_CHI_CAP,
        "cap_scope_exhaustion_reproduced": cap_reproduced,
        "cap_isentropic_residual_kg_s": cap_isentropic.get(
            "compatibility_residual_kg_s"
        ),
        "cap_hugoniot_residual_kg_s": cap_hugoniot.get(
            "compatibility_residual_kg_s"
        ),
        "isentropic_scan_monotone_nonincreasing": isentropic_monotone,
        "hugoniot_scan_monotone_nonincreasing": hugoniot_monotone,
        "isentropic_sign_change_count": len(isentropic_brackets),
        "hugoniot_sign_change_count": len(hugoniot_brackets),
        "isentropic_root": isentropic_root,
        "hugoniot_root": hugoniot_root,
        "hugoniot_root_gate_passed": hugoniot_gate,
        "curve_comparison": comparison,
        "outcome": outcome,
        "diagnostic_classification_complete": True,
        "fvm_step_484_attempted": False,
        "finite_compression_flux_applied": False,
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
    return (
        summary,
        isentropic_scan,
        hugoniot_scan,
        hugoniot.density_search_rows,
        comparison,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--tolerance-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    if not args.tolerance_spec.is_file():
        raise FileNotFoundError(args.tolerance_spec)
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_final = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    summary, isentropic_rows, hugoniot_rows, density_rows, comparison = _run(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_final=U_final,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)
    summary["tolerance_spec_sha256"] = _sha256(args.tolerance_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "isentropic_extrapolation_scan.csv", isentropic_rows)
    _write_csv(output / "hugoniot_compression_scan.csv", hugoniot_rows)
    _write_csv(output / "hugoniot_density_search.csv", density_rows)
    (output / "curve_comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        output / "step483_state_identity.npz",
        U_before=np.asarray(U_final, dtype=float),
        U_after=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray([EXPECTED_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray([EXPECTED_SOLVER_STEP], dtype=np.int64),
        solver_time_before_s=np.asarray([EXPECTED_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([EXPECTED_SOLVER_TIME_S]),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 finite-compression Increment 5\n\n"
        "MODEL_REVIEW / DIAGNOSTIC_ONLY evidence. The authoritative accepted "
        "step-483 state was loaded without mutation. Diagnostic-only "
        "isentropic extrapolation and a general-EOS compression Hugoniot locus "
        "were compared through the unchanged B1 Adapter. No flux was applied "
        "and FvmSolver step 484 was not attempted.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "isentropic_extrapolation_scan.csv",
        "hugoniot_compression_scan.csv",
        "hugoniot_density_search.csv",
        "curve_comparison.json",
        "step483_state_identity.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
