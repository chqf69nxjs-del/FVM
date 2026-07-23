"""Verification-only projected one-step liquid-to-two-phase FVM dry run.

This increment consumes the fixed raw one-step matrix established by PR #70,
applies the existing equilibrium-quality projection, recovers the synchronized
mixed liquid/open-two-phase accepted state, verifies that a second projection is
a no-op, and closes the projection vapor-mass account.

No production solver, numerical flux, CFL, EOS, phase classifier, acoustic
algorithm, or tolerance is changed by this module.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Protocol

import numpy as np

from .hem_equilibrium_quality_sync import (
    HEMEquilibriumQualityProjection,
    HEMEquilibriumQualitySyncConfig,
    HEMEquilibriumQualitySyncResult,
)
from .hem_liquid_to_two_phase_minimal_fvm_dry_run import (
    HEMMinimalRawFvmDryRunConfig,
    HEMMinimalRawFvmDryRunResult,
    MinimalRawFvmCaseResult,
    run_minimal_raw_fvm_dry_run_matrix,
)
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_phase_classification import HEMPhaseClassificationConfig
from .phase_budget import PhaseChangeBudgetTracker
from .state import inventory, vapor_mass_fraction

ProjectedCaseOutcome = Literal[
    "ACCEPTED_CROSSING",
    "ACCEPTED_ALL_LIQUID_NOOP",
    "RAW_STATE_REJECTED",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]


class HEMProjectedFvmDryRunError(RuntimeError):
    """Raised when the projected one-step dry-run contract cannot be satisfied."""


class AcceptedStateEOS(Protocol):
    """Minimal accepted-state EOS contract needed by this increment."""

    @property
    def last_regions(self) -> np.ndarray | None:
        """Return the most recently accepted boundary regions."""

    def primitive_from_conserved(self, U: np.ndarray):
        """Return synchronized primitive state data."""


ProjectionFactory = Callable[
    [HEMEquilibriumQualitySyncConfig], HEMEquilibriumQualityProjection
]
AcceptedEosFactory = Callable[
    [HEMPhaseClassificationConfig, HEMEquilibriumQualitySyncConfig, float],
    AcceptedStateEOS,
]
RawMatrixRunner = Callable[..., HEMMinimalRawFvmDryRunResult]


@dataclass(frozen=True)
class HEMProjectedFvmDryRunConfig:
    """Configuration for the fixed projection/accepted-state verification matrix."""

    raw_config: HEMMinimalRawFvmDryRunConfig = field(
        default_factory=HEMMinimalRawFvmDryRunConfig
    )
    projection_config: HEMEquilibriumQualitySyncConfig = field(
        default_factory=HEMEquilibriumQualitySyncConfig
    )
    accepted_state_quality_tolerance: float = 1.0e-10
    vapor_budget_absolute_tolerance_kg: float = 1.0e-12

    def __post_init__(self) -> None:
        if (
            not np.isfinite(self.accepted_state_quality_tolerance)
            or self.accepted_state_quality_tolerance < 0.0
        ):
            raise ValueError(
                "accepted_state_quality_tolerance must be finite and non-negative"
            )
        if (
            self.accepted_state_quality_tolerance
            < self.projection_config.activation_tolerance
        ):
            raise ValueError(
                "accepted-state tolerance must not be tighter than projection activation"
            )
        if (
            not np.isfinite(self.vapor_budget_absolute_tolerance_kg)
            or self.vapor_budget_absolute_tolerance_kg < 0.0
        ):
            raise ValueError(
                "vapor_budget_absolute_tolerance_kg must be finite and non-negative"
            )


@dataclass(frozen=True)
class ProjectedFvmCellRecord:
    """Cellwise raw, projected, accepted-state, and second-projection evidence."""

    case_id: str
    cell_index: int
    raw_region: str
    post_region: str
    transition_event: str
    q_transport_raw: float
    q_equilibrium: float
    q_after_first_projection: float
    q_after_second_projection: float
    delta_q_first: float
    delta_rho_q_first: float
    first_projection_applied: bool
    second_projection_applied: bool
    post_pressure_pa: float
    post_temperature_K: float
    post_void_fraction: float
    post_sound_speed_m_s: float


@dataclass(frozen=True)
class ProjectedFvmCaseResult:
    """Accepted one-step result for one raw dry-run case."""

    raw_case: MinimalRawFvmCaseResult
    outcome: ProjectedCaseOutcome
    failure_reason: str
    first_projection: HEMEquilibriumQualitySyncResult | None
    second_projection: HEMEquilibriumQualitySyncResult | None
    post_U: np.ndarray
    second_U: np.ndarray
    post_regions: np.ndarray
    cells: tuple[ProjectedFvmCellRecord, ...]
    budget_diagnostics: dict[str, float]
    post_accepted_state_eos_exercised: bool

    def summary(self) -> dict[str, object]:
        raw_summary = self.raw_case.summary()
        crossing_cells = [
            cell.cell_index
            for cell in self.raw_case.cells
            if cell.transition_event == "LIQUID_TO_TWO_PHASE_CROSSING"
        ]
        first_cells = [
            cell.cell_index for cell in self.cells if cell.first_projection_applied
        ]
        second_cells = [
            cell.cell_index for cell in self.cells if cell.second_projection_applied
        ]
        max_post_mismatch = max(
            (
                abs(cell.q_after_first_projection - cell.q_equilibrium)
                for cell in self.cells
            ),
            default=0.0,
        )
        max_second_delta = max(
            (
                abs(
                    cell.q_after_second_projection
                    - cell.q_after_first_projection
                )
                for cell in self.cells
            ),
            default=0.0,
        )
        return {
            "case_id": self.raw_case.spec.case_id,
            "role": self.raw_case.spec.role,
            "raw_outcome": self.raw_case.outcome,
            "outcome": self.outcome,
            "failure_reason": self.failure_reason,
            "dt_s": self.raw_case.dt_s,
            "dx_m": self.raw_case.dx_m,
            "crossing_cell_indices": crossing_cells,
            "first_projection_cell_indices": first_cells,
            "second_projection_cell_indices": second_cells,
            "crossing_and_first_projection_cells_match": crossing_cells == first_cells,
            "first_projection_cell_count": len(first_cells),
            "second_projection_cell_count": len(second_cells),
            "max_post_quality_mismatch": float(max_post_mismatch),
            "max_second_projection_state_delta_q": float(max_second_delta),
            "post_accepted_state_eos_exercised": (
                self.post_accepted_state_eos_exercised
            ),
            "post_regions": [
                str(value) for value in np.asarray(self.post_regions).ravel()
            ],
            "raw_case_summary": raw_summary,
            "first_projection_summary": (
                self.first_projection.summary()
                if self.first_projection is not None
                else None
            ),
            "second_projection_summary": (
                self.second_projection.summary()
                if self.second_projection is not None
                else None
            ),
            "budget_diagnostics": dict(self.budget_diagnostics),
        }


@dataclass(frozen=True)
class HEMProjectedFvmDryRunResult:
    """Fixed strong/moderate/control projection verification matrix."""

    config: HEMProjectedFvmDryRunConfig
    raw_summary: dict[str, object]
    cases: tuple[ProjectedFvmCaseResult, ...]

    def summary(self) -> dict[str, object]:
        outcome_counts = {
            outcome: sum(case.outcome == outcome for case in self.cases)
            for outcome in (
                "ACCEPTED_CROSSING",
                "ACCEPTED_ALL_LIQUID_NOOP",
                "RAW_STATE_REJECTED",
                "GUARD_FAILURE",
                "BACKEND_FAILURE",
            )
        }
        crossing_cases = [
            case.raw_case.spec.case_id
            for case in self.cases
            if case.outcome == "ACCEPTED_CROSSING"
        ]
        no_op_cases = [
            case.raw_case.spec.case_id
            for case in self.cases
            if case.outcome == "ACCEPTED_ALL_LIQUID_NOOP"
        ]
        all_success = bool(
            self.cases
            and all(
                case.outcome
                in {"ACCEPTED_CROSSING", "ACCEPTED_ALL_LIQUID_NOOP"}
                for case in self.cases
            )
        )
        return {
            "schema_version": "stage7_lco2_hem_projected_fvm_dry_run_v1",
            "scope": "verification_only",
            "case_count": len(self.cases),
            "outcome_counts": outcome_counts,
            "accepted_crossing_case_ids": crossing_cases,
            "accepted_liquid_noop_case_ids": no_op_cases,
            "raw_first_order_fvm_crossing_observed": bool(crossing_cases),
            "equilibrium_quality_projection_exercised": True,
            "post_projection_accepted_eos_exercised": True,
            "second_projection_noop_exercised": True,
            "phase_vapor_budget_exercised": True,
            "all_fixed_cases_completed": all_success,
            "complete_one_step_crossing_path_observed": (
                bool(crossing_cases) and all_success
            ),
            "actual_first_order_fvm_crossing_verified": False,
            "case_a_frozen": False,
            "case_b_frozen": False,
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "two_phase_acoustic_accuracy_band_approved": False,
            "raw_summary": dict(self.raw_summary),
        }


def _default_projection_factory(
    config: HEMEquilibriumQualitySyncConfig,
) -> HEMEquilibriumQualityProjection:
    return HEMEquilibriumQualityProjection(config=config)


def _default_accepted_eos_factory(
    phase_config: HEMPhaseClassificationConfig,
    quality_sync_config: HEMEquilibriumQualitySyncConfig,
    quality_tolerance: float,
) -> VerificationHEMLiquidOpenTwoPhaseEOS:
    return VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_config=phase_config,
        quality_sync_config=quality_sync_config,
        quality_tolerance=quality_tolerance,
    )


def _failure_outcome(exc: Exception) -> ProjectedCaseOutcome:
    text = f"{type(exc).__name__}: {exc}".lower()
    backend_terms = (
        "coolprop",
        "backend",
        "phase evaluation failed",
        "property evaluation failed",
        "sound-speed evaluation failed",
    )
    return (
        "BACKEND_FAILURE"
        if any(term in text for term in backend_terms)
        else "GUARD_FAILURE"
    )


def _raw_regions(raw_case: MinimalRawFvmCaseResult) -> np.ndarray:
    if len(raw_case.cells) != raw_case.raw_U.shape[0]:
        raise HEMProjectedFvmDryRunError(
            "raw case must retain one cell record per conservative cell"
        )
    return np.asarray([cell.raw_region for cell in raw_case.cells], dtype="<U40")


def _crossing_cells(raw_case: MinimalRawFvmCaseResult) -> list[int]:
    return [
        cell.cell_index
        for cell in raw_case.cells
        if cell.transition_event == "LIQUID_TO_TWO_PHASE_CROSSING"
    ]


def _budget_diagnostics(
    *,
    raw_case: MinimalRawFvmCaseResult,
    first: HEMEquilibriumQualitySyncResult,
    post_U: np.ndarray,
    config: HEMProjectedFvmDryRunConfig,
) -> dict[str, float]:
    area = math.pi * config.raw_config.diameter_m**2 / 4.0
    dx = raw_case.dx_m
    raw_inventory = inventory(raw_case.raw_U, dx, area)
    post_inventory = inventory(post_U, dx, area)
    phase_tracker = PhaseChangeBudgetTracker(initial_inventory=raw_inventory)
    phase_tracker.record_phase_change(
        U_before=raw_case.raw_U,
        U_after=post_U,
        dx=dx,
        area_m2=area,
        dt=raw_case.dt_s,
    )
    phase_diag = phase_tracker.diagnostics(post_inventory)

    initial_inventory = inventory(raw_case.initial_U, dx, area)
    boundary_net = float(
        raw_case.budget_diagnostics.get("budget_vapor_mass_net_boundary", 0.0)
    )
    projection_source = float(phase_tracker.last_source_kg)
    direct_projection_source = float(np.sum(first.delta_rho_q) * dx * area)
    combined_expected = (
        float(initial_inventory["vapor_mass_total"])
        + boundary_net
        + projection_source
    )
    actual_post = float(post_inventory["vapor_mass_total"])
    combined_residual = actual_post - combined_expected
    source_consistency = projection_source - direct_projection_source

    out = {str(key): float(value) for key, value in phase_diag.items()}
    out.update(
        {
            "initial_vapor_mass_kg": float(
                initial_inventory["vapor_mass_total"]
            ),
            "raw_vapor_mass_kg": float(raw_inventory["vapor_mass_total"]),
            "post_vapor_mass_kg": actual_post,
            "raw_boundary_vapor_net_kg": boundary_net,
            "projection_vapor_source_kg": projection_source,
            "projection_vapor_source_from_delta_rho_q_kg": (
                direct_projection_source
            ),
            "projection_source_consistency_residual_kg": source_consistency,
            "combined_expected_post_vapor_mass_kg": combined_expected,
            "combined_post_vapor_balance_residual_kg": combined_residual,
        }
    )
    return out


def run_one_projected_fvm_case(
    raw_case: MinimalRawFvmCaseResult,
    config: HEMProjectedFvmDryRunConfig,
    *,
    projection_factory: ProjectionFactory = _default_projection_factory,
    accepted_eos_factory: AcceptedEosFactory = _default_accepted_eos_factory,
) -> ProjectedFvmCaseResult:
    """Project, accept, re-project, and budget one PR #70 raw case."""

    empty_U = np.empty((0, 4), dtype=float)
    empty_regions = np.empty((0,), dtype="<U40")
    if raw_case.outcome not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
        return ProjectedFvmCaseResult(
            raw_case=raw_case,
            outcome="RAW_STATE_REJECTED",
            failure_reason=f"unsupported raw outcome: {raw_case.outcome}",
            first_projection=None,
            second_projection=None,
            post_U=empty_U,
            second_U=empty_U,
            post_regions=empty_regions,
            cells=(),
            budget_diagnostics={},
            post_accepted_state_eos_exercised=False,
        )

    try:
        raw_regions = _raw_regions(raw_case)
        crossing_cells = _crossing_cells(raw_case)
        first_operator = projection_factory(config.projection_config)
        first = first_operator.project(np.array(raw_case.raw_U, copy=True))
        first_cells = np.flatnonzero(first.projection_applied).astype(int).tolist()

        if raw_case.outcome == "OPEN_TWO_PHASE":
            if not crossing_cells:
                raise HEMProjectedFvmDryRunError(
                    "open-two-phase raw case must contain crossing cells"
                )
            if first_cells != crossing_cells:
                raise HEMProjectedFvmDryRunError(
                    "first projection cells do not match raw crossing cells: "
                    f"crossing={crossing_cells}, projection={first_cells}"
                )
        elif first_cells:
            raise HEMProjectedFvmDryRunError(
                "all-liquid control must remain a first-projection no-op"
            )

        first_summary = first.summary()
        for key in (
            "mass_bitwise_unchanged",
            "momentum_bitwise_unchanged",
            "energy_bitwise_unchanged",
            "quality_synchronized_within_tolerance",
        ):
            if first_summary[key] is not True:
                raise HEMProjectedFvmDryRunError(
                    f"first projection invariant failed: {key}"
                )

        post_U = np.array(first.U_after, dtype=float, copy=True)
        accepted_eos = accepted_eos_factory(
            config.raw_config.phase_config,
            config.projection_config,
            config.accepted_state_quality_tolerance,
        )
        post_primitive = accepted_eos.primitive_from_conserved(post_U)
        post_regions_value = accepted_eos.last_regions
        if post_regions_value is None:
            raise HEMProjectedFvmDryRunError(
                "accepted-state EOS did not retain post regions"
            )
        post_regions = np.asarray(post_regions_value).astype(str)
        if post_regions.shape != raw_regions.shape:
            raise HEMProjectedFvmDryRunError(
                "post accepted-state region shape does not match raw regions"
            )
        if not np.array_equal(post_regions, raw_regions):
            raise HEMProjectedFvmDryRunError(
                "post accepted-state regions do not match the raw thermodynamic regions"
            )
        for name, value in (
            ("pressure", post_primitive.p),
            ("temperature", post_primitive.T),
            ("sound speed", post_primitive.c),
        ):
            array = np.asarray(value, dtype=float)
            if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
                raise HEMProjectedFvmDryRunError(
                    f"post accepted-state {name} must be finite and positive"
                )

        second_operator = projection_factory(config.projection_config)
        second = second_operator.project(np.array(post_U, copy=True))
        if np.any(second.projection_applied):
            raise HEMProjectedFvmDryRunError(
                "second equilibrium-quality projection must be a no-op"
            )
        if not np.array_equal(second.U_after, post_U):
            raise HEMProjectedFvmDryRunError(
                "second projection changed the already synchronized state"
            )

        q_raw = np.asarray(vapor_mass_fraction(raw_case.raw_U), dtype=float)
        q_post = np.asarray(vapor_mass_fraction(post_U), dtype=float)
        q_second = np.asarray(vapor_mass_fraction(second.U_after), dtype=float)
        q_eq = np.asarray(first.q_equilibrium, dtype=float)
        if np.any(
            np.abs(q_post - q_eq)
            > config.projection_config.activation_tolerance
        ):
            raise HEMProjectedFvmDryRunError(
                "post-projection transported quality does not match equilibrium quality"
            )

        budget = _budget_diagnostics(
            raw_case=raw_case,
            first=first,
            post_U=post_U,
            config=config,
        )
        for key in (
            "phase_vapor_mass_balance_residual_kg",
            "projection_source_consistency_residual_kg",
            "combined_post_vapor_balance_residual_kg",
        ):
            if (
                abs(float(budget[key]))
                > config.vapor_budget_absolute_tolerance_kg
            ):
                raise HEMProjectedFvmDryRunError(
                    f"vapor budget residual exceeds tolerance: {key}={budget[key]}"
                )

        p = np.asarray(post_primitive.p, dtype=float)
        T = np.asarray(post_primitive.T, dtype=float)
        alpha = np.asarray(post_primitive.alpha, dtype=float)
        sound = np.asarray(post_primitive.c, dtype=float)
        expected = (raw_case.raw_U.shape[0],)
        if any(
            np.asarray(value).shape != expected
            for value in (q_raw, q_post, q_second, q_eq, p, T, alpha, sound)
        ):
            raise HEMProjectedFvmDryRunError(
                "projected cellwise evidence returned an incompatible shape"
            )

        raw_cells_by_index = {
            cell.cell_index: cell for cell in raw_case.cells
        }
        cell_records = tuple(
            ProjectedFvmCellRecord(
                case_id=raw_case.spec.case_id,
                cell_index=index,
                raw_region=str(raw_regions[index]),
                post_region=str(post_regions[index]),
                transition_event=raw_cells_by_index[index].transition_event,
                q_transport_raw=float(q_raw[index]),
                q_equilibrium=float(q_eq[index]),
                q_after_first_projection=float(q_post[index]),
                q_after_second_projection=float(q_second[index]),
                delta_q_first=float(first.delta_q[index]),
                delta_rho_q_first=float(first.delta_rho_q[index]),
                first_projection_applied=bool(
                    first.projection_applied[index]
                ),
                second_projection_applied=bool(
                    second.projection_applied[index]
                ),
                post_pressure_pa=float(p[index]),
                post_temperature_K=float(T[index]),
                post_void_fraction=float(alpha[index]),
                post_sound_speed_m_s=float(sound[index]),
            )
            for index in range(raw_case.raw_U.shape[0])
        )

        outcome: ProjectedCaseOutcome = (
            "ACCEPTED_CROSSING"
            if raw_case.outcome == "OPEN_TWO_PHASE"
            else "ACCEPTED_ALL_LIQUID_NOOP"
        )
        return ProjectedFvmCaseResult(
            raw_case=raw_case,
            outcome=outcome,
            failure_reason="",
            first_projection=first,
            second_projection=second,
            post_U=post_U,
            second_U=np.array(second.U_after, dtype=float, copy=True),
            post_regions=np.array(post_regions, copy=True),
            cells=cell_records,
            budget_diagnostics=budget,
            post_accepted_state_eos_exercised=True,
        )
    except Exception as exc:
        return ProjectedFvmCaseResult(
            raw_case=raw_case,
            outcome=_failure_outcome(exc),
            failure_reason=f"{type(exc).__name__}: {exc}",
            first_projection=None,
            second_projection=None,
            post_U=empty_U,
            second_U=empty_U,
            post_regions=empty_regions,
            cells=(),
            budget_diagnostics={},
            post_accepted_state_eos_exercised=False,
        )


def run_projected_fvm_dry_run_matrix(
    config: HEMProjectedFvmDryRunConfig | None = None,
    *,
    raw_result: HEMMinimalRawFvmDryRunResult | None = None,
    raw_runner: RawMatrixRunner = run_minimal_raw_fvm_dry_run_matrix,
    projection_factory: ProjectionFactory = _default_projection_factory,
    accepted_eos_factory: AcceptedEosFactory = _default_accepted_eos_factory,
) -> HEMProjectedFvmDryRunResult:
    """Run the fixed projection, accepted-state, no-op, and vapor-budget matrix."""

    cfg = config or HEMProjectedFvmDryRunConfig()
    raw = raw_result or raw_runner(cfg.raw_config)
    cases = tuple(
        run_one_projected_fvm_case(
            case,
            cfg,
            projection_factory=projection_factory,
            accepted_eos_factory=accepted_eos_factory,
        )
        for case in raw.cases
    )
    return HEMProjectedFvmDryRunResult(
        config=cfg,
        raw_summary=raw.summary(),
        cases=cases,
    )


def _config_payload(config: HEMProjectedFvmDryRunConfig) -> dict[str, object]:
    return {
        "raw_config": {
            "n_cells": config.raw_config.n_cells,
            "length_m": config.raw_config.length_m,
            "diameter_m": config.raw_config.diameter_m,
            "cfl": config.raw_config.cfl,
            "n_ghost": config.raw_config.n_ghost,
            "interface_cell": config.raw_config.resolved_interface_cell,
            "case_specs": [
                asdict(spec) for spec in config.raw_config.case_specs
            ],
        },
        "projection_config": asdict(config.projection_config),
        "accepted_state_quality_tolerance": (
            config.accepted_state_quality_tolerance
        ),
        "vapor_budget_absolute_tolerance_kg": (
            config.vapor_budget_absolute_tolerance_kg
        ),
    }


def write_projected_fvm_dry_run_artifacts(
    output_dir: str | Path,
    result: HEMProjectedFvmDryRunResult,
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown, and NPZ evidence for the fixed matrix."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_projected_fvm_dry_run"
    paths = {
        "json": target / f"{stem}.json",
        "cases_csv": target / f"{stem}_cases.csv",
        "cells_csv": target / f"{stem}_cells.csv",
        "markdown": target / f"{stem}.md",
        "npz": target / f"{stem}.npz",
    }

    case_summaries = [case.summary() for case in result.cases]
    payload = {
        **result.summary(),
        "config": _config_payload(result.config),
        "cases": case_summaries,
        "cells": [
            asdict(cell) for case in result.cases for cell in case.cells
        ],
    }
    paths["json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with paths["cases_csv"].open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fieldnames = [
            "case_id",
            "role",
            "raw_outcome",
            "outcome",
            "failure_reason",
            "dt_s",
            "crossing_cell_indices",
            "first_projection_cell_indices",
            "second_projection_cell_indices",
            "max_post_quality_mismatch",
            "projection_vapor_source_kg",
            "combined_post_vapor_balance_residual_kg",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for summary in case_summaries:
            budget = summary["budget_diagnostics"] or {}
            writer.writerow(
                {
                    "case_id": summary["case_id"],
                    "role": summary["role"],
                    "raw_outcome": summary["raw_outcome"],
                    "outcome": summary["outcome"],
                    "failure_reason": summary["failure_reason"],
                    "dt_s": summary["dt_s"],
                    "crossing_cell_indices": json.dumps(
                        summary["crossing_cell_indices"]
                    ),
                    "first_projection_cell_indices": json.dumps(
                        summary["first_projection_cell_indices"]
                    ),
                    "second_projection_cell_indices": json.dumps(
                        summary["second_projection_cell_indices"]
                    ),
                    "max_post_quality_mismatch": summary[
                        "max_post_quality_mismatch"
                    ],
                    "projection_vapor_source_kg": budget.get(
                        "projection_vapor_source_kg"
                    ),
                    "combined_post_vapor_balance_residual_kg": budget.get(
                        "combined_post_vapor_balance_residual_kg"
                    ),
                }
            )

    cell_rows = [
        asdict(cell) for case in result.cases for cell in case.cells
    ]
    with paths["cells_csv"].open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        if cell_rows:
            writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
            writer.writeheader()
            writer.writerows(cell_rows)
        else:
            handle.write("case_id,cell_index\n")

    lines = [
        "# Stage 7 Projected Liquid-to-Two-Phase FVM Dry Run",
        "",
        "Verification-only one-step projection and accepted-state evidence.",
        "",
        (
            "- accepted crossing cases: "
            f"{result.summary()['accepted_crossing_case_ids']}"
        ),
        (
            "- liquid no-op cases: "
            f"{result.summary()['accepted_liquid_noop_case_ids']}"
        ),
        "- formal Case A / Case B freeze: false",
        "- production / Validation / design use: false",
        "",
        "| case | raw outcome | projected outcome | crossing cells | "
        "projection cells | second projection | vapor source kg |",
        "|---|---|---|---|---|---|---:|",
    ]
    for summary in case_summaries:
        budget = summary["budget_diagnostics"] or {}
        lines.append(
            "| {case} | {raw} | {outcome} | {crossing} | {first} | "
            "{second} | {source} |".format(
                case=summary["case_id"],
                raw=summary["raw_outcome"],
                outcome=summary["outcome"],
                crossing=summary["crossing_cell_indices"],
                first=summary["first_projection_cell_indices"],
                second=summary["second_projection_cell_indices"],
                source=budget.get("projection_vapor_source_kg", ""),
            )
        )
    paths["markdown"].write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    arrays: dict[str, np.ndarray] = {}
    for case in result.cases:
        key = case.raw_case.spec.case_id
        arrays[f"{key}_raw_U"] = np.asarray(
            case.raw_case.raw_U, dtype=float
        )
        arrays[f"{key}_post_U"] = np.asarray(case.post_U, dtype=float)
        arrays[f"{key}_second_U"] = np.asarray(case.second_U, dtype=float)
    np.savez(paths["npz"], **arrays)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed projected liquid-to-two-phase FVM dry-run matrix."
        )
    )
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    result = run_projected_fvm_dry_run_matrix()
    paths = write_projected_fvm_dry_run_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if result.summary()["all_fixed_cases_completed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
