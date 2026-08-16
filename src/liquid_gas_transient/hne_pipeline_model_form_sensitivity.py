"""Stage 7 P2-A1 HEM/HNE quality-relaxation model-form sensitivity.

This verification-only increment starts one accepted step before the locked P1
first thermodynamic crossing and advances the unchanged first-order FVM path
through the crossing plus 64 post-crossing steps.  The HEM reference uses the
existing instantaneous phase-change operator.  HNE cases use the existing exact
exponential relaxation operator for transported vapor mass fraction.

The mechanical/thermal closure remains the reviewed equilibrium ``rho/e``
closure.  Only transported vapor quality and its diagnostic homogeneous void
fraction are allowed to lag.  This is therefore a single-pressure,
single-temperature quality-relaxation scaffold, not a complete physical HNE,
nucleation, metastability, or two-temperature model.  Relaxation times are
predeclared sensitivity parameters and are not validated material properties.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .boundary import LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from . import hem_pipeline_post_crossing_propagation as gate6
from .hem_pipeline_depressurization_boundary import (
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    run_pipeline_depressurization_case,
)
from .phase_change import HEMPhaseChange, HNERelaxationPhaseChange
from .solver import FvmSolver
from .state import (
    IDX_RHO,
    N_VARS,
    PrimitiveState,
    internal_energy,
    inventory,
    vapor_mass_fraction,
)

P2_A1_SCHEMA_VERSION = "stage7_p2_hne_model_form_sensitivity_a1_v1"
P2_A1_MODEL_ID = "HNE_QUALITY_RELAXATION_SCAFFOLD"
P2_A1_BASELINE_CASE_ID = "pipeline_crossing_candidate_p5m5_to_p2m5"
P2_A1_SOURCE_CLOSEOUT_SHA = "7ed7d71a35676a8160643eb7af81ecaebfe90e15"
P2_A1_KINETIC_QUALITY_FLOOR = 1.0e-6
P2_A1_START_STEPS_BEFORE_CROSSING = 1
P2_A1_POST_CROSSING_STEPS = 64
P2_A1_TAU_CASES = (
    ("HNE_TAU_NEAR_ZERO", 1.0e-9),
    ("HNE_TAU_MEDIUM", 1.0e-5),
    ("HNE_TAU_SLOW", 1.0e-4),
)
P2_A1_OUTPUT_FILES = (
    "model_form_summary.json",
    "case_comparison.csv",
    "time_history.csv",
    "cell_history.csv",
    "tau_limit_comparison.csv",
    "quality_lag_comparison.png",
    "phase_front_comparison.png",
    "operator_report.md",
    "model_form_manifest.json",
)
P2_A1_FORMAL_STATUS = {
    "implemented": True,
    "p2_model_form_vertical_slice": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}


class P2HNEModelFormError(RuntimeError):
    """Raised when the bounded P2-A1 comparison cannot proceed safely."""


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _array_sha256(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values, dtype="<f8"))
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""

    return {
        "source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def _baseline_case():
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        if case.case_id == P2_A1_BASELINE_CASE_ID:
            return case
    raise P2HNEModelFormError(
        f"locked P1 baseline case not found: {P2_A1_BASELINE_CASE_ID}"
    )


def _front_distance(mask: np.ndarray, distances_from_outlet_m: np.ndarray) -> float | None:
    active = np.flatnonzero(np.asarray(mask, dtype=bool))
    if active.size == 0:
        return None
    return float(np.max(np.asarray(distances_from_outlet_m, dtype=float)[active]))


def _budget_within(
    diagnostics: dict[str, float],
    name: str,
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> bool:
    absolute = abs(float(diagnostics[f"budget_{name}_residual"]))
    relative = abs(float(diagnostics[f"budget_{name}_relative_residual"]))
    return absolute <= absolute_tolerance or relative <= relative_tolerance


@dataclass
class VerificationHNEQualityRelaxationEOS:
    """Permissive verification EOS for a transported-quality relaxation scaffold.

    Pressure, temperature, equilibrium quality and sound speed are inherited
    from the reviewed HEM ``rho/e`` closure.  The returned primitive ``xv`` is
    the transported quality, not the equilibrium quality.  A diagnostic void
    fraction is reconstructed from transported quality and saturation densities
    at the inherited equilibrium pressure.
    """

    pipeline_config: HEMPipelineDepressurizationConfig = field(
        default_factory=HEMPipelineDepressurizationConfig
    )
    _hem: VerificationHEMLiquidOpenTwoPhaseEOS = field(init=False, repr=False)
    _last_regions: np.ndarray | None = field(init=False, default=None, repr=False)
    _last_equilibrium_quality: np.ndarray | None = field(
        init=False, default=None, repr=False
    )
    _last_equilibrium_alpha: np.ndarray | None = field(
        init=False, default=None, repr=False
    )
    _last_transported_quality: np.ndarray | None = field(
        init=False, default=None, repr=False
    )
    _last_kinetic_alpha: np.ndarray | None = field(
        init=False, default=None, repr=False
    )
    _saturation_density_cache: dict[float, tuple[float, float]] = field(
        init=False, default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        cfg = self.pipeline_config
        self._hem = VerificationHEMLiquidOpenTwoPhaseEOS(
            quality_tolerance=1.0,
            phase_config=cfg.phase_config,
            quality_sync_config=cfg.projection_config,
        )

    @property
    def backend_name(self) -> str:
        return "coolprop_hem_rhoe_with_hne_quality_relaxation_scaffold"

    @property
    def last_regions(self) -> np.ndarray | None:
        return None if self._last_regions is None else np.array(self._last_regions, copy=True)

    @property
    def last_equilibrium_quality(self) -> np.ndarray | None:
        return (
            None
            if self._last_equilibrium_quality is None
            else np.array(self._last_equilibrium_quality, copy=True)
        )

    @property
    def last_equilibrium_alpha(self) -> np.ndarray | None:
        return (
            None
            if self._last_equilibrium_alpha is None
            else np.array(self._last_equilibrium_alpha, copy=True)
        )

    @property
    def last_transported_quality(self) -> np.ndarray | None:
        return (
            None
            if self._last_transported_quality is None
            else np.array(self._last_transported_quality, copy=True)
        )

    @property
    def last_kinetic_alpha(self) -> np.ndarray | None:
        return (
            None
            if self._last_kinetic_alpha is None
            else np.array(self._last_kinetic_alpha, copy=True)
        )

    def _saturation_densities(self, pressure_pa: float) -> tuple[float, float]:
        key = float(pressure_pa)
        cached = self._saturation_density_cache.get(key)
        if cached is not None:
            return cached
        try:
            from CoolProp.CoolProp import PropsSI  # type: ignore

            rho_l = float(PropsSI("Dmass", "P", key, "Q", 0.0, "CO2"))
            rho_v = float(PropsSI("Dmass", "P", key, "Q", 1.0, "CO2"))
        except Exception as exc:
            raise P2HNEModelFormError(
                f"saturation-density reconstruction failed at p={key} Pa"
            ) from exc
        if (
            not math.isfinite(rho_l)
            or not math.isfinite(rho_v)
            or rho_l <= 0.0
            or rho_v <= 0.0
            or rho_l <= rho_v
        ):
            raise P2HNEModelFormError(
                "saturation-density reconstruction returned invalid densities"
            )
        result = (rho_l, rho_v)
        self._saturation_density_cache[key] = result
        return result

    def _kinetic_alpha(self, pressure_pa: np.ndarray, quality: np.ndarray) -> np.ndarray:
        alpha = np.empty_like(quality, dtype=float)
        for index in np.ndindex(quality.shape):
            q = float(quality[index])
            if q <= 0.0:
                alpha[index] = 0.0
                continue
            if q >= 1.0:
                alpha[index] = 1.0
                continue
            rho_l, rho_v = self._saturation_densities(float(pressure_pa[index]))
            vapor_volume = q / rho_v
            liquid_volume = (1.0 - q) / rho_l
            denominator = vapor_volume + liquid_volume
            if not math.isfinite(denominator) or denominator <= 0.0:
                raise P2HNEModelFormError("kinetic void-fraction denominator is invalid")
            alpha[index] = float(np.clip(vapor_volume / denominator, 0.0, 1.0))
        return alpha

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        array = np.asarray(U, dtype=float)
        if array.ndim < 1 or array.shape[-1] != N_VARS:
            raise P2HNEModelFormError("U must have N_VARS entries in its last dimension")
        q_transport = np.asarray(vapor_mass_fraction(array), dtype=float)
        if not np.all(np.isfinite(q_transport)):
            raise P2HNEModelFormError("transported quality contains nonfinite values")
        if np.any(q_transport < -1.0e-12) or np.any(q_transport > 1.0 + 1.0e-12):
            raise P2HNEModelFormError("transported quality lies outside [0, 1]")
        q_transport = np.clip(q_transport, 0.0, 1.0)

        equilibrium = self._hem.primitive_from_conserved(array)
        regions = self._hem.last_regions
        if regions is None:
            raise P2HNEModelFormError("HEM closure did not retain thermodynamic regions")
        q_eq = np.asarray(equilibrium.xv, dtype=float)
        alpha_eq = np.asarray(equilibrium.alpha, dtype=float)
        alpha_kinetic = self._kinetic_alpha(
            np.asarray(equilibrium.p, dtype=float), q_transport
        )
        for values, name in (
            (q_eq, "equilibrium quality"),
            (alpha_eq, "equilibrium void fraction"),
            (alpha_kinetic, "kinetic void fraction"),
        ):
            if not np.all(np.isfinite(values)):
                raise P2HNEModelFormError(f"{name} contains nonfinite values")

        self._last_regions = np.asarray(regions).astype(str)
        self._last_equilibrium_quality = np.array(q_eq, copy=True)
        self._last_equilibrium_alpha = np.array(alpha_eq, copy=True)
        self._last_transported_quality = np.array(q_transport, copy=True)
        self._last_kinetic_alpha = np.array(alpha_kinetic, copy=True)
        return PrimitiveState(
            rho=np.array(equilibrium.rho, copy=True),
            u=np.array(equilibrium.u, copy=True),
            p=np.array(equilibrium.p, copy=True),
            e=np.array(equilibrium.e, copy=True),
            E=np.array(equilibrium.E, copy=True),
            T=np.array(equilibrium.T, copy=True),
            xv=np.array(q_transport, copy=True),
            alpha=np.array(alpha_kinetic, copy=True),
            c=np.array(equilibrium.c, copy=True),
        )

    def equilibrium_vapor_mass_fraction(self, primitive: PrimitiveState) -> np.ndarray:
        if self._last_equilibrium_quality is None:
            raise P2HNEModelFormError(
                "equilibrium quality requested before primitive evaluation"
            )
        if self._last_equilibrium_quality.shape != primitive.xv.shape:
            raise P2HNEModelFormError(
                "equilibrium quality cache shape differs from primitive state"
            )
        return np.array(self._last_equilibrium_quality, copy=True)

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        raise NotImplementedError(
            "P2-A1 uses the reviewed prescribed-state boundary, not EOS inversion"
        )


@dataclass(frozen=True)
class P2A1Config:
    pipeline: HEMPipelineDepressurizationConfig = field(
        default_factory=HEMPipelineDepressurizationConfig
    )
    kinetic_quality_floor: float = P2_A1_KINETIC_QUALITY_FLOOR
    start_steps_before_crossing: int = P2_A1_START_STEPS_BEFORE_CROSSING
    post_crossing_steps: int = P2_A1_POST_CROSSING_STEPS
    tau_cases: tuple[tuple[str, float], ...] = P2_A1_TAU_CASES

    def __post_init__(self) -> None:
        if self.pipeline != HEMPipelineDepressurizationConfig():
            raise ValueError("P2-A1 retains the locked P1 baseline configuration")
        if self.kinetic_quality_floor != 1.0e-6:
            raise ValueError("P2-A1 kinetic quality floor is fixed at 1e-6")
        if self.start_steps_before_crossing != 1:
            raise ValueError("P2-A1 starts exactly one accepted step before crossing")
        if self.post_crossing_steps != 64:
            raise ValueError("P2-A1 continues exactly 64 steps after crossing")
        if self.tau_cases != P2_A1_TAU_CASES:
            raise ValueError("P2-A1 tau sensitivity cases are predeclared")
        if any(not math.isfinite(tau) or tau <= 0.0 for _, tau in self.tau_cases):
            raise ValueError("all relaxation times must be finite and positive")

    @property
    def total_steps(self) -> int:
        return self.start_steps_before_crossing + self.post_crossing_steps


@dataclass(frozen=True)
class _ModelSpec:
    model_id: str
    model_family: str
    tau_s: float | None


MODEL_SPECS = (
    _ModelSpec("HEM_EQUILIBRIUM", "HEM", None),
    *tuple(_ModelSpec(name, "HNE", tau) for name, tau in P2_A1_TAU_CASES),
)


def _source_state(config: P2A1Config):
    case = _baseline_case()
    baseline = run_pipeline_depressurization_case(case, config.pipeline)
    gate6._require_exact_baseline(baseline)
    if baseline.crossing_step is None or baseline.crossing_step <= 0:
        raise P2HNEModelFormError("locked baseline does not retain a positive crossing step")
    start_step = baseline.crossing_step - config.start_steps_before_crossing
    if start_step < 0 or baseline.accepted_state_history.shape[0] <= start_step:
        raise P2HNEModelFormError("pre-crossing accepted source state is unavailable")
    if start_step == 0:
        start_time_s = 0.0
    else:
        record = next(
            (row for row in baseline.steps if row.step_index == start_step), None
        )
        if record is None:
            raise P2HNEModelFormError("pre-crossing source step record is missing")
        start_time_s = float(record.time_after_s)
    return case, baseline, start_step, start_time_s, np.array(
        baseline.accepted_state_history[start_step], dtype=float, copy=True
    )


def _run_model(
    spec: _ModelSpec,
    *,
    config: P2A1Config,
    case,
    baseline,
    start_step: int,
    start_time_s: float,
    start_U: np.ndarray,
) -> dict[str, object]:
    pipeline = config.pipeline
    schedule = LinearPressureRamp(
        p_initial_pa=pipeline.initial_pressure_pa,
        p_final_pa=case.final_boundary_pressure_pa,
        t_start_s=0.0,
        duration_s=baseline.ramp_duration_s,
    )
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=pipeline.subcooling_K,
        phase_config=pipeline.phase_config,
    )
    right_boundary = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    grid = UniformGrid(
        PipeGeometry(length_m=pipeline.length_m, diameter_m=pipeline.diameter_m),
        n_cells=pipeline.n_cells,
    )
    eos = VerificationHNEQualityRelaxationEOS(pipeline_config=pipeline)
    phase_change = (
        HEMPhaseChange()
        if spec.model_family == "HEM"
        else HNERelaxationPhaseChange(tau_s=float(spec.tau_s))
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=np.array(start_U, dtype=float, copy=True),
        cfl=pipeline.cfl,
        n_ghost=pipeline.n_ghost,
        left_boundary=ReflectiveBoundary(),
        right_boundary=right_boundary,
        phase_change=phase_change,
        enable_boundary_budget=True,
        enable_phase_budget=True,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=start_time_s,
        step_count=start_step,
    )
    distances = pipeline.length_m - grid.cell_centers
    history: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    first_thermodynamic_crossing_time_s: float | None = None
    first_kinetic_crossing_time_s: float | None = None
    first_kinetic_crossing_step: int | None = None
    maximum_dt_over_tau = 0.0

    for local_step in range(1, config.total_steps + 1):
        time_before = float(solver.t)
        dt = float(solver.compute_dt())
        if not math.isfinite(dt) or dt <= 0.0:
            raise P2HNEModelFormError(f"{spec.model_id}: computed dt is invalid")
        dt_over_tau = 0.0 if spec.tau_s is None else dt / float(spec.tau_s)
        if not math.isfinite(dt_over_tau) or dt_over_tau < 0.0:
            raise P2HNEModelFormError(f"{spec.model_id}: dt/tau is invalid")
        maximum_dt_over_tau = max(maximum_dt_over_tau, dt_over_tau)
        actual_dt = float(solver.step(dt))
        if actual_dt != dt:
            raise P2HNEModelFormError(
                f"{spec.model_id}: unexpected dt alteration without external hook"
            )
        if right_boundary.reverse_flow_fallback_count != 0:
            raise P2HNEModelFormError(
                f"{spec.model_id}: reverse-flow fallback was activated"
            )

        primitive = solver.primitive()
        regions_value = eos.last_regions
        q_eq_value = eos.last_equilibrium_quality
        alpha_eq_value = eos.last_equilibrium_alpha
        if regions_value is None or q_eq_value is None or alpha_eq_value is None:
            raise P2HNEModelFormError(
                f"{spec.model_id}: EOS diagnostics were not retained"
            )
        regions = np.asarray(regions_value).astype(str)
        q_eq = np.asarray(q_eq_value, dtype=float)
        alpha_eq = np.asarray(alpha_eq_value, dtype=float)
        q_transport = np.asarray(primitive.xv, dtype=float)
        alpha_kinetic = np.asarray(primitive.alpha, dtype=float)
        pressure = np.asarray(primitive.p, dtype=float)
        temperature = np.asarray(primitive.T, dtype=float)
        rho = np.asarray(primitive.rho, dtype=float)
        e = np.asarray(primitive.e, dtype=float)
        arrays = (
            q_eq,
            alpha_eq,
            q_transport,
            alpha_kinetic,
            pressure,
            temperature,
            rho,
            e,
        )
        if any(array.shape != (pipeline.n_cells,) for array in arrays):
            raise P2HNEModelFormError(
                f"{spec.model_id}: diagnostic arrays have incompatible shape"
            )
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise P2HNEModelFormError(
                f"{spec.model_id}: diagnostic arrays contain nonfinite values"
            )
        if np.any(q_transport < -1.0e-12) or np.any(q_transport > 1.0 + 1.0e-12):
            raise P2HNEModelFormError(
                f"{spec.model_id}: transported quality left [0, 1]"
            )
        if np.any(alpha_kinetic < -1.0e-12) or np.any(alpha_kinetic > 1.0 + 1.0e-12):
            raise P2HNEModelFormError(
                f"{spec.model_id}: kinetic void fraction left [0, 1]"
            )

        current_inventory = inventory(
            solver.U, grid.dx, grid.geometry.area_m2
        )
        if solver.boundary_budget is None or solver.phase_budget is None:
            raise P2HNEModelFormError(
                f"{spec.model_id}: boundary and phase budgets are required"
            )
        boundary_diag = solver.boundary_budget.diagnostics(current_inventory)
        phase_diag = solver.phase_budget.diagnostics(
            current_inventory, boundary_budget=solver.boundary_budget
        )
        if not _budget_within(
            boundary_diag,
            "mass",
            absolute_tolerance=pipeline.mass_budget_absolute_tolerance_kg,
            relative_tolerance=pipeline.mass_budget_relative_tolerance,
        ):
            raise P2HNEModelFormError(f"{spec.model_id}: mass budget did not close")
        if not _budget_within(
            boundary_diag,
            "momentum",
            absolute_tolerance=pipeline.momentum_budget_absolute_tolerance_kg_m_s,
            relative_tolerance=pipeline.momentum_budget_relative_tolerance,
        ):
            raise P2HNEModelFormError(
                f"{spec.model_id}: momentum budget did not close"
            )
        if not _budget_within(
            boundary_diag,
            "energy",
            absolute_tolerance=pipeline.energy_budget_absolute_tolerance_J,
            relative_tolerance=pipeline.energy_budget_relative_tolerance,
        ):
            raise P2HNEModelFormError(f"{spec.model_id}: energy budget did not close")
        if (
            abs(float(phase_diag["phase_vapor_mass_balance_residual_kg"]))
            > pipeline.vapor_budget_absolute_tolerance_kg
        ):
            raise P2HNEModelFormError(
                f"{spec.model_id}: vapor/phase budget did not close"
            )

        thermodynamic_mask = regions == "OPEN_TWO_PHASE"
        kinetic_mask = q_transport >= config.kinetic_quality_floor
        relative_pressure_drop = (
            pipeline.initial_pressure_pa - pressure
        ) / pipeline.initial_pressure_pa
        pressure_mask = (
            relative_pressure_drop >= pipeline.pressure_drop_evidence_relative
        )
        pressure_front = _front_distance(pressure_mask, distances)
        thermodynamic_front = _front_distance(thermodynamic_mask, distances)
        kinetic_front = _front_distance(kinetic_mask, distances)
        if first_thermodynamic_crossing_time_s is None and np.any(thermodynamic_mask):
            first_thermodynamic_crossing_time_s = float(solver.t)
        if first_kinetic_crossing_time_s is None and np.any(kinetic_mask):
            first_kinetic_crossing_time_s = float(solver.t)
            first_kinetic_crossing_step = int(solver.step_count)

        lag = q_eq - q_transport
        history.append(
            {
                "model_id": spec.model_id,
                "model_family": spec.model_family,
                "tau_s": spec.tau_s,
                "local_step": local_step,
                "absolute_step": int(solver.step_count),
                "time_before_s": time_before,
                "dt_s": dt,
                "time_s": float(solver.t),
                "dt_over_tau": dt_over_tau,
                "relaxation_factor": (
                    0.0 if spec.tau_s is None else math.exp(-dt_over_tau)
                ),
                "thermodynamic_open_cell_count": int(np.count_nonzero(thermodynamic_mask)),
                "kinetic_open_cell_count": int(np.count_nonzero(kinetic_mask)),
                "pressure_front_distance_from_outlet_m": pressure_front,
                "thermodynamic_phase_front_distance_from_outlet_m": thermodynamic_front,
                "kinetic_phase_front_distance_from_outlet_m": kinetic_front,
                "pressure_to_thermodynamic_separation_m": (
                    None
                    if pressure_front is None or thermodynamic_front is None
                    else pressure_front - thermodynamic_front
                ),
                "pressure_to_kinetic_separation_m": (
                    None
                    if pressure_front is None or kinetic_front is None
                    else pressure_front - kinetic_front
                ),
                "maximum_equilibrium_quality": float(np.max(q_eq, initial=0.0)),
                "maximum_transport_quality": float(np.max(q_transport, initial=0.0)),
                "maximum_signed_quality_lag": float(np.max(lag, initial=0.0)),
                "maximum_absolute_quality_lag": float(np.max(np.abs(lag), initial=0.0)),
                "mean_absolute_quality_lag": float(np.mean(np.abs(lag))),
                "integrated_absolute_quality_lag_m": float(np.sum(np.abs(lag)) * grid.dx),
                "maximum_equilibrium_void_fraction": float(np.max(alpha_eq, initial=0.0)),
                "maximum_kinetic_void_fraction": float(np.max(alpha_kinetic, initial=0.0)),
                "mass_total_kg": float(current_inventory["mass_total"]),
                "momentum_total_kg_m_s": float(current_inventory["momentum_total"]),
                "energy_total_J": float(current_inventory["energy_total"]),
                "vapor_mass_total_kg": float(current_inventory["vapor_mass_total"]),
                "phase_source_last_kg": float(solver.phase_budget.last_source_kg),
                "phase_source_cumulative_kg": float(solver.phase_budget.cumulative_source_kg),
                "boundary_mass_residual_kg": float(boundary_diag["budget_mass_residual"]),
                "boundary_momentum_residual_kg_m_s": float(boundary_diag["budget_momentum_residual"]),
                "boundary_energy_residual_J": float(boundary_diag["budget_energy_residual"]),
                "phase_vapor_residual_kg": float(
                    phase_diag["phase_vapor_mass_balance_residual_kg"]
                ),
                "hydrodynamic_state_sha256": _array_sha256(solver.U[:, :3]),
                "full_state_sha256": gate6._state_sha256(solver.U),
            }
        )
        for cell_index in range(pipeline.n_cells):
            cells.append(
                {
                    "model_id": spec.model_id,
                    "model_family": spec.model_family,
                    "tau_s": spec.tau_s,
                    "local_step": local_step,
                    "absolute_step": int(solver.step_count),
                    "time_s": float(solver.t),
                    "cell_index": cell_index,
                    "cell_center_m": float(grid.cell_centers[cell_index]),
                    "distance_from_outlet_m": float(distances[cell_index]),
                    "thermodynamic_region": str(regions[cell_index]),
                    "rho_kg_m3": float(rho[cell_index]),
                    "internal_energy_j_kg": float(e[cell_index]),
                    "pressure_pa": float(pressure[cell_index]),
                    "temperature_K": float(temperature[cell_index]),
                    "equilibrium_quality": float(q_eq[cell_index]),
                    "transport_quality": float(q_transport[cell_index]),
                    "signed_quality_lag": float(lag[cell_index]),
                    "equilibrium_void_fraction": float(alpha_eq[cell_index]),
                    "kinetic_void_fraction": float(alpha_kinetic[cell_index]),
                    "kinetic_evidence_open": bool(kinetic_mask[cell_index]),
                }
            )

    return {
        "model_id": spec.model_id,
        "model_family": spec.model_family,
        "tau_s": spec.tau_s,
        "completed": True,
        "step_count": len(history),
        "start_absolute_step": start_step,
        "start_time_s": start_time_s,
        "final_absolute_step": int(solver.step_count),
        "final_time_s": float(solver.t),
        "first_thermodynamic_crossing_time_s": first_thermodynamic_crossing_time_s,
        "first_kinetic_crossing_time_s": first_kinetic_crossing_time_s,
        "first_kinetic_crossing_step": first_kinetic_crossing_step,
        "maximum_dt_over_tau": maximum_dt_over_tau,
        "maximum_quality_lag": max(
            float(row["maximum_absolute_quality_lag"]) for row in history
        ),
        "final_quality_lag": float(history[-1]["maximum_absolute_quality_lag"]),
        "final_thermodynamic_phase_front_m": history[-1][
            "thermodynamic_phase_front_distance_from_outlet_m"
        ],
        "final_kinetic_phase_front_m": history[-1][
            "kinetic_phase_front_distance_from_outlet_m"
        ],
        "final_vapor_mass_total_kg": history[-1]["vapor_mass_total_kg"],
        "final_hydrodynamic_state_sha256": history[-1][
            "hydrodynamic_state_sha256"
        ],
        "final_full_state_sha256": history[-1]["full_state_sha256"],
        "reverse_flow_fallback_count": int(right_boundary.reverse_flow_fallback_count),
        "history": history,
        "cells": cells,
    }


def _evaluate(
    *,
    config: P2A1Config,
    baseline,
    model_results: Sequence[dict[str, object]],
) -> tuple[list[dict[str, object]], bool, dict[str, object]]:
    by_id = {str(result["model_id"]): result for result in model_results}
    hem = by_id["HEM_EQUILIBRIUM"]
    near = by_id["HNE_TAU_NEAR_ZERO"]
    medium = by_id["HNE_TAU_MEDIUM"]
    slow = by_id["HNE_TAU_SLOW"]
    expected_ids = [spec.model_id for spec in MODEL_SPECS]
    actual_ids = [str(result["model_id"]) for result in model_results]

    hem_history = hem["history"]
    near_history = near["history"]
    all_histories = [result["history"] for result in model_results]
    exact_hem_limit = all(
        h["full_state_sha256"] == n["full_state_sha256"]
        for h, n in zip(hem_history, near_history)
    )
    hydro_invariant = all(
        tuple(row["hydrodynamic_state_sha256"] for row in history)
        == tuple(row["hydrodynamic_state_sha256"] for row in hem_history)
        for history in all_histories
    )
    thermo_front_invariant = all(
        tuple(row["thermodynamic_phase_front_distance_from_outlet_m"] for row in history)
        == tuple(row["thermodynamic_phase_front_distance_from_outlet_m"] for row in hem_history)
        for history in all_histories
    )
    finite_tau_lag = (
        float(medium["maximum_quality_lag"]) > 0.0
        and float(slow["maximum_quality_lag"]) > 0.0
    )
    lag_ordering = (
        float(near["maximum_quality_lag"])
        <= float(medium["maximum_quality_lag"])
        <= float(slow["maximum_quality_lag"])
    )
    all_complete = all(
        result["completed"] is True
        and int(result["step_count"]) == config.total_steps
        for result in model_results
    )
    no_reverse = all(
        int(result["reverse_flow_fallback_count"]) == 0
        for result in model_results
    )
    event_scalars_finite = all(
        result["first_thermodynamic_crossing_time_s"] is not None
        and math.isfinite(float(result["first_thermodynamic_crossing_time_s"]))
        and result["first_kinetic_crossing_time_s"] is not None
        and math.isfinite(float(result["first_kinetic_crossing_time_s"]))
        for result in model_results
    )
    baseline_exact = (
        baseline.outcome == "ACCEPTED_FIRST_CROSSING"
        and baseline.final_state_sha256 == gate6.EXPECTED_BASELINE["final_state_sha256"]
        and baseline.run_signature_sha256 == gate6.EXPECTED_BASELINE["run_signature_sha256"]
    )
    first_hem = hem_history[0]
    hem_crossing_exact = (
        int(first_hem["absolute_step"]) == int(baseline.crossing_step)
        and math.isclose(
            float(first_hem["time_s"]),
            float(baseline.crossing_time_s),
            rel_tol=0.0,
            abs_tol=0.0,
        )
        and first_hem["full_state_sha256"] == baseline.final_state_sha256
    )
    budgets_finite = all(
        math.isfinite(float(row[key]))
        for history in all_histories
        for row in history
        for key in (
            "boundary_mass_residual_kg",
            "boundary_momentum_residual_kg_m_s",
            "boundary_energy_residual_J",
            "phase_vapor_residual_kg",
        )
    )

    gates = [
        {"gate": "PREDECLARED_MODEL_MATRIX_EXACT", "passed": actual_ids == expected_ids},
        {"gate": "LOCKED_P1_BASELINE_REPRODUCED", "passed": baseline_exact},
        {"gate": "HEM_REFERENCE_REPRODUCES_FIRST_CROSSING", "passed": hem_crossing_exact},
        {"gate": "ALL_MODEL_CASES_COMPLETE", "passed": all_complete},
        {"gate": "NO_REVERSE_FLOW_FALLBACK", "passed": no_reverse},
        {"gate": "BUDGET_DIAGNOSTICS_FINITE_AND_GUARDED", "passed": budgets_finite},
        {"gate": "TAU_TO_ZERO_BITWISE_HEM_LIMIT", "passed": exact_hem_limit},
        {"gate": "HYDRODYNAMIC_PATH_INVARIANT_BY_CONSTRUCTION", "passed": hydro_invariant},
        {"gate": "THERMODYNAMIC_FRONT_INVARIANT_BY_CONSTRUCTION", "passed": thermo_front_invariant},
        {"gate": "FINITE_TAU_QUALITY_LAG_OBSERVED", "passed": finite_tau_lag},
        {"gate": "QUALITY_LAG_NONDECREASING_WITH_TAU", "passed": lag_ordering},
        {"gate": "EVENT_SCALARS_FINITE", "passed": event_scalars_finite},
        {"gate": "TAU_RETAINED_AS_UNVALIDATED_SENSITIVITY_PARAMETER", "passed": True},
        {"gate": "PROJECT_MATURITY_NOT_PROMOTED", "passed": not any(
            P2_A1_FORMAL_STATUS[key]
            for key in (
                "working_vertical_slice",
                "verified",
                "accepted",
                "physically_validated",
                "design_use_accepted",
                "production_approved",
            )
        )},
    ]
    ready = all(bool(gate["passed"]) for gate in gates)
    interpretation = {
        "tau_to_zero_limit": (
            "BITWISE_HEM_LIMIT_REPRODUCED" if exact_hem_limit else "NOT_REPRODUCED"
        ),
        "finite_tau_effect": (
            "TRANSPORTED_QUALITY_AND_KINETIC_PHASE_FRONT_LAG_OBSERVED"
            if finite_tau_lag
            else "NO_RESOLVED_LAG"
        ),
        "hydrodynamic_feedback_in_this_scaffold": (
            "ABSENT_BY_CONSTRUCTION" if hydro_invariant else "UNEXPECTED_DIFFERENCE"
        ),
        "thermodynamic_completeness": "NOT_ESTABLISHED",
        "physical_tau_validation": "NOT_ESTABLISHED",
    }
    return gates, ready, interpretation


def analyze_hne_model_form_sensitivity(
    config: P2A1Config | None = None,
) -> dict[str, object]:
    cfg = config or P2A1Config()
    case, baseline, start_step, start_time_s, start_U = _source_state(cfg)
    model_results = [
        _run_model(
            spec,
            config=cfg,
            case=case,
            baseline=baseline,
            start_step=start_step,
            start_time_s=start_time_s,
            start_U=start_U,
        )
        for spec in MODEL_SPECS
    ]
    gates, ready, interpretation = _evaluate(
        config=cfg, baseline=baseline, model_results=model_results
    )
    case_comparison = [
        {key: value for key, value in result.items() if key not in {"history", "cells"}}
        for result in model_results
    ]
    history = [row for result in model_results for row in result["history"]]
    cells = [row for result in model_results for row in result["cells"]]
    hem = next(row for row in case_comparison if row["model_id"] == "HEM_EQUILIBRIUM")
    tau_limit = []
    for row in case_comparison:
        tau_limit.append(
            {
                "model_id": row["model_id"],
                "tau_s": row["tau_s"],
                "first_thermodynamic_crossing_time_s": row[
                    "first_thermodynamic_crossing_time_s"
                ],
                "first_kinetic_crossing_time_s": row["first_kinetic_crossing_time_s"],
                "kinetic_crossing_delay_from_hem_s": (
                    None
                    if row["first_kinetic_crossing_time_s"] is None
                    else float(row["first_kinetic_crossing_time_s"])
                    - float(hem["first_kinetic_crossing_time_s"])
                ),
                "maximum_quality_lag": row["maximum_quality_lag"],
                "final_quality_lag": row["final_quality_lag"],
                "final_thermodynamic_phase_front_m": row[
                    "final_thermodynamic_phase_front_m"
                ],
                "final_kinetic_phase_front_m": row["final_kinetic_phase_front_m"],
                "final_kinetic_front_lag_m": (
                    None
                    if row["final_thermodynamic_phase_front_m"] is None
                    or row["final_kinetic_phase_front_m"] is None
                    else float(row["final_thermodynamic_phase_front_m"])
                    - float(row["final_kinetic_phase_front_m"])
                ),
                "full_state_matches_hem": row["final_full_state_sha256"]
                == hem["final_full_state_sha256"],
                "hydrodynamic_state_matches_hem": row[
                    "final_hydrodynamic_state_sha256"
                ]
                == hem["final_hydrodynamic_state_sha256"],
            }
        )

    warnings = [
        "HNE_IS_A_SINGLE_PRESSURE_SINGLE_TEMPERATURE_QUALITY_RELAXATION_SCAFFOLD",
        "PRESSURE_TEMPERATURE_AND_SOUND_SPEED_RETAIN_HEM_RHOE_CLOSURE",
        "TAU_VALUES_ARE_UNVALIDATED_SENSITIVITY_PARAMETERS",
        "NO_NUCLEATION_OR_METASTABILITY_MODEL",
        "NO_SLIP_OR_TWO_FLUID_MODEL",
        "HYDRODYNAMIC_FEEDBACK_FROM_NON_EQUILIBRIUM_QUALITY_IS_ABSENT_BY_CONSTRUCTION",
        "P1_MESH_AND_CFL_LIMITATIONS_REMAIN_ACTIVE",
        "PRESCRIBED_DEPRESSURIZATION_IS_NOT_FULL_PHYSICAL_DISCHARGE_FEEDBACK",
    ]
    payload = {
        "schema_version": P2_A1_SCHEMA_VERSION,
        "scope": "p2_hne_quality_relaxation_model_form_vertical_slice",
        "model_id": P2_A1_MODEL_ID,
        "source_p1_closeout_sha": P2_A1_SOURCE_CLOSEOUT_SHA,
        "case_id": case.case_id,
        "start_absolute_step": start_step,
        "start_time_s": start_time_s,
        "source_crossing_step": baseline.crossing_step,
        "source_crossing_time_s": baseline.crossing_time_s,
        "fixed_kinetic_quality_floor": cfg.kinetic_quality_floor,
        "total_accepted_steps_per_model": cfg.total_steps,
        "post_crossing_steps": cfg.post_crossing_steps,
        "tau_cases": [
            {"model_id": name, "tau_s": tau, "parameter_status": "ASSUMED_SENSITIVITY_PARAMETER"}
            for name, tau in cfg.tau_cases
        ],
        "case_comparison": case_comparison,
        "time_history": history,
        "cell_history": cells,
        "tau_limit_comparison": tau_limit,
        "gates": gates,
        "gate_results": {str(gate["gate"]): bool(gate["passed"]) for gate in gates},
        "model_form_slice_ready": ready,
        "execution_status": (
            "WORKING_MODEL_FORM_SLICE_WITH_EXPLICIT_LIMITATIONS"
            if ready
            else "FAIL_CLOSED"
        ),
        "interpretation": interpretation,
        "warnings": warnings,
        "next_phase_decision": (
            "PROCEED_TO_P2_A2_RELAXATION_SENSITIVITY_AND_THERMODYNAMIC_CLOSURE_REFINEMENT"
            if ready
            else "STOP_AND_DIAGNOSE_P2_A1"
        ),
        "provenance": _git_provenance(),
        "formal_status": dict(P2_A1_FORMAL_STATUS),
    }
    digest_payload = dict(payload)
    payload["model_form_sha256"] = _canonical_json_sha256(digest_payload)
    return payload


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise P2HNEModelFormError(f"cannot write empty CSV: {path.name}")
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        json.dumps(value, sort_keys=True, separators=(",", ":"))
                        if isinstance(value, (list, tuple, dict))
                        else value
                    )
                    for key, value in row.items()
                }
            )


def _plot_quality_lag(path: Path, summary: dict[str, object]) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    for case in summary["case_comparison"]:
        model_id = case["model_id"]
        rows = [row for row in summary["time_history"] if row["model_id"] == model_id]
        time_us = 1.0e6 * np.asarray(
            [float(row["time_s"]) - float(summary["source_crossing_time_s"]) for row in rows]
        )
        lag = np.asarray([float(row["maximum_absolute_quality_lag"]) for row in rows])
        ax.plot(time_us, lag, label=str(model_id))
    ax.set_xlabel("Time relative to P1 thermodynamic crossing [microseconds]")
    ax.set_ylabel("Maximum |q_eq - q_transport| [-]")
    ax.set_title("P2-A1 transported-quality relaxation lag")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_phase_front(path: Path, summary: dict[str, object]) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    for case in summary["case_comparison"]:
        model_id = case["model_id"]
        rows = [row for row in summary["time_history"] if row["model_id"] == model_id]
        time_us = 1.0e6 * np.asarray(
            [float(row["time_s"]) - float(summary["source_crossing_time_s"]) for row in rows]
        )
        kinetic = np.asarray(
            [
                np.nan
                if row["kinetic_phase_front_distance_from_outlet_m"] is None
                else float(row["kinetic_phase_front_distance_from_outlet_m"])
                for row in rows
            ]
        )
        ax.plot(time_us, kinetic, label=f"{model_id} kinetic front")
    hem_rows = [
        row for row in summary["time_history"] if row["model_id"] == "HEM_EQUILIBRIUM"
    ]
    time_us = 1.0e6 * np.asarray(
        [float(row["time_s"]) - float(summary["source_crossing_time_s"]) for row in hem_rows]
    )
    thermo = np.asarray(
        [
            np.nan
            if row["thermodynamic_phase_front_distance_from_outlet_m"] is None
            else float(row["thermodynamic_phase_front_distance_from_outlet_m"])
            for row in hem_rows
        ]
    )
    ax.plot(time_us, thermo, linestyle="--", label="Thermodynamic rho/e front")
    ax.set_xlabel("Time relative to P1 thermodynamic crossing [microseconds]")
    ax.set_ylabel("Distance from outlet [m]")
    ax.set_title("P2-A1 thermodynamic and kinetic phase-front comparison")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _operator_report(summary: dict[str, object]) -> str:
    lines = [
        "# P2-A1 HEM / HNE Model-Form Sensitivity",
        "",
        f"- execution status: `{summary['execution_status']}`",
        f"- tau -> 0 result: `{summary['interpretation']['tau_to_zero_limit']}`",
        f"- finite-tau result: `{summary['interpretation']['finite_tau_effect']}`",
        "- pressure/T/sound-speed closure: `HEM rho/e closure retained`",
        "- tau status: `assumed sensitivity parameter; not validated`",
        "",
        "## Case summary",
        "",
        "| model | tau [s] | kinetic crossing [ms] | max q lag | final thermo front [m] | final kinetic front [m] |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["case_comparison"]:
        crossing = row["first_kinetic_crossing_time_s"]
        lines.append(
            "| {model} | {tau} | {crossing} | {lag:.12g} | {thermo} | {kinetic} |".format(
                model=row["model_id"],
                tau="HEM" if row["tau_s"] is None else f"{float(row['tau_s']):.6g}",
                crossing=(
                    "N/A" if crossing is None else f"{1.0e3 * float(crossing):.9f}"
                ),
                lag=float(row["maximum_quality_lag"]),
                thermo=row["final_thermodynamic_phase_front_m"],
                kinetic=row["final_kinetic_phase_front_m"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "The near-zero tau case reproduces the HEM state path. Finite tau "
                "delays transported quality and the kinetic evidence front while "
                "mass, momentum, energy, pressure, temperature and the thermodynamic "
                "rho/e front remain identical by construction."
            ),
            "",
            (
                "This is a model-form software scaffold. It is not a complete HNE "
                "thermodynamic closure, does not model nucleation/metastability, and "
                "does not identify a physical relaxation time."
            ),
            "",
            "## Formal maturity boundary",
            "",
            "- IMPLEMENTED: true",
            "- P2 MODEL-FORM VERTICAL SLICE: true",
            "- PROJECT WORKING VERTICAL SLICE: false",
            "- VERIFIED: false",
            "- ACCEPTED: false",
            "- PHYSICALLY VALIDATED: false",
            "- DESIGN-USE ACCEPTED: false",
            "- PRODUCTION APPROVED: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_hne_model_form_artifacts(
    output_dir: str | Path,
    summary: dict[str, object],
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P2_A1_OUTPUT_FILES)
    existing = {path.name for path in target.iterdir() if path.is_file()}
    unexpected = existing - expected
    if unexpected:
        raise P2HNEModelFormError(
            f"output directory contains unexpected files: {sorted(unexpected)}"
        )
    paths = {
        "summary": target / "model_form_summary.json",
        "cases": target / "case_comparison.csv",
        "history": target / "time_history.csv",
        "cells": target / "cell_history.csv",
        "tau_limit": target / "tau_limit_comparison.csv",
        "quality_plot": target / "quality_lag_comparison.png",
        "front_plot": target / "phase_front_comparison.png",
        "operator_report": target / "operator_report.md",
        "manifest": target / "model_form_manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["cases"], summary["case_comparison"])
    _write_csv(paths["history"], summary["time_history"])
    _write_csv(paths["cells"], summary["cell_history"])
    _write_csv(paths["tau_limit"], summary["tau_limit_comparison"])
    _plot_quality_lag(paths["quality_plot"], summary)
    _plot_phase_front(paths["front_plot"], summary)
    paths["operator_report"].write_text(
        _operator_report(summary), encoding="utf-8"
    )

    payload_files: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if key == "manifest":
            continue
        payload_files[path.name] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": P2_A1_SCHEMA_VERSION,
        "artifact_contract": "stage7_p2_hne_model_form_sensitivity_exactly_9_files",
        "declared_file_count": len(P2_A1_OUTPUT_FILES),
        "declared_file_names": list(P2_A1_OUTPUT_FILES),
        "execution_status": summary["execution_status"],
        "model_form_slice_ready": summary["model_form_slice_ready"],
        "model_form_sha256": summary["model_form_sha256"],
        "source_p1_closeout_sha": P2_A1_SOURCE_CLOSEOUT_SHA,
        "payload_files": payload_files,
        "formal_status": dict(P2_A1_FORMAL_STATUS),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P2HNEModelFormError(
            f"P2-A1 output contract mismatch: expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    summary = analyze_hne_model_form_sensitivity()
    paths = write_hne_model_form_artifacts(output_dir, summary)
    output = dict(summary)
    output["artifact_paths"] = {key: str(path) for key, path in paths.items()}
    return output


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the P2-A1 HEM/HNE transported-quality relaxation comparison "
            "without changing the P1 authorities or production defaults."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["model_form_slice_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
