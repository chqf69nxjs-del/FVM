"""P2-A2.3 read-only HNE thermodynamic shadow on a finite FVM pipe.

The authoritative solver remains surrogate HEM.  Accepted conservative states
are observed by the A2 closure, but no HNE pressure, temperature, void fraction
or acoustic diagnostic is allowed to feed flux, CFL, boundaries or sources.
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
    IDX_RHO,
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
    """Raised when the focused shadow path cannot remain fail-closed."""


@dataclass(frozen=True)
class ShadowPipelineConfig:
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
        if self.n_cells < 4 or self.n_cells % 2:
            raise ValueError("n_cells must be even and at least four")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe geometry must be positive")
        if not 0.0 < self.cfl <= 1.0 or self.n_steps <= 0:
            raise ValueError("invalid numerical configuration")
        if not math.isfinite(self.initial_velocity_m_s):
            raise ValueError("initial velocity must be finite")
        for value in (
            self.left_initial_q,
            self.right_initial_q,
            self.constructed_equilibrium_q,
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("qualities must be finite and within [0, 1]")
        if not 0.0 < self.constructed_equilibrium_q < 1.0:
            raise ValueError("constructed equilibrium quality must be two-phase")
        if (
            not math.isfinite(self.constructed_temperature_K)
            or self.constructed_temperature_K <= 0.0
        ):
            raise ValueError("constructed temperature must be positive and finite")


@dataclass(frozen=True)
class TransportedQualityExactRelaxation:
    """Exact q source; only rho*q may change.

    For ``tau=+inf`` this is an exact array-copy no-op.  Avoiding a divide/multiply
    round trip is required for bitwise equivalence with ``NoPhaseChange``.
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

    def apply(self, U: np.ndarray, eos: object, dt: float, t: float) -> np.ndarray:
        del t
        if not isinstance(eos, LCO2PropertyEOSAdapter):
            raise HNEShadowPipelineError("quality source requires the LCO2 adapter")
        rho = np.asarray(U[..., IDX_RHO], dtype=float)
        q = np.asarray(U[..., IDX_RHO_XV] / rho, dtype=float)
        if np.any(~np.isfinite(q)) or np.any(q < -1.0e-15) or np.any(q > 1.0 + 1.0e-15):
            raise HNEShadowPipelineError("transported q is outside [0, 1]")
        factor = self.relaxation_factor(float(dt))
        if math.isinf(self.tau_s):
            return np.array(U, dtype=float, copy=True)
        prim = eos.primitive_from_conserved(U)
        q_eq = np.asarray(eos.equilibrium_vapor_mass_fraction(prim), dtype=float)
        if (
            q_eq.shape != q.shape
            or np.any(~np.isfinite(q_eq))
            or np.any(q_eq < 0.0)
            or np.any(q_eq > 1.0)
        ):
            raise HNEShadowPipelineError("authoritative EOS returned invalid q_eq")
        q_new = q_eq + (q - q_eq) * factor
        if np.any(q_new < -1.0e-15) or np.any(q_new > 1.0 + 1.0e-15):
            raise HNEShadowPipelineError("exact relaxation produced invalid q")
        out = np.array(U, dtype=float, copy=True)
        out[..., IDX_RHO_XV] = rho * np.clip(q_new, 0.0, 1.0)
        if not np.array_equal(out[..., :IDX_RHO_XV], U[..., :IDX_RHO_XV]):
            raise HNEShadowPipelineError("quality source damaged hydrodynamic U")
        return out


@dataclass(frozen=True)
class ShadowObservation:
    step_row: dict[str, object]
    cell_rows: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class HNEThermodynamicShadowObserver:
    closure: SurrogateFrozenQualityThermodynamicClosure = field(
        default_factory=SurrogateFrozenQualityThermodynamicClosure
    )

    def assert_compatible(self, eos: object) -> None:
        if not isinstance(eos, LCO2PropertyEOSAdapter):
            raise HNEShadowPipelineError("shadow requires LCO2PropertyEOSAdapter")
        if eos.quality_source != "backend":
            raise HNEShadowPipelineError("HEM backend quality must retain flux/CFL authority")
        if eos.backend_name != EXPECTED_BACKEND_NAME:
            raise HNEShadowPipelineError("only surrogate_lco2 is allowed")
        if type(eos.backend) is not SurrogateLCO2PropertyBackend:
            raise HNEShadowPipelineError("unexpected authoritative backend type")
        if eos.backend != self.closure.backend:
            raise HNEShadowPipelineError("authoritative and shadow backend parameters differ")

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
        state_sha = _array_sha(U)
        rho = np.asarray(U[..., IDX_RHO], dtype=float)
        u = np.asarray(velocity(U), dtype=float)
        e = np.asarray(internal_energy(U), dtype=float)
        q = np.asarray(vapor_mass_fraction(U), dtype=float)
        hem = self.closure.backend.state_from_rho_e(rho, e)
        cells: list[dict[str, object]] = []
        for i in range(grid.n_cells):
            try:
                hne = self.closure.evaluate(float(rho[i]), float(e[i]), float(q[i]))
            except HNEThermodynamicClosureError as exc:
                raise HNEShadowPipelineError(
                    f"A2 closure failed at step={step}, cell={i}: {exc}"
                ) from exc
            residual = (
                (1.0 - hne.vapor_mass_fraction) / hne.liquid_density_kg_m3
                + hne.vapor_mass_fraction / hne.vapor_density_kg_m3
                - 1.0 / hne.rho_kg_m3
            )
            row = {
                "case_id": case_id,
                "tau_s": _tau_value(tau_s),
                "step": step,
                "time_s": float(time_s),
                "dt_s": float(dt_s),
                "cell_index": i,
                "x_m": float(grid.cell_centers[i]),
                "rho_kg_m3": float(rho[i]),
                "u_m_s": float(u[i]),
                "e_j_kg": float(e[i]),
                "q_transport": float(q[i]),
                "q_equilibrium": hne.equilibrium_vapor_mass_fraction,
                "signed_q_lag": hne.equilibrium_vapor_mass_fraction - hne.vapor_mass_fraction,
                "p_hem_pa": float(hem.p[i]),
                "p_hne_shadow_pa": hne.pressure_pa,
                "delta_p_hne_minus_hem_pa": hne.pressure_pa - float(hem.p[i]),
                "T_hem_K": float(hem.T[i]),
                "T_hne_shadow_K": hne.temperature_K,
                "delta_T_hne_minus_hem_K": hne.temperature_K - float(hem.T[i]),
                "alpha_hem": float(hem.alpha[i]),
                "alpha_hne_shadow": hne.void_fraction,
                "delta_alpha_hne_minus_hem": hne.void_fraction - float(hem.alpha[i]),
                "c_hem_m_s": float(hem.c[i]),
                "c_hne_diagnostic_m_s": hne.acoustic_speed_diagnostic_m_s,
                "volume_residual_m3_kg": residual,
                "shadow_acoustic_authority": hne.acoustic_authority,
            }
            numeric = [value for key, value in row.items() if key not in {"case_id", "tau_s", "shadow_acoustic_authority"}]
            if not all(math.isfinite(float(value)) for value in numeric):
                raise HNEShadowPipelineError(f"nonfinite shadow value at step={step}, cell={i}")
            cells.append(row)
        if _array_sha(U) != state_sha:
            raise HNEShadowPipelineError("shadow observer mutated authoritative U")
        step_row = {
            "case_id": case_id,
            "tau_s": _tau_value(tau_s),
            "step": step,
            "time_s": float(time_s),
            "dt_s": float(dt_s),
            "state_sha256": state_sha,
            "hydrodynamic_state_sha256": _array_sha(U[..., :IDX_RHO_XV]),
            "q_min": float(np.min(q)),
            "q_max": float(np.max(q)),
            "maximum_absolute_q_lag": _max_abs(cells, "signed_q_lag"),
            "maximum_absolute_pressure_delta_pa": _max_abs(cells, "delta_p_hne_minus_hem_pa"),
            "maximum_absolute_temperature_delta_K": _max_abs(cells, "delta_T_hne_minus_hem_K"),
            "maximum_absolute_alpha_delta": _max_abs(cells, "delta_alpha_hne_minus_hem"),
            "maximum_absolute_volume_residual_m3_kg": _max_abs(cells, "volume_residual_m3_kg"),
            "closure_success_count": grid.n_cells,
            "closure_failure_count": 0,
            "authoritative_acoustic_authority": AUTHORITATIVE_ACOUSTIC_AUTHORITY,
            "shadow_acoustic_authority": ACOUSTIC_AUTHORITY,
            "shadow_state_read_only": True,
        }
        return ShadowObservation(step_row=step_row, cell_rows=tuple(cells))


@dataclass(frozen=True)
class ShadowPipelineAnalysis:
    summary: dict[str, object]
    case_rows: tuple[dict[str, object], ...]
    step_rows: tuple[dict[str, object], ...]
    cell_rows: tuple[dict[str, object], ...]


def _max_abs(rows: Sequence[dict[str, object]], key: str) -> float:
    return max(abs(float(row[key])) for row in rows)


def _tau_value(tau_s: float) -> float | str:
    return "INF" if math.isinf(tau_s) else float(tau_s)


def _array_sha(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array, dtype=float).tobytes()).hexdigest()


def _payload_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
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
        "git_status_porcelain": run("git", "status", "--porcelain=v1", "--untracked-files=all"),
    }


def _constructed_rho_e(config: ShadowPipelineConfig, backend: SurrogateLCO2PropertyBackend) -> tuple[float, float]:
    q = config.constructed_equilibrium_q
    rho = 1.0 / ((1.0 - q) / backend.rho_l_ref_kg_m3 + q / backend.rho_v_ref_kg_m3)
    cv = (1.0 - q) * backend.cv_liquid_j_kgK + q * backend.cv_vapor_j_kgK
    e = backend.e_l_ref_j_kg + q * backend.latent_heat_ref_j_kg + cv * (
        config.constructed_temperature_K - backend.T_sat_ref_K
    )
    return float(rho), float(e)


def _initial_state(config: ShadowPipelineConfig, backend: SurrogateLCO2PropertyBackend) -> np.ndarray:
    rho, e = _constructed_rho_e(config, backend)
    q = np.full(config.n_cells, config.right_initial_q, dtype=float)
    q[: config.n_cells // 2] = config.left_initial_q
    U = make_conserved(
        np.full(config.n_cells, rho),
        np.full(config.n_cells, config.initial_velocity_m_s),
        np.full(config.n_cells, e),
        q,
    )
    check_physical_state(U, names=["A2.3 initial U"])
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
    grid = UniformGrid(PipeGeometry(config.length_m, config.diameter_m), config.n_cells)
    phase = NoPhaseChange() if no_phase_change else TransportedQualityExactRelaxation(tau_s)
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=_initial_state(config, backend),
        cfl=config.cfl,
        phase_change=phase,
        enable_boundary_budget=False,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    return solver, SurrogateFrozenQualityThermodynamicClosure(backend=backend)


def _run(
    case_id: str,
    tau_s: float,
    config: ShadowPipelineConfig,
    *,
    with_shadow: bool,
    no_phase_change: bool = False,
) -> dict[str, object]:
    solver, closure = _build_solver(config, tau_s, no_phase_change=no_phase_change)
    observer = HNEThermodynamicShadowObserver(closure)
    initial_inventory = inventory(solver.U, solver.grid.dx, solver.grid.geometry.area_m2)
    state_hashes = [_array_sha(solver.U)]
    hydro_hashes = [_array_sha(solver.U[..., :IDX_RHO_XV])]
    steps: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []

    def observe(dt_s: float) -> None:
        observation = observer.observe(
            case_id=case_id,
            tau_s=tau_s,
            U=solver.U,
            eos=solver.eos,
            grid=solver.grid,
            step=solver.step_count,
            time_s=solver.t,
            dt_s=dt_s,
        )
        steps.append(observation.step_row)
        cells.extend(observation.cell_rows)

    if with_shadow:
        observe(0.0)
    for _ in range(config.n_steps):
        dt = float(solver.compute_dt())
        accepted = float(solver.step(dt))
        if accepted != dt:
            raise HNEShadowPipelineError("focused case changed candidate dt")
        state_hashes.append(_array_sha(solver.U))
        hydro_hashes.append(_array_sha(solver.U[..., :IDX_RHO_XV]))
        if with_shadow:
            observe(accepted)
    return {
        "trajectory": tuple(state_hashes),
        "hydro_trajectory": tuple(hydro_hashes),
        "initial_inventory": initial_inventory,
        "final_inventory": inventory(solver.U, solver.grid.dx, solver.grid.geometry.area_m2),
        "final_q": np.asarray(vapor_mass_fraction(solver.U), dtype=float).copy(),
        "step_rows": tuple(steps),
        "cell_rows": tuple(cells),
        "initial_state_sha256": state_hashes[0],
        "final_state_sha256": state_hashes[-1],
        "step_count": solver.step_count,
        "final_time_s": solver.t,
    }


def _conserved(run: dict[str, object]) -> bool:
    initial = run["initial_inventory"]
    final = run["final_inventory"]
    assert isinstance(initial, dict) and isinstance(final, dict)
    for key in ("mass_total", "momentum_total", "energy_total"):
        a, b = float(initial[key]), float(final[key])
        tol = 256.0 * np.finfo(float).eps * max(abs(a), 1.0)
        if abs(b - a) > tol:
            return False
    return True


def _case_row(
    case_id: str,
    tau_s: float,
    baseline: dict[str, object],
    shadow: dict[str, object],
    no_phase: dict[str, object] | None,
) -> dict[str, object]:
    final_step = shadow["step_rows"][-1]
    initial = shadow["initial_inventory"]
    final = shadow["final_inventory"]
    assert isinstance(initial, dict) and isinstance(final, dict)
    q = np.asarray(shadow["final_q"], dtype=float)
    return {
        "case_id": case_id,
        "tau_s": _tau_value(tau_s),
        "step_count": shadow["step_count"],
        "final_time_s": shadow["final_time_s"],
        "baseline_shadow_full_trajectory_bitwise_equal": baseline["trajectory"] == shadow["trajectory"],
        "baseline_shadow_hydrodynamic_trajectory_bitwise_equal": baseline["hydro_trajectory"] == shadow["hydro_trajectory"],
        "hydrodynamic_state_unchanged_from_initial": len(set(shadow["hydro_trajectory"])) == 1,
        "mass_momentum_energy_conserved": _conserved(shadow),
        "q_min_final": float(np.min(q)),
        "q_max_final": float(np.max(q)),
        "maximum_absolute_q_lag_final": final_step["maximum_absolute_q_lag"],
        "maximum_absolute_pressure_delta_pa_final": final_step["maximum_absolute_pressure_delta_pa"],
        "maximum_absolute_temperature_delta_K_final": final_step["maximum_absolute_temperature_delta_K"],
        "maximum_absolute_alpha_delta_final": final_step["maximum_absolute_alpha_delta"],
        "maximum_absolute_volume_residual_m3_kg_final": final_step["maximum_absolute_volume_residual_m3_kg"],
        "all_shadow_states_read_only": all(row["shadow_state_read_only"] for row in shadow["step_rows"]),
        "all_closure_calls_succeeded": all(row["closure_failure_count"] == 0 for row in shadow["step_rows"]),
        "frozen_source_matches_no_phase_change": None if no_phase is None else baseline["trajectory"] == no_phase["trajectory"],
        "mass_residual_kg": float(final["mass_total"]) - float(initial["mass_total"]),
        "momentum_residual_kg_m_s": float(final["momentum_total"]) - float(initial["momentum_total"]),
        "energy_residual_J": float(final["energy_total"]) - float(initial["energy_total"]),
        "initial_state_sha256": shadow["initial_state_sha256"],
        "final_state_sha256": shadow["final_state_sha256"],
    }


def analyze_shadow_pipeline(config: ShadowPipelineConfig | None = None) -> ShadowPipelineAnalysis:
    config = config or ShadowPipelineConfig()
    cases: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    runs: dict[str, dict[str, object]] = {}
    for case_id, tau_s in TAU_CASES:
        baseline = _run(case_id, tau_s, config, with_shadow=False)
        shadow = _run(case_id, tau_s, config, with_shadow=True)
        no_phase = (
            _run("NO_PHASE_REFERENCE", tau_s, config, with_shadow=False, no_phase_change=True)
            if case_id == "TAU_FROZEN"
            else None
        )
        cases.append(_case_row(case_id, tau_s, baseline, shadow, no_phase))
        steps.extend(shadow["step_rows"])
        cells.extend(shadow["cell_rows"])
        runs[case_id] = shadow

    repeat = _run("TAU_FINITE", 1.0e-4, config, with_shadow=True)
    finite_run = runs["TAU_FINITE"]
    reproducible = (
        finite_run["trajectory"] == repeat["trajectory"]
        and _payload_sha(finite_run["step_rows"]) == _payload_sha(repeat["step_rows"])
        and _payload_sha(finite_run["cell_rows"]) == _payload_sha(repeat["cell_rows"])
    )
    by_id = {row["case_id"]: row for row in cases}
    near, finite, frozen = by_id["TAU_NEAR_ZERO"], by_id["TAU_FINITE"], by_id["TAU_FROZEN"]
    maturity_closed = all(
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
        ("SURROGATE_BACKEND_CONTRACT_RETAINED", True),
        ("AUTHORITATIVE_HEM_FLUX_CFL_RETAINED", True),
        ("SHADOW_OBSERVER_READ_ONLY", all(row["baseline_shadow_full_trajectory_bitwise_equal"] and row["all_shadow_states_read_only"] for row in cases)),
        ("AUTHORITATIVE_HYDRODYNAMIC_TRAJECTORY_UNCHANGED", all(row["baseline_shadow_hydrodynamic_trajectory_bitwise_equal"] and row["hydrodynamic_state_unchanged_from_initial"] for row in cases)),
        ("ALL_SHADOW_CLOSURES_SUCCEEDED", all(row["all_closure_calls_succeeded"] for row in cases)),
        ("ALL_STATES_FINITE_AND_Q_BOUNDED", all(0.0 <= float(row["q_min_final"]) <= float(row["q_max_final"]) <= 1.0 for row in cases)),
        ("MASS_MOMENTUM_ENERGY_NOT_DAMAGED", all(row["mass_momentum_energy_conserved"] for row in cases)),
        ("TAU_TO_ZERO_FINITE_PIPELINE_HEM_LIMIT", float(near["maximum_absolute_q_lag_final"]) <= 1.0e-15 and float(near["maximum_absolute_pressure_delta_pa_final"]) <= 1.0e-8 and float(near["maximum_absolute_temperature_delta_K_final"]) <= 1.0e-12 and float(near["maximum_absolute_alpha_delta_final"]) <= 1.0e-12),
        ("FINITE_TAU_THERMODYNAMIC_DIFFERENCE_VISIBLE", float(finite["maximum_absolute_q_lag_final"]) > 1.0e-8 and float(finite["maximum_absolute_pressure_delta_pa_final"]) > 1.0 and float(finite["maximum_absolute_temperature_delta_K_final"]) > 1.0e-6 and float(finite["maximum_absolute_alpha_delta_final"]) > 1.0e-9),
        ("TAU_INFINITY_SOURCE_EQUALS_NO_PHASE_CHANGE", frozen["frozen_source_matches_no_phase_change"] is True),
        ("VOLUME_CLOSURE_RESIDUAL_WITHIN_TOLERANCE", all(float(row["maximum_absolute_volume_residual_m3_kg_final"]) <= 1.0e-12 for row in cases)),
        ("DETERMINISTIC_REPRODUCIBILITY", reproducible),
        ("NON_EQUILIBRIUM_ACOUSTIC_REMAINS_DIAGNOSTIC_ONLY", True),
        ("HYDRODYNAMIC_COUPLING_GATE_REMAINS_CLOSED", FORMAL_STATUS["hydrodynamic_coupling_allowed"] is False),
        ("MATURITY_NOT_PROMOTED", maturity_closed),
    ]
    gate_rows = [{"gate": name, "passed": bool(passed)} for name, passed in gates]
    failed = [name for name, passed in gates if not passed]
    ready = not failed
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "p2_a2_3_finite_pipeline_hne_shadow_integration",
        "source_a2_sha": SOURCE_A2_SHA,
        "configuration": asdict(config),
        "case_matrix": [{"case_id": name, "tau_s": _tau_value(tau)} for name, tau in TAU_CASES],
        "backend_contract": {
            "authoritative_backend": EXPECTED_BACKEND_NAME,
            "authoritative_eos_quality_source": "backend",
            "authoritative_pressure_temperature_sound_speed": "HEM_BACKEND",
            "transported_quality_storage": "RHO_Q_CONSERVATIVE_SCALAR",
            "shadow_closure": "SurrogateFrozenQualityThermodynamicClosure",
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
        "case_summary": cases,
        "gates": gate_rows,
        "gate_results": {name: bool(passed) for name, passed in gates},
        "failed_gates": failed,
        "a2_3_shadow_ready": ready,
        "execution_status": "A2_3_FINITE_PIPELINE_SHADOW_READY_WITH_COUPLING_GATE_CLOSED" if ready else "FAIL_CLOSED",
        "physical_hne_claim_allowed": False,
        "hydrodynamic_coupling_allowed": False,
        "acoustic_authority": {"authoritative": AUTHORITATIVE_ACOUSTIC_AUTHORITY, "shadow": ACOUSTIC_AUTHORITY},
        "interpretation": {
            "shadow_integration": "A2_THERMODYNAMIC_STATE_RECONSTRUCTION_ON_ACCEPTED_FINITE_PIPELINE_STATES",
            "tau_to_zero_limit": "FINITE_PIPELINE_HEM_LIMIT_RETAINED",
            "finite_tau_behavior": "THERMODYNAMIC_DIFFERENCE_VISIBLE_WITHOUT_HYDRODYNAMIC_FEEDBACK",
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
        "next_phase_decision": "PROCEED_TO_A2_4_NONEQUILIBRIUM_ACOUSTIC_CLOSURE_DESIGN" if ready else "STOP_AND_DIAGNOSE_A2_3_SHADOW_INTEGRATION",
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
    return ShadowPipelineAnalysis(summary, tuple(cases), tuple(steps), tuple(cells))


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
        "HEM backend pressure, temperature and sound speed retain FVM authority.",
        "The A2 closure is evaluated read-only after accepted steps.",
        "",
        "| case | tau [s] | max |q-qeq| | max |dp| [Pa] | max |dT| [K] | no effect |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in summary["case_summary"]:
        lines.append(
            "| {case} | {tau} | {q:.8g} | {p:.8g} | {T:.8g} | {same} |".format(
                case=row["case_id"],
                tau=row["tau_s"],
                q=float(row["maximum_absolute_q_lag_final"]),
                p=float(row["maximum_absolute_pressure_delta_pa_final"]),
                T=float(row["maximum_absolute_temperature_delta_K_final"]),
                same=row["baseline_shadow_full_trajectory_bitwise_equal"],
            )
        )
    lines += [
        "",
        "## Decision",
        "",
        "Retain this increment as diagnostic shadow evidence only. The coupling",
        "gate stays closed pending a defensible nonequilibrium acoustic closure.",
        "",
        "## Maturity",
        "",
        "- IMPLEMENTED / FINITE-PIPELINE SHADOW: true",
        "- HYDRODYNAMIC COUPLING / PHYSICAL HNE / WORKING SLICE: false",
        "- VERIFIED / ACCEPTED / VALIDATED / DESIGN-USE / PRODUCTION: false",
        "",
    ]
    return "\n".join(lines)


def write_artifacts(output_dir: str | Path, analysis: ShadowPipelineAnalysis) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    unexpected = {p.name for p in target.iterdir() if p.is_file()} - expected
    if unexpected:
        raise HNEShadowPipelineError(f"unexpected output files: {sorted(unexpected)}")
    paths = {
        "summary": target / "summary.json",
        "cases": target / "case_summary.csv",
        "steps": target / "step_history.csv",
        "cells": target / "cell_history.csv",
        "report": target / "operator_report.md",
        "manifest": target / "manifest.json",
    }
    paths["summary"].write_text(json.dumps(analysis.summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    _write_csv(paths["cases"], analysis.case_rows)
    _write_csv(paths["steps"], analysis.step_rows)
    _write_csv(paths["cells"], analysis.cell_rows)
    paths["report"].write_text(_report(analysis.summary), encoding="utf-8")
    payload = {key: path for key, path in paths.items() if key != "manifest"}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "analysis_sha256": analysis.summary["analysis_sha256"],
        "a2_3_shadow_ready": analysis.summary["a2_3_shadow_ready"],
        "hydrodynamic_coupling_allowed": False,
        "payload_files": {
            path.name: {"size_bytes": path.stat().st_size, "sha256": _file_sha(path)}
            for path in payload.values()
        },
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    actual = {p.name for p in target.iterdir() if p.is_file()}
    if actual != expected:
        raise HNEShadowPipelineError(f"artifact mismatch: {sorted(actual)}")
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    analysis = analyze_shadow_pipeline()
    paths = write_artifacts(output_dir, analysis)
    return {**analysis.summary, "artifact_paths": {key: str(path) for key, path in paths.items()}}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["a2_3_shadow_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
