"""Verification-only mesh/CFL variant runner for Stage 7 P1-A3.

The locked Gate 6 runner remains untouched.  This module reuses its reviewed
step orchestration and evidence helpers, but supplies a separately declared
mesh/CFL matrix and a variant baseline validator.  It is not a production
configuration path and it does not relax the fixed Gate 6 authority contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Literal

import numpy as np

from . import hem_pipeline_post_crossing_propagation as gate6
from .hem_pipeline_depressurization_first_crossing import (
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
)

P1_A3_ALLOWED_MESH_CFL: tuple[tuple[int, float], ...] = (
    (16, 0.10),
    (32, 0.10),
    (64, 0.10),
    (32, 0.05),
    (32, 0.20),
)
P1_A3_CONTINUATION_OFFSETS = gate6.CONTINUATION_OFFSETS

VariantContinuationOutcome = Literal[
    "COMPLETED_FIXED_CHECKPOINTS",
    "FAIL_SAFE_STOP",
]


class HEMMeshCflVariantError(RuntimeError):
    """Raised when a P1-A3 variant cannot satisfy its bounded contract."""


@dataclass(frozen=True)
class HEMMeshCflPipelineConfig(HEMPipelineDepressurizationConfig):
    """A verification-only derivative varying only mesh count and CFL."""

    def __post_init__(self) -> None:
        baseline = HEMPipelineDepressurizationConfig()
        for item in fields(HEMPipelineDepressurizationConfig):
            if item.name in {"n_cells", "cfl"}:
                continue
            actual = getattr(self, item.name)
            expected = getattr(baseline, item.name)
            if actual != expected:
                raise ValueError(
                    "P1-A3 may vary only n_cells and cfl; "
                    f"{item.name}={actual!r}, expected={expected!r}"
                )

        allowed = any(
            self.n_cells == cells
            and math.isclose(self.cfl, cfl, rel_tol=0.0, abs_tol=1.0e-15)
            for cells, cfl in P1_A3_ALLOWED_MESH_CFL
        )
        if not allowed:
            raise ValueError(
                "P1-A3 mesh/CFL pair is outside the predeclared matrix: "
                f"n_cells={self.n_cells}, cfl={self.cfl}"
            )
        if self.n_cells < 4:
            raise ValueError("P1-A3 n_cells must be at least 4")
        if not math.isfinite(self.cfl) or not 0.0 < self.cfl <= 1.0:
            raise ValueError("P1-A3 cfl must be finite and lie in (0, 1]")


@dataclass(frozen=True)
class HEMMeshCflPropagationConfig:
    """Duck-typed continuation config used only by the P1-A3 variant runner."""

    pipeline: HEMMeshCflPipelineConfig
    continuation_offsets: tuple[int, ...] = P1_A3_CONTINUATION_OFFSETS

    def __post_init__(self) -> None:
        if self.continuation_offsets != P1_A3_CONTINUATION_OFFSETS:
            raise ValueError(
                "P1-A3 continuation offsets are fixed at +1 / +4 / +16 / +64"
            )

    @property
    def maximum_post_crossing_steps(self) -> int:
        return self.continuation_offsets[-1]


@dataclass(frozen=True)
class MeshCflVariantExecution:
    """Internal accepted-history bundle for one P1-A3 variant."""

    config: HEMMeshCflPropagationConfig
    baseline: PipelineCaseResult
    outcome: VariantContinuationOutcome
    failure_category: str
    failure_reason: str
    failure_absolute_step: int | None
    failure_post_crossing_step: int | None
    last_valid_state_sha256: str
    steps: tuple[gate6.PostCrossingStepRecord, ...]
    cells: tuple[gate6.PostCrossingCellRecord, ...]
    checkpoints: tuple[gate6.PostCrossingCheckpointRecord, ...]
    classifications: tuple[str, ...]
    classification_rationale: tuple[str, ...]
    baseline_open_two_phase_cell_indices: tuple[int, ...]
    region_toggle_counts: tuple[int, ...]
    provenance: dict[str, object]


def _require_variant_first_crossing(
    result: PipelineCaseResult,
    expected_config: HEMMeshCflPipelineConfig,
) -> None:
    """Fail closed unless the variant reaches a finite accepted first crossing."""

    failures: list[str] = []
    if result.config != expected_config:
        failures.append("returned config differs from requested variant")
    if result.outcome != "ACCEPTED_FIRST_CROSSING":
        failures.append(f"outcome={result.outcome}")
    if result.failure_reason:
        failures.append(f"failure_reason={result.failure_reason}")
    if result.crossing_step is None or result.crossing_step != result.step_count:
        failures.append("crossing step must equal the retained stop step")
    if result.crossing_time_s is None or not math.isfinite(result.crossing_time_s):
        failures.append("crossing time is unavailable or nonfinite")
    if not result.crossing_cell_indices:
        failures.append("no crossing cells were retained")
    if len(result.crossing_cell_indices) != len(
        result.crossing_distances_from_outlet_m
    ):
        failures.append("crossing cell and distance counts differ")
    if result.reverse_flow_fallback_count != 0:
        failures.append("reverse-flow fallback was activated")
    if (
        not math.isfinite(result.maximum_crossing_quality)
        or result.maximum_crossing_quality
        < expected_config.crossing_evidence_min_quality
    ):
        failures.append("crossing quality does not meet the fixed evidence floor")
    if result.accepted_state_history.shape != (
        result.step_count + 1,
        expected_config.n_cells,
        gate6.N_VARS,
    ):
        failures.append("accepted-state history shape is incompatible")
    if result.pressure_history_pa.shape != (
        result.step_count + 1,
        expected_config.n_cells,
    ):
        failures.append("pressure history shape is incompatible")
    if result.time_history_s.shape != (result.step_count + 1,):
        failures.append("time history shape is incompatible")
    if len(result.pressure_drop_arrival_times_s) != expected_config.n_cells:
        failures.append("pressure-arrival vector length is incompatible")
    if not np.all(np.isfinite(result.accepted_state_history)):
        failures.append("accepted-state history contains nonfinite values")
    if not np.all(np.isfinite(result.pressure_history_pa)):
        failures.append("pressure history contains nonfinite values")
    if not np.all(np.isfinite(result.time_history_s)):
        failures.append("time history contains nonfinite values")
    if np.any(np.diff(result.time_history_s) <= 0.0):
        failures.append("time history is not strictly increasing")
    if failures:
        raise HEMMeshCflVariantError("; ".join(failures))


def run_mesh_cfl_variant(
    config: HEMMeshCflPropagationConfig,
) -> MeshCflVariantExecution:
    """Run one predeclared mesh/CFL variant through first crossing and +64 steps."""

    pipeline = config.pipeline
    case = gate6._baseline_case_spec()
    baseline = gate6.run_pipeline_depressurization_case(case, pipeline)
    _require_variant_first_crossing(baseline, pipeline)

    crossing_U = np.array(
        baseline.accepted_state_history[-1], dtype=float, copy=True
    )
    schedule = gate6.LinearPressureRamp(
        p_initial_pa=pipeline.initial_pressure_pa,
        p_final_pa=case.final_boundary_pressure_pa,
        t_start_s=0.0,
        duration_s=baseline.ramp_duration_s,
    )
    provider = gate6.VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=pipeline.subcooling_K,
        phase_config=pipeline.phase_config,
    )
    right_boundary = gate6.VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    grid = gate6.UniformGrid(
        gate6.PipeGeometry(
            length_m=pipeline.length_m,
            diameter_m=pipeline.diameter_m,
        ),
        n_cells=pipeline.n_cells,
    )
    eos = gate6.VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=pipeline.accepted_state_quality_tolerance,
        phase_config=pipeline.phase_config,
        quality_sync_config=pipeline.projection_config,
    )
    solver = gate6.FvmSolver(
        grid=grid,
        eos=eos,
        U=crossing_U,
        cfl=pipeline.cfl,
        n_ghost=pipeline.n_ghost,
        left_boundary=gate6.ReflectiveBoundary(),
        right_boundary=right_boundary,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=baseline.final_time_s,
        step_count=baseline.step_count,
    )
    continuation_initial_inventory = gate6.inventory(
        crossing_U, grid.dx, grid.geometry.area_m2
    )
    phase_tracker = gate6.PhaseChangeBudgetTracker(
        initial_inventory=continuation_initial_inventory
    )
    baseline_regions = gate6._baseline_regions(baseline)
    baseline_open_cells = tuple(
        index
        for index, region in enumerate(baseline_regions)
        if region == "OPEN_TWO_PHASE"
    )
    previous_regions = list(baseline_regions)
    toggle_counts = [0] * pipeline.n_cells
    step_records: list[gate6.PostCrossingStepRecord] = []
    cell_records: list[gate6.PostCrossingCellRecord] = []
    checkpoint_by_offset: dict[int, gate6.PostCrossingCheckpointRecord] = {}
    latest_projected_budget: dict[str, float] = {}
    outcome: VariantContinuationOutcome = "COMPLETED_FIXED_CHECKPOINTS"
    failure_category = ""
    failure_reason = ""
    failure_absolute_step: int | None = None
    failure_post_step: int | None = None
    last_valid_hash = gate6._state_sha256(solver.U)

    for post_step in range(1, config.maximum_post_crossing_steps + 1):
        try:
            time_before = float(solver.t)
            previous_U = np.array(solver.U, dtype=float, copy=True)
            previous_primitive = solver.primitive()
            previous_inventory = gate6.inventory(
                previous_U, grid.dx, grid.geometry.area_m2
            )
            if solver.boundary_budget is None:
                raise HEMMeshCflVariantError("boundary budget tracker is required")
            left_before = np.array(
                solver.boundary_budget.cumulative_left,
                dtype=float,
                copy=True,
            )
            right_before = np.array(
                solver.boundary_budget.cumulative_right,
                dtype=float,
                copy=True,
            )
            reverse_before = right_boundary.reverse_flow_fallback_count
            dt = float(solver.compute_dt())
            if not math.isfinite(dt) or dt <= 0.0:
                raise HEMMeshCflVariantError(
                    "computed continuation dt must be finite and positive"
                )

            solver.step(dt)
            raw_U = np.array(solver.U, dtype=float, copy=True)
            raw_inventory = gate6.inventory(
                raw_U, grid.dx, grid.geometry.area_m2
            )
            raw_budget = gate6._incremental_boundary_budget(
                previous_inventory=previous_inventory,
                raw_inventory=raw_inventory,
                step_left=solver.boundary_budget.cumulative_left - left_before,
                step_right=solver.boundary_budget.cumulative_right - right_before,
                config=pipeline,
            )
            if (
                right_boundary.reverse_flow_fallback_count - reverse_before
            ) > 0:
                raise HEMMeshCflVariantError(
                    "reverse flow fallback was activated"
                )

            detection = gate6.detect_raw_transition_events(
                previous_U,
                raw_U,
                phase_config=pipeline.phase_config,
            )
            raw_class = gate6._classify_raw_state(detection)
            if raw_class not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
                raise HEMMeshCflVariantError(
                    f"raw continuation entered {raw_class}"
                )
            boundary_state = right_boundary.last_state or provider.state_at(
                time_before
            )
            raw_case = gate6._raw_case(
                case=case,
                config=pipeline,
                grid=grid,
                previous_U=previous_U,
                raw_U=raw_U,
                previous_primitive=previous_primitive,
                detection=detection,
                boundary_state=boundary_state,
                dt=dt,
                raw_budget=raw_budget,
            )
            (
                first,
                second,
                post_U,
                primitive,
                post_regions,
                projected_budget,
            ) = gate6._project_and_accept(
                raw_case=raw_case,
                detection=detection,
                config=pipeline,
            )
            latest_projected_budget = dict(projected_budget)
            phase_tracker.record_phase_change(
                U_before=raw_U,
                U_after=post_U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
                dt=dt,
            )
            solver.U = np.array(post_U, dtype=float, copy=True)
            boundary_diag, phase_diag = gate6._validate_cumulative_budgets(
                solver=solver,
                phase_tracker=phase_tracker,
                initial_inventory=continuation_initial_inventory,
                latest_projected_budget=latest_projected_budget,
                config=pipeline,
            )

            regions = np.asarray(post_regions).astype(str)
            events = np.asarray(detection.transitions.event).astype(str)
            raw_regions = np.asarray(detection.raw.region).astype(str)
            previous_detection_regions = np.asarray(
                detection.previous.region
            ).astype(str)
            q_raw = np.asarray(gate6.vapor_mass_fraction(raw_U), dtype=float)
            q_eq = np.asarray(first.q_equilibrium, dtype=float)
            q_post = np.asarray(gate6.vapor_mass_fraction(post_U), dtype=float)
            alpha = np.asarray(primitive.alpha, dtype=float)
            pressure = np.asarray(primitive.p, dtype=float)
            temperature = np.asarray(primitive.T, dtype=float)
            sound = np.asarray(primitive.c, dtype=float)
            speed = np.asarray(gate6.velocity(post_U), dtype=float)
            e = np.asarray(gate6.internal_energy(post_U), dtype=float)

            open_cells = tuple(
                int(index)
                for index in np.flatnonzero(regions == "OPEN_TWO_PHASE")
            )
            furthest = min(open_cells) if open_cells else None
            furthest_distance = (
                None
                if furthest is None
                else float(pipeline.length_m - grid.cell_centers[furthest])
            )
            for index, region in enumerate(regions):
                if region != previous_regions[index]:
                    toggle_counts[index] += 1
                previous_regions[index] = str(region)

            acoustic_by_cell: list[dict[str, object]] = []
            for index in range(pipeline.n_cells):
                acoustic_by_cell.append(
                    gate6._sound_speed_evidence(
                        float(post_U[index, gate6.IDX_RHO]),
                        float(e[index]),
                    )
                )

            for index in range(pipeline.n_cells):
                acoustic = acoustic_by_cell[index]
                cell_records.append(
                    gate6.PostCrossingCellRecord(
                        case_id=case.case_id,
                        absolute_step=int(solver.step_count),
                        post_crossing_step=post_step,
                        time_s=float(solver.t),
                        cell_index=index,
                        cell_center_m=float(grid.cell_centers[index]),
                        distance_from_outlet_m=float(
                            pipeline.length_m - grid.cell_centers[index]
                        ),
                        previous_region=str(previous_detection_regions[index]),
                        raw_region=str(raw_regions[index]),
                        post_region=str(regions[index]),
                        transition_event=str(events[index]),
                        rho_kg_m3=float(post_U[index, gate6.IDX_RHO]),
                        momentum_kg_m2_s=float(post_U[index, gate6.IDX_MOM]),
                        rhoE_J_m3=float(post_U[index, gate6.IDX_RHOE]),
                        rho_q_kg_m3=float(post_U[index, gate6.IDX_RHO_XV]),
                        velocity_m_s=float(speed[index]),
                        internal_energy_j_kg=float(e[index]),
                        pressure_pa=float(pressure[index]),
                        temperature_K=float(temperature[index]),
                        q_transport_raw=float(q_raw[index]),
                        q_equilibrium=float(q_eq[index]),
                        q_post=float(q_post[index]),
                        void_fraction=float(alpha[index]),
                        projection_applied=bool(first.projection_applied[index]),
                        delta_rho_q=float(first.delta_rho_q[index]),
                        **acoustic,
                    )
                )

            current_inventory = gate6.inventory(
                post_U, grid.dx, grid.geometry.area_m2
            )
            liquid_mask = regions == "LIQUID_CANDIDATE"
            two_phase_mask = regions == "OPEN_TWO_PHASE"

            def extrema(mask: np.ndarray) -> tuple[float | None, float | None]:
                values = sound[mask]
                if values.size == 0:
                    return None, None
                return float(np.min(values)), float(np.max(values))

            liquid_c_min, liquid_c_max = extrema(liquid_mask)
            two_phase_c_min, two_phase_c_max = extrema(two_phase_mask)
            record = gate6.PostCrossingStepRecord(
                case_id=case.case_id,
                absolute_step=int(solver.step_count),
                post_crossing_step=post_step,
                time_before_s=time_before,
                dt_s=dt,
                time_after_s=float(solver.t),
                raw_state_class=raw_class,
                accepted_state_class=(
                    "OPEN_TWO_PHASE_PRESENT" if open_cells else "ALL_LIQUID"
                ),
                open_two_phase_cell_count=len(open_cells),
                open_two_phase_cell_indices=open_cells,
                furthest_upstream_two_phase_cell=furthest,
                furthest_upstream_distance_from_outlet_m=furthest_distance,
                liquid_to_two_phase_event_count=int(
                    np.count_nonzero(
                        events == "LIQUID_TO_TWO_PHASE_CROSSING"
                    )
                ),
                reverse_transition_event_count=int(
                    np.count_nonzero(events == "REVERSE_TRANSITION")
                ),
                projection_cell_count=int(
                    np.count_nonzero(first.projection_applied)
                ),
                second_projection_cell_count=int(
                    np.count_nonzero(second.projection_applied)
                ),
                maximum_equilibrium_quality=float(
                    np.max(q_eq, initial=0.0)
                ),
                integrated_equilibrium_quality=float(
                    np.sum(q_eq) * grid.dx
                ),
                maximum_void_fraction=float(
                    np.max(alpha, initial=0.0)
                ),
                pressure_min_pa=float(np.min(pressure)),
                pressure_max_pa=float(np.max(pressure)),
                liquid_sound_speed_min_m_s=liquid_c_min,
                liquid_sound_speed_max_m_s=liquid_c_max,
                two_phase_sound_speed_min_m_s=two_phase_c_min,
                two_phase_sound_speed_max_m_s=two_phase_c_max,
                mass_total_kg=float(current_inventory["mass_total"]),
                momentum_total_kg_m_s=float(
                    current_inventory["momentum_total"]
                ),
                energy_total_J=float(current_inventory["energy_total"]),
                vapor_mass_total_kg=float(
                    current_inventory["vapor_mass_total"]
                ),
                boundary_mass_residual_kg=float(
                    boundary_diag["budget_mass_residual"]
                ),
                boundary_momentum_residual_kg_m_s=float(
                    boundary_diag["budget_momentum_residual"]
                ),
                boundary_energy_residual_J=float(
                    boundary_diag["budget_energy_residual"]
                ),
                phase_vapor_residual_kg=float(
                    phase_diag["phase_vapor_mass_balance_residual_kg"]
                ),
                projection_vapor_source_step_kg=float(
                    projected_budget["projection_vapor_source_kg"]
                ),
                boundary_vapor_step_kg=float(
                    raw_budget["budget_vapor_mass_net_boundary"]
                ),
                second_projection_noop=bool(
                    not np.any(second.projection_applied)
                    and np.array_equal(second.U_after, post_U)
                ),
                state_sha256=gate6._state_sha256(post_U),
            )
            step_records.append(record)
            last_valid_hash = record.state_sha256
            if post_step in config.continuation_offsets:
                checkpoint_by_offset[post_step] = gate6._checkpoint_from_step(
                    record
                )
        except Exception as exc:
            outcome = "FAIL_SAFE_STOP"
            failure_category = gate6._failure_category(exc)
            failure_reason = f"{type(exc).__name__}: {exc}"
            failure_absolute_step = int(solver.step_count)
            failure_post_step = post_step
            break

    checkpoints = tuple(
        checkpoint_by_offset.get(
            offset,
            gate6._missing_checkpoint(
                case.case_id,
                offset,
                int(solver.step_count),
                float(solver.t),
                last_valid_hash,
            ),
        )
        for offset in config.continuation_offsets
    )
    labels, rationale = gate6._review_classifications(
        outcome=outcome,
        steps=step_records,
        baseline_open_cells=baseline_open_cells,
        region_toggle_counts=toggle_counts,
    )
    return MeshCflVariantExecution(
        config=config,
        baseline=baseline,
        outcome=outcome,
        failure_category=failure_category,
        failure_reason=failure_reason,
        failure_absolute_step=failure_absolute_step,
        failure_post_crossing_step=failure_post_step,
        last_valid_state_sha256=last_valid_hash,
        steps=tuple(step_records),
        cells=tuple(cell_records),
        checkpoints=checkpoints,
        classifications=labels,
        classification_rationale=rationale,
        baseline_open_two_phase_cell_indices=baseline_open_cells,
        region_toggle_counts=tuple(toggle_counts),
        provenance=gate6._git_provenance(),
    )
