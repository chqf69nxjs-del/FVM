"""Verification-only mesh sensitivity for the fixed Stage 7 pipeline matrix.

The merged PR #77 configuration remains immutable.  This module introduces a
separate mesh-only harness that permits exactly 32, 64, or 128 cells, derives
``dx`` from the fixed 1 m pipe, and scales the computational step cap as
2000/4000/8000 while preserving the fixed physical horizon and CFL=0.10.

No production solver, numerical flux, phase classifier, projection, boundary
model, or tolerance is modified here.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Callable, Literal, Sequence

import numpy as np

from .hem_equilibrium_sound_speed import estimate_coolprop_equilibrium_sound_speed
from .hem_pipeline_4mpa_subthreshold_forensics import _saturation_margin_values
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineCellRecord,
    PipelineDepressurizationCaseSpec,
    PipelineStepRecord,
    run_pipeline_depressurization_case,
)
from .state import IDX_RHO, internal_energy


MESH_CELL_COUNTS: tuple[int, ...] = (32, 64, 128)
MESH_STEP_CAPS: dict[int, int] = {32: 2000, 64: 4000, 128: 8000}
FOUR_MPA_CASE_ID = "pipeline_liquid_control_p5m5_to_p4m5"

MeshClassification = Literal[
    "CROSSING_VANISHES_WITH_REFINEMENT",
    "CROSSING_DEPTH_DECAYS_WITH_REFINEMENT",
    "FINITE_CROSSING_PERSISTS_ACROSS_MESHES",
    "CROSSING_TIME_POSITION_TREND_STABLE",
    "CROSSING_TIME_POSITION_NOT_STABLE",
    "MESH_SEQUENCE_NON_MONOTONE",
    "MESH_SENSITIVITY_INCONCLUSIVE",
]

EXPECTED_32_CELL_4MPA = {
    "outcome": "GUARD_FAILURE",
    "failure_reason": (
        "HEMPipelineDepressurizationError: "
        "crossing quality evidence is below the fixed minimum"
    ),
    "step_count": 313,
    "final_time_s": 0.001996923102525957,
    "crossing_step": 313,
    "crossing_time_s": 0.001996923102525957,
    "crossing_cell_index": 25,
    "crossing_distance_from_outlet_m": 0.203125,
    "maximum_crossing_quality": 9.672588429198319e-9,
    "final_state_sha256": (
        "7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1"
    ),
    "run_signature_sha256": (
        "fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202"
    ),
}


class HEMPipelineMeshSensitivityError(RuntimeError):
    """Raised when the reviewed mesh-only contract cannot be completed."""


@dataclass(frozen=True)
class HEMPipelineMeshSensitivityConfig(HEMPipelineDepressurizationConfig):
    """PR #77 configuration with only the reviewed mesh fields variable."""

    def __post_init__(self) -> None:
        if isinstance(self.n_cells, bool) or self.n_cells not in MESH_CELL_COUNTS:
            raise ValueError(
                f"mesh sensitivity n_cells must be one of {MESH_CELL_COUNTS}"
            )
        expected_steps = MESH_STEP_CAPS[self.n_cells]
        if self.max_steps != expected_steps:
            raise ValueError(
                f"mesh sensitivity max_steps is fixed at {expected_steps} "
                f"for n_cells={self.n_cells}"
            )

        fixed = HEMPipelineDepressurizationConfig()
        for item in fields(HEMPipelineDepressurizationConfig):
            if item.name in {"n_cells", "max_steps"}:
                continue
            actual = getattr(self, item.name)
            expected = getattr(fixed, item.name)
            if actual != expected:
                raise ValueError(
                    f"mesh sensitivity may not change {item.name}: "
                    f"expected {expected!r}, received {actual!r}"
                )

    @classmethod
    def for_cells(cls, n_cells: int) -> "HEMPipelineMeshSensitivityConfig":
        if isinstance(n_cells, bool) or n_cells not in MESH_STEP_CAPS:
            raise ValueError(f"n_cells must be one of {MESH_CELL_COUNTS}")
        return cls(n_cells=int(n_cells), max_steps=MESH_STEP_CAPS[int(n_cells)])

    @property
    def mesh_override(self) -> dict[str, object]:
        return {
            "n_cells": self.n_cells,
            "dx_m": self.dx_m,
            "maximum_steps": self.max_steps,
        }


@dataclass(frozen=True)
class ClosestLiquidMargin:
    step_index: int
    time_s: float
    cell_index: int
    distance_from_outlet_m: float
    pressure_pa: float
    rho_kg_m3: float
    e_j_kg: float
    delta_u_sat_j_kg: float
    delta_v_sat_m3_kg: float
    q_from_internal_energy: float
    q_from_specific_volume: float


@dataclass(frozen=True)
class MeshCaseMetrics:
    run_id: str
    case_id: str
    role: str
    final_boundary_pressure_pa: float
    n_cells: int
    dx_m: float
    maximum_steps: int
    cfl: float
    outcome: str
    failure_reason: str
    step_count: int
    final_time_s: float
    initial_acoustic_time_s: float
    maximum_horizon_s: float
    preflight_accepted_sample_count: int
    raw_crossing_observed: bool
    crossing_step: int | None
    crossing_time_s: float | None
    normalized_crossing_time: float | None
    crossing_cell_index: int | None
    crossing_cell_center_m: float | None
    crossing_distance_from_outlet_m: float | None
    normalized_crossing_distance_from_outlet: float | None
    maximum_crossing_quality: float
    maximum_projected_quality: float
    maximum_void_fraction: float
    crossing_delta_u_sat_j_kg: float | None
    crossing_delta_v_sat_m3_kg: float | None
    crossing_q_from_internal_energy: float | None
    crossing_q_from_specific_volume: float | None
    pre_crossing_liquid_sound_speed_m_s: float | None
    raw_crossing_sound_speed_m_s: float | None
    sound_speed_ratio_raw_to_pre: float | None
    closest_liquid_step: int | None
    closest_liquid_time_s: float | None
    closest_liquid_cell_index: int | None
    closest_liquid_distance_from_outlet_m: float | None
    closest_liquid_delta_u_sat_j_kg: float | None
    closest_liquid_delta_v_sat_m3_kg: float | None
    closest_liquid_q_from_internal_energy: float | None
    closest_liquid_q_from_specific_volume: float | None
    projection_vapor_source_kg: float | None
    boundary_vapor_transport_kg: float | None
    mass_residual_kg: float | None
    momentum_residual_kg_m_s: float | None
    energy_residual_J: float | None
    combined_vapor_residual_kg: float | None
    reverse_flow_fallback_count: int
    final_state_sha256: str
    run_signature_sha256: str

    def summary(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HEMPipelineMeshSensitivityResult:
    cases: tuple[MeshCaseMetrics, ...]
    four_mpa_classifications: tuple[MeshClassification, ...]
    four_mpa_classification_rationale: dict[str, str]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "stage7_lco2_hem_pipeline_mesh_sensitivity_v1",
            "scope": "verification_only",
            "case_count": len(self.cases),
            "mesh_cell_counts": list(MESH_CELL_COUNTS),
            "mesh_step_caps": {str(key): value for key, value in MESH_STEP_CAPS.items()},
            "final_boundary_pressures_pa": [
                case.final_boundary_pressure_pa
                for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
            ],
            "four_mpa_classifications": list(self.four_mpa_classifications),
            "four_mpa_classification_rationale": dict(
                self.four_mpa_classification_rationale
            ),
            "thirty_two_cell_baseline_reproduced_exactly": True,
            "only_mesh_fields_varied": True,
            "CFL": 0.10,
            "Gate_P2_passed": False,
            "mesh_independent_crossing_verified": False,
            "CFL_independent_crossing_verified": False,
            "two_phase_acoustic_accuracy_band_approved": False,
            "post_crossing_propagation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


MeshCaseRunner = Callable[
    [PipelineDepressurizationCaseSpec, HEMPipelineDepressurizationConfig],
    PipelineCaseResult,
]
MeshCaseCallback = Callable[[PipelineCaseResult, MeshCaseMetrics], None]


def _props_si():
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("CoolProp is required for pipeline mesh sensitivity") from exc
    return PropsSI


def _finite_or_none(mapping: dict[str, float], key: str) -> float | None:
    if key not in mapping:
        return None
    value = float(mapping[key])
    return value if np.isfinite(value) else None


def _crossing_cell_record(case: PipelineCaseResult) -> PipelineCellRecord | None:
    if case.crossing_step is None:
        return None
    indices = set(case.crossing_cell_indices)
    candidates = [
        cell
        for cell in case.cells
        if cell.step_index == case.crossing_step
        and cell.cell_index in indices
        and cell.transition_event == "LIQUID_TO_TWO_PHASE_CROSSING"
    ]
    if not candidates:
        candidates = [
            cell
            for cell in case.cells
            if cell.step_index == case.crossing_step and cell.cell_index in indices
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.q_equilibrium)


def _sound_speed_from_conserved(U: np.ndarray) -> float:
    state = np.asarray(U, dtype=float)
    rho = float(state[IDX_RHO])
    e = float(internal_energy(state))
    estimate = estimate_coolprop_equilibrium_sound_speed(rho, e)
    return float(estimate.sound_speed_m_s)


def _vector_saturation_property(
    output: str,
    pressure_pa: np.ndarray,
    quality: float,
    *,
    chunk_size: int = 4096,
) -> np.ndarray:
    props = _props_si()
    pressure = np.asarray(pressure_pa, dtype=float)
    result = np.empty_like(pressure)
    for start in range(0, pressure.size, chunk_size):
        stop = min(start + chunk_size, pressure.size)
        chunk = pressure[start:stop]
        try:
            values = np.asarray(
                props(output, "P", chunk, "Q", float(quality), "CO2"),
                dtype=float,
            )
            if values.shape == ():
                values = np.full(chunk.shape, float(values), dtype=float)
            if values.shape != chunk.shape:
                raise ValueError("unexpected vectorized CoolProp shape")
        except Exception:
            values = np.asarray(
                [
                    float(props(output, "P", float(p), "Q", float(quality), "CO2"))
                    for p in chunk
                ],
                dtype=float,
            )
        result[start:stop] = values
    if not np.all(np.isfinite(result)):
        raise HEMPipelineMeshSensitivityError(
            f"non-finite saturation property returned for {output}"
        )
    return result


def _closest_liquid_margin(case: PipelineCaseResult) -> ClosestLiquidMargin | None:
    records = [cell for cell in case.cells if cell.raw_region == "LIQUID_CANDIDATE"]
    if not records:
        return None

    pressure = np.asarray([cell.pressure_raw_pa for cell in records], dtype=float)
    rho = np.asarray([cell.rho_raw_kg_m3 for cell in records], dtype=float)
    e = np.asarray([cell.e_raw_j_kg for cell in records], dtype=float)

    uf = _vector_saturation_property("Umass", pressure, 0.0)
    ug = _vector_saturation_property("Umass", pressure, 1.0)
    rhof = _vector_saturation_property("Dmass", pressure, 0.0)
    rhog = _vector_saturation_property("Dmass", pressure, 1.0)
    vf = 1.0 / rhof
    vg = 1.0 / rhog
    v = 1.0 / rho

    delta_u = e - uf
    delta_v = v - vf
    q_u = delta_u / (ug - uf)
    q_v = delta_v / (vg - vf)

    valid = (
        np.isfinite(q_u)
        & np.isfinite(q_v)
        & (delta_u <= 0.0)
        & (delta_v <= 0.0)
    )
    if np.any(valid):
        valid_indices = np.flatnonzero(valid)
        score = np.minimum(q_u[valid], q_v[valid])
        selected = int(valid_indices[int(np.argmax(score))])
    else:
        distance = np.maximum(np.abs(q_u), np.abs(q_v))
        selected = int(np.nanargmin(distance))

    record = records[selected]
    return ClosestLiquidMargin(
        step_index=record.step_index,
        time_s=record.time_s,
        cell_index=record.cell_index,
        distance_from_outlet_m=record.distance_from_outlet_m,
        pressure_pa=record.pressure_raw_pa,
        rho_kg_m3=record.rho_raw_kg_m3,
        e_j_kg=record.e_raw_j_kg,
        delta_u_sat_j_kg=float(delta_u[selected]),
        delta_v_sat_m3_kg=float(delta_v[selected]),
        q_from_internal_energy=float(q_u[selected]),
        q_from_specific_volume=float(q_v[selected]),
    )


def _case_metrics(case: PipelineCaseResult) -> MeshCaseMetrics:
    cfg = case.config
    crossing = _crossing_cell_record(case)
    crossing_margin: dict[str, float | str] | None = None
    pre_sound: float | None = None
    raw_sound: float | None = None
    sound_ratio: float | None = None

    if crossing is not None:
        crossing_margin = _saturation_margin_values(
            crossing.rho_raw_kg_m3,
            crossing.e_raw_j_kg,
            crossing.pressure_raw_pa,
        )
        raw_sound = float(
            estimate_coolprop_equilibrium_sound_speed(
                crossing.rho_raw_kg_m3,
                crossing.e_raw_j_kg,
            ).sound_speed_m_s
        )
        if case.crossing_step is not None and case.crossing_step >= 1:
            before = case.accepted_state_history[
                case.crossing_step - 1,
                crossing.cell_index,
            ]
            pre_sound = _sound_speed_from_conserved(before)
            if pre_sound > 0.0:
                sound_ratio = raw_sound / pre_sound

    closest = None if crossing is not None else _closest_liquid_margin(case)
    max_post_q = max((cell.q_post for cell in case.cells), default=0.0)
    max_alpha = max(
        (
            0.0 if cell.alpha_post is None else float(cell.alpha_post)
            for cell in case.cells
        ),
        default=0.0,
    )

    boundary = case.boundary_budget_diagnostics
    phase = case.phase_budget_diagnostics
    crossing_cell = None if crossing is None else crossing.cell_index
    crossing_distance = (
        None if crossing is None else crossing.distance_from_outlet_m
    )
    crossing_center = (
        None
        if crossing_distance is None
        else cfg.length_m - crossing_distance
    )
    crossing_time = case.crossing_time_s

    return MeshCaseMetrics(
        run_id=f"{case.case.case_id}__n{cfg.n_cells}",
        case_id=case.case.case_id,
        role=case.case.role,
        final_boundary_pressure_pa=case.case.final_boundary_pressure_pa,
        n_cells=cfg.n_cells,
        dx_m=cfg.dx_m,
        maximum_steps=cfg.max_steps,
        cfl=cfg.cfl,
        outcome=case.outcome,
        failure_reason=case.failure_reason,
        step_count=case.step_count,
        final_time_s=case.final_time_s,
        initial_acoustic_time_s=case.initial_acoustic_time_s,
        maximum_horizon_s=case.maximum_horizon_s,
        preflight_accepted_sample_count=len(case.preflight.records),
        raw_crossing_observed=case.crossing_step is not None,
        crossing_step=case.crossing_step,
        crossing_time_s=crossing_time,
        normalized_crossing_time=(
            None
            if crossing_time is None
            else crossing_time / case.initial_acoustic_time_s
        ),
        crossing_cell_index=crossing_cell,
        crossing_cell_center_m=crossing_center,
        crossing_distance_from_outlet_m=crossing_distance,
        normalized_crossing_distance_from_outlet=(
            None
            if crossing_distance is None
            else crossing_distance / cfg.length_m
        ),
        maximum_crossing_quality=case.maximum_crossing_quality,
        maximum_projected_quality=float(max_post_q),
        maximum_void_fraction=float(max_alpha),
        crossing_delta_u_sat_j_kg=(
            None
            if crossing_margin is None
            else float(crossing_margin["delta_u"])
        ),
        crossing_delta_v_sat_m3_kg=(
            None
            if crossing_margin is None
            else float(crossing_margin["delta_v"])
        ),
        crossing_q_from_internal_energy=(
            None if crossing_margin is None else float(crossing_margin["q_u"])
        ),
        crossing_q_from_specific_volume=(
            None if crossing_margin is None else float(crossing_margin["q_v"])
        ),
        pre_crossing_liquid_sound_speed_m_s=pre_sound,
        raw_crossing_sound_speed_m_s=raw_sound,
        sound_speed_ratio_raw_to_pre=sound_ratio,
        closest_liquid_step=None if closest is None else closest.step_index,
        closest_liquid_time_s=None if closest is None else closest.time_s,
        closest_liquid_cell_index=None if closest is None else closest.cell_index,
        closest_liquid_distance_from_outlet_m=(
            None if closest is None else closest.distance_from_outlet_m
        ),
        closest_liquid_delta_u_sat_j_kg=(
            None if closest is None else closest.delta_u_sat_j_kg
        ),
        closest_liquid_delta_v_sat_m3_kg=(
            None if closest is None else closest.delta_v_sat_m3_kg
        ),
        closest_liquid_q_from_internal_energy=(
            None if closest is None else closest.q_from_internal_energy
        ),
        closest_liquid_q_from_specific_volume=(
            None if closest is None else closest.q_from_specific_volume
        ),
        projection_vapor_source_kg=_finite_or_none(
            phase, "phase_vapor_mass_source_cumulative_kg"
        ),
        boundary_vapor_transport_kg=_finite_or_none(
            boundary, "boundary_vapor_transport_cumulative_kg"
        ),
        mass_residual_kg=_finite_or_none(boundary, "budget_mass_residual"),
        momentum_residual_kg_m_s=_finite_or_none(
            boundary, "budget_momentum_residual"
        ),
        energy_residual_J=_finite_or_none(boundary, "budget_energy_residual"),
        combined_vapor_residual_kg=_finite_or_none(
            phase, "phase_vapor_mass_balance_residual_kg"
        ),
        reverse_flow_fallback_count=case.reverse_flow_fallback_count,
        final_state_sha256=case.final_state_sha256,
        run_signature_sha256=case.run_signature_sha256,
    )


def _assert_32_cell_baseline(metric: MeshCaseMetrics) -> None:
    actual = {
        "outcome": metric.outcome,
        "failure_reason": metric.failure_reason,
        "step_count": metric.step_count,
        "final_time_s": metric.final_time_s,
        "crossing_step": metric.crossing_step,
        "crossing_time_s": metric.crossing_time_s,
        "crossing_cell_index": metric.crossing_cell_index,
        "crossing_distance_from_outlet_m": metric.crossing_distance_from_outlet_m,
        "maximum_crossing_quality": metric.maximum_crossing_quality,
        "final_state_sha256": metric.final_state_sha256,
        "run_signature_sha256": metric.run_signature_sha256,
    }
    if actual != EXPECTED_32_CELL_4MPA:
        raise HEMPipelineMeshSensitivityError(
            "32-cell PR #77 baseline mismatch; mesh comparison is not allowed: "
            + json.dumps(
                {"actual": actual, "expected": EXPECTED_32_CELL_4MPA},
                sort_keys=True,
            )
        )


def _strictly_decreasing(values: Sequence[float | None]) -> bool:
    return bool(
        len(values) == 3
        and all(value is not None and np.isfinite(value) for value in values)
        and float(values[0]) > float(values[1]) > float(values[2])
    )


def _nonmonotone(values: Sequence[float | None]) -> bool:
    if len(values) != 3 or any(
        value is None or not np.isfinite(value) for value in values
    ):
        return False
    first = float(values[1]) - float(values[0])
    second = float(values[2]) - float(values[1])
    return first * second < 0.0


def classify_four_mpa_mesh_sequence(
    cases: Sequence[MeshCaseMetrics],
) -> tuple[tuple[MeshClassification, ...], dict[str, str]]:
    control = sorted(
        [case for case in cases if case.case_id == FOUR_MPA_CASE_ID],
        key=lambda item: item.n_cells,
    )
    categories: list[MeshClassification] = []
    rationale: dict[str, str] = {}
    if [case.n_cells for case in control] != list(MESH_CELL_COUNTS):
        return (
            ("MESH_SENSITIVITY_INCONCLUSIVE",),
            {
                "MESH_SENSITIVITY_INCONCLUSIVE": (
                    "The fixed 32/64/128-cell 4 MPa sequence is incomplete."
                )
            },
        )

    severe = {
        "ENDPOINT_LANDING",
        "FORBIDDEN_TRANSITION",
        "REVERSE_FLOW_GUARD",
        "BACKEND_FAILURE",
    }
    if any(case.outcome in severe for case in control):
        categories.append("MESH_SENSITIVITY_INCONCLUSIVE")
        rationale["MESH_SENSITIVITY_INCONCLUSIVE"] = (
            "At least one 4 MPa mesh ended in an endpoint, forbidden, reverse-flow, "
            "or backend outcome."
        )

    crossed = [case.raw_crossing_observed for case in control]
    if crossed[0] and not crossed[2]:
        categories.append("CROSSING_VANISHES_WITH_REFINEMENT")
        rationale["CROSSING_VANISHES_WITH_REFINEMENT"] = (
            "The 32-cell row crosses while the 128-cell row remains liquid through "
            "the fixed horizon."
        )

    q_values = [case.maximum_crossing_quality if flag else None for case, flag in zip(control, crossed)]
    du_values = [case.crossing_delta_u_sat_j_kg if flag else None for case, flag in zip(control, crossed)]
    dv_values = [case.crossing_delta_v_sat_m3_kg if flag else None for case, flag in zip(control, crossed)]

    depth_decays = (
        _strictly_decreasing(q_values)
        and _strictly_decreasing(du_values)
        and _strictly_decreasing(dv_values)
    )
    if depth_decays:
        categories.append("CROSSING_DEPTH_DECAYS_WITH_REFINEMENT")
        rationale["CROSSING_DEPTH_DECAYS_WITH_REFINEMENT"] = (
            "q_eq, Delta_u_sat, and Delta_v_sat decrease strictly across the "
            "32/64/128-cell crossing sequence."
        )

    if all(crossed) and not depth_decays:
        categories.append("FINITE_CROSSING_PERSISTS_ACROSS_MESHES")
        rationale["FINITE_CROSSING_PERSISTS_ACROSS_MESHES"] = (
            "All three meshes cross and the reviewed depth coordinates do not all "
            "decrease strictly with refinement."
        )

    if all(crossed):
        times = [case.normalized_crossing_time for case in control]
        positions = [
            case.normalized_crossing_distance_from_outlet for case in control
        ]
        if all(value is not None for value in times + positions):
            time_stable = abs(float(times[2]) - float(times[1])) <= abs(
                float(times[1]) - float(times[0])
            )
            position_stable = abs(float(positions[2]) - float(positions[1])) <= abs(
                float(positions[1]) - float(positions[0])
            )
            if time_stable and position_stable:
                categories.append("CROSSING_TIME_POSITION_TREND_STABLE")
                rationale["CROSSING_TIME_POSITION_TREND_STABLE"] = (
                    "The 64-to-128 changes in normalized crossing time and position "
                    "do not exceed the 32-to-64 changes."
                )
            else:
                categories.append("CROSSING_TIME_POSITION_NOT_STABLE")
                rationale["CROSSING_TIME_POSITION_NOT_STABLE"] = (
                    "Normalized crossing time or position does not show a smaller "
                    "64-to-128 change."
                )

    if any(
        _nonmonotone(values) for values in (q_values, du_values, dv_values)
    ):
        categories.append("MESH_SEQUENCE_NON_MONOTONE")
        rationale["MESH_SEQUENCE_NON_MONOTONE"] = (
            "At least one principal crossing-depth coordinate reverses trend across "
            "the three meshes."
        )

    if not categories:
        categories.append("MESH_SENSITIVITY_INCONCLUSIVE")
        rationale["MESH_SENSITIVITY_INCONCLUSIVE"] = (
            "The reviewed classification rules do not resolve the observed sequence."
        )
    return tuple(categories), rationale


def run_fixed_pipeline_mesh_sensitivity_matrix(
    *,
    case_runner: MeshCaseRunner = run_pipeline_depressurization_case,
    on_case_result: MeshCaseCallback | None = None,
) -> HEMPipelineMeshSensitivityResult:
    """Run the fixed nine-run matrix with no result-dependent tuning."""

    metrics: list[MeshCaseMetrics] = []
    for n_cells in MESH_CELL_COUNTS:
        config = HEMPipelineMeshSensitivityConfig.for_cells(n_cells)
        for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
            raw = case_runner(case, config)
            metric = _case_metrics(raw)
            if n_cells == 32 and case.case_id == FOUR_MPA_CASE_ID:
                _assert_32_cell_baseline(metric)
            if on_case_result is not None:
                on_case_result(raw, metric)
            metrics.append(metric)

    classifications, rationale = classify_four_mpa_mesh_sequence(metrics)
    return HEMPipelineMeshSensitivityResult(
        cases=tuple(metrics),
        four_mpa_classifications=classifications,
        four_mpa_classification_rationale=rationale,
    )


def _flatten_csv(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_metric_rows(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten_csv(value) for key, value in row.items()})


def _generate_plots(target: Path, result: HEMPipelineMeshSensitivityResult) -> dict[str, Path]:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pragma: no cover - optional plotting path
        raise HEMPipelineMeshSensitivityError(
            "matplotlib is required for the reviewed mesh-sensitivity artifact bundle"
        ) from exc

    control = sorted(
        [case for case in result.cases if case.case_id == FOUR_MPA_CASE_ID],
        key=lambda item: item.n_cells,
    )
    dx = np.asarray([case.dx_m for case in control], dtype=float)
    q = np.asarray(
        [max(case.maximum_crossing_quality, 1.0e-16) for case in control],
        dtype=float,
    )
    q_u = np.asarray(
        [
            np.nan
            if case.crossing_q_from_internal_energy is None
            else case.crossing_q_from_internal_energy
            for case in control
        ],
        dtype=float,
    )
    q_v = np.asarray(
        [
            np.nan
            if case.crossing_q_from_specific_volume is None
            else case.crossing_q_from_specific_volume
            for case in control
        ],
        dtype=float,
    )

    paths: dict[str, Path] = {}

    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.plot(dx, q, marker="o")
    ax.set_yscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("dx [m]")
    ax.set_ylabel("maximum q_eq (display floor 1e-16)")
    ax.set_title("4 MPa crossing quality versus mesh spacing")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    paths["plot_qeq"] = target / "mesh_qeq_vs_dx.png"
    fig.savefig(paths["plot_qeq"], dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.plot(dx, q_u, marker="o", label="q from internal energy")
    ax.plot(dx, q_v, marker="o", label="q from specific volume")
    ax.axhline(0.0)
    ax.invert_xaxis()
    ax.set_xlabel("dx [m]")
    ax.set_ylabel("quality-like saturation coordinate")
    ax.set_title("4 MPa saturation-side depth versus mesh spacing")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    paths["plot_margin"] = target / "mesh_saturation_margin_vs_dx.png"
    fig.savefig(paths["plot_margin"], dpi=180, bbox_inches="tight")
    plt.close(fig)

    times = np.asarray(
        [
            np.nan if case.normalized_crossing_time is None else case.normalized_crossing_time
            for case in control
        ],
        dtype=float,
    )
    positions = np.asarray(
        [
            np.nan
            if case.normalized_crossing_distance_from_outlet is None
            else case.normalized_crossing_distance_from_outlet
            for case in control
        ],
        dtype=float,
    )
    fig, ax_time = plt.subplots(figsize=(7.5, 5.2))
    ax_position = ax_time.twinx()
    time_line = ax_time.plot(dx, times, marker="o", label="t/t_acoustic,0")
    position_line = ax_position.plot(
        dx,
        positions,
        marker="s",
        label="outlet distance/L",
    )
    ax_time.invert_xaxis()
    ax_time.set_xlabel("dx [m]")
    ax_time.set_ylabel("normalized crossing time")
    ax_position.set_ylabel("normalized distance from outlet")
    ax_time.set_title("4 MPa crossing time and position versus mesh spacing")
    lines = time_line + position_line
    ax_time.legend(lines, [line.get_label() for line in lines])
    ax_time.grid(True, alpha=0.3)
    fig.tight_layout()
    paths["plot_time_position"] = target / "mesh_crossing_time_position.png"
    fig.savefig(paths["plot_time_position"], dpi=180, bbox_inches="tight")
    plt.close(fig)

    ratios = np.asarray(
        [
            np.nan
            if case.sound_speed_ratio_raw_to_pre is None
            else case.sound_speed_ratio_raw_to_pre
            for case in control
        ],
        dtype=float,
    )
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.plot(dx, ratios, marker="o")
    ax.invert_xaxis()
    ax.set_xlabel("dx [m]")
    ax.set_ylabel("raw crossing sound speed / pre-crossing liquid sound speed")
    ax.set_title("4 MPa near-saturation sound-speed jump versus mesh")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    paths["plot_sound_speed"] = target / "mesh_sound_speed_jump.png"
    fig.savefig(paths["plot_sound_speed"], dpi=180, bbox_inches="tight")
    plt.close(fig)

    return paths


def write_pipeline_mesh_sensitivity_artifacts(
    output_dir: str | Path,
) -> tuple[HEMPipelineMeshSensitivityResult, dict[str, Path]]:
    """Execute once and stream the reviewed JSON/CSV/NPZ/Markdown/PNG bundle."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_json": target / "4mpa_mesh_sensitivity_summary.json",
        "cases_csv": target / "4mpa_mesh_sensitivity_cases.csv",
        "steps_csv": target / "4mpa_mesh_sensitivity_steps.csv",
        "cells_csv": target / "4mpa_mesh_sensitivity_cells.csv",
        "crossing_metrics_csv": target / "4mpa_mesh_sensitivity_crossing_metrics.csv",
        "markdown": target / "4mpa_mesh_sensitivity.md",
        "npz": target / "4mpa_mesh_sensitivity.npz",
    }

    step_handle = paths["steps_csv"].open("w", newline="", encoding="utf-8")
    cell_handle = paths["cells_csv"].open("w", newline="", encoding="utf-8")
    step_fields = ["n_cells", "dx_m", "maximum_steps"] + [
        item.name for item in fields(PipelineStepRecord)
    ]
    cell_fields = ["n_cells", "dx_m", "maximum_steps"] + [
        item.name for item in fields(PipelineCellRecord)
    ]
    step_writer = csv.DictWriter(step_handle, fieldnames=step_fields)
    cell_writer = csv.DictWriter(cell_handle, fieldnames=cell_fields)
    step_writer.writeheader()
    cell_writer.writeheader()

    def retain(raw: PipelineCaseResult, metric: MeshCaseMetrics) -> None:
        prefix = {
            "n_cells": metric.n_cells,
            "dx_m": metric.dx_m,
            "maximum_steps": metric.maximum_steps,
        }
        for step in raw.steps:
            row = {**prefix, **asdict(step)}
            step_writer.writerow({key: _flatten_csv(value) for key, value in row.items()})
        for cell in raw.cells:
            row = {**prefix, **asdict(cell)}
            cell_writer.writerow({key: _flatten_csv(value) for key, value in row.items()})
        step_handle.flush()
        cell_handle.flush()

    try:
        result = run_fixed_pipeline_mesh_sensitivity_matrix(on_case_result=retain)
    finally:
        step_handle.close()
        cell_handle.close()

    rows = [case.summary() for case in result.cases]
    _write_metric_rows(paths["cases_csv"], rows)
    _write_metric_rows(
        paths["crossing_metrics_csv"],
        [case.summary() for case in result.cases if case.case_id == FOUR_MPA_CASE_ID],
    )

    fixed = HEMPipelineDepressurizationConfig()
    payload = {
        **result.summary(),
        "immutable_pr77_base_config": asdict(fixed),
        "mesh_only_overrides": [
            HEMPipelineMeshSensitivityConfig.for_cells(n_cells).mesh_override
            for n_cells in MESH_CELL_COUNTS
        ],
        "cases": rows,
    }
    paths["summary_json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    np.savez_compressed(
        paths["npz"],
        n_cells=np.asarray([case.n_cells for case in result.cases], dtype=int),
        dx_m=np.asarray([case.dx_m for case in result.cases], dtype=float),
        final_boundary_pressure_pa=np.asarray(
            [case.final_boundary_pressure_pa for case in result.cases], dtype=float
        ),
        crossing_time_s=np.asarray(
            [
                np.nan if case.crossing_time_s is None else case.crossing_time_s
                for case in result.cases
            ],
            dtype=float,
        ),
        crossing_distance_from_outlet_m=np.asarray(
            [
                np.nan
                if case.crossing_distance_from_outlet_m is None
                else case.crossing_distance_from_outlet_m
                for case in result.cases
            ],
            dtype=float,
        ),
        maximum_crossing_quality=np.asarray(
            [case.maximum_crossing_quality for case in result.cases], dtype=float
        ),
        crossing_delta_u_sat_j_kg=np.asarray(
            [
                np.nan
                if case.crossing_delta_u_sat_j_kg is None
                else case.crossing_delta_u_sat_j_kg
                for case in result.cases
            ],
            dtype=float,
        ),
        crossing_delta_v_sat_m3_kg=np.asarray(
            [
                np.nan
                if case.crossing_delta_v_sat_m3_kg is None
                else case.crossing_delta_v_sat_m3_kg
                for case in result.cases
            ],
            dtype=float,
        ),
        sound_speed_ratio_raw_to_pre=np.asarray(
            [
                np.nan
                if case.sound_speed_ratio_raw_to_pre is None
                else case.sound_speed_ratio_raw_to_pre
                for case in result.cases
            ],
            dtype=float,
        ),
    )

    plot_paths = _generate_plots(target, result)
    paths.update(plot_paths)

    lines = [
        "# Stage 7 Pipeline Mesh Sensitivity",
        "",
        "`VERIFICATION ONLY; FIRST-ORDER RUSANOV; CFL 0.10; GATE P2 FALSE`",
        "",
        "| pressure [MPa] | cells | outcome | crossing t/t_a | outlet distance/L | max q_eq |",
        "|---:|---:|---|---:|---:|---:|",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.final_boundary_pressure_pa / 1.0e6:.0f} | {case.n_cells} | "
            f"{case.outcome} | "
            f"{'' if case.normalized_crossing_time is None else format(case.normalized_crossing_time, '.17g')} | "
            f"{'' if case.normalized_crossing_distance_from_outlet is None else format(case.normalized_crossing_distance_from_outlet, '.17g')} | "
            f"{case.maximum_crossing_quality:.17g} |"
        )
    lines.extend(
        [
            "",
            "## 4 MPa classifications",
            "",
            "```text",
            *result.four_mpa_classifications,
            "```",
            "",
            "## Approval boundary",
            "",
            "```text",
            "Gate_P2_passed = false",
            "mesh_independent_crossing_verified = false",
            "CFL_independent_crossing_verified = false",
            "two_phase_acoustic_accuracy_band_approved = false",
            "physical_validation = false",
            "design_use_acceptance = false",
            "production_hem_activation_approved = false",
            "```",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result, paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed Stage 7 32/64/128-cell mesh-sensitivity matrix."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result, paths = write_pipeline_mesh_sensitivity_artifacts(args.output_dir)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
