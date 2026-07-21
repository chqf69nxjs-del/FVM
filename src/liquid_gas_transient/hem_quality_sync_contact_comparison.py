"""Verification-only equal-pressure HEM contact and projection contrast.

The equal-pressure case is a negative control for the merged equilibrium-quality
projection. First-order Rusanov transport must spread the stationary quality
contact, but conservative mixing of two states on one saturation line should
remain in equilibrium. The projection should therefore update zero cells. The
runner compares that result with the merged weak pressure-offset activated case.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .config import PipeGeometry
from .grid import UniformGrid
from .hem_equilibrium_quality_sync import (
    HEMEquilibriumQualityProjection,
    HEMEquilibriumQualitySyncConfig as ProjectionConfig,
)
from .hem_nonuniform_quality_sync import (
    HEMNonuniformQualitySyncConfig,
    HEMNonuniformQualitySyncResult,
    run_nonuniform_hem_quality_sync,
)
from .hem_uniform_state_preservation import VerificationHEMEquilibriumEOS
from .solver import FvmSolver
from .state import inventory, make_conserved

PROPERTY_BACKEND_NAME = "coolprop_co2"
PROPERTY_BACKEND_DESIGN_STATUS = "not_approved_for_design_use"
MODEL_NAME = "pure_co2_hem_equilibrium_quality_projection_verification"
OUTPUT_VERSION = "stage7_lco2_hem_quality_sync_contact_comparison_v1"
FLUID_NAME = "CO2"


class HEMQualitySyncContactComparisonError(RuntimeError):
    """Raised when the fixed contact comparison is inconsistent."""


@dataclass(frozen=True)
class HEMQualitySyncContactComparisonConfig:
    pressure_pa: float = 2.00e6
    activated_pressure_offset_pa: float = 1.00e4
    left_quality: float = 0.45
    right_quality: float = 0.55
    velocity_m_s: float = 0.0
    length_m: float = 10.0
    diameter_m: float = 0.10
    n_cells: int = 32
    cfl: float = 0.10
    n_steps: int = 4
    projection_activation_tolerance: float = 1.0e-12
    quality_sync_tolerance: float = 1.0e-10
    budget_relative_tolerance: float = 1.0e-11
    equal_pressure_span_tolerance_pa: float = 1.0e-2
    minimum_delta_q_contrast_ratio: float = 1.0e6

    def __post_init__(self) -> None:
        numeric = (
            self.pressure_pa,
            self.activated_pressure_offset_pa,
            self.left_quality,
            self.right_quality,
            self.velocity_m_s,
            self.length_m,
            self.diameter_m,
            self.cfl,
            self.projection_activation_tolerance,
            self.quality_sync_tolerance,
            self.budget_relative_tolerance,
            self.equal_pressure_span_tolerance_pa,
            self.minimum_delta_q_contrast_ratio,
        )
        if not all(np.isfinite(value) for value in numeric):
            raise ValueError("contact-comparison settings must be finite")
        if self.pressure_pa <= 0.0:
            raise ValueError("pressure_pa must be positive")
        if not 0.0 < self.activated_pressure_offset_pa < self.pressure_pa:
            raise ValueError("activated pressure offset must lie in (0, pressure)")
        if not 0.0 < self.left_quality < 1.0:
            raise ValueError("left_quality must lie in (0, 1)")
        if not 0.0 < self.right_quality < 1.0:
            raise ValueError("right_quality must lie in (0, 1)")
        if self.left_quality == self.right_quality:
            raise ValueError("left_quality and right_quality must differ")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 4 or self.n_cells % 2:
            raise ValueError("n_cells must be even and at least 4")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must lie in (0, 1]")
        if self.n_steps <= 0:
            raise ValueError("n_steps must be positive")
        if min(
            self.projection_activation_tolerance,
            self.quality_sync_tolerance,
            self.budget_relative_tolerance,
            self.equal_pressure_span_tolerance_pa,
        ) < 0.0:
            raise ValueError("tolerances must be non-negative")
        if self.minimum_delta_q_contrast_ratio <= 1.0:
            raise ValueError("minimum contrast ratio must exceed one")


@dataclass(frozen=True)
class HEMQualitySyncContactComparisonResult:
    config: HEMQualitySyncContactComparisonConfig
    summary: dict[str, object]
    no_op: HEMNonuniformQualitySyncResult
    activated: HEMNonuniformQualitySyncResult


def _coolprop_api():
    try:
        import CoolProp  # type: ignore
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError("CoolProp is required for the HEM contact case") from exc
    return PropsSI, str(CoolProp.__version__)


def _traceability() -> dict[str, str]:
    _, coolprop_version = _coolprop_api()
    return {
        "model_name": MODEL_NAME,
        "fluid_name": FLUID_NAME,
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
        "coolprop_version": coolprop_version,
        "numpy_version": str(np.__version__),
        "output_version": OUTPUT_VERSION,
    }


def _profiles(primitive) -> dict[str, np.ndarray]:
    return {
        "rho_kg_m3": np.array(primitive.rho, copy=True),
        "velocity_m_s": np.array(primitive.u, copy=True),
        "pressure_pa": np.array(primitive.p, copy=True),
        "internal_energy_j_kg": np.array(primitive.e, copy=True),
        "temperature_K": np.array(primitive.T, copy=True),
        "quality": np.array(primitive.xv, copy=True),
        "void_fraction": np.array(primitive.alpha, copy=True),
        "sound_speed_m_s": np.array(primitive.c, copy=True),
    }


def _max_abs(rows: list[dict[str, float]], key: str) -> float:
    return float(max(abs(row[key]) for row in rows))


def _run_equal_pressure_contact(
    cfg: HEMQualitySyncContactComparisonConfig,
) -> HEMNonuniformQualitySyncResult:
    case_cfg = HEMNonuniformQualitySyncConfig(
        left_pressure_pa=cfg.pressure_pa,
        left_quality=cfg.left_quality,
        right_pressure_pa=cfg.pressure_pa,
        right_quality=cfg.right_quality,
        velocity_m_s=cfg.velocity_m_s,
        length_m=cfg.length_m,
        diameter_m=cfg.diameter_m,
        n_cells=cfg.n_cells,
        cfl=cfg.cfl,
        n_steps=cfg.n_steps,
        quality_sync_tolerance=cfg.quality_sync_tolerance,
        budget_relative_tolerance=cfg.budget_relative_tolerance,
    )
    props_si, _ = _coolprop_api()
    states: list[tuple[float, float]] = []
    for quality in (cfg.left_quality, cfg.right_quality):
        try:
            rho = float(props_si("Dmass", "P", cfg.pressure_pa, "Q", quality, FLUID_NAME))
            e = float(props_si("Umass", "P", cfg.pressure_pa, "Q", quality, FLUID_NAME))
        except Exception as exc:
            raise HEMQualitySyncContactComparisonError(
                "CoolProp failed to construct the equal-pressure contact"
            ) from exc
        if not np.isfinite(rho) or not np.isfinite(e) or rho <= 0.0:
            raise HEMQualitySyncContactComparisonError("invalid initial contact state")
        states.append((rho, e))

    grid = UniformGrid(
        PipeGeometry(length_m=cfg.length_m, diameter_m=cfg.diameter_m),
        n_cells=cfg.n_cells,
    )
    x_m = grid.cell_centers
    left = x_m < 0.5 * cfg.length_m
    rho = np.where(left, states[0][0], states[1][0])
    e = np.where(left, states[0][1], states[1][1])
    quality = np.where(left, cfg.left_quality, cfg.right_quality)
    U_initial = make_conserved(rho, cfg.velocity_m_s, e, quality)

    projection = HEMEquilibriumQualityProjection(
        config=ProjectionConfig(
            activation_tolerance=cfg.projection_activation_tolerance
        )
    )
    solver = FvmSolver(
        grid=grid,
        eos=VerificationHEMEquilibriumEOS(
            quality_tolerance=cfg.quality_sync_tolerance
        ),
        U=U_initial,
        cfl=cfg.cfl,
        phase_change=projection,
    )
    initial_profiles = _profiles(solver.primitive())
    initial_inventory = inventory(U_initial, grid.dx, grid.geometry.area_m2)

    history: list[dict[str, float]] = []
    records = []
    all_invariants = True
    all_two_phase = True
    max_post_mismatch = 0.0
    for _ in range(cfg.n_steps):
        dt = solver.step()
        record = projection.last_result
        if record is None:
            raise HEMQualitySyncContactComparisonError(
                "projection did not record a contact result"
            )
        records.append(record)
        record_summary = record.summary()
        all_invariants = all_invariants and all(
            bool(record_summary[key])
            for key in (
                "mass_bitwise_unchanged",
                "momentum_bitwise_unchanged",
                "energy_bitwise_unchanged",
                "quality_synchronized_within_tolerance",
            )
        )
        all_two_phase = all_two_phase and bool(
            np.all(record.phase_class == "liquid_vapor_two_phase")
        )
        max_post_mismatch = max(
            max_post_mismatch,
            float(np.max(np.abs(record.q_after - record.q_equilibrium))),
        )

        primitive = solver.primitive()
        current_inventory = inventory(solver.U, grid.dx, grid.geometry.area_m2)
        if (
            solver.boundary_budget is None
            or solver.phase_budget is None
            or solver.energy_budget is None
        ):
            raise HEMQualitySyncContactComparisonError(
                "required contact budget is unavailable"
            )
        boundary = solver.boundary_budget.diagnostics(current_inventory)
        phase = solver.phase_budget.diagnostics(
            current_inventory, boundary_budget=solver.boundary_budget
        )
        energy = solver.energy_budget.diagnostics(
            current_inventory, boundary_budget=solver.boundary_budget
        )
        history.append(
            {
                "step": float(solver.step_count),
                "time_s": float(solver.t),
                "dt_s": float(dt),
                "cfl_max": float(
                    np.max((np.abs(primitive.u) + primitive.c) * dt / grid.dx)
                ),
                "projection_cell_count": float(
                    record_summary["projection_cell_count"]
                ),
                "max_abs_delta_q": float(record_summary["max_abs_delta_q"]),
                "pressure_min_pa": float(np.min(primitive.p)),
                "pressure_max_pa": float(np.max(primitive.p)),
                "velocity_max_abs_m_s": float(np.max(np.abs(primitive.u))),
                "budget_mass_relative_residual": float(
                    boundary["budget_mass_relative_residual"]
                ),
                "budget_momentum_relative_residual": float(
                    boundary["budget_momentum_relative_residual"]
                ),
                "energy_budget_balance_relative_residual": float(
                    energy["energy_budget_balance_relative_residual"]
                ),
                "phase_vapor_mass_balance_relative_residual": float(
                    phase["phase_vapor_mass_balance_relative_residual"]
                ),
                "phase_vapor_mass_source_cumulative_kg": float(
                    phase["phase_vapor_mass_source_cumulative_kg"]
                ),
                "phase_energy_delta_cumulative_j": float(
                    energy["energy_budget_phase_delta_cumulative_j"]
                ),
            }
        )

    final_primitive = solver.primitive()
    final_profiles = _profiles(final_primitive)
    final_record = records[-1]
    final_projection = {
        "q_before": np.array(final_record.q_before, copy=True),
        "q_equilibrium": np.array(final_record.q_equilibrium, copy=True),
        "q_after": np.array(final_record.q_after, copy=True),
        "delta_q": np.array(final_record.delta_q, copy=True),
        "projection_applied": np.array(
            final_record.projection_applied, dtype=bool, copy=True
        ),
        "phase_class": np.array(final_record.phase_class, copy=True),
    }

    total_updates = sum(
        int(record.summary()["projection_cell_count"]) for record in records
    )
    max_delta_q = max(
        float(record.summary()["max_abs_delta_q"]) for record in records
    )
    pressure_span = max(
        row["pressure_max_pa"] - row["pressure_min_pa"] for row in history
    )
    conservative_delta = solver.U - U_initial
    initial_jump = float(
        np.max(np.abs(np.diff(initial_profiles["quality"])), initial=0.0)
    )
    final_jump = float(
        np.max(np.abs(np.diff(final_profiles["quality"])), initial=0.0)
    )
    q_low = min(cfg.left_quality, cfg.right_quality)
    q_high = max(cfg.left_quality, cfg.right_quality)
    mixed_cells = int(
        np.count_nonzero(
            (final_profiles["quality"] > q_low + 1.0e-14)
            & (final_profiles["quality"] < q_high - 1.0e-14)
        )
    )
    mass_residual = _max_abs(history, "budget_mass_relative_residual")
    momentum_residual = _max_abs(history, "budget_momentum_relative_residual")
    energy_residual = _max_abs(history, "energy_budget_balance_relative_residual")
    vapor_residual = _max_abs(history, "phase_vapor_mass_balance_relative_residual")
    vapor_source = _max_abs(history, "phase_vapor_mass_source_cumulative_kg")
    phase_energy_delta = _max_abs(history, "phase_energy_delta_cumulative_j")
    final_inventory = inventory(solver.U, grid.dx, grid.geometry.area_m2)

    summary: dict[str, object] = {
        "schema_version": "stage7_lco2_hem_equal_pressure_contact_noop_v1",
        "scope": "verification_only",
        "case_kind": "equal_pressure_quality_contact_no_op",
        **_traceability(),
        "completed_steps": int(solver.step_count),
        "final_time_s": float(solver.t),
        "cfl_max": max(row["cfl_max"] for row in history),
        "projection_total_cell_updates": total_updates,
        "projection_ever_applied": total_updates > 0,
        "max_abs_delta_q": max_delta_q,
        "maximum_post_projection_quality_mismatch": max_post_mismatch,
        "quality_no_op_tolerance_satisfied": bool(
            max(max_delta_q, max_post_mismatch)
            <= cfg.projection_activation_tolerance
        ),
        "all_projection_invariants_satisfied": all_invariants,
        "all_projection_states_open_two_phase": all_two_phase,
        "all_sound_speeds_finite_positive": bool(
            np.all(np.isfinite(final_primitive.c))
            and np.all(final_primitive.c > 0.0)
        ),
        "contact_transport_exercised": bool(np.any(conservative_delta != 0.0)),
        "transport_changed_cell_count": int(
            np.count_nonzero(np.any(conservative_delta != 0.0, axis=1))
        ),
        "maximum_abs_conservative_change": float(
            np.max(np.abs(conservative_delta), initial=0.0)
        ),
        "initial_max_quality_jump": initial_jump,
        "final_max_quality_jump": final_jump,
        "quality_max_jump_reduced": final_jump < initial_jump,
        "mixed_quality_cell_count": mixed_cells,
        "pressure_span_max_pa": pressure_span,
        "equal_pressure_span_tolerance_satisfied": bool(
            pressure_span <= cfg.equal_pressure_span_tolerance_pa
        ),
        "maximum_abs_velocity_m_s": max(
            row["velocity_max_abs_m_s"] for row in history
        ),
        "mass_budget_max_relative_residual": mass_residual,
        "momentum_budget_max_relative_residual": momentum_residual,
        "energy_budget_max_relative_residual": energy_residual,
        "phase_vapor_budget_max_relative_residual": vapor_residual,
        "phase_vapor_source_max_abs_kg": vapor_source,
        "phase_energy_delta_max_abs_j": phase_energy_delta,
        "initial_mass_kg": float(initial_inventory["mass_total"]),
        "initial_momentum_kg_m_s": float(initial_inventory["momentum_total"]),
        "initial_energy_j": float(initial_inventory["energy_total"]),
        "initial_vapor_mass_kg": float(initial_inventory["vapor_mass_total"]),
        "final_mass_kg": float(final_inventory["mass_total"]),
        "final_momentum_kg_m_s": float(final_inventory["momentum_total"]),
        "final_energy_j": float(final_inventory["energy_total"]),
        "final_vapor_mass_kg": float(final_inventory["vapor_mass_total"]),
        "budget_tolerance_satisfied": bool(
            max(mass_residual, momentum_residual, energy_residual, vapor_residual)
            <= cfg.budget_relative_tolerance
        ),
        "fvm_solver_exercised": True,
        "rusanov_flux_exercised": True,
        "cfl_exercised": True,
        "equilibrium_quality_projection_exercised": True,
        "production_default_changed": False,
        "production_hem_activation_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
    }
    accepted = (
        total_updates == 0
        and bool(summary["quality_no_op_tolerance_satisfied"])
        and bool(summary["all_projection_invariants_satisfied"])
        and bool(summary["all_projection_states_open_two_phase"])
        and bool(summary["all_sound_speeds_finite_positive"])
        and bool(summary["contact_transport_exercised"])
        and bool(summary["quality_max_jump_reduced"])
        and mixed_cells >= 2
        and bool(summary["equal_pressure_span_tolerance_satisfied"])
        and bool(summary["budget_tolerance_satisfied"])
        and vapor_source == 0.0
        and phase_energy_delta == 0.0
    )
    if not accepted:
        raise HEMQualitySyncContactComparisonError(
            f"equal-pressure contact acceptance failed: {summary}"
        )

    return HEMNonuniformQualitySyncResult(
        config=case_cfg,
        summary=summary,
        history=history,
        x_m=np.array(x_m, copy=True),
        initial_U=np.array(U_initial, copy=True),
        final_U=np.array(solver.U, copy=True),
        initial_profiles=initial_profiles,
        final_profiles=final_profiles,
        final_projection=final_projection,
    )


def run_hem_quality_sync_contact_comparison(
    config: HEMQualitySyncContactComparisonConfig | None = None,
) -> HEMQualitySyncContactComparisonResult:
    cfg = config or HEMQualitySyncContactComparisonConfig()
    no_op = _run_equal_pressure_contact(cfg)
    activated = run_nonuniform_hem_quality_sync(
        HEMNonuniformQualitySyncConfig(
            left_pressure_pa=cfg.pressure_pa + cfg.activated_pressure_offset_pa,
            left_quality=cfg.left_quality,
            right_pressure_pa=cfg.pressure_pa - cfg.activated_pressure_offset_pa,
            right_quality=cfg.right_quality,
            velocity_m_s=cfg.velocity_m_s,
            length_m=cfg.length_m,
            diameter_m=cfg.diameter_m,
            n_cells=cfg.n_cells,
            cfl=cfg.cfl,
            n_steps=cfg.n_steps,
            quality_sync_tolerance=cfg.quality_sync_tolerance,
            budget_relative_tolerance=cfg.budget_relative_tolerance,
        )
    )

    no_op_delta = float(no_op.summary["max_abs_delta_q"])
    activated_delta = float(activated.summary["max_abs_delta_q"])
    ratio = activated_delta / max(no_op_delta, float(np.finfo(float).eps))
    no_op_source = float(no_op.summary["phase_vapor_source_max_abs_kg"])
    activated_source = abs(
        float(activated.history[-1]["phase_vapor_mass_source_cumulative_kg"])
    )
    summary: dict[str, object] = {
        "schema_version": OUTPUT_VERSION,
        "scope": "verification_only",
        **_traceability(),
        "no_op_projection_total_cell_updates": int(
            no_op.summary["projection_total_cell_updates"]
        ),
        "activated_projection_total_cell_updates": int(
            activated.summary["projection_total_cell_updates"]
        ),
        "no_op_max_abs_delta_q": no_op_delta,
        "activated_max_abs_delta_q": activated_delta,
        "activated_to_no_op_delta_q_ratio": ratio,
        "minimum_delta_q_contrast_ratio": cfg.minimum_delta_q_contrast_ratio,
        "delta_q_contrast_satisfied": bool(
            ratio >= cfg.minimum_delta_q_contrast_ratio
        ),
        "no_op_phase_vapor_source_max_abs_kg": no_op_source,
        "activated_phase_vapor_source_abs_kg": activated_source,
        "projection_activity_contrast_satisfied": bool(
            int(activated.summary["projection_total_cell_updates"]) > 0
            and int(no_op.summary["projection_total_cell_updates"]) == 0
        ),
        "vapor_source_contrast_satisfied": activated_source > no_op_source,
        "no_op_contact_transport_exercised": bool(
            no_op.summary["contact_transport_exercised"]
        ),
        "no_op_budget_tolerance_satisfied": bool(
            no_op.summary["budget_tolerance_satisfied"]
        ),
        "activated_budget_tolerance_satisfied": bool(
            activated.summary["budget_tolerance_satisfied"]
        ),
        "no_op_all_states_open_two_phase": bool(
            no_op.summary["all_projection_states_open_two_phase"]
        ),
        "activated_all_states_open_two_phase": bool(
            activated.summary["all_projection_states_open_two_phase"]
        ),
        "comparison_acceptance_satisfied": False,
        "production_default_changed": False,
        "production_hem_activation_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
    }
    keys = (
        "delta_q_contrast_satisfied",
        "projection_activity_contrast_satisfied",
        "vapor_source_contrast_satisfied",
        "no_op_contact_transport_exercised",
        "no_op_budget_tolerance_satisfied",
        "activated_budget_tolerance_satisfied",
        "no_op_all_states_open_two_phase",
        "activated_all_states_open_two_phase",
    )
    summary["comparison_acceptance_satisfied"] = all(
        bool(summary[key]) for key in keys
    )
    if not bool(summary["comparison_acceptance_satisfied"]):
        raise HEMQualitySyncContactComparisonError(
            f"contact comparison acceptance failed: {summary}"
        )
    return HEMQualitySyncContactComparisonResult(
        config=cfg, summary=summary, no_op=no_op, activated=activated
    )


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _case_summary_with_traceability(summary: dict[str, object]) -> dict[str, object]:
    return {**summary, **_traceability()}


def write_hem_quality_sync_contact_comparison_artifacts(
    output_dir: str | Path,
    result: HEMQualitySyncContactComparisonResult,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_quality_sync_contact_comparison"
    paths = {
        "json": out / f"{stem}.json",
        "history_csv": out / f"{stem}_history.csv",
        "profile_csv": out / f"{stem}_final_profile.csv",
        "markdown": out / f"{stem}.md",
        "npz": out / f"{stem}.npz",
    }
    trace = _traceability()
    payload = {
        **result.summary,
        "config": asdict(result.config),
        "no_op": {
            "config": asdict(result.no_op.config),
            "summary": _case_summary_with_traceability(result.no_op.summary),
            "history": result.no_op.history,
            "x_m": result.no_op.x_m,
            "initial_profiles": result.no_op.initial_profiles,
            "final_profiles": result.no_op.final_profiles,
            "final_projection": result.no_op.final_projection,
        },
        "activated": {
            "config": asdict(result.activated.config),
            "summary": _case_summary_with_traceability(result.activated.summary),
            "history": result.activated.history,
            "x_m": result.activated.x_m,
            "initial_profiles": result.activated.initial_profiles,
            "final_profiles": result.activated.final_profiles,
            "final_projection": result.activated.final_projection,
        },
    }
    paths["json"].write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    rows = []
    for no_op, activated in zip(result.no_op.history, result.activated.history):
        rows.append(
            {
                **trace,
                "step": no_op["step"],
                "no_op_projection_cell_count": no_op["projection_cell_count"],
                "activated_projection_cell_count": activated[
                    "projection_cell_count"
                ],
                "no_op_max_abs_delta_q": no_op["max_abs_delta_q"],
                "activated_max_abs_delta_q": activated["max_abs_delta_q"],
                "no_op_vapor_source_kg": no_op[
                    "phase_vapor_mass_source_cumulative_kg"
                ],
                "activated_vapor_source_kg": activated[
                    "phase_vapor_mass_source_cumulative_kg"
                ],
                "no_op_pressure_span_pa": (
                    no_op["pressure_max_pa"] - no_op["pressure_min_pa"]
                ),
                "activated_pressure_span_pa": (
                    activated["pressure_max_pa"] - activated["pressure_min_pa"]
                ),
            }
        )
    with paths["history_csv"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    fields = (
        *trace.keys(),
        "x_m",
        "no_op_initial_quality",
        "no_op_final_quality",
        "no_op_delta_q",
        "no_op_projection_applied",
        "activated_initial_quality",
        "activated_final_quality",
        "activated_delta_q",
        "activated_projection_applied",
    )
    with paths["profile_csv"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, x_m in enumerate(result.no_op.x_m):
            writer.writerow(
                {
                    **trace,
                    "x_m": float(x_m),
                    "no_op_initial_quality": float(
                        result.no_op.initial_profiles["quality"][i]
                    ),
                    "no_op_final_quality": float(
                        result.no_op.final_profiles["quality"][i]
                    ),
                    "no_op_delta_q": float(
                        result.no_op.final_projection["delta_q"][i]
                    ),
                    "no_op_projection_applied": bool(
                        result.no_op.final_projection["projection_applied"][i]
                    ),
                    "activated_initial_quality": float(
                        result.activated.initial_profiles["quality"][i]
                    ),
                    "activated_final_quality": float(
                        result.activated.final_profiles["quality"][i]
                    ),
                    "activated_delta_q": float(
                        result.activated.final_projection["delta_q"][i]
                    ),
                    "activated_projection_applied": bool(
                        result.activated.final_projection["projection_applied"][i]
                    ),
                }
            )

    lines = [
        "# Stage 7 LCO2 HEM Quality-Sync Contact Comparison",
        "",
        "`VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION`",
        "",
        "## Traceability",
        "",
        "```text",
        *[f"{key}: {value}" for key, value in trace.items()],
        "```",
        "",
        "## Comparison result",
        "",
        "```text",
    ]
    for key in (
        "no_op_projection_total_cell_updates",
        "activated_projection_total_cell_updates",
        "no_op_max_abs_delta_q",
        "activated_max_abs_delta_q",
        "activated_to_no_op_delta_q_ratio",
        "comparison_acceptance_satisfied",
    ):
        lines.append(f"{key}: {result.summary[key]}")
    lines.extend(
        [
            "```",
            "",
            "The equal-pressure contact spreads under Rusanov transport but remains",
            "on one saturation line, so quality projection is a numerical no-op.",
            "This evidence is verification-only and does not approve production HEM",
            "or the CoolProp backend for design use.",
            "",
        ]
    )
    paths["markdown"].write_text("\n".join(lines), encoding="utf-8")
    np.savez_compressed(
        paths["npz"],
        x_m=result.no_op.x_m,
        no_op_initial_U=result.no_op.initial_U,
        no_op_final_U=result.no_op.final_U,
        activated_initial_U=result.activated.initial_U,
        activated_final_U=result.activated.final_U,
        no_op_delta_q=result.no_op.final_projection["delta_q"],
        activated_delta_q=result.activated.final_projection["delta_q"],
        **{key: np.asarray(value) for key, value in trace.items()},
    )
    return paths


def _figure_footer(result: HEMQualitySyncContactComparisonResult) -> str:
    trace = result.summary
    return (
        f"model={trace['model_name']} | fluid={trace['fluid_name']} | "
        f"backend={trace['property_backend_name']} "
        f"({trace['property_backend_design_status']}) | "
        f"CoolProp={trace['coolprop_version']} | output={trace['output_version']} | "
        "VERIFICATION ONLY"
    )


def _save_figure(fig, path: Path, footer: str) -> None:
    fig.text(0.5, 0.01, footer, ha="center", va="bottom", fontsize=7)
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    fig.savefig(path, dpi=160)


def write_hem_quality_sync_contact_comparison_plots(
    output_dir: str | Path,
    result: HEMQualitySyncContactComparisonResult,
) -> dict[str, Path]:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        raise ImportError("matplotlib is required for comparison plots") from exc

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "quality_profiles_png": out / "quality_contact_comparison.png",
        "projection_activity_png": out / "projection_activity_comparison.png",
        "budget_history_png": out / "contact_comparison_budgets.png",
    }
    footer = _figure_footer(result)
    x = result.no_op.x_m
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    fig.suptitle("Stage 7 HEM quality-contact comparison")
    for axis, case, label in (
        (axes[0], result.no_op, "equal-pressure"),
        (axes[1], result.activated, "pressure-offset"),
    ):
        axis.plot(x, case.initial_profiles["quality"], linestyle="--", label="initial")
        axis.plot(x, case.final_profiles["quality"], marker=".", label="final")
        axis.set_ylabel(f"{label} quality [-]")
        axis.legend()
        axis.grid(True, alpha=0.3)
    axes[1].set_xlabel("x [m]")
    _save_figure(fig, paths["quality_profiles_png"], footer)
    plt.close(fig)

    steps = [row["step"] for row in result.no_op.history]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.suptitle("Stage 7 HEM projection activity")
    axes[0].plot(
        steps,
        [row["projection_cell_count"] for row in result.no_op.history],
        marker="o",
        label="equal-pressure",
    )
    axes[0].plot(
        steps,
        [row["projection_cell_count"] for row in result.activated.history],
        marker="s",
        label="pressure-offset",
    )
    axes[0].set_ylabel("projected cells")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[1].semilogy(
        steps,
        [
            max(row["max_abs_delta_q"], float(np.finfo(float).tiny))
            for row in result.no_op.history
        ],
        marker="o",
        label="equal-pressure",
    )
    axes[1].semilogy(
        steps,
        [row["max_abs_delta_q"] for row in result.activated.history],
        marker="s",
        label="pressure-offset",
    )
    axes[1].set_xlabel("step")
    axes[1].set_ylabel("max |delta q|")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    _save_figure(fig, paths["projection_activity_png"], footer)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10, 5))
    fig.suptitle("Stage 7 HEM cumulative projection vapor source")
    axis.plot(
        steps,
        [
            row["phase_vapor_mass_source_cumulative_kg"]
            for row in result.no_op.history
        ],
        marker="o",
        label="equal-pressure",
    )
    axis.plot(
        steps,
        [
            row["phase_vapor_mass_source_cumulative_kg"]
            for row in result.activated.history
        ],
        marker="s",
        label="pressure-offset",
    )
    axis.set_xlabel("step")
    axis.set_ylabel("cumulative vapor source [kg]")
    axis.legend()
    axis.grid(True, alpha=0.3)
    _save_figure(fig, paths["budget_history_png"], footer)
    plt.close(fig)
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Stage 7 HEM contact/projection comparison."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_hem_quality_sync_contact_comparison()
    paths = write_hem_quality_sync_contact_comparison_artifacts(
        args.output_dir, result
    )
    paths.update(
        write_hem_quality_sync_contact_comparison_plots(args.output_dir, result)
    )
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
