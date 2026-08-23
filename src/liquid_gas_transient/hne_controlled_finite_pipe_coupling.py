"""P2-A3.2 controlled finite-pipe HNE hydrodynamic coupling.

This module extends the green P2-A3.1 dedicated interior candidate into one
narrow finite-pipe verification harness.  It uses a reflective left end and a
prescribed right ghost state following a controlled pressure ramp.  The right
boundary is deliberately *not* an HNE characteristic boundary, critical-flow
law, rupture model, or physical discharge model.

The existing production/default EOS, flux, CFL, Rusanov, boundary, and
discharge paths are not modified.
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

from .boundary import LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .flux import RusanovFluxEvaluation, observe_rusanov_flux
from .grid import UniformGrid
from .hne_acoustic_authority_types import AcousticCompatibleHNEVerificationEOS
from .hne_equilibrium_acoustic_closure import (
    DEFAULT_CONFIG,
    recover_equilibrium_state,
    state_from_pressure_quality,
)
from .hne_limited_interior_coupling_facade import (
    CandidateQualityExactRelaxation,
    analyze_limited_interior_coupling,
)
from .solver import FvmSolver
from .state import (
    IDX_RHO,
    check_physical_state,
    internal_energy,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)

SCHEMA_VERSION = "stage7_p2_hne_controlled_finite_pipe_coupling_a3_2_v1"
SOURCE_A3_1_SHA = "d4db09a6447ba4c98fcf0618e37e3ad6fe859ec1"
SOURCE_A3_1_WORKFLOW_RUN_ID = 32638595911
SOURCE_A3_1_JOB_ID = 97192025339
SOURCE_A3_1_ARTIFACT_ID = 9493006871
SOURCE_A3_1_ARTIFACT_DIGEST = (
    "sha256:21fbde78e47b271d12061dd8c2be67a2128f44645aa6434fe487d50b16d6d423"
)
PROPERTY_BACKEND_NAME = "surrogate_lco2"
BOUNDARY_MODEL_NAME = "prescribed_verification_ghost_state_pressure_ramp"
PRESCRIBED_PRESSURE_RECOVERY_TOLERANCE_PA = 5.0e-4
CONTROLLED_CONDITION_ID = "A3_2_P32_TO_P26_Q012_FINITE_PIPE_RAMP"
FORMAL_OUTCOME = (
    "P2_A3_2_CONTROLLED_FINITE_PIPE_HNE_HYDRODYNAMIC_COUPLING_"
    "WORKING_VERTICAL_SLICE_WITH_PHYSICAL_DISCHARGE_AUTHORITY_CLOSED"
)
NEXT_ACTION = (
    "PROCEED_TO_U3_PHYSICAL_DISCHARGE_COUPLING_AS_A_SEPARATE_CONTROLLED_INCREMENT"
)
OUTPUT_FILES = (
    "summary.json",
    "case_summary.csv",
    "probe_history.csv",
    "step_history.csv",
    "operator_report.md",
    "manifest.json",
)

FORMAL_STATUS = {
    "implemented": True,
    "working_verification_slice": False,
    "working_vertical_slice": False,
    "controlled_finite_pipe_hne_hydrodynamic_coupling": False,
    "limited_interior_hne_hydrodynamic_coupling": True,
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
    "prescribed_verification_ghost_state_pressure_ramp": True,
    "existing_production_default_path_modified": False,
    "equilibrium_c_to_solver": False,
    "finite_relaxation_phase_speed_to_solver": False,
    "hne_boundary_characteristics": False,
    "hne_critical_discharge": False,
    "physical_discharge_model": False,
    "rupture_model": False,
    "design_use": False,
    "production_use": False,
}

CASE_DEFINITIONS = (
    ("TAU_NEAR_ZERO_HEM_LIMIT", "near_zero", "near_zero_tau_s"),
    ("TAU_FINITE_HNE", "finite", "finite_tau_s"),
    ("TAU_INFINITY_FROZEN_LIMIT", "frozen", None),
)


class HNEControlledFinitePipeCouplingError(RuntimeError):
    """Raised when the dedicated A3.2 harness leaves its declared scope."""


@dataclass(frozen=True)
class ControlledFinitePipeConfig:
    """Focused finite-pipe pressure-ramp configuration for P2-A3.2."""

    n_cells: int = 64
    length_m: float = 1.2
    diameter_m: float = 0.05
    cfl: float = 0.25
    initial_pressure_pa: float = 3.2e6
    final_boundary_pressure_pa: float = 2.6e6
    initial_equilibrium_quality: float = 0.12
    ramp_start_s: float = 2.0e-4
    ramp_duration_s: float = 1.2e-3
    final_time_s: float = 7.0e-3
    finite_tau_s: float = 8.0e-4
    near_zero_tau_s: float = 1.0e-18
    probe_fractions: tuple[float, ...] = (0.25, 0.50, 0.75)
    arrival_pressure_drop_pa: float = 250.0
    probe_sample_stride: int = 4
    max_steps: int = 4000

    def __post_init__(self) -> None:
        if self.n_cells < 32:
            raise ValueError("n_cells must be at least 32")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe geometry must be positive")
        if not 0.0 < self.cfl <= 0.5:
            raise ValueError("focused A3.2 CFL must be in (0, 0.5]")
        if not (
            DEFAULT_CONFIG.claimed_pressure_min_pa
            < self.final_boundary_pressure_pa
            < self.initial_pressure_pa
            < DEFAULT_CONFIG.claimed_pressure_max_pa
        ):
            raise ValueError(
                "controlled pressure ramp must remain inside the open authority domain"
            )
        if not (
            DEFAULT_CONFIG.claimed_quality_min
            < self.initial_equilibrium_quality
            < DEFAULT_CONFIG.claimed_quality_max
        ):
            raise ValueError("initial quality must remain in the open authority domain")
        if self.ramp_start_s < 0.0 or self.ramp_duration_s <= 0.0:
            raise ValueError("ramp start must be nonnegative and duration positive")
        if self.final_time_s <= self.ramp_start_s + self.ramp_duration_s:
            raise ValueError("final_time_s must extend beyond the pressure ramp")
        if not math.isfinite(self.finite_tau_s) or self.finite_tau_s <= 0.0:
            raise ValueError("finite_tau_s must be finite and positive")
        if not math.isfinite(self.near_zero_tau_s) or self.near_zero_tau_s <= 0.0:
            raise ValueError("near_zero_tau_s must be finite and positive")
        if not self.probe_fractions:
            raise ValueError("at least one probe is required")
        if any(not 0.0 < value < 1.0 for value in self.probe_fractions):
            raise ValueError("probe fractions must lie in (0,1)")
        if tuple(sorted(set(self.probe_fractions))) != self.probe_fractions:
            raise ValueError("probe fractions must be unique and ascending")
        if self.arrival_pressure_drop_pa <= 0.0:
            raise ValueError("arrival pressure-drop threshold must be positive")
        if self.arrival_pressure_drop_pa >= (
            self.initial_pressure_pa - self.final_boundary_pressure_pa
        ):
            raise ValueError("arrival threshold must be smaller than the imposed drop")
        if self.probe_sample_stride <= 0 or self.max_steps <= 0:
            raise ValueError("sampling stride and max_steps must be positive")

        for pressure in (
            self.initial_pressure_pa,
            self.final_boundary_pressure_pa,
        ):
            state = state_from_pressure_quality(
                pressure,
                self.initial_equilibrium_quality,
            )
            if not state.within_claimed_domain:
                raise ValueError("endpoint state is outside the claimed authority domain")

    @property
    def ramp_end_s(self) -> float:
        return float(self.ramp_start_s + self.ramp_duration_s)

    @property
    def imposed_pressure_drop_pa(self) -> float:
        return float(self.initial_pressure_pa - self.final_boundary_pressure_pa)


@dataclass(frozen=True)
class PrescribedHNEPressureRampOutlet:
    """Right-side prescribed verification ghost state for a pressure ramp.

    This boundary constructs an equilibrium-manifold ghost state at a prescribed
    pressure and quality and copies the adjacent interior velocity.  It is only
    a deterministic external excitation for the A3.2 verification harness.
    It does not solve HNE characteristics or a physical discharge law.
    """

    pressure_schedule: LinearPressureRamp
    prescribed_quality: float

    def __post_init__(self) -> None:
        if not (
            DEFAULT_CONFIG.claimed_quality_min
            < self.prescribed_quality
            < DEFAULT_CONFIG.claimed_quality_max
        ):
            raise ValueError("prescribed boundary quality is outside authority scope")
        for pressure in (
            self.pressure_schedule.p_initial_pa,
            self.pressure_schedule.p_final_pa,
        ):
            state = state_from_pressure_quality(pressure, self.prescribed_quality)
            if not state.within_claimed_domain:
                raise ValueError("prescribed boundary endpoint is outside authority scope")

    def pressure_pa(self, t: float) -> float:
        pressure = float(self.pressure_schedule.pressure_pa(t))
        if not math.isfinite(pressure):
            raise HNEControlledFinitePipeCouplingError(
                "prescribed pressure schedule returned a nonfinite value"
            )
        return pressure

    def apply(
        self,
        U_ext: np.ndarray,
        n_ghost: int,
        side: str,
        t: float,
        eos: object,
    ) -> None:
        if side != "right":
            raise NotImplementedError(
                "PrescribedHNEPressureRampOutlet is right-boundary only"
            )
        if not isinstance(eos, AcousticCompatibleHNEVerificationEOS):
            raise HNEControlledFinitePipeCouplingError(
                "prescribed HNE ghost state requires the verification EOS"
            )
        if n_ghost <= 0:
            raise ValueError("n_ghost must be positive")

        pressure = self.pressure_pa(t)
        state = state_from_pressure_quality(pressure, self.prescribed_quality)
        if not state.within_claimed_domain:
            raise HNEControlledFinitePipeCouplingError(
                "prescribed ghost state left the open authority domain"
            )
        interior = np.asarray(U_ext[-n_ghost - 1], dtype=float)
        interior_velocity = float(interior[1] / interior[IDX_RHO])
        ghost = np.asarray(
            make_conserved(
                state.rho_kg_m3,
                interior_velocity,
                state.e_j_kg,
                self.prescribed_quality,
            ),
            dtype=float,
        )
        candidate = eos.evaluate(
            state.rho_kg_m3,
            state.e_j_kg,
            self.prescribed_quality,
        )
        tolerance = max(
            PRESCRIBED_PRESSURE_RECOVERY_TOLERANCE_PA,
            32.0 * abs(float(np.spacing(max(abs(pressure), 1.0)))),
        )
        if abs(candidate.pressure_pa - pressure) > tolerance:
            raise HNEControlledFinitePipeCouplingError(
                "candidate EOS did not recover prescribed ghost pressure"
            )
        for offset in range(n_ghost):
            U_ext[-offset - 1] = ghost

    def diagnostics(self, t: float) -> dict[str, object]:
        return {
            "boundary_model": BOUNDARY_MODEL_NAME,
            "prescribed_pressure_pa": self.pressure_pa(t),
            "prescribed_quality": float(self.prescribed_quality),
            "hne_characteristic_boundary": False,
            "critical_discharge_law": False,
            "physical_discharge_model": False,
        }


@dataclass(frozen=True)
class ControlledCaseRun:
    case_row: dict[str, object]
    step_rows: tuple[dict[str, object], ...]
    probe_rows: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class ControlledFinitePipeAnalysis:
    summary: dict[str, object]
    case_rows: tuple[dict[str, object], ...]
    probe_rows: tuple[dict[str, object], ...]
    step_rows: tuple[dict[str, object], ...]


def _json_native(value: object) -> object:
    """Recursively convert NumPy containers and scalars to strict JSON values."""

    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return _json_native(value.tolist())
    if isinstance(value, dict):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    return value


def _payload_sha(value: object) -> str:
    raw = json.dumps(
        _json_native(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _array_sha(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(values, dtype=float).tobytes()
    ).hexdigest()


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


def pressure_ramp_fraction(t_s: float, config: ControlledFinitePipeConfig) -> float:
    if t_s < config.ramp_start_s:
        return 0.0
    return float(
        np.clip(
            (t_s - config.ramp_start_s) / config.ramp_duration_s,
            0.0,
            1.0,
        )
    )


def requested_boundary_pressure_pa(
    t_s: float,
    config: ControlledFinitePipeConfig,
) -> float:
    fraction = pressure_ramp_fraction(t_s, config)
    return float(
        config.initial_pressure_pa
        + fraction
        * (config.final_boundary_pressure_pa - config.initial_pressure_pa)
    )


def schedule_pressure_tolerance_pa(config: ControlledFinitePipeConfig) -> float:
    scale = max(
        abs(config.initial_pressure_pa),
        abs(config.final_boundary_pressure_pa),
        1.0,
    )
    return float(32.0 * abs(np.spacing(scale)))


def _grid(config: ControlledFinitePipeConfig) -> UniformGrid:
    return UniformGrid(
        PipeGeometry(config.length_m, config.diameter_m),
        config.n_cells,
    )


def _initial_state(config: ControlledFinitePipeConfig) -> np.ndarray:
    state = state_from_pressure_quality(
        config.initial_pressure_pa,
        config.initial_equilibrium_quality,
    )
    if not state.within_claimed_domain:
        raise HNEControlledFinitePipeCouplingError(
            "initial state is outside the authority domain"
        )
    return np.asarray(
        make_conserved(
            np.full(config.n_cells, state.rho_kg_m3),
            np.zeros(config.n_cells),
            np.full(config.n_cells, state.e_j_kg),
            np.full(config.n_cells, state.vapor_mass_fraction),
        ),
        dtype=float,
    )


def build_controlled_finite_pipe_solver(
    config: ControlledFinitePipeConfig | None = None,
    *,
    tau_s: float | None,
) -> tuple[FvmSolver, PrescribedHNEPressureRampOutlet]:
    """Build the dedicated finite-pipe candidate without modifying defaults."""

    cfg = config or ControlledFinitePipeConfig()
    relaxation_tau = math.inf if tau_s is None else float(tau_s)
    schedule = LinearPressureRamp(
        p_initial_pa=cfg.initial_pressure_pa,
        p_final_pa=cfg.final_boundary_pressure_pa,
        t_start_s=cfg.ramp_start_s,
        duration_s=cfg.ramp_duration_s,
    )
    right_boundary = PrescribedHNEPressureRampOutlet(
        pressure_schedule=schedule,
        prescribed_quality=cfg.initial_equilibrium_quality,
    )
    solver = FvmSolver(
        grid=_grid(cfg),
        eos=AcousticCompatibleHNEVerificationEOS(),
        U=_initial_state(cfg),
        cfl=cfg.cfl,
        left_boundary=ReflectiveBoundary(),
        right_boundary=right_boundary,
        phase_change=CandidateQualityExactRelaxation(relaxation_tau),
        enable_boundary_budget=True,
        enable_phase_budget=True,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    return solver, right_boundary


def _probe_name(fraction: float) -> str:
    return f"x_over_L_{fraction:.2f}".replace(".", "_")


def _probe_specs(
    config: ControlledFinitePipeConfig,
    solver: FvmSolver,
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for fraction in config.probe_fractions:
        target = fraction * config.length_m
        index = int(np.argmin(np.abs(solver.grid.cell_centers - target)))
        rows.append(
            {
                "probe_name": _probe_name(fraction),
                "probe_fraction": float(fraction),
                "probe_target_x_m": float(target),
                "probe_cell_index": index,
                "probe_cell_center_x_m": float(solver.grid.cell_centers[index]),
            }
        )
    return tuple(rows)


def _observe_state(solver: FvmSolver) -> dict[str, object]:
    values = np.asarray(solver.U, dtype=float)
    check_physical_state(values, names=["P2-A3.2 accepted state"])
    primitive = solver.primitive()
    rho = np.asarray(values[..., IDX_RHO], dtype=float)
    e = np.asarray(internal_energy(values), dtype=float)
    q_actual = np.asarray(vapor_mass_fraction(values), dtype=float)
    q_equilibrium = np.empty_like(q_actual)
    p_equilibrium = np.empty_like(q_actual)
    for index in np.ndindex(q_actual.shape):
        try:
            equilibrium = recover_equilibrium_state(
                float(rho[index]),
                float(e[index]),
            )
        except Exception as exc:
            raise HNEControlledFinitePipeCouplingError(
                f"equilibrium recovery failed at {index}: {exc}"
            ) from exc
        if not equilibrium.within_claimed_domain:
            raise HNEControlledFinitePipeCouplingError(
                f"equilibrium state outside authority domain at {index}"
            )
        q_equilibrium[index] = equilibrium.vapor_mass_fraction
        p_equilibrium[index] = equilibrium.pressure_pa

    p_hne = np.asarray(primitive.p, dtype=float)
    c_frozen = np.asarray(primitive.c, dtype=float)
    alpha = np.asarray(primitive.alpha, dtype=float)
    temperature = np.asarray(primitive.T, dtype=float)
    speed = np.asarray(primitive.u, dtype=float)
    q_lag = q_actual - q_equilibrium
    pressure_offset = p_hne - p_equilibrium
    finite = all(
        np.all(np.isfinite(array))
        for array in (
            rho,
            e,
            q_actual,
            q_equilibrium,
            p_hne,
            p_equilibrium,
            c_frozen,
            alpha,
            temperature,
            speed,
        )
    )
    authority_open = bool(
        np.all(q_actual > DEFAULT_CONFIG.claimed_quality_min)
        and np.all(q_actual < DEFAULT_CONFIG.claimed_quality_max)
        and np.all(q_equilibrium > DEFAULT_CONFIG.claimed_quality_min)
        and np.all(q_equilibrium < DEFAULT_CONFIG.claimed_quality_max)
        and np.all(p_hne > DEFAULT_CONFIG.claimed_pressure_min_pa)
        and np.all(p_hne < DEFAULT_CONFIG.claimed_pressure_max_pa)
        and np.all(p_equilibrium > DEFAULT_CONFIG.claimed_pressure_min_pa)
        and np.all(p_equilibrium < DEFAULT_CONFIG.claimed_pressure_max_pa)
    )
    positive = bool(
        np.all(rho > 0.0)
        and np.all(c_frozen > 0.0)
        and np.all(temperature > 0.0)
        and np.all(alpha >= 0.0)
        and np.all(alpha <= 1.0)
    )
    return {
        "rho": rho,
        "e": e,
        "u": speed,
        "q_actual": q_actual,
        "q_equilibrium": q_equilibrium,
        "q_lag": q_lag,
        "p_hne": p_hne,
        "p_equilibrium": p_equilibrium,
        "pressure_offset": pressure_offset,
        "c_frozen": c_frozen,
        "alpha": alpha,
        "temperature": temperature,
        "all_finite": finite,
        "all_positive": positive,
        "authority_open": authority_open,
    }


def _required_budget_diagnostics(solver: FvmSolver, dt_s: float) -> dict[str, float]:
    diagnostics = solver.diagnostics(dt=dt_s)
    required = (
        "budget_mass_residual",
        "budget_mass_relative_residual",
        "budget_momentum_residual",
        "budget_momentum_relative_residual",
        "budget_energy_residual",
        "budget_energy_relative_residual",
        "phase_vapor_mass_source_cumulative_kg",
        "phase_vapor_mass_balance_residual_kg",
        "phase_vapor_mass_balance_relative_residual",
    )
    missing = [key for key in required if key not in diagnostics]
    if missing:
        raise HNEControlledFinitePipeCouplingError(
            f"missing required budget diagnostics: {missing}"
        )
    return {key: float(diagnostics[key]) for key in required}


def _step_row(
    *,
    case_id: str,
    regime: str,
    solver: FvmSolver,
    boundary: PrescribedHNEPressureRampOutlet,
    config: ControlledFinitePipeConfig,
    dt_s: float,
    snapshot: Mapping[str, object],
    budget: Mapping[str, float],
) -> dict[str, object]:
    requested = requested_boundary_pressure_pa(solver.t, config)
    prescribed = boundary.pressure_pa(solver.t)
    return {
        "case_id": case_id,
        "relaxation_regime": regime,
        "controlled_condition_id": CONTROLLED_CONDITION_ID,
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "boundary_model": BOUNDARY_MODEL_NAME,
        "step": int(solver.step_count),
        "time_s": float(solver.t),
        "dt_s": float(dt_s),
        "requested_boundary_pressure_pa": requested,
        "prescribed_boundary_pressure_pa": prescribed,
        "schedule_pressure_error_pa": float(prescribed - requested),
        "minimum_pressure_pa": float(np.min(snapshot["p_hne"])),
        "maximum_pressure_pa": float(np.max(snapshot["p_hne"])),
        "minimum_equilibrium_pressure_pa": float(
            np.min(snapshot["p_equilibrium"])
        ),
        "maximum_equilibrium_pressure_pa": float(
            np.max(snapshot["p_equilibrium"])
        ),
        "minimum_actual_quality": float(np.min(snapshot["q_actual"])),
        "maximum_actual_quality": float(np.max(snapshot["q_actual"])),
        "minimum_equilibrium_quality": float(
            np.min(snapshot["q_equilibrium"])
        ),
        "maximum_equilibrium_quality": float(
            np.max(snapshot["q_equilibrium"])
        ),
        "maximum_absolute_quality_lag": float(
            np.max(np.abs(snapshot["q_lag"]))
        ),
        "maximum_absolute_hne_equilibrium_pressure_offset_pa": float(
            np.max(np.abs(snapshot["pressure_offset"]))
        ),
        "minimum_frozen_c_m_s": float(np.min(snapshot["c_frozen"])),
        "maximum_frozen_c_m_s": float(np.max(snapshot["c_frozen"])),
        "minimum_alpha": float(np.min(snapshot["alpha"])),
        "maximum_alpha": float(np.max(snapshot["alpha"])),
        "minimum_velocity_m_s": float(np.min(snapshot["u"])),
        "maximum_velocity_m_s": float(np.max(snapshot["u"])),
        **budget,
    }


def _probe_rows(
    *,
    case_id: str,
    regime: str,
    solver: FvmSolver,
    config: ControlledFinitePipeConfig,
    probes: Sequence[Mapping[str, object]],
    dt_s: float,
    snapshot: Mapping[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for probe in probes:
        index = int(probe["probe_cell_index"])
        rows.append(
            {
                "case_id": case_id,
                "relaxation_regime": regime,
                "controlled_condition_id": CONTROLLED_CONDITION_ID,
                "property_backend_name": PROPERTY_BACKEND_NAME,
                "boundary_model": BOUNDARY_MODEL_NAME,
                "step": int(solver.step_count),
                "time_s": float(solver.t),
                "dt_s": float(dt_s),
                **probe,
                "pressure_pa": float(snapshot["p_hne"][index]),
                "equilibrium_pressure_pa": float(
                    snapshot["p_equilibrium"][index]
                ),
                "hne_equilibrium_pressure_offset_pa": float(
                    snapshot["pressure_offset"][index]
                ),
                "actual_quality": float(snapshot["q_actual"][index]),
                "equilibrium_quality": float(
                    snapshot["q_equilibrium"][index]
                ),
                "quality_lag": float(snapshot["q_lag"][index]),
                "frozen_c_m_s": float(snapshot["c_frozen"][index]),
                "alpha": float(snapshot["alpha"][index]),
                "temperature_K": float(snapshot["temperature"][index]),
                "density_kg_m3": float(snapshot["rho"][index]),
                "velocity_m_s": float(snapshot["u"][index]),
                "pressure_drop_from_initial_pa": float(
                    config.initial_pressure_pa - snapshot["p_hne"][index]
                ),
            }
        )
    return rows


def _case_tau(
    regime: str,
    config: ControlledFinitePipeConfig,
) -> tuple[float | None, float | None]:
    if regime == "near_zero":
        return config.near_zero_tau_s, config.near_zero_tau_s
    if regime == "finite":
        return config.finite_tau_s, config.finite_tau_s
    if regime == "frozen":
        return None, None
    raise ValueError(f"unknown relaxation regime: {regime}")


def _run_controlled_case(
    case_id: str,
    regime: str,
    config: ControlledFinitePipeConfig,
) -> ControlledCaseRun:
    tau_argument, tau_evidence = _case_tau(regime, config)
    solver, boundary = build_controlled_finite_pipe_solver(
        config,
        tau_s=tau_argument,
    )
    probes = _probe_specs(config, solver)
    arrivals: dict[str, float | None] = {
        str(probe["probe_name"]): None for probe in probes
    }
    step_rows: list[dict[str, object]] = []
    probe_rows: list[dict[str, object]] = []

    extrema = {
        "minimum_pressure_pa": math.inf,
        "maximum_pressure_pa": -math.inf,
        "minimum_actual_quality": math.inf,
        "maximum_actual_quality": -math.inf,
        "minimum_equilibrium_quality": math.inf,
        "maximum_equilibrium_quality": -math.inf,
        "minimum_frozen_c_m_s": math.inf,
        "maximum_frozen_c_m_s": -math.inf,
        "minimum_alpha": math.inf,
        "maximum_alpha": -math.inf,
        "maximum_absolute_quality_lag": 0.0,
        "maximum_absolute_hne_equilibrium_pressure_offset_pa": 0.0,
        "maximum_absolute_hydro_budget_relative_residual": 0.0,
        "maximum_absolute_phase_vapor_balance_relative_residual": 0.0,
        "maximum_absolute_schedule_pressure_error_pa": 0.0,
    }
    all_finite = True
    all_positive = True
    authority_open = True

    def update(
        snapshot: Mapping[str, object],
        budget: Mapping[str, float],
    ) -> None:
        nonlocal all_finite, all_positive, authority_open
        extrema["minimum_pressure_pa"] = min(
            extrema["minimum_pressure_pa"],
            float(np.min(snapshot["p_hne"])),
        )
        extrema["maximum_pressure_pa"] = max(
            extrema["maximum_pressure_pa"],
            float(np.max(snapshot["p_hne"])),
        )
        extrema["minimum_actual_quality"] = min(
            extrema["minimum_actual_quality"],
            float(np.min(snapshot["q_actual"])),
        )
        extrema["maximum_actual_quality"] = max(
            extrema["maximum_actual_quality"],
            float(np.max(snapshot["q_actual"])),
        )
        extrema["minimum_equilibrium_quality"] = min(
            extrema["minimum_equilibrium_quality"],
            float(np.min(snapshot["q_equilibrium"])),
        )
        extrema["maximum_equilibrium_quality"] = max(
            extrema["maximum_equilibrium_quality"],
            float(np.max(snapshot["q_equilibrium"])),
        )
        extrema["minimum_frozen_c_m_s"] = min(
            extrema["minimum_frozen_c_m_s"],
            float(np.min(snapshot["c_frozen"])),
        )
        extrema["maximum_frozen_c_m_s"] = max(
            extrema["maximum_frozen_c_m_s"],
            float(np.max(snapshot["c_frozen"])),
        )
        extrema["minimum_alpha"] = min(
            extrema["minimum_alpha"],
            float(np.min(snapshot["alpha"])),
        )
        extrema["maximum_alpha"] = max(
            extrema["maximum_alpha"],
            float(np.max(snapshot["alpha"])),
        )
        extrema["maximum_absolute_quality_lag"] = max(
            extrema["maximum_absolute_quality_lag"],
            float(np.max(np.abs(snapshot["q_lag"]))),
        )
        extrema["maximum_absolute_hne_equilibrium_pressure_offset_pa"] = max(
            extrema["maximum_absolute_hne_equilibrium_pressure_offset_pa"],
            float(np.max(np.abs(snapshot["pressure_offset"]))),
        )
        extrema["maximum_absolute_hydro_budget_relative_residual"] = max(
            extrema["maximum_absolute_hydro_budget_relative_residual"],
            *(abs(float(budget[key])) for key in (
                "budget_mass_relative_residual",
                "budget_momentum_relative_residual",
                "budget_energy_relative_residual",
            )),
        )
        extrema[
            "maximum_absolute_phase_vapor_balance_relative_residual"
        ] = max(
            extrema["maximum_absolute_phase_vapor_balance_relative_residual"],
            abs(float(budget["phase_vapor_mass_balance_relative_residual"])),
        )
        requested = requested_boundary_pressure_pa(solver.t, config)
        prescribed = boundary.pressure_pa(solver.t)
        extrema["maximum_absolute_schedule_pressure_error_pa"] = max(
            extrema["maximum_absolute_schedule_pressure_error_pa"],
            abs(prescribed - requested),
        )
        all_finite = all_finite and bool(snapshot["all_finite"])
        all_positive = all_positive and bool(snapshot["all_positive"])
        authority_open = authority_open and bool(snapshot["authority_open"])

    snapshot = _observe_state(solver)
    budget = _required_budget_diagnostics(solver, 0.0)
    update(snapshot, budget)
    step_rows.append(
        _step_row(
            case_id=case_id,
            regime=regime,
            solver=solver,
            boundary=boundary,
            config=config,
            dt_s=0.0,
            snapshot=snapshot,
            budget=budget,
        )
    )
    probe_rows.extend(
        _probe_rows(
            case_id=case_id,
            regime=regime,
            solver=solver,
            config=config,
            probes=probes,
            dt_s=0.0,
            snapshot=snapshot,
        )
    )

    for _ in range(config.max_steps):
        if solver.t >= config.final_time_s:
            break
        candidate_dt = float(solver.compute_dt(config.final_time_s))
        if candidate_dt <= 0.0:
            break
        accepted_dt = float(solver.step(candidate_dt))
        snapshot = _observe_state(solver)
        budget = _required_budget_diagnostics(solver, accepted_dt)
        update(snapshot, budget)

        for probe in probes:
            name = str(probe["probe_name"])
            index = int(probe["probe_cell_index"])
            pressure_drop = (
                config.initial_pressure_pa - float(snapshot["p_hne"][index])
            )
            if arrivals[name] is None and pressure_drop >= config.arrival_pressure_drop_pa:
                arrivals[name] = float(solver.t)

        step_rows.append(
            _step_row(
                case_id=case_id,
                regime=regime,
                solver=solver,
                boundary=boundary,
                config=config,
                dt_s=accepted_dt,
                snapshot=snapshot,
                budget=budget,
            )
        )
        if (
            solver.step_count % config.probe_sample_stride == 0
            or solver.t >= config.final_time_s
        ):
            probe_rows.extend(
                _probe_rows(
                    case_id=case_id,
                    regime=regime,
                    solver=solver,
                    config=config,
                    probes=probes,
                    dt_s=accepted_dt,
                    snapshot=snapshot,
                )
            )
    else:
        raise HNEControlledFinitePipeCouplingError(
            "max_steps reached before controlled final time"
        )

    if solver.t < config.final_time_s:
        raise HNEControlledFinitePipeCouplingError(
            "controlled case stopped before final time"
        )

    final_snapshot = _observe_state(solver)
    final_budget = _required_budget_diagnostics(solver, 0.0)
    arrival_values = [arrivals[str(probe["probe_name"])] for probe in probes]
    all_arrived = all(value is not None for value in arrival_values)
    arrival_order = bool(
        all_arrived
        and all(
            float(arrival_values[index]) > float(arrival_values[index + 1])
            for index in range(len(arrival_values) - 1)
        )
    )
    front_speeds: list[float] = []
    if all_arrived:
        for index in range(len(probes) - 1):
            x_left = float(probes[index]["probe_cell_center_x_m"])
            x_right = float(probes[index + 1]["probe_cell_center_x_m"])
            t_left = float(arrival_values[index])
            t_right = float(arrival_values[index + 1])
            delta_t = t_left - t_right
            if delta_t <= 0.0:
                raise HNEControlledFinitePipeCouplingError(
                    "pressure-front arrival order produced nonpositive travel time"
                )
            front_speeds.append((x_right - x_left) / delta_t)

    source = state_from_pressure_quality(
        config.initial_pressure_pa,
        config.initial_equilibrium_quality,
    )
    initial_candidate = solver.eos.evaluate(
        source.rho_kg_m3,
        source.e_j_kg,
        source.vapor_mass_fraction,
    )
    q_actual_range = (
        extrema["maximum_actual_quality"] - extrema["minimum_actual_quality"]
    )
    q_equilibrium_range = (
        extrema["maximum_equilibrium_quality"]
        - extrema["minimum_equilibrium_quality"]
    )
    frozen_c_range = (
        extrema["maximum_frozen_c_m_s"] - extrema["minimum_frozen_c_m_s"]
    )
    pressure_drop_observed = (
        config.initial_pressure_pa - extrema["minimum_pressure_pa"]
    )
    final_state_sha = _array_sha(solver.U)
    step_history_sha = _payload_sha(step_rows)
    probe_history_sha = _payload_sha(probe_rows)
    trajectory_sha = _payload_sha(
        {
            "final_state_sha256": final_state_sha,
            "step_history_sha256": step_history_sha,
            "probe_history_sha256": probe_history_sha,
        }
    )

    row: dict[str, object] = {
        "case_id": case_id,
        "relaxation_regime": regime,
        "tau_s": tau_evidence,
        "tau_is_infinite": regime == "frozen",
        "controlled_condition_id": CONTROLLED_CONDITION_ID,
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "boundary_model": BOUNDARY_MODEL_NAME,
        "left_boundary_model": "reflective_closed_end",
        "initial_pressure_pa": config.initial_pressure_pa,
        "final_prescribed_boundary_pressure_pa": config.final_boundary_pressure_pa,
        "initial_equilibrium_quality": config.initial_equilibrium_quality,
        "final_time_s": float(solver.t),
        "solver_step_count": int(solver.step_count),
        "initial_frozen_c_m_s": initial_candidate.frozen_c_m_s,
        **extrema,
        "actual_quality_range": q_actual_range,
        "equilibrium_quality_range": q_equilibrium_range,
        "frozen_c_range_m_s": frozen_c_range,
        "maximum_observed_pressure_drop_pa": pressure_drop_observed,
        "all_states_finite": all_finite,
        "all_states_positive": all_positive,
        "actual_and_equilibrium_states_remained_in_open_authority_domain": authority_open,
        "all_pressure_wave_probes_arrived": all_arrived,
        "pressure_wave_arrival_order_outlet_to_upstream": arrival_order,
        "probe_arrival_times_s": arrivals,
        "front_speed_estimates_m_s": front_speeds,
        "minimum_front_speed_to_initial_frozen_c_ratio": (
            min(front_speeds) / initial_candidate.frozen_c_m_s
            if front_speeds
            else None
        ),
        "maximum_front_speed_to_initial_frozen_c_ratio": (
            max(front_speeds) / initial_candidate.frozen_c_m_s
            if front_speeds
            else None
        ),
        "boundary_schedule_reached_final_pressure": abs(
            boundary.pressure_pa(solver.t) - config.final_boundary_pressure_pa
        ) <= schedule_pressure_tolerance_pa(config),
        "final_budget_mass_residual_kg": final_budget["budget_mass_residual"],
        "final_budget_momentum_residual_kg_m_s": final_budget[
            "budget_momentum_residual"
        ],
        "final_budget_energy_residual_J": final_budget["budget_energy_residual"],
        "phase_vapor_mass_source_cumulative_kg": final_budget[
            "phase_vapor_mass_source_cumulative_kg"
        ],
        "final_phase_vapor_mass_balance_residual_kg": final_budget[
            "phase_vapor_mass_balance_residual_kg"
        ],
        "final_state_sha256": final_state_sha,
        "step_history_sha256": step_history_sha,
        "probe_history_sha256": probe_history_sha,
        "trajectory_sha256": trajectory_sha,
        "candidate_pressure_active_in_interior_flux": True,
        "candidate_frozen_c_active_in_rusanov_and_cfl": True,
        "prescribed_verification_ghost_state_only": True,
        "hne_boundary_characteristics_authorized": False,
        "critical_discharge_authorized": False,
        "physical_discharge_model_active": False,
    }
    return ControlledCaseRun(
        case_row=_json_native(row),
        step_rows=tuple(_json_native(step_rows)),
        probe_rows=tuple(_json_native(probe_rows)),
    )


def _observe_finite_pipe_activation(
    config: ControlledFinitePipeConfig,
) -> dict[str, object]:
    solver, _ = build_controlled_finite_pipe_solver(
        config,
        tau_s=config.finite_tau_s,
    )
    source = state_from_pressure_quality(
        config.initial_pressure_pa,
        config.initial_equilibrium_quality,
    )
    candidate = solver.eos.evaluate(
        source.rho_kg_m3,
        source.e_j_kg,
        source.vapor_mass_fraction,
    )
    primitive = solver.primitive()
    expected_dt = config.cfl * solver.grid.dx / candidate.frozen_c_m_s
    computed_dt = float(solver.compute_dt())
    observations: list[RusanovFluxEvaluation] = []
    with observe_rusanov_flux(observations.append):
        solver._base_fluxes()
    if len(observations) != 1:
        raise HNEControlledFinitePipeCouplingError(
            "expected one vectorized finite-pipe Rusanov evaluation"
        )
    observed_speed = np.asarray(observations[0].maximum_wave_speed, dtype=float)
    return {
        "candidate_pressure_matches_initial_primitive": bool(
            np.allclose(primitive.p, candidate.pressure_pa, rtol=0.0, atol=0.0)
        ),
        "candidate_frozen_c_matches_initial_primitive": bool(
            np.allclose(primitive.c, candidate.frozen_c_m_s, rtol=0.0, atol=0.0)
        ),
        "candidate_frozen_c_controls_initial_cfl": abs(computed_dt - expected_dt)
        <= 8.0 * np.finfo(float).eps * max(abs(expected_dt), 1.0),
        "candidate_frozen_c_controls_initial_rusanov": bool(
            np.allclose(
                observed_speed,
                candidate.frozen_c_m_s,
                rtol=0.0,
                atol=1.0e-12,
            )
        ),
        "initial_candidate_pressure_pa": candidate.pressure_pa,
        "initial_candidate_frozen_c_m_s": candidate.frozen_c_m_s,
    }


def analyze_controlled_finite_pipe_coupling(
    config: ControlledFinitePipeConfig | None = None,
) -> ControlledFinitePipeAnalysis:
    cfg = config or ControlledFinitePipeConfig()
    source_analysis = analyze_limited_interior_coupling()
    source_green = bool(
        source_analysis.summary["p2_a3_1_limited_interior_coupling_ready"]
    )
    activation = _observe_finite_pipe_activation(cfg)

    runs: list[ControlledCaseRun] = []
    for case_id, regime, _ in CASE_DEFINITIONS:
        runs.append(_run_controlled_case(case_id, regime, cfg))
    finite_repeat = _run_controlled_case("TAU_FINITE_HNE", "finite", cfg)

    case_rows = tuple(run.case_row for run in runs)
    step_rows = tuple(row for run in runs for row in run.step_rows)
    probe_rows = tuple(row for run in runs for row in run.probe_rows)
    by_id = {str(row["case_id"]): row for row in case_rows}
    near_zero = by_id["TAU_NEAR_ZERO_HEM_LIMIT"]
    finite = by_id["TAU_FINITE_HNE"]
    frozen = by_id["TAU_INFINITY_FROZEN_LIMIT"]

    repeatability = {
        "finite_final_state_sha256_match": (
            finite["final_state_sha256"]
            == finite_repeat.case_row["final_state_sha256"]
        ),
        "finite_step_history_sha256_match": (
            finite["step_history_sha256"]
            == finite_repeat.case_row["step_history_sha256"]
        ),
        "finite_probe_history_sha256_match": (
            finite["probe_history_sha256"]
            == finite_repeat.case_row["probe_history_sha256"]
        ),
        "finite_trajectory_sha256_match": (
            finite["trajectory_sha256"]
            == finite_repeat.case_row["trajectory_sha256"]
        ),
    }
    repeatability["deterministic_repeatability_passed"] = all(
        repeatability.values()
    )

    schedule_tolerance = schedule_pressure_tolerance_pa(cfg)
    all_cases = list(case_rows)
    all_case_budgets_green = all(
        float(row["maximum_absolute_hydro_budget_relative_residual"]) <= 1.0e-9
        and float(
            row["maximum_absolute_phase_vapor_balance_relative_residual"]
        )
        <= 1.0e-9
        for row in all_cases
    )
    all_case_wave_green = all(
        row["all_pressure_wave_probes_arrived"] is True
        and row["pressure_wave_arrival_order_outlet_to_upstream"] is True
        and row["minimum_front_speed_to_initial_frozen_c_ratio"] is not None
        and 0.4
        <= float(row["minimum_front_speed_to_initial_frozen_c_ratio"])
        <= 2.5
        and 0.4
        <= float(row["maximum_front_speed_to_initial_frozen_c_ratio"])
        <= 2.5
        and float(row["maximum_observed_pressure_drop_pa"])
        >= 0.75 * cfg.imposed_pressure_drop_pa
        for row in all_cases
    )
    all_case_state_green = all(
        row["all_states_finite"] is True
        and row["all_states_positive"] is True
        and row[
            "actual_and_equilibrium_states_remained_in_open_authority_domain"
        ]
        is True
        and row["boundary_schedule_reached_final_pressure"] is True
        and float(row["maximum_absolute_schedule_pressure_error_pa"])
        <= schedule_tolerance
        for row in all_cases
    )

    gates: dict[str, bool] = {
        "SOURCE_A3_1_PROVENANCE_PINNED": (
            SOURCE_A3_1_SHA
            == "d4db09a6447ba4c98fcf0618e37e3ad6fe859ec1"
            and SOURCE_A3_1_WORKFLOW_RUN_ID == 32638595911
            and SOURCE_A3_1_JOB_ID == 97192025339
            and SOURCE_A3_1_ARTIFACT_ID == 9493006871
            and SOURCE_A3_1_ARTIFACT_DIGEST
            == "sha256:21fbde78e47b271d12061dd8c2be67a2128f44645aa6434fe487d50b16d6d423"
        ),
        "SOURCE_A3_1_RUNTIME_GATES_REMAIN_GREEN": source_green,
        "CANDIDATE_PRESSURE_ACTIVE_IN_FINITE_PIPE_INTERIOR_FLUX": bool(
            activation["candidate_pressure_matches_initial_primitive"]
        ),
        "CANDIDATE_FROZEN_C_ACTIVE_IN_FINITE_PIPE_RUSANOV": bool(
            activation["candidate_frozen_c_controls_initial_rusanov"]
        ),
        "CANDIDATE_FROZEN_C_ACTIVE_IN_FINITE_PIPE_CFL": bool(
            activation["candidate_frozen_c_controls_initial_cfl"]
        ),
        "CONTROLLED_RAMP_IDENTICAL_ACROSS_THREE_RELAXATION_REGIMES": (
            len({row["controlled_condition_id"] for row in all_cases}) == 1
            and all(row["boundary_model"] == BOUNDARY_MODEL_NAME for row in all_cases)
        ),
        "PRESSURE_WAVE_PROPAGATES_OUTLET_TO_UPSTREAM_IN_ALL_CASES": all_case_wave_green,
        "BOUNDARY_AND_PHASE_BUDGETS_CLOSE_IN_ALL_CASES": all_case_budgets_green,
        "FINITE_POSITIVE_OPEN_DOMAIN_STATES_PRESERVED": all_case_state_green,
        "NEAR_ZERO_TAU_RECOVERS_HEM_LIMIT": (
            float(near_zero["maximum_absolute_quality_lag"]) <= 1.0e-12
            and float(
                near_zero[
                    "maximum_absolute_hne_equilibrium_pressure_offset_pa"
                ]
            )
            <= 1.0e-3
            and float(near_zero["phase_vapor_mass_source_cumulative_kg"])
            > 1.0e-6
        ),
        "FINITE_TAU_CLOSES_HNE_PHASE_WAVE_FEEDBACK_LOOP": (
            1.0e-4
            < float(finite["maximum_absolute_quality_lag"])
            < float(frozen["maximum_absolute_quality_lag"])
            and float(
                finite["maximum_absolute_hne_equilibrium_pressure_offset_pa"]
            )
            > 1.0e3
            and float(finite["equilibrium_quality_range"]) > 5.0e-3
            and float(finite["frozen_c_range_m_s"]) > 0.5
            and float(finite["phase_vapor_mass_source_cumulative_kg"])
            > 1.0e-6
            and finite["trajectory_sha256"] != near_zero["trajectory_sha256"]
            and finite["trajectory_sha256"] != frozen["trajectory_sha256"]
        ),
        "TAU_INFINITY_RECOVERS_FROZEN_QUALITY_LIMIT": (
            abs(float(frozen["phase_vapor_mass_source_cumulative_kg"]))
            <= 1.0e-14
            and float(frozen["actual_quality_range"]) <= 1.0e-12
            and float(frozen["maximum_absolute_quality_lag"]) > 1.0e-3
            and float(
                frozen["maximum_absolute_hne_equilibrium_pressure_offset_pa"]
            )
            > 1.0e4
        ),
        "RELAXATION_REGIMES_SHOW_ORDERED_PHASE_RESPONSE": (
            float(near_zero["phase_vapor_mass_source_cumulative_kg"])
            > float(finite["phase_vapor_mass_source_cumulative_kg"])
            > float(frozen["phase_vapor_mass_source_cumulative_kg"])
            - 1.0e-14
            and float(near_zero["maximum_actual_quality"])
            > float(finite["maximum_actual_quality"])
            > float(frozen["maximum_actual_quality"])
        ),
        "DETERMINISTIC_FINITE_TAU_REPEATABILITY": bool(
            repeatability["deterministic_repeatability_passed"]
        ),
        "EXISTING_PRODUCTION_DEFAULT_PATH_UNCHANGED": (
            IMPLEMENTATION_AUTHORITY["existing_production_default_path_modified"]
            is False
        ),
        "CHARACTERISTIC_CRITICAL_RUPTURE_AND_PHYSICAL_DISCHARGE_AUTHORITY_CLOSED": all(
            IMPLEMENTATION_AUTHORITY[key] is False
            for key in (
                "hne_boundary_characteristics",
                "hne_critical_discharge",
                "physical_discharge_model",
                "rupture_model",
                "design_use",
                "production_use",
            )
        ),
    }
    failed = [name for name, passed in gates.items() if not passed]
    ready = not failed
    effective_status = dict(FORMAL_STATUS)
    effective_status["working_verification_slice"] = ready
    effective_status["working_vertical_slice"] = ready
    effective_status[
        "controlled_finite_pipe_hne_hydrodynamic_coupling"
    ] = ready

    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "p2_a3_2_controlled_finite_pipe_hne_hydrodynamic_coupling",
        "source_a3_1": {
            "head_sha": SOURCE_A3_1_SHA,
            "workflow_run_id": SOURCE_A3_1_WORKFLOW_RUN_ID,
            "job_id": SOURCE_A3_1_JOB_ID,
            "artifact_id": SOURCE_A3_1_ARTIFACT_ID,
            "artifact_digest": SOURCE_A3_1_ARTIFACT_DIGEST,
            "runtime_analysis_sha256": source_analysis.summary["analysis_sha256"],
            "runtime_gate_green": source_green,
        },
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "property_backend_design_status": "verification_surrogate_not_approved_for_design_use",
        "controlled_condition_id": CONTROLLED_CONDITION_ID,
        "configuration": asdict(cfg),
        "boundary_contract": {
            "left_boundary": "reflective_closed_end",
            "right_boundary": BOUNDARY_MODEL_NAME,
            "prescribed_ghost_state": True,
            "hne_characteristic_boundary": False,
            "critical_discharge_law": False,
            "physical_discharge_model": False,
        },
        "implementation_authority": dict(IMPLEMENTATION_AUTHORITY),
        "activation_observation": activation,
        "formal_status": effective_status,
        "formal_outcome": (
            FORMAL_OUTCOME
            if ready
            else "P2_A3_2_IMPLEMENTED_NOT_GREEN_WITH_FAIL_CLOSED_GATES"
        ),
        "next_action": (
            NEXT_ACTION
            if ready
            else "RESOLVE_FAILED_P2_A3_2_GATES_BEFORE_PHYSICAL_DISCHARGE_COUPLING"
        ),
        "case_summary": list(case_rows),
        "repeatability": repeatability,
        "gate_results": gates,
        "failed_gates": failed,
        "p2_a3_2_controlled_finite_pipe_coupling_ready": ready,
        "existing_production_default_path_modified": False,
        "hne_boundary_characteristics_authorized": False,
        "critical_discharge_authorized": False,
        "physical_discharge_authorized": False,
        "rupture_model_authorized": False,
        "physically_validated": False,
        "runtime_provenance": _provenance(),
        "limitations": [
            "VERIFICATION_SURROGATE_NOT_REAL_CO2_PREDICTION",
            "PRESCRIBED_GHOST_STATE_IS_NOT_AN_HNE_CHARACTERISTIC_BOUNDARY",
            "NO_CRITICAL_DISCHARGE_OR_RUPTURE_MODEL",
            "NO_PHYSICAL_DISCHARGE_COUPLING",
            "TAU_NOT_PHYSICALLY_CALIBRATED",
            "NO_NUCLEATION_BUBBLE_GROWTH_SLIP_OR_TWO_FLUID_MODEL",
            "NO_DESIGN_OR_PRODUCTION_USE",
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
            "cases": case_rows,
            "probe_history": probe_rows,
            "step_history": step_rows,
        }
    )
    normalized_summary = _json_native(summary)
    return ControlledFinitePipeAnalysis(
        summary=normalized_summary,
        case_rows=tuple(_json_native(case_rows)),
        probe_rows=tuple(_json_native(probe_rows)),
        step_rows=tuple(_json_native(step_rows)),
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise HNEControlledFinitePipeCouplingError(
            f"CSV requires at least one row: {path.name}"
        )
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            normalized = _json_native(row)
            writer.writerow(
                {
                    key: (
                        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
                        if isinstance(value, (dict, list, tuple))
                        else value
                    )
                    for key, value in normalized.items()
                }
            )


def _operator_report(summary: Mapping[str, object]) -> str:
    ready = bool(summary["p2_a3_2_controlled_finite_pipe_coupling_ready"])
    lines = [
        "# Stage 7 P2-A3.2 Controlled Finite-Pipe HNE Coupling",
        "",
        f"- Outcome: `{summary['formal_outcome']}`",
        f"- Property backend: `{summary['property_backend_name']}`",
        f"- Controlled condition: `{summary['controlled_condition_id']}`",
        f"- Right boundary: `{BOUNDARY_MODEL_NAME}`",
        f"- Next action: `{summary['next_action']}`",
        "- Existing production/default path modified: `false`",
        "- HNE characteristic, critical-discharge, rupture, and physical-discharge authority: `false`",
        "",
        "| regime | max |q-qeq| | max |pHNE-peq| [Pa] | phase source [kg] | max hydro budget relative residual |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summary["case_summary"]:  # type: ignore[index]
        lines.append(
            "| {regime} | {lag} | {offset} | {source} | {budget} |".format(
                regime=row["relaxation_regime"],
                lag=row["maximum_absolute_quality_lag"],
                offset=row[
                    "maximum_absolute_hne_equilibrium_pressure_offset_pa"
                ],
                source=row["phase_vapor_mass_source_cumulative_kg"],
                budget=row[
                    "maximum_absolute_hydro_budget_relative_residual"
                ],
            )
        )
    lines.append("")
    if ready:
        lines.extend(
            [
                "The controlled finite-pipe HNE feedback loop is a working verification vertical slice.",
                "Proceed only to a separately gated U3 physical-discharge coupling increment.",
                "Do not reinterpret the prescribed ghost boundary as a discharge law.",
            ]
        )
    else:
        lines.append("STOP: P2-A3.2 gates failed; do not proceed to discharge coupling.")
        lines.extend(f"- `{gate}`" for gate in summary["failed_gates"])  # type: ignore[index]
    lines.append("")
    return "\n".join(lines)


def write_artifacts(
    output_dir: str | Path,
    analysis: ControlledFinitePipeAnalysis,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    unexpected = {path.name for path in target.iterdir() if path.is_file()} - expected
    if unexpected:
        raise HNEControlledFinitePipeCouplingError(
            f"unexpected output files: {sorted(unexpected)}"
        )
    paths = {
        "summary": target / "summary.json",
        "cases": target / "case_summary.csv",
        "probes": target / "probe_history.csv",
        "steps": target / "step_history.csv",
        "report": target / "operator_report.md",
        "manifest": target / "manifest.json",
    }
    normalized_summary = _json_native(analysis.summary)
    paths["summary"].write_text(
        json.dumps(
            normalized_summary,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["cases"], analysis.case_rows)
    _write_csv(paths["probes"], analysis.probe_rows)
    _write_csv(paths["steps"], analysis.step_rows)
    paths["report"].write_text(
        _operator_report(normalized_summary),
        encoding="utf-8",
    )
    payload = {key: path for key, path in paths.items() if key != "manifest"}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "analysis_sha256": normalized_summary["analysis_sha256"],
        "p2_a3_2_controlled_finite_pipe_coupling_ready": normalized_summary[
            "p2_a3_2_controlled_finite_pipe_coupling_ready"
        ],
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "source_a3_1_sha": SOURCE_A3_1_SHA,
        "existing_production_default_path_modified": False,
        "hne_boundary_characteristics_authorized": False,
        "critical_discharge_authorized": False,
        "physical_discharge_authorized": False,
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
        raise HNEControlledFinitePipeCouplingError(
            f"artifact envelope mismatch: {sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    analysis = analyze_controlled_finite_pipe_coupling()
    paths = write_artifacts(output_dir, analysis)
    return _json_native(
        {
            **analysis.summary,
            "artifact_paths": {key: str(path) for key, path in paths.items()},
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    result = execute(parser.parse_args(argv).output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["p2_a3_2_controlled_finite_pipe_coupling_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
