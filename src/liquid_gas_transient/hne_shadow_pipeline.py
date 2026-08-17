"""P2-A2.3 finite-pipeline shadow integration for the A2 HNE closure.

The authoritative one-dimensional FVM path remains a surrogate HEM calculation.
The A2 closure observes accepted conservative states and reconstructs independent
``p_HNE``, ``T_HNE`` and ``alpha_HNE`` values without mutating the solver state or
feeding any quantity back into the numerical flux, CFL condition, boundaries or
source operators.

This is a software/model-form diagnostic increment only.  It is not a physical
HNE vertical slice.  In particular the A2 acoustic value remains diagnostic and
is prohibited from hydrodynamic use.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from .config import PipeGeometry
from .eos import LCO2PropertyEOSAdapter
from .grid import UniformGrid
from .hne_thermodynamic_closure import (
    ACOUSTIC_AUTHORITY,
    HNEThermodynamicClosureError,
    SurrogateFrozenQualityThermodynamicClosure,
)
from .phase_change import NoPhaseChange
from .properties import SurrogateLCO2PropertyBackend
from .solver import FvmSolver
from .state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    check_physical_state,
    internal_energy,
    inventory,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)

SCHEMA_VERSION = "stage7_p2_hne_shadow_pipeline_a2_3_v1"
SOURCE_A2_SHA = "b45156f349ddc9754d481c285a8e1efde5d74d22"
EXPECTED_BACKEND_NAME = "surrogate_lco2"
AUTHORITATIVE_ACOUSTIC_AUTHORITY = "SURROGATE_HEM_BACKEND_FLUX_AND_CFL"
OUTPUT_FILES = (
    "summary.json",
    "case_summary.csv",
    "step_history.csv",
    "cell_history.csv",
    "operator_report.md",
    "manifest.json",
)
TAU_CASES = (
    ("TAU_NEAR_ZERO", 1.0e-18),
    ("TAU_FINITE", 1.0e-4),
    ("TAU_FROZEN", math.inf),
)
FORMAL_STATUS = {
    "implemented": True,
    "finite_pipeline_shadow_integration": True,
    "diagnostic_evidence_ready": True,
    "hydrodynamic_coupling_allowed": False,
    "physical_hne_vertical_slice": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}


class HNEShadowPipelineError(RuntimeError):
    """Raised when the shadow integration cannot remain fail-closed."""


@dataclass(frozen=True)
class ShadowPipelineConfig:
    """Small deterministic finite-pipeline case for A2.3 evidence."""

    n_cells: int = 16
    length_m: float = 0.16
    diameter_m: float = 0.05
    cfl: float = 0.25
    n_steps: int = 16
    initial_velocity_m_s: float = 2.0
    left_initial_q: float = 0.05
    right_initial_q: float = 0.10
    constructed_equilibrium_q: float = 0.20
    constructed_temperature_K: float = 260.0

    def __post_init__(self) -> None:
        if self.n_cells < 4:
            raise ValueError("n_cells must be at least four")
        if self.n_cells % 2:
            raise ValueError("n_cells must be even for the deterministic q step")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe geometry must be positive")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.n_steps <= 0:
            raise ValueError("n_steps must be positive")
        if not math.isfinite(self.initial_velocity_m_s):
            raise ValueError("initial velocity must be finite")
        for name, value in (
            ("left_initial_q", self.left_initial_q),
            ("right_initial_q", self.right_initial_q),
            ("constructed_equilibrium_q", self.constructed_equilibrium_q),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and within [0, 1]")
        if not 0.0 < self.constructed_equilibrium_q < 1.0:
            raise ValueError("constructed_equilibrium_q must be strictly two-phase")
        if (
            not math.isfinite(self.constructed_temperature_K)
            or self.constructed_temperature_K <= 0.0
        ):
            raise ValueError("constructed temperature must be finite and positive")


@dataclass(frozen=True)
class TransportedQualityExactRelaxation:
    """Exact split source that reads transported q while HEM drives flux/CFL.

    ``LCO2PropertyEOSAdapter(quality_source='backend')`` is intentionally used on
    the authoritative line so pressure, temperature, void fraction and sound
    speed are backend HEM values.  This source therefore reads ``rho*q`` directly
    rather than using ``PrimitiveState.xv``.  Only the fourth conserved component
    may change.
    """

    tau_s: float

    def __post_init__(self) -> None:
        if math.isnan(self.tau_s) or self.tau_s <= 0.0:
            raise ValueError("tau_s must be positive or +inf")

    def relaxation_factor(self, dt_s: float) -> float:
        if not math.isfinite(dt_s) or dt_s < 0.0:
            raise HNEShadowPipelineError("dt_s must be finite and nonnegative")
        if math.isinf(self.tau_s):
            return 1.0
        ratio = dt_s / self.tau_s
        return 0.0 if ratio >= 745.0 else math.exp(-ratio)

    def apply(
        self,
        U: np.ndarray,
        eos: object,
        dt: float,
        t: float,
    ) -> np.ndarray:
        del t
        if not isinstance(eos, LCO2PropertyEOSAdapter):
            raise HNEShadowPipelineError(
                "transported-quality source requires LCO2PropertyEOSAdapter"
            )
        rho = np.asarray(U[..., IDX_RHO], dtype=float)
        q = np.asarray(U[..., IDX_RHO_XV] / rho, dtype=float)
        if np.any(~np.isfinite(q)) or np.any(q < -1.0e-15) or np.any(q > 1.0 + 1.0e-15):
            raise HNEShadowPipelineError("transported q is outside [0, 1]")
        primitive = eos.primitive_from_conserved(U)
        q_eq = np.asarray(eos.equilibrium_vapor_mass_fraction(primitive), dtype=float)
        if (
            q_eq.shape != q.shape
            or np.any(~np.isfinite(q_eq))
            or np.any(q_eq < 0.0)
            or np.any(q_eq > 1.0)
        ):
            raise HNEShadowPipelineError("invalid equilibrium q from authoritative EOS")
        factor = self.relaxation_factor(float(dt))
        q_new = q_eq + (q - q_eq) * factor
        if np.any(q_new < -1.0e-15) or np.any(q_new > 1.0 + 1.0e-15):
            raise HNEShadowPipelineError("exact relaxation produced out-of-bounds q")
        out = np.array(U, dtype=float, copy=True)
        out[..., IDX_RHO_XV] = rho * np.clip(q_new, 0.0, 1.0)
        if not np.array_equal(out[..., :IDX_RHO_XV], U[..., :IDX_RHO_XV]):
            raise HNEShadowPipelineError(
                "quality source modified mass, momentum or total energy"
            )
        return out


@dataclass(frozen=True)
class ShadowObservation:
    step_row: dict[str, object]
    cell_rows: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class HNEThermodynamicShadowObserver:
    """Read-only observer that evaluates the A2 closure on accepted FVM states."""

    closure: SurrogateFrozenQualityThermodynamicClosure = field(
        default_factory=SurrogateFrozenQualityThermodynamicClosure
    )

    def assert_compatible(self, eos: object) -> None:
        if not isinstance(eos, LCO2PropertyEOSAdapter):
            raise HNEShadowPipelineError(
                "shadow observer requires LCO2PropertyEOSAdapter"
            )
        if eos.quality_source != "backend":
            raise HNEShadowPipelineError(
                "authoritative EOS must use backend quality for HEM flux/CFL"
            )
        if eos.backend_name != EXPECTED_BACKEND_NAME:
            raise HNEShadowPipelineError(
                "shadow observer is restricted to the surrogate_lco2 backend"
            )
        if type(eos.backend) is not SurrogateLCO2PropertyBackend:
            raise HNEShadowPipelineError("unexpected authoritative backend type")
        if eos.backend != self.closure.backend:
            raise HNEShadowPipelineError(
                "authoritative and shadow surrogate parameter sets differ"
            )

    def observe(
        self,
        *,
        case_id: str,
        tau_s: float,
        U: np.ndarray,
        eos: object,
        grid: UniformGrid,
        step: int,
        time_s: float,
        dt_s: float,
    ) -> ShadowObservation:
        self.assert_compatible(eos)
        check_physical_state(U, names=["A2.3 accepted shadow input"])
        before_sha = _array_sha(U)

        rho = np.asarray(U[..., IDX_RHO], dtype=float)
        u = np.asarray(velocity(U), dtype=float)
        e = np.asarray(internal_energy(U), dtype=float)
        q = np.asarray(vapor_mass_fraction(U), dtype=float)
        authoritative = self.closure.backend.state_from_rho_e(rho, e)

        rows: list[dict[str, object]] = []
        pressure_delta: list[float] = []
        temperature_delta: list[float] = []
        alpha_delta: list[float] = []
        acoustic_delta: list[float] = []
        volume_residuals: list[float] = []
        for index in range(grid.n_cells):
            try:
                shadow = self.closure.evaluate(
                    float(rho[index]),
                    float(e[index]),
                    float(q[index]),
                )
            except HNEThermodynamicClosureError as exc:
                raise HNEShadowPipelineError(
                    f"A2 closure failed at step={step}, cell={index}: {exc}"
                ) from exc
            volume_residual = (
                (1.0 - shadow.vapor_mass_fraction)
                / shadow.liquid_density_kg_m3
                + shadow.vapor_mass_fraction / shadow.vapor_density_kg_m3
                - 1.0 / shadow.rho_kg_m3
            )
            p_hem = float(authoritative.p[index])
            T_hem = float(authoritative.T[index])
            alpha_hem = float(authoritative.alpha[index])
            c_hem = float(authoritative.c[index])
            dp = shadow.pressure_pa - p_hem
            dT = shadow.temperature_K - T_hem
            da = shadow.void_fraction - alpha_hem
            dc = shadow.acoustic_speed_diagnostic_m_s - c_hem
            values = (
                shadow.pressure_pa,
                shadow.temperature_K,
                shadow.void_fraction,
                shadow.acoustic_speed_diagnostic_m_s,
                volume_residual,
                dp,
                dT,
                da,
                dc,
            )
            if not all(math.isfinite(value) for value in values):
                raise HNEShadowPipelineError(
                    f"nonfinite shadow diagnostic at step={step}, cell={index}"
                )
            pressure_delta.append(dp)
            temperature_delta.append(dT)
            alpha_delta.append(da)
            acoustic_delta.append(dc)
            volume_residuals.append(volume_residual)
            rows.append(
                {
                    "case_id": case_id,
                    "tau_s": _tau_value(tau_s),
                    "step": step,
                    "time_s": float(time_s),
                    "dt_s": float(dt_s),
                    "cell_index": index,
                    "x_m": float(grid.cell_centers[index]),
                    "rho_kg_m3": float(rho[index]),
                    "u_m_s": float(u[index]),
                    "e_j_kg": float(e[index]),
                    "q_transport": float(q[index]),
                    "q_equilibrium": shadow.equilibrium_vapor_mass_fraction,
                    "signed_q_lag": (
                        shadow.equilibrium_vapor_mass_fraction
                        - shadow.vapor_mass_fraction
                    ),
                    "p_hem_pa": p_hem,
                    "p_hne_shadow_pa": shadow.pressure_pa,
                    "delta_p_hne_minus_hem_pa": dp,
                    "T_hem_K": T_hem,
                    "T_hne_shadow_K": shadow.temperature_K,
                    "delta_T_hne_minus_hem_K": dT,
                    "alpha_hem": alpha_hem,
                    "alpha_hne_shadow": shadow.void_fraction,
                    "delta_alpha_hne_minus_hem": da,
                    "c_hem_m_s": c_hem,
                    "c_hne_diagnostic_m_s": (
                        shadow.acoustic_speed_diagnostic_m_s
                    ),
                    "delta_c_diagnostic_minus_hem_m_s": dc,
                    "volume_residual_m3_kg": volume_residual,
                    "shadow_acoustic_authority": shadow.acoustic_authority,
                }
            )

        after_sha = _array_sha(U)
        if after_sha != before_sha:
            raise HNEShadowPipelineError("shadow observer mutated authoritative U")
        row = {
            "case_id": case_id,
            "tau_s": _tau_value(tau_s),
            "step": step,
            "time_s": float(time_s),
            "dt_s": float(dt_s),
            "state_sha256": before_sha,
            "hydrodynamic_state_sha256": _array_sha(U[..., :IDX_RHO_XV]),
            "q_min": float(np.min(q)),
            "q_max": float(np.max(q)),
            "maximum_absolute_q_lag": float(
                max(
                    abs(float(item["signed_q_lag"]))
                    for item in rows
                )
            ),
            "maximum_absolute_pressure_delta_pa": float(
                np.max(np.abs(np.asarray(pressure_delta)))
            ),
            "maximum_absolute_temperature_delta_K": float(
                np.max(np.abs(np.asarray(temperature_delta)))
            ),
            "maximum_absolute_alpha_delta": float(
                np.max(np.abs(np.asarray(alpha_delta)))
            ),
            "maximum_absolute_acoustic_diagnostic_delta_m_s": float(
                np.max(np.abs(np.asarray(acoustic_delta)))
            ),
            "maximum_absolute_volume_residual_m3_kg": float(
                np.max(np.abs(np.asarray(volume_residuals)))
            ),
            "closure_success_count": grid.n_cells,
            "closure_failure_count": 0,
            "authoritative_acoustic_authority": AUTHORITATIVE_ACOUSTIC_AUTHORITY,
            "shadow_acoustic_authority": ACOUSTIC_AUTHORITY,
            "shadow_state_read_only": after_sha == before_sha,
        }
        return ShadowObservation(step_row=row, cell_rows=tuple(rows))


@dataclass(frozen=True)
class ShadowPipelineAnalysis:
    summary: dict[str, object]
    case_rows: tuple[dict[str, object], ...]
    step_rows: tuple[dict[str, object], ...]
    cell_rows: tuple[dict[str, object], ...]


def _tau_value(tau_s: float) -> float | str:
    return "INF" if math.isinf(tau_s) else float(tau_s)


def _array_sha(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(np.asarray(array, dtype=float))
    return hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()


def _payload_sha(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _constructed_rho_e(
    config: ShadowPipelineConfig,
    backend: SurrogateLCO2PropertyBackend,
) -> tuple[float, float]:
    q_eq = config.constructed_equilibrium_q
    rho = 1.0 / (
        (1.0 - q_eq) / backend.rho_l_ref_kg_m3
        + q_eq / backend.rho_v_ref_kg_m3
    )
    cv_mix = (
        (1.0 - q_eq) * backend.cv_liquid_j_kgK
        + q_eq * backend.cv_vapor_j_kgK
    )
    e = (
        backend.e_l_ref_j_kg
        + q_eq * backend.latent_heat_ref_j_kg
        + cv_mix
        * (config.constructed_temperature_K - backend.T_sat_ref_K)
    )
    return float(rho), float(e)


def _initial_state(
    config: ShadowPipelineConfig,
    backend: SurrogateLCO2PropertyBackend,
) -> np.ndarray:
    rho, e = _constructed_rho_e(config, backend)
    q = np.empty(config.n_cells, dtype=float)
    midpoint = config.n_cells // 2
    q[:midpoint] = config.left_initial_q
    q[midpoint:] = config.right_initial_q
    U = make_conserved(
        rho=np.full(config.n_cells, rho, dtype=float),
        u=np.full(config.n_cells, config.initial_velocity_m_s, dtype=float),
        e=np.full(config.n_cells, e, dtype=float),
        xv=q,
    )
    check_physical_state(U, names=["A2.3 deterministic initial state"])
    return U


def _build_solver(
    config: ShadowPipelineConfig,
    tau_s: float,
    *,
    no_phase_change: bool = False,
) -> tuple[FvmSolver, SurrogateFrozenQualityThermodynamicClosure]:
    backend = SurrogateLCO2PropertyBackend()
    eos = LCO2PropertyEOSAdapter(
        backend=backend,
        boundary_temperature_K=config.constructed_temperature_K,
        quality_source="backend",
    )
    grid = UniformGrid(
        geometry=PipeGeometry(
            length_m=config.length_m,
            diameter_m=config.diameter_m,
        ),
        n_cells=config.n_cells,
    )
    phase_change = (
        NoPhaseChange()
        if no_phase_change
        else TransportedQualityExactRelaxation(tau_s=tau_s)
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=_initial_state(config, backend),
        cfl=config.cfl,
        phase_change=phase_change,
        enable_boundary_budget=False,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    closure = SurrogateFrozenQualityThermodynamicClosure(backend=backend)
    return solver, closure


def _run_pipeline(
    case_id: str,
    tau_s: float,
    config: ShadowPipelineConfig,
    *,
    with_shadow: bool,
    no_phase_change: bool = False,
) -> dict[str, object]:
    solver, closure = _build_solver(
        config,
        tau_s,
        no_phase_change=no_phase_change,
    )
    observer = HNEThermodynamicShadowObserver(closure=closure)
    initial_inventory = inventory(
        solver.U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    initial_state_sha = _array_sha(solver.U)
    trajectory_sha = [initial_state_sha]
    hydrodynamic_sha = [_array_sha(solver.U[..., :IDX_RHO_XV])]
    dt_history: list[float] = []
    step_rows: list[dict[str, object]] = []
    cell_rows: list[dict[str, object]] = []

    if with_shadow:
        observation = observer.observe(
            case_id=case_id,
            tau_s=tau_s,
            U=solver.U,
            eos=solver.eos,
            grid=solver.grid,
            step=solver.step_count,
            time_s=solver.t,
            dt_s=0.0,
        )
        step_rows.append(observation.step_row)
        cell_rows.extend(observation.cell_rows)

    for _ in range(config.n_steps):
        dt = float(solver.compute_dt())
        accepted_dt = float(solver.step(dt))
        if accepted_dt != dt:
            raise HNEShadowPipelineError(
                "focused A2.3 case unexpectedly changed the candidate dt"
            )
        dt_history.append(accepted_dt)
        trajectory_sha.append(_array_sha(solver.U))
        hydrodynamic_sha.append(_array_sha(solver.U[..., :IDX_RHO_XV]))
        if with_shadow:
            observation = observer.observe(
                case_id=case_id,
                tau_s=tau_s,
                U=solver.U,
                eos=solver.eos,
                grid=solver.grid,
                step=solver.step_count,
                time_s=solver.t,
                dt_s=accepted_dt,
            )
            step_rows.append(observation.step_row)
            cell_rows.extend(observation.cell_rows)

    final_inventory = inventory(
        solver.U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    final_q = np.asarray(vapor_mass_fraction(solver.U), dtype=float)
    return {
        "case_id": case_id,
        "tau_s": tau_s,
        "initial_state_sha256": initial_state_sha,
        "final_state_sha256": _array_sha(solver.U),
        "trajectory_sha256": tuple(trajectory_sha),
        "hydrodynamic_trajectory_sha256": tuple(hydrodynamic_sha),
        "dt_history_s": tuple(dt_history),
        "initial_inventory": initial_inventory,
        "final_inventory": final_inventory,
        "final_q": final_q.copy(),
        "final_U": solver.U.copy(),
        "step_rows": tuple(step_rows),
        "cell_rows": tuple(cell_rows),
        "final_time_s": float(solver.t),
        "step_count": int(solver.step_count),
    }


def _inventory_conserved(run: dict[str, object]) -> bool:
    initial = run["initial_inventory"]
    final = run["final_inventory"]
    assert isinstance(initial, dict) and isinstance(final, dict)
    for key in ("mass_total", "momentum_total", "energy_total"):
        reference = float(initial[key])
        residual = float(final[key]) - reference
        tolerance = 32.0 * np.finfo(float).eps * max(abs(reference), 1.0)
        if abs(residual) > tolerance:
            return False
    return True


def _case_row(
    case_id: str,
    tau_s: float,
    baseline: dict[str, object],
    shadow: dict[str, object],
    *,
    no_phase_reference: dict[str, object] | None = None,
) -> dict[str, object]:
    steps = shadow["step_rows"]
    assert isinstance(steps, tuple) and steps
    final_step = steps[-1]
    final_q = np.asarray(shadow["final_q"], dtype=float)
    full_equal = baseline["trajectory_sha256"] == shadow["trajectory_sha256"]
    hydro_equal = (
        baseline["hydrodynamic_trajectory_sha256"]
        == shadow["hydrodynamic_trajectory_sha256"]
    )
    frozen_matches = None
    if no_phase_reference is not None:
        frozen_matches = (
            baseline["trajectory_sha256"]
            == no_phase_reference["trajectory_sha256"]
        )
    initial_inventory = shadow["initial_inventory"]
    final_inventory = shadow["final_inventory"]
    assert isinstance(initial_inventory, dict) and isinstance(final_inventory, dict)
    return {
        "case_id": case_id,
        "tau_s": _tau_value(tau_s),
        "step_count": shadow["step_count"],
        "final_time_s": shadow["final_time_s"],
        "baseline_shadow_full_trajectory_bitwise_equal": full_equal,
        "baseline_shadow_hydrodynamic_trajectory_bitwise_equal": hydro_equal,
        "hydrodynamic_state_unchanged_from_initial": len(
            set(shadow["hydrodynamic_trajectory_sha256"])
        )
        == 1,
        "mass_momentum_energy_conserved": _inventory_conserved(shadow),
        "q_min_final": float(np.min(final_q)),
        "q_max_final": float(np.max(final_q)),
        "maximum_absolute_q_lag_final": final_step[
            "maximum_absolute_q_lag"
        ],
        "maximum_absolute_pressure_delta_pa_final": final_step[
            "maximum_absolute_pressure_delta_pa"
        ],
        "maximum_absolute_temperature_delta_K_final": final_step[
            "maximum_absolute_temperature_delta_K"
        ],
        "maximum_absolute_alpha_delta_final": final_step[
            "maximum_absolute_alpha_delta"
        ],
        "maximum_absolute_volume_residual_m3_kg_final": final_step[
            "maximum_absolute_volume_residual_m3_kg"
        ],
        "all_shadow_states_read_only": all(
            bool(row["shadow_state_read_only"]) for row in steps
        ),
        "all_closure_calls_succeeded": all(
            int(row["closure_failure_count"]) == 0
            and int(row["closure_success_count"]) > 0
            for row in steps
        ),
        "frozen_source_matches_no_phase_change": frozen_matches,
        "mass_residual_kg": (
            float(final_inventory["mass_total"])
            - float(initial_inventory["mass_total"])
        ),
        "momentum_residual_kg_m_s": (
            float(final_inventory["momentum_total"])
            - float(initial_inventory["momentum_total"])
        ),
        "energy_residual_J": (
            float(final_inventory["energy_total"])
            - float(initial_inventory["energy_total"])
        ),
        "initial_state_sha256": shadow["initial_state_sha256"],
        "final_state_sha256": shadow["final_state_sha256"],
    }


def analyze_shadow_pipeline(
    config: ShadowPipelineConfig | None = None,
) -> ShadowPipelineAnalysis:
    """Execute the focused A2.3 matrix and return evidence in memory."""

    config = config or ShadowPipelineConfig()
    case_rows: list[dict[str, object]] = []
    step_rows: list[dict[str, object]] = []
    cell_rows: list[dict[str, object]] = []
    runs: dict[str, dict[str, object]] = {}

    for case_id, tau_s in TAU_CASES:
        baseline = _run_pipeline(
            case_id,
            tau_s,
            config,
            with_shadow=False,
        )
        shadow = _run_pipeline(
            case_id,
            tau_s,
            config,
            with_shadow=True,
        )
        no_phase_reference = None
        if case_id == "TAU_FROZEN":
            no_phase_reference = _run_pipeline(
                "NO_PHASE_REFERENCE",
                tau_s,
                config,
                with_shadow=False,
                no_phase_change=True,
            )
        row = _case_row(
            case_id,
            tau_s,
            baseline,
            shadow,
            no_phase_reference=no_phase_reference,
        )
        case_rows.append(row)
        step_rows.extend(shadow["step_rows"])
        cell_rows.extend(shadow["cell_rows"])
        runs[case_id] = shadow

    finite_repeat = _run_pipeline(
        "TAU_FINITE",
        1.0e-4,
        config,
        with_shadow=True,
    )
    finite = runs["TAU_FINITE"]
    reproducible = (
        finite["trajectory_sha256"] == finite_repeat["trajectory_sha256"]
        and _payload_sha(finite["step_rows"])
        == _payload_sha(finite_repeat["step_rows"])
        and _payload_sha(finite["cell_rows"])
        == _payload_sha(finite_repeat["cell_rows"])
    )

    by_id = {str(row["case_id"]): row for row in case_rows}
    near = by_id["TAU_NEAR_ZERO"]
    medium = by_id["TAU_FINITE"]
    frozen = by_id["TAU_FROZEN"]
    maturity_not_promoted = all(
        FORMAL_STATUS[key] is False
        for key in (
            "hydrodynamic_coupling_allowed",
            "physical_hne_vertical_slice",
            "working_vertical_slice",
            "verified",
            "accepted",
            "physically_validated",
            "design_use_accepted",
            "production_approved",
        )
    )
    gates = [
        {
            "gate": "SURROGATE_BACKEND_CONTRACT_RETAINED",
            "passed": True,
        },
        {
            "gate": "AUTHORITATIVE_HEM_FLUX_CFL_RETAINED",
            "passed": True,
        },
        {
            "gate": "SHADOW_OBSERVER_READ_ONLY",
            "passed": all(
                bool(row["baseline_shadow_full_trajectory_bitwise_equal"])
                and bool(row["all_shadow_states_read_only"])
                for row in case_rows
            ),
        },
        {
            "gate": "AUTHORITATIVE_HYDRODYNAMIC_TRAJECTORY_UNCHANGED",
            "passed": all(
                bool(row[
                    "baseline_shadow_hydrodynamic_trajectory_bitwise_equal"
                ])
                and bool(row["hydrodynamic_state_unchanged_from_initial"])
                for row in case_rows
            ),
        },
        {
            "gate": "ALL_SHADOW_CLOSURES_SUCCEEDED",
            "passed": all(
                bool(row["all_closure_calls_succeeded"]) for row in case_rows
            ),
        },
        {
            "gate": "ALL_STATES_FINITE_AND_Q_BOUNDED",
            "passed": all(
                0.0 <= float(row["q_min_final"])
                <= float(row["q_max_final"])
                <= 1.0
                for row in case_rows
            )
            and all(
                math.isfinite(float(value))
                for row in cell_rows
                for key, value in row.items()
                if key
                not in {
                    "case_id",
                    "tau_s",
                    "shadow_acoustic_authority",
                }
            ),
        },
        {
            "gate": "MASS_MOMENTUM_ENERGY_NOT_DAMAGED",
            "passed": all(
                bool(row["mass_momentum_energy_conserved"])
                for row in case_rows
            ),
        },
        {
            "gate": "TAU_TO_ZERO_FINITE_PIPELINE_HEM_LIMIT",
            "passed": float(near["maximum_absolute_q_lag_final"]) <= 1.0e-15
            and float(near["maximum_absolute_pressure_delta_pa_final"])
            <= 1.0e-8
            and float(near["maximum_absolute_temperature_delta_K_final"])
            <= 1.0e-12
            and float(near["maximum_absolute_alpha_delta_final"])
            <= 1.0e-12,
        },
        {
            "gate": "FINITE_TAU_THERMODYNAMIC_DIFFERENCE_VISIBLE",
            "passed": float(medium["maximum_absolute_q_lag_final"]) > 1.0e-8
            and float(medium["maximum_absolute_pressure_delta_pa_final"])
            > 1.0
            and float(medium["maximum_absolute_temperature_delta_K_final"])
            > 1.0e-6
            and float(medium["maximum_absolute_alpha_delta_final"])
            > 1.0e-9,
        },
        {
            "gate": "TAU_INFINITY_SOURCE_EQUALS_NO_PHASE_CHANGE",
            "passed": frozen["frozen_source_matches_no_phase_change"] is True,
        },
        {
            "gate": "VOLUME_CLOSURE_RESIDUAL_WITHIN_TOLERANCE",
            "passed": all(
                float(row["maximum_absolute_volume_residual_m3_kg_final"])
                <= 1.0e-12
                for row in case_rows
            ),
        },
        {
            "gate": "DETERMINISTIC_REPRODUCIBILITY",
            "passed": reproducible,
        },
        {
            "gate": "NON_EQUILIBRIUM_ACOUSTIC_REMAINS_DIAGNOSTIC_ONLY",
            "passed": True,
        },
        {
            "gate": "HYDRODYNAMIC_COUPLING_GATE_REMAINS_CLOSED",
            "passed": FORMAL_STATUS["hydrodynamic_coupling_allowed"] is False,
        },
        {
            "gate": "MATURITY_NOT_PROMOTED",
            "passed": maturity_not_promoted,
        },
    ]
    ready = all(bool(gate["passed"]) for gate in gates)
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "p2_a2_3_finite_pipeline_hne_shadow_integration",
        "source_a2_sha": SOURCE_A2_SHA,
        "configuration": asdict(config),
        "case_matrix": [
            {"case_id": case_id, "tau_s": _tau_value(tau_s)}
            for case_id, tau_s in TAU_CASES
        ],
        "backend_contract": {
            "authoritative_backend": EXPECTED_BACKEND_NAME,
            "authoritative_eos_quality_source": "backend",
            "authoritative_pressure_temperature_sound_speed": "HEM_BACKEND",
            "transported_quality_storage": "RHO_Q_CONSERVATIVE_SCALAR",
            "shadow_closure": (
                "SurrogateFrozenQualityThermodynamicClosure"
            ),
            "backend_mixing_allowed": False,
        },
        "coupling_contract": {
            "shadow_reads_accepted_U": True,
            "shadow_may_mutate_U": False,
            "p_hne_to_flux": False,
            "T_hne_to_flux": False,
            "alpha_hne_to_flux": False,
            "c_hne_to_flux_or_cfl": False,
            "hydrodynamic_coupling_allowed": False,
        },
        "case_summary": case_rows,
        "gates": gates,
        "gate_results": {
            str(gate["gate"]): bool(gate["passed"]) for gate in gates
        },
        "a2_3_shadow_ready": ready,
        "execution_status": (
            "A2_3_FINITE_PIPELINE_SHADOW_READY_WITH_COUPLING_GATE_CLOSED"
            if ready
            else "FAIL_CLOSED"
        ),
        "physical_hne_claim_allowed": False,
        "hydrodynamic_coupling_allowed": False,
        "acoustic_authority": {
            "authoritative": AUTHORITATIVE_ACOUSTIC_AUTHORITY,
            "shadow": ACOUSTIC_AUTHORITY,
        },
        "interpretation": {
            "shadow_integration": (
                "A2_THERMODYNAMIC_STATE_RECONSTRUCTION_ON_ACCEPTED_FINITE_PIPELINE_STATES"
            ),
            "tau_to_zero_limit": "FINITE_PIPELINE_HEM_LIMIT_RETAINED",
            "finite_tau_behavior": (
                "THERMODYNAMIC_DIFFERENCE_VISIBLE_WITHOUT_HYDRODYNAMIC_FEEDBACK"
            ),
            "tau_infinity_limit": "SOURCE_EQUIVALENT_TO_NO_PHASE_CHANGE",
            "authoritative_solver_effect": "BITWISE_NONE",
            "next_authority_gap": "NONEQUILIBRIUM_ACOUSTIC_CLOSURE",
        },
        "open_limitations": [
            "SURROGATE_CONSTITUENT_EOS_ONLY",
            "NO_VALIDATED_NONEQUILIBRIUM_ACOUSTIC_DERIVATIVE",
            "NO_HNE_PRESSURE_FEEDBACK_TO_FLUX",
            "NO_NUCLEATION_METASTABILITY_OR_BUBBLE_GROWTH_MODEL",
            "NO_SLIP_MODEL",
            "TAU_NOT_PHYSICALLY_VALIDATED",
            "NO_REAL_FLUID_BACKEND_COMPATIBILITY",
            "NO_PHYSICAL_DISCHARGE_FEEDBACK_LOOP",
            "P1_MESH_CFL_LIMITATIONS_RETAINED",
        ],
        "next_phase_decision": (
            "PROCEED_TO_A2_4_NONEQUILIBRIUM_ACOUSTIC_CLOSURE_DESIGN"
            if ready
            else "STOP_AND_DIAGNOSE_A2_3_SHADOW_INTEGRATION"
        ),
        "warnings": [
            "SHADOW_OUTPUTS_ARE_DIAGNOSTIC_NOT_HYDRODYNAMIC_AUTHORITY",
            "C_HNE_MUST_NOT_ENTER_FLUX_OR_CFL",
            "SURROGATE_RESULTS_ARE_NOT_PHYSICAL_CO2_PREDICTIONS",
            "COOLPROP_AND_SURROGATE_STATES_MUST_NOT_BE_MIXED",
            "NO_MATURITY_PROMOTION_AUTHORIZED",
        ],
        "formal_status": dict(FORMAL_STATUS),
        "provenance": _provenance(),
    }
    summary["analysis_sha256"] = _payload_sha(summary)
    return ShadowPipelineAnalysis(
        summary=summary,
        case_rows=tuple(case_rows),
        step_rows=tuple(step_rows),
        cell_rows=tuple(cell_rows),
    )


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise HNEShadowPipelineError(f"cannot write empty CSV: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _report(summary: dict[str, object]) -> str:
    lines = [
        "# P2-A2.3 Finite-Pipeline HNE Shadow Integration",
        "",
        f"- status: `{summary['execution_status']}`",
        "- hydrodynamic coupling allowed: `false`",
        "- physical HNE claim allowed: `false`",
        "",
        "The accepted conservative finite-pipeline state is reconstructed by the",
        "A2 thermodynamic closure in a read-only shadow path. HEM backend pressure,",
        "temperature and sound speed continue to drive the authoritative FVM line.",
        "The HNE acoustic value remains diagnostic and is not used by flux or CFL.",
        "",
        "| case | tau [s] | max |q-qeq| | max |dp| [Pa] | max |dT| [K] | max |dalpha| | bitwise no-effect |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["case_summary"]:
        lines.append(
            "| {case} | {tau} | {q:.8g} | {p:.8g} | {T:.8g} | {a:.8g} | {same} |".format(
                case=row["case_id"],
                tau=row["tau_s"],
                q=float(row["maximum_absolute_q_lag_final"]),
                p=float(row["maximum_absolute_pressure_delta_pa_final"]),
                T=float(row["maximum_absolute_temperature_delta_K_final"]),
                a=float(row["maximum_absolute_alpha_delta_final"]),
                same=row["baseline_shadow_full_trajectory_bitwise_equal"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The finite-pipeline shadow path is eligible as diagnostic evidence only.",
            "The hydrodynamic coupling gate remains closed pending a defensible",
            "nonequilibrium acoustic closure and later targeted coupling evidence.",
            "",
            "## Maturity",
            "",
            "- IMPLEMENTED: true",
            "- FINITE-PIPELINE SHADOW INTEGRATION: true",
            "- DIAGNOSTIC EVIDENCE READY: true",
            "- HYDRODYNAMIC COUPLING ALLOWED: false",
            "- PHYSICAL HNE / WORKING VERTICAL SLICE: false",
            "- VERIFIED / ACCEPTED / PHYSICALLY VALIDATED: false",
            "- DESIGN-USE ACCEPTED / PRODUCTION APPROVED: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    output_dir: str | Path,
    analysis: ShadowPipelineAnalysis,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    unexpected = {
        path.name for path in target.iterdir() if path.is_file()
    } - expected
    if unexpected:
        raise HNEShadowPipelineError(
            f"unexpected files in output directory: {sorted(unexpected)}"
        )
    paths = {
        "summary": target / "summary.json",
        "cases": target / "case_summary.csv",
        "steps": target / "step_history.csv",
        "cells": target / "cell_history.csv",
        "report": target / "operator_report.md",
        "manifest": target / "manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(
            analysis.summary,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["cases"], analysis.case_rows)
    _write_csv(paths["steps"], analysis.step_rows)
    _write_csv(paths["cells"], analysis.cell_rows)
    paths["report"].write_text(
        _report(analysis.summary),
        encoding="utf-8",
    )
    payload_paths = {
        key: path for key, path in paths.items() if key != "manifest"
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "analysis_sha256": analysis.summary["analysis_sha256"],
        "a2_3_shadow_ready": analysis.summary["a2_3_shadow_ready"],
        "hydrodynamic_coupling_allowed": False,
        "payload_files": {
            path.name: {
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha(path),
            }
            for path in payload_paths.values()
        },
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise HNEShadowPipelineError(
            f"artifact set mismatch: expected={sorted(expected)} actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    analysis = analyze_shadow_pipeline()
    paths = write_artifacts(output_dir, analysis)
    return {
        **analysis.summary,
        "artifact_paths": {key: str(path) for key, path in paths.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["a2_3_shadow_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
