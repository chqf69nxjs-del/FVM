"""P2-A3.1 limited interior HNE hydrodynamic coupling vertical slice.

This increment activates the Acoustic Authority Gate candidate only inside a
new, dedicated verification harness.  The existing production/default EOS,
flux, CFL, Rusanov, boundary, and discharge paths are not modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .config import PipeGeometry
from .flux import RusanovFluxEvaluation, observe_rusanov_flux
from .grid import UniformGrid
from .hne_acoustic_authority_analysis import analyze_acoustic_authority_gate
from .hne_acoustic_authority_types import (
    AcousticCompatibleHNEVerificationEOS,
    HNEAcousticAuthorityGateError,
)
from .hne_equilibrium_acoustic_closure import (
    recover_equilibrium_state,
    state_from_pressure_quality,
)
from .phase_change import NoPhaseChange
from .solver import FvmSolver
from .state import (
    IDX_RHO,
    IDX_RHO_XV,
    check_physical_state,
    internal_energy,
    inventory,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)

SCHEMA_VERSION = "stage7_p2_hne_limited_interior_coupling_a3_1_v1"
SOURCE_AUTHORITY_GATE_SHA = "d4c1daf4db9c6e367a75d77c6660f417a9aee061"
SOURCE_AUTHORITY_GATE_RUN_ID = 32629047962
PROPERTY_BACKEND_NAME = "surrogate_lco2"
FORMAL_OUTCOME = (
    "P2_A3_1_LIMITED_INTERIOR_HNE_COUPLING_WORKING_VERTICAL_SLICE_"
    "WITH_BOUNDARY_AND_DISCHARGE_AUTHORITY_CLOSED"
)
NEXT_ACTION = "PROCEED_TO_P2_A3_2_CONTROLLED_FINITE_PIPE_HNE_COUPLING"
OUTPUT_FILES = (
    "summary.json",
    "case_summary.csv",
    "pulse_step_history.csv",
    "operator_report.md",
    "manifest.json",
)

FORMAL_STATUS = {
    "implemented": True,
    "limited_interior_hne_hydrodynamic_coupling": True,
    "working_vertical_slice": True,
    "finite_pipeline_hne_coupling": False,
    "boundary_characteristics_authorized": False,
    "critical_discharge_authorized": False,
    "discharge_feedback_authorized": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

IMPLEMENTATION_AUTHORITY = {
    "candidate_pressure_to_dedicated_interior_euler_flux": True,
    "candidate_frozen_c_to_dedicated_interior_rusanov": True,
    "candidate_frozen_c_to_dedicated_interior_cfl": True,
    "existing_production_default_path_modified": False,
    "equilibrium_c_to_solver": False,
    "finite_relaxation_phase_speed_to_solver": False,
    "hne_boundary_characteristics": False,
    "hne_critical_discharge": False,
    "finite_pipe_discharge_feedback": False,
    "design_use": False,
    "production_use": False,
}


class HNELimitedInteriorCouplingError(RuntimeError):
    """Raised when the dedicated P2-A3.1 candidate leaves its authority scope."""


@dataclass(frozen=True)
class InteriorCouplingConfig:
    n_cells: int = 240
    length_m: float = 1.2
    diameter_m: float = 0.05
    cfl: float = 0.25
    pulse_final_time_s: float = 1.2e-3
    pulse_relative_density_amplitude: float = 1.0e-4
    pulse_sigma_m: float = 0.035
    base_pressure_pa: float = 2.5e6
    equilibrium_quality: float = 0.10
    base_velocity_m_s: float = 0.0
    off_equilibrium_quality_offset: float = 0.02

    def __post_init__(self) -> None:
        if self.n_cells < 80 or self.n_cells % 2:
            raise ValueError("n_cells must be even and at least 80")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe geometry must be positive")
        if not 0.0 < self.cfl <= 0.5:
            raise ValueError("focused coupling CFL must be in (0,0.5]")
        if self.pulse_final_time_s <= 0.0 or self.pulse_sigma_m <= 0.0:
            raise ValueError("pulse timing and width must be positive")
        if not 0.0 < self.pulse_relative_density_amplitude <= 1.0e-3:
            raise ValueError("pulse amplitude must remain in the linear range")
        if not 0.02 < self.equilibrium_quality < 0.45:
            raise ValueError("equilibrium quality must be inside the authority domain")
        actual_q = self.equilibrium_quality + self.off_equilibrium_quality_offset
        if not 0.02 < actual_q < 0.45:
            raise ValueError("off-equilibrium quality must remain inside authority domain")


@dataclass(frozen=True)
class CandidateQualityExactRelaxation:
    """Exact transported-quality relaxation for the dedicated candidate path."""

    tau_s: float

    def __post_init__(self) -> None:
        if math.isnan(self.tau_s) or self.tau_s <= 0.0:
            raise ValueError("tau_s must be positive or +inf")

    def _factor(self, dt_s: float) -> float:
        if not math.isfinite(dt_s) or dt_s < 0.0:
            raise HNELimitedInteriorCouplingError("dt must be finite and nonnegative")
        if math.isinf(self.tau_s):
            return 1.0
        ratio = dt_s / self.tau_s
        return 0.0 if ratio >= 745.0 else math.exp(-ratio)

    def apply(self, U: np.ndarray, eos: object, dt: float, t: float) -> np.ndarray:
        del t
        if not isinstance(eos, AcousticCompatibleHNEVerificationEOS):
            raise HNELimitedInteriorCouplingError(
                "relaxation requires AcousticCompatibleHNEVerificationEOS"
            )
        values = np.asarray(U, dtype=float)
        check_physical_state(values, names=["P2-A3.1 relaxation input"])
        if math.isinf(self.tau_s):
            return np.array(values, dtype=float, copy=True)
        rho = np.asarray(values[..., IDX_RHO], dtype=float)
        e = np.asarray(internal_energy(values), dtype=float)
        q = np.asarray(vapor_mass_fraction(values), dtype=float)
        q_eq = np.empty_like(q)
        for index in np.ndindex(q.shape):
            try:
                equilibrium = recover_equilibrium_state(
                    float(rho[index]),
                    float(e[index]),
                )
            except Exception as exc:
                raise HNELimitedInteriorCouplingError(
                    f"equilibrium recovery failed at {index}: {exc}"
                ) from exc
            if not equilibrium.within_claimed_domain:
                raise HNELimitedInteriorCouplingError(
                    f"equilibrium state outside authority domain at {index}"
                )
            q_eq[index] = equilibrium.vapor_mass_fraction
        factor = self._factor(float(dt))
        q_new = q_eq + (q - q_eq) * factor
        if np.any(~np.isfinite(q_new)) or np.any(q_new <= 0.02) or np.any(q_new >= 0.45):
            raise HNELimitedInteriorCouplingError(
                "relaxation left the open acoustic authority domain"
            )
        output = np.array(values, dtype=float, copy=True)
        output[..., IDX_RHO_XV] = rho * q_new
        if not np.array_equal(output[..., :IDX_RHO_XV], values[..., :IDX_RHO_XV]):
            raise HNELimitedInteriorCouplingError(
                "quality relaxation modified hydrodynamic conserved variables"
            )
        eos.primitive_from_conserved(output)
        return output


@dataclass(frozen=True)
class CouplingAnalysis:
    summary: dict[str, object]
    case_rows: tuple[dict[str, object], ...]
    pulse_rows: tuple[dict[str, object], ...]


def _array_sha(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(values, dtype=float).tobytes()
    ).hexdigest()


def _payload_sha(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""

    return {
        "analysis_source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def _source_state(config: InteriorCouplingConfig):
    return state_from_pressure_quality(
        config.base_pressure_pa,
        config.equilibrium_quality,
    )


def _grid(config: InteriorCouplingConfig) -> UniformGrid:
    return UniformGrid(
        PipeGeometry(config.length_m, config.diameter_m),
        config.n_cells,
    )


def _uniform_U(
    config: InteriorCouplingConfig,
    *,
    actual_quality: float,
    velocity_m_s: float | None = None,
) -> np.ndarray:
    source = _source_state(config)
    velocity_value = config.base_velocity_m_s if velocity_m_s is None else velocity_m_s
    return np.asarray(
        make_conserved(
            np.full(config.n_cells, source.rho_kg_m3),
            np.full(config.n_cells, velocity_value),
            np.full(config.n_cells, source.e_j_kg),
            np.full(config.n_cells, actual_quality),
        ),
        dtype=float,
    )


def build_candidate_solver(
    config: InteriorCouplingConfig,
    *,
    actual_quality: float,
    tau_s: float = math.inf,
    no_phase_change: bool = False,
    U: np.ndarray | None = None,
) -> FvmSolver:
    eos = AcousticCompatibleHNEVerificationEOS()
    phase = NoPhaseChange() if no_phase_change else CandidateQualityExactRelaxation(tau_s)
    initial = (
        _uniform_U(config, actual_quality=actual_quality)
        if U is None
        else np.asarray(U, dtype=float)
    )
    return FvmSolver(
        grid=_grid(config),
        eos=eos,
        U=initial,
        cfl=config.cfl,
        phase_change=phase,
        enable_boundary_budget=False,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )


def _inventory_residuals(solver: FvmSolver, initial: Mapping[str, float]) -> dict[str, float]:
    final = inventory(solver.U, solver.grid.dx, solver.grid.geometry.area_m2)
    return {
        "mass_residual_kg": float(final["mass_total"] - initial["mass_total"]),
        "momentum_residual_kg_m_s": float(
            final["momentum_total"] - initial["momentum_total"]
        ),
        "energy_residual_J": float(final["energy_total"] - initial["energy_total"]),
    }


def _run_uniform_case(config: InteriorCouplingConfig) -> dict[str, object]:
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    solver = build_candidate_solver(
        config,
        actual_quality=actual_q,
        tau_s=math.inf,
    )
    initial_U = solver.U.copy()
    primitive = solver.primitive()
    candidate = solver.eos.evaluate(
        float(initial_U[0, IDX_RHO]),
        float(internal_energy(initial_U)[0]),
        actual_q,
    )
    expected_dt = config.cfl * solver.grid.dx / (
        abs(config.base_velocity_m_s) + candidate.frozen_c_m_s
    )
    computed_dt = float(solver.compute_dt())

    observations: list[RusanovFluxEvaluation] = []
    with observe_rusanov_flux(observations.append):
        solver._base_fluxes()
    if len(observations) != 1:
        raise HNELimitedInteriorCouplingError("expected one vectorized Rusanov evaluation")
    observed_smax = np.asarray(observations[0].maximum_wave_speed, dtype=float)
    expected_smax = abs(config.base_velocity_m_s) + candidate.frozen_c_m_s

    for _ in range(6):
        dt = float(solver.compute_dt())
        solver.step(dt)
    return {
        "case_id": "UNIFORM_NONEQUILIBRIUM_INTERIOR_COUPLING",
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "actual_quality": actual_q,
        "candidate_pressure_pa": candidate.pressure_pa,
        "candidate_frozen_c_m_s": candidate.frozen_c_m_s,
        "primitive_pressure_matches_candidate": bool(
            np.allclose(primitive.p, candidate.pressure_pa, rtol=0.0, atol=0.0)
        ),
        "primitive_c_matches_candidate_frozen_c": bool(
            np.allclose(primitive.c, candidate.frozen_c_m_s, rtol=0.0, atol=0.0)
        ),
        "cfl_dt_matches_candidate_frozen_c": abs(computed_dt - expected_dt)
        <= 8.0 * np.finfo(float).eps * max(abs(expected_dt), 1.0),
        "rusanov_smax_matches_candidate_frozen_c": bool(
            np.allclose(observed_smax, expected_smax, rtol=0.0, atol=1.0e-12)
        ),
        "uniform_state_bitwise_preserved": np.array_equal(solver.U, initial_U),
        "solver_step_count": solver.step_count,
    }


def _run_frozen_limit_case(config: InteriorCouplingConfig) -> dict[str, object]:
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    candidate = build_candidate_solver(config, actual_quality=actual_q, tau_s=math.inf)
    reference = build_candidate_solver(
        config,
        actual_quality=actual_q,
        no_phase_change=True,
    )
    trajectory_equal = True
    for _ in range(6):
        dt_candidate = float(candidate.compute_dt())
        dt_reference = float(reference.compute_dt())
        if dt_candidate != dt_reference:
            trajectory_equal = False
            break
        candidate.step(dt_candidate)
        reference.step(dt_reference)
        if not np.array_equal(candidate.U, reference.U):
            trajectory_equal = False
            break
    return {
        "case_id": "TAU_INFINITY_FROZEN_LIMIT",
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "actual_quality": actual_q,
        "trajectory_bitwise_equal_to_no_phase_change": trajectory_equal,
        "candidate_final_state_sha256": _array_sha(candidate.U),
        "reference_final_state_sha256": _array_sha(reference.U),
        "solver_step_count": candidate.step_count,
    }


def _run_equilibrium_limit_case(config: InteriorCouplingConfig) -> dict[str, object]:
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    solver = build_candidate_solver(config, actual_quality=actual_q, tau_s=1.0e-18)
    initial_hydrodynamic_sha = _array_sha(solver.U[..., :IDX_RHO_XV])
    dt = float(solver.compute_dt())
    solver.step(dt)
    final_q = np.asarray(vapor_mass_fraction(solver.U), dtype=float)
    source = _source_state(config)
    equilibrium_q_error = float(np.max(np.abs(final_q - source.vapor_mass_fraction)))
    final_hydrodynamic_sha = _array_sha(solver.U[..., :IDX_RHO_XV])
    primitive = solver.primitive()
    equilibrium = recover_equilibrium_state(
        float(solver.U[0, IDX_RHO]),
        float(internal_energy(solver.U)[0]),
    )
    return {
        "case_id": "TAU_NEAR_ZERO_EQUILIBRIUM_LIMIT",
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "initial_actual_quality": actual_q,
        "final_quality": float(final_q[0]),
        "equilibrium_quality": source.vapor_mass_fraction,
        "maximum_equilibrium_quality_error": equilibrium_q_error,
        "hydrodynamic_state_unchanged_by_uniform_step_and_relaxation": (
            initial_hydrodynamic_sha == final_hydrodynamic_sha
        ),
        "candidate_pressure_recovers_equilibrium_pressure": abs(
            float(primitive.p[0]) - equilibrium.pressure_pa
        ) <= 5.0e-4,
        "candidate_temperature_recovers_equilibrium_temperature": abs(
            float(primitive.T[0]) - equilibrium.temperature_K
        ) <= 2.0e-9,
        "solver_step_count": solver.step_count,
    }


def _pulse_initial_U(config: InteriorCouplingConfig) -> np.ndarray:
    source = _source_state(config)
    grid = _grid(config)
    x0 = 0.5 * config.length_m
    gaussian = np.exp(-0.5 * ((grid.cell_centers - x0) / config.pulse_sigma_m) ** 2)
    rho = source.rho_kg_m3 * (
        1.0 + config.pulse_relative_density_amplitude * gaussian
    )
    return np.asarray(
        make_conserved(
            rho,
            np.full(config.n_cells, config.base_velocity_m_s),
            np.full(config.n_cells, source.e_j_kg),
            np.full(config.n_cells, config.equilibrium_quality),
        ),
        dtype=float,
    )


def _weighted_centroid(x: np.ndarray, weight: np.ndarray) -> float:
    total = float(np.sum(weight))
    if total <= 0.0 or not math.isfinite(total):
        raise HNELimitedInteriorCouplingError("pulse centroid has no positive weight")
    return float(np.sum(x * weight) / total)


def _run_pulse_case(
    config: InteriorCouplingConfig,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    initial_U = _pulse_initial_U(config)
    solver = build_candidate_solver(
        config,
        actual_quality=config.equilibrium_quality,
        tau_s=math.inf,
        U=initial_U,
    )
    source = _source_state(config)
    candidate = solver.eos.evaluate(
        source.rho_kg_m3,
        source.e_j_kg,
        source.vapor_mass_fraction,
    )
    initial_inventory = inventory(
        solver.U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    x = np.asarray(solver.grid.cell_centers, dtype=float)
    x0 = 0.5 * config.length_m
    history: list[dict[str, object]] = []

    def record() -> None:
        primitive = solver.primitive()
        history.append(
            {
                "step": solver.step_count,
                "time_s": float(solver.t),
                "minimum_pressure_pa": float(np.min(primitive.p)),
                "maximum_pressure_pa": float(np.max(primitive.p)),
                "minimum_frozen_c_m_s": float(np.min(primitive.c)),
                "maximum_frozen_c_m_s": float(np.max(primitive.c)),
                **_inventory_residuals(solver, initial_inventory),
            }
        )

    record()
    while solver.t < config.pulse_final_time_s:
        dt = float(solver.compute_dt(config.pulse_final_time_s))
        if dt <= 0.0:
            break
        solver.step(dt)
        record()

    primitive = solver.primitive()
    positive_pressure = np.maximum(np.asarray(primitive.p) - source.pressure_pa, 0.0)
    left_mask = x < x0
    right_mask = x > x0
    left_centroid = _weighted_centroid(x[left_mask], positive_pressure[left_mask])
    right_centroid = _weighted_centroid(x[right_mask], positive_pressure[right_mask])
    left_speed = (x0 - left_centroid) / solver.t
    right_speed = (right_centroid - x0) / solver.t
    measured_speed = 0.5 * (left_speed + right_speed)
    relative_speed_error = abs(measured_speed - candidate.frozen_c_m_s) / candidate.frozen_c_m_s
    residuals = _inventory_residuals(solver, initial_inventory)
    return (
        {
            "case_id": "SMALL_AMPLITUDE_PRESSURE_PULSE",
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "expected_frozen_wave_speed_m_s": candidate.frozen_c_m_s,
            "measured_left_wave_speed_m_s": left_speed,
            "measured_right_wave_speed_m_s": right_speed,
            "measured_mean_wave_speed_m_s": measured_speed,
            "relative_wave_speed_error": relative_speed_error,
            "wave_speed_within_focused_tolerance": relative_speed_error <= 0.20,
            "left_right_speed_symmetry_relative_error": abs(left_speed - right_speed)
            / candidate.frozen_c_m_s,
            "pulse_remained_inside_domain": (
                left_centroid > 0.1 * config.length_m
                and right_centroid < 0.9 * config.length_m
            ),
            "final_time_s": solver.t,
            "solver_step_count": solver.step_count,
            **residuals,
        },
        tuple(history),
    )


def analyze_limited_interior_coupling(
    config: InteriorCouplingConfig | None = None,
) -> CouplingAnalysis:
    cfg = config or InteriorCouplingConfig()
    authority_summary, _, _ = analyze_acoustic_authority_gate()
    authority_green = bool(authority_summary["acoustic_authority_gate_passed"])
    authority_grant = authority_summary["effective_authority_grant"]
    if not isinstance(authority_grant, Mapping):
        raise HNELimitedInteriorCouplingError("authority grant is not a mapping")

    uniform = _run_uniform_case(cfg)
    frozen = _run_frozen_limit_case(cfg)
    equilibrium = _run_equilibrium_limit_case(cfg)
    pulse, pulse_rows = _run_pulse_case(cfg)
    cases = [uniform, frozen, equilibrium, pulse]

    pulse_conservation_scale = max(
        abs(float(pulse["mass_residual_kg"])),
        abs(float(pulse["momentum_residual_kg_m_s"])),
        abs(float(pulse["energy_residual_J"])),
    )
    gates = {
        "AUTHORITY_GATE_SOURCE_PINNED_AND_GREEN": (
            SOURCE_AUTHORITY_GATE_SHA
            == "d4c1daf4db9c6e367a75d77c6660f417a9aee061"
            and SOURCE_AUTHORITY_GATE_RUN_ID == 32629047962
            and authority_green
        ),
        "AUTHORITY_GRANT_COVERS_ONLY_DEDICATED_INTERIOR_IMPLEMENTATION": (
            authority_grant[
                "candidate_pressure_to_interior_euler_flux_in_p2_a3_1"
            ]
            and authority_grant[
                "candidate_frozen_c_to_interior_rusanov_in_p2_a3_1"
            ]
            and authority_grant[
                "candidate_frozen_c_to_interior_cfl_in_p2_a3_1"
            ]
            and all(
                authority_grant[key] is False
                for key in (
                    "equilibrium_c_to_solver",
                    "finite_relaxation_phase_speed_to_solver",
                    "hne_boundary_characteristics",
                    "hne_critical_discharge",
                    "finite_pipe_discharge_feedback",
                    "design_use",
                    "production_use",
                )
            )
        ),
        "CANDIDATE_PRESSURE_ACTIVE_IN_DEDICATED_INTERIOR_FLUX": uniform[
            "primitive_pressure_matches_candidate"
        ],
        "CANDIDATE_FROZEN_C_ACTIVE_IN_DEDICATED_RUSANOV": uniform[
            "rusanov_smax_matches_candidate_frozen_c"
        ],
        "CANDIDATE_FROZEN_C_ACTIVE_IN_DEDICATED_CFL": uniform[
            "cfl_dt_matches_candidate_frozen_c"
        ],
        "UNIFORM_NONEQUILIBRIUM_STATE_PRESERVED": uniform[
            "uniform_state_bitwise_preserved"
        ],
        "TAU_INFINITY_RECOVERS_FROZEN_NO_SOURCE_LIMIT": frozen[
            "trajectory_bitwise_equal_to_no_phase_change"
        ],
        "TAU_NEAR_ZERO_RECOVERS_A2_4_2R_EQUILIBRIUM_LIMIT": (
            float(equilibrium["maximum_equilibrium_quality_error"]) <= 1.0e-15
            and equilibrium[
                "hydrodynamic_state_unchanged_by_uniform_step_and_relaxation"
            ]
            and equilibrium["candidate_pressure_recovers_equilibrium_pressure"]
            and equilibrium["candidate_temperature_recovers_equilibrium_temperature"]
        ),
        "SMALL_AMPLITUDE_WAVE_PROPAGATES_AT_FROZEN_SPEED": pulse[
            "wave_speed_within_focused_tolerance"
        ],
        "SMALL_AMPLITUDE_LEFT_RIGHT_WAVES_REMAIN_SYMMETRIC": float(
            pulse["left_right_speed_symmetry_relative_error"]
        ) <= 0.05,
        "PULSE_REMAINS_INTERIOR_AND_BOUNDARY_AUTHORITY_UNUSED": pulse[
            "pulse_remained_inside_domain"
        ],
        "PULSE_GLOBAL_CONSERVATION_WITHIN_FOCUSED_ROUNDOFF_BAND": (
            pulse_conservation_scale <= 1.0e-8
        ),
        "EXISTING_PRODUCTION_DEFAULT_PATH_UNCHANGED": (
            IMPLEMENTATION_AUTHORITY["existing_production_default_path_modified"]
            is False
        ),
        "BOUNDARY_DISCHARGE_AND_PRODUCTION_AUTHORITY_REMAIN_CLOSED": all(
            IMPLEMENTATION_AUTHORITY[key] is False
            for key in (
                "equilibrium_c_to_solver",
                "finite_relaxation_phase_speed_to_solver",
                "hne_boundary_characteristics",
                "hne_critical_discharge",
                "finite_pipe_discharge_feedback",
                "design_use",
                "production_use",
            )
        ),
    }
    failed = [name for name, passed in gates.items() if not passed]
    ready = not failed
    effective_status = dict(FORMAL_STATUS)
    effective_status["working_vertical_slice"] = ready
    effective_status["limited_interior_hne_hydrodynamic_coupling"] = ready
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "p2_a3_1_limited_dedicated_interior_hne_hydrodynamic_coupling",
        "source_acoustic_authority_gate": {
            "head_sha": SOURCE_AUTHORITY_GATE_SHA,
            "workflow_run_id": SOURCE_AUTHORITY_GATE_RUN_ID,
            "formal_outcome": authority_summary["formal_outcome"],
        },
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "configuration": asdict(cfg),
        "implementation_authority": dict(IMPLEMENTATION_AUTHORITY),
        "formal_status": effective_status,
        "formal_outcome": (
            FORMAL_OUTCOME
            if ready
            else "P2_A3_1_IMPLEMENTED_NOT_GREEN_WITH_FAIL_CLOSED_GATES"
        ),
        "next_action": (
            NEXT_ACTION
            if ready
            else "RESOLVE_FAILED_P2_A3_1_GATES_BEFORE_FINITE_PIPE_COUPLING"
        ),
        "case_summary": cases,
        "gate_results": gates,
        "failed_gates": failed,
        "p2_a3_1_limited_interior_coupling_ready": ready,
        "existing_production_default_path_modified": False,
        "boundary_characteristics_authorized": False,
        "critical_discharge_authorized": False,
        "discharge_feedback_authorized": False,
        "physically_validated": False,
        "runtime_provenance": _provenance(),
        "limitations": [
            "VERIFICATION_SURROGATE_NOT_REAL_CO2_PREDICTION",
            "TRANSMISSIVE_BOUNDARIES_USED_ONLY_TO_ISOLATE_INTERIOR_BEHAVIOR",
            "NO_HNE_BOUNDARY_CHARACTERISTIC_AUTHORITY",
            "NO_CRITICAL_DISCHARGE_OR_FINITE_PIPE_FEEDBACK",
            "TAU_NOT_PHYSICALLY_CALIBRATED",
        ],
    }
    authority_payload = {
        key: value
        for key, value in summary.items()
        if key not in {"runtime_provenance", "case_summary"}
    }
    summary["analysis_sha256"] = _payload_sha(
        {
            "authority": authority_payload,
            "cases": cases,
            "pulse_history": pulse_rows,
        }
    )
    return CouplingAnalysis(summary, tuple(cases), pulse_rows)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise HNELimitedInteriorCouplingError("CSV requires rows")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        json.dumps(value, sort_keys=True, separators=(",", ":"))
                        if isinstance(value, (dict, list, tuple))
                        else value
                    )
                    for key, value in row.items()
                }
            )


def _report(summary: Mapping[str, object]) -> str:
    ready = bool(summary["p2_a3_1_limited_interior_coupling_ready"])
    lines = [
        "# Stage 7 P2-A3.1 Limited Interior HNE Coupling",
        "",
        f"- Outcome: `{summary['formal_outcome']}`",
        f"- Property backend: `{summary['property_backend_name']}`",
        f"- Next action: `{summary['next_action']}`",
        "- Existing production/default path modified: `false`",
        "- Boundary, critical-discharge, and discharge-feedback authority: `false`",
        "",
        "| case | key result | value |",
        "|---|---|---:|",
    ]
    for row in summary["case_summary"]:  # type: ignore[index]
        case_id = row["case_id"]
        if case_id == "UNIFORM_NONEQUILIBRIUM_INTERIOR_COUPLING":
            key = "frozen c [m/s]"
            value = row["candidate_frozen_c_m_s"]
        elif case_id == "TAU_INFINITY_FROZEN_LIMIT":
            key = "bitwise frozen-limit match"
            value = row["trajectory_bitwise_equal_to_no_phase_change"]
        elif case_id == "TAU_NEAR_ZERO_EQUILIBRIUM_LIMIT":
            key = "max |q-qeq|"
            value = row["maximum_equilibrium_quality_error"]
        else:
            key = "relative wave-speed error"
            value = row["relative_wave_speed_error"]
        lines.append(f"| {case_id} | {key} | {value} |")
    lines.append("")
    if ready:
        lines.append(
            "The dedicated interior candidate is a working verification vertical slice. "
            "Proceed only to controlled finite-pipe HNE coupling; keep all boundary and "
            "discharge authority closed."
        )
    else:
        lines.append("STOP: P2-A3.1 gates failed; do not proceed to finite-pipe coupling.")
        lines.extend(f"- `{gate}`" for gate in summary["failed_gates"])  # type: ignore[index]
    lines.append("")
    return "\n".join(lines)


def write_artifacts(
    output_dir: str | Path,
    analysis: CouplingAnalysis,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    unexpected = {path.name for path in target.iterdir() if path.is_file()} - expected
    if unexpected:
        raise HNELimitedInteriorCouplingError(
            f"unexpected output files: {sorted(unexpected)}"
        )
    paths = {
        "summary": target / "summary.json",
        "cases": target / "case_summary.csv",
        "pulse": target / "pulse_step_history.csv",
        "report": target / "operator_report.md",
        "manifest": target / "manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(analysis.summary, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["cases"], analysis.case_rows)
    _write_csv(paths["pulse"], analysis.pulse_rows)
    paths["report"].write_text(_report(analysis.summary), encoding="utf-8")
    payload = {key: path for key, path in paths.items() if key != "manifest"}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "analysis_sha256": analysis.summary["analysis_sha256"],
        "p2_a3_1_limited_interior_coupling_ready": analysis.summary[
            "p2_a3_1_limited_interior_coupling_ready"
        ],
        "existing_production_default_path_modified": False,
        "boundary_characteristics_authorized": False,
        "critical_discharge_authorized": False,
        "discharge_feedback_authorized": False,
        "payload_files": {
            path.name: {
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha(path),
            }
            for path in payload.values()
        },
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise HNELimitedInteriorCouplingError(
            f"artifact envelope mismatch: {sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    analysis = analyze_limited_interior_coupling()
    paths = write_artifacts(output_dir, analysis)
    return {
        **analysis.summary,
        "artifact_paths": {key: str(path) for key, path in paths.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    result = execute(parser.parse_args(argv).output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["p2_a3_1_limited_interior_coupling_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())