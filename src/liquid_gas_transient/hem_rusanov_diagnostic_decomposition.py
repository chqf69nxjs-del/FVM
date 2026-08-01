"""Stage 7 Gate 9 D2 exact production-Rusanov diagnostic decomposition.

This verification-only increment observes the existing Rusanov evaluation after
its production flux has been computed.  It does not replace the numerical flux,
re-evaluate the EOS, change a wave speed, truncate a time step, or continue past
an unchanged formal stop.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .flux import RusanovFluxEvaluation, observe_rusanov_flux
from .hem_pipeline_crossing_depth_diagnosis import (
    Gate9AcousticAttemptRecord,
    Gate9CellStageRecord,
    Gate9InterfaceFluxRecord,
    Gate9RunResult,
    instrument_pipeline_case_result,
    solver_identity,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    run_pipeline_depressurization_case,
)
from .state import N_VARS

RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE = 5.0e-13
D2_CAPTURE_STATUS = "D2_EXACT_PRODUCTION_RUSANOV_EVALUATION"
PROPERTY_BACKEND_NAME = "coolprop_co2"
PROPERTY_BACKEND_DESIGN_STATUS = "VERIFICATION_ONLY_NOT_APPROVED_FOR_DESIGN_USE"


class HEMGate9RusanovDiagnosticError(RuntimeError):
    """Raised when the locked D2 reconstruction or identity contract fails."""


@dataclass
class Gate9RusanovEvaluationCollector:
    """Collect immutable snapshots emitted by the production Rusanov function."""

    evaluations: list[RusanovFluxEvaluation] = field(default_factory=list)

    def __call__(self, evaluation: RusanovFluxEvaluation) -> None:
        self.evaluations.append(evaluation)


@dataclass(frozen=True)
class Gate9D2Result:
    d1_diagnostics: Gate9RunResult
    interface_flux_records: tuple[Gate9InterfaceFluxRecord, ...]
    production_evaluation_count: int
    maximum_normalized_reconstruction_residual: float
    diagnostic_off_on_identity: bool
    solver_identity_off: Mapping[str, object]
    solver_identity_on: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        candidate = asdict(self.d1_diagnostics.candidate_summary)
        return {
            "schema_version": "stage7_gate9_d2_rusanov_decomposition_increment1_v1",
            "scope": "verification_only_read_only_production_rusanov_observer",
            "case_id": self.d1_diagnostics.case_id,
            "cfl": self.d1_diagnostics.cfl,
            "property_backend_name": PROPERTY_BACKEND_NAME,
            "property_backend_design_status": PROPERTY_BACKEND_DESIGN_STATUS,
            "focused_cells": list(self.d1_diagnostics.focused_cells),
            "focused_interfaces": list(self.d1_diagnostics.focused_interfaces),
            "production_evaluation_count": self.production_evaluation_count,
            "captured_step_count": len(
                {record.absolute_step for record in self.interface_flux_records}
            ),
            "interface_flux_record_count": len(self.interface_flux_records),
            "cell_stage_record_count": len(self.d1_diagnostics.cell_stage_records),
            "acoustic_attempt_record_count": len(
                self.d1_diagnostics.acoustic_attempt_records
            ),
            "candidate_summary": candidate,
            "normalized_reconstruction_residual_tolerance": (
                RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
            ),
            "maximum_normalized_reconstruction_residual": (
                self.maximum_normalized_reconstruction_residual
            ),
            "rusanov_reconstruction_guard_passed": bool(
                np.isfinite(self.maximum_normalized_reconstruction_residual)
                and self.maximum_normalized_reconstruction_residual
                <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
            ),
            "diagnostic_off_on_identity": self.diagnostic_off_on_identity,
            "solver_identity_off": dict(self.solver_identity_off),
            "solver_identity_on": dict(self.solver_identity_on),
            "retained_history_sha256_before": (
                self.d1_diagnostics.retained_history_sha256_before
            ),
            "retained_history_sha256_after": (
                self.d1_diagnostics.retained_history_sha256_after
            ),
            "solver_state_preserved": self.d1_diagnostics.solver_state_preserved,
            "interface_capture_status": "D2_CAPTURE_COMPLETE",
            "acoustic_capture_status": "PENDING_D3_ACOUSTIC_ATTEMPT_HOOKS",
            "event_window_capture_status": "PENDING_D4_EVENT_ALIGNED_RETENTION",
            "production_flux_expression_changed": False,
            "production_solver_equations_changed": False,
            "eos_re_evaluated_for_decomposition": False,
            "wave_speed_recomputed_for_decomposition": False,
            "sound_speed_formula_changed": False,
            "phase_classifier_changed": False,
            "quality_projection_changed": False,
            "crossing_threshold_changed": False,
            "boundary_changed": False,
            "Gate_9_execution_complete": False,
            "crossing_depth_CFL_sensitivity_characterized": False,
            "crossing_depth_root_cause_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


def _as_vector(values: np.ndarray, *, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (N_VARS,) or not np.all(np.isfinite(vector)):
        raise HEMGate9RusanovDiagnosticError(
            f"{name} must be a finite N_VARS vector"
        )
    return vector


def normalized_rusanov_reconstruction_residual(
    reconstructed: np.ndarray,
    production: np.ndarray,
    central: np.ndarray,
    dissipative: np.ndarray,
) -> float:
    """Return the normalized residual fixed by the Gate 9 contract."""

    reconstructed_v = _as_vector(reconstructed, name="reconstructed flux")
    production_v = _as_vector(production, name="production flux")
    central_v = _as_vector(central, name="central flux")
    dissipative_v = _as_vector(dissipative, name="dissipative flux")
    scale = np.maximum.reduce(
        (
            np.ones(N_VARS, dtype=float),
            np.abs(reconstructed_v),
            np.abs(production_v),
            np.abs(central_v),
            np.abs(dissipative_v),
        )
    )
    return float(np.max(np.abs(reconstructed_v - production_v) / scale))


def decompose_rusanov_interface(
    evaluation: RusanovFluxEvaluation,
    interface_index: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    float,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    float,
]:
    """Decompose one observed interface without any property re-evaluation."""

    left_all = np.asarray(evaluation.left_conserved_state, dtype=float)
    right_all = np.asarray(evaluation.right_conserved_state, dtype=float)
    left_flux_all = np.asarray(evaluation.left_physical_flux, dtype=float)
    right_flux_all = np.asarray(evaluation.right_physical_flux, dtype=float)
    speed_all = np.asarray(evaluation.maximum_wave_speed, dtype=float)
    production_all = np.asarray(evaluation.production_flux, dtype=float)

    expected_flux_shape = left_all.shape
    if (
        left_all.ndim != 2
        or left_all.shape[-1] != N_VARS
        or right_all.shape != expected_flux_shape
        or left_flux_all.shape != expected_flux_shape
        or right_flux_all.shape != expected_flux_shape
        or production_all.shape != expected_flux_shape
        or speed_all.shape != expected_flux_shape[:-1]
    ):
        raise HEMGate9RusanovDiagnosticError(
            "observed Rusanov arrays have incompatible shapes"
        )
    if not 0 <= interface_index < left_all.shape[0]:
        raise HEMGate9RusanovDiagnosticError(
            f"interface index {interface_index} is outside the observed flux array"
        )

    left = _as_vector(left_all[interface_index], name="left conserved state")
    right = _as_vector(right_all[interface_index], name="right conserved state")
    left_flux = _as_vector(
        left_flux_all[interface_index], name="left physical flux"
    )
    right_flux = _as_vector(
        right_flux_all[interface_index], name="right physical flux"
    )
    a_max = float(speed_all[interface_index])
    if not np.isfinite(a_max) or a_max < 0.0:
        raise HEMGate9RusanovDiagnosticError(
            "observed maximum wave speed must be finite and non-negative"
        )
    production = _as_vector(
        production_all[interface_index], name="production Rusanov flux"
    )

    central = 0.5 * (left_flux + right_flux)
    dissipative = -0.5 * a_max * (right - left)
    reconstructed = central + dissipative
    residual = normalized_rusanov_reconstruction_residual(
        reconstructed,
        production,
        central,
        dissipative,
    )
    return (
        left,
        right,
        left_flux,
        right_flux,
        a_max,
        central,
        dissipative,
        reconstructed,
        production,
        residual,
    )


def _focused_interface_specs(
    *,
    n_cells: int,
    n_ghost: int,
) -> tuple[tuple[str, int, int, int | None], ...]:
    if n_cells != 32 or n_ghost != 2:
        raise HEMGate9RusanovDiagnosticError(
            "Gate 9 D2 is fixed to the 32-cell case with two ghost cells"
        )
    return (
        ("27|28", n_ghost + 27, 27, 28),
        ("28|29", n_ghost + 28, 28, 29),
        ("29|30", n_ghost + 29, 29, 30),
        ("30|31", n_ghost + 30, 30, 31),
        ("RIGHT_BOUNDARY", n_ghost + n_cells - 1, 31, None),
    )


def _tuple(values: np.ndarray) -> tuple[float, ...]:
    return tuple(float(value) for value in np.asarray(values, dtype=float))


def build_gate9_interface_flux_records(
    result: PipelineCaseResult,
    evaluations: Sequence[RusanovFluxEvaluation],
) -> tuple[Gate9InterfaceFluxRecord, ...]:
    """Align exact production evaluations with the retained accepted step records."""

    steps = tuple(result.steps)
    if len(evaluations) != len(steps):
        raise HEMGate9RusanovDiagnosticError(
            "production Rusanov evaluation count does not match retained step count: "
            f"{len(evaluations)} != {len(steps)}"
        )

    specs = _focused_interface_specs(
        n_cells=int(result.config.n_cells),
        n_ghost=int(result.config.n_ghost),
    )
    dx = float(result.config.dx_m)
    if not np.isfinite(dx) or dx <= 0.0:
        raise HEMGate9RusanovDiagnosticError("grid spacing must be finite and positive")

    records: list[Gate9InterfaceFluxRecord] = []
    for step, evaluation in zip(steps, evaluations):
        dt = float(step.dt_s)
        if not np.isfinite(dt) or dt <= 0.0:
            raise HEMGate9RusanovDiagnosticError(
                f"step {step.step_index} has invalid dt"
            )
        state_increment_scale = dt / dx
        for interface_id, flux_index, left_cell, right_cell in specs:
            (
                left,
                right,
                left_flux,
                right_flux,
                a_max,
                central,
                dissipative,
                reconstructed,
                production,
                residual,
            ) = decompose_rusanov_interface(evaluation, flux_index)
            if (
                not np.isfinite(residual)
                or residual > RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
            ):
                raise HEMGate9RusanovDiagnosticError(
                    "Rusanov decomposition reconstruction failure at "
                    f"step {step.step_index}, interface {interface_id}: "
                    f"residual={residual:.17g}"
                )
            records.append(
                Gate9InterfaceFluxRecord(
                    case_id=result.case.case_id,
                    cfl=float(result.config.cfl),
                    absolute_step=int(step.step_index),
                    absolute_time_s=float(step.time_before_s),
                    dt_s=dt,
                    interface_id=interface_id,
                    left_cell=left_cell,
                    right_cell=right_cell,
                    left_conserved_state=_tuple(left),
                    right_conserved_state=_tuple(right),
                    left_physical_flux=_tuple(left_flux),
                    right_physical_flux=_tuple(right_flux),
                    a_max=a_max,
                    central_component=_tuple(central),
                    dissipative_component=_tuple(dissipative),
                    reconstructed_rusanov_flux=_tuple(reconstructed),
                    production_rusanov_flux=_tuple(production),
                    normalized_reconstruction_residual=residual,
                    left_cell_increment_over_dt_dx=_tuple(
                        -state_increment_scale * production
                    ),
                    right_cell_increment_over_dt_dx=(
                        None
                        if right_cell is None
                        else _tuple(state_increment_scale * production)
                    ),
                    capture_status=D2_CAPTURE_STATUS,
                )
            )
    return tuple(records)


def _require_gate8_cfl_0p10_reference(result: PipelineCaseResult) -> None:
    expected_time = 7.999325695335248e-4
    expected_quality = 3.773646403587342e-6
    if (
        float(result.config.cfl) != 0.10
        or result.outcome != "ACCEPTED_FIRST_CROSSING"
        or int(result.step_count) != 125
        or result.crossing_step != 125
        or result.crossing_time_s != expected_time
        or tuple(result.crossing_cell_indices) != (29,)
        or result.maximum_crossing_quality != expected_quality
    ):
        raise HEMGate9RusanovDiagnosticError(
            "D2 CFL 0.10 run did not reproduce the immutable Gate 8 candidate"
        )


def _require_exact_off_on_identity(
    diagnostic_off: PipelineCaseResult,
    diagnostic_on: PipelineCaseResult,
) -> None:
    if solver_identity(diagnostic_off) != solver_identity(diagnostic_on):
        raise HEMGate9RusanovDiagnosticError(
            "D2 diagnostic off/on solver identity mismatch"
        )
    for name in (
        "time_history_s",
        "pressure_history_pa",
        "accepted_state_history",
    ):
        if not np.array_equal(
            np.asarray(getattr(diagnostic_off, name)),
            np.asarray(getattr(diagnostic_on, name)),
        ):
            raise HEMGate9RusanovDiagnosticError(
                f"D2 diagnostic off/on {name} mismatch"
            )


def run_gate9_d2_identity_pair(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig,
) -> tuple[PipelineCaseResult, PipelineCaseResult, Gate9D2Result]:
    """Run the fixed CFL=0.10 case off/on and capture exact Rusanov evidence."""

    diagnostic_off = run_pipeline_depressurization_case(case, config)
    collector = Gate9RusanovEvaluationCollector()
    with observe_rusanov_flux(collector):
        diagnostic_on = run_pipeline_depressurization_case(case, config)

    _require_exact_off_on_identity(diagnostic_off, diagnostic_on)
    _require_gate8_cfl_0p10_reference(diagnostic_on)
    d1_diagnostics = instrument_pipeline_case_result(diagnostic_on)
    interface_records = build_gate9_interface_flux_records(
        diagnostic_on,
        collector.evaluations,
    )
    expected_record_count = len(diagnostic_on.steps) * 5
    if len(interface_records) != expected_record_count or not interface_records:
        raise HEMGate9RusanovDiagnosticError(
            "D2 focused-interface record count is incomplete: "
            f"{len(interface_records)} != {expected_record_count}"
        )
    maximum_residual = max(
        (
            float(record.normalized_reconstruction_residual)
            for record in interface_records
            if record.normalized_reconstruction_residual is not None
        ),
        default=0.0,
    )
    result = Gate9D2Result(
        d1_diagnostics=d1_diagnostics,
        interface_flux_records=interface_records,
        production_evaluation_count=len(collector.evaluations),
        maximum_normalized_reconstruction_residual=maximum_residual,
        diagnostic_off_on_identity=True,
        solver_identity_off=solver_identity(diagnostic_off),
        solver_identity_on=solver_identity(diagnostic_on),
    )
    if not result.summary()["rusanov_reconstruction_guard_passed"]:
        raise HEMGate9RusanovDiagnosticError(
            "D2 result did not pass the locked Rusanov reconstruction guard"
        )
    return diagnostic_off, diagnostic_on, result


def _flatten(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_dataclass_rows(path: Path, record_type: type, rows: Sequence[object]) -> None:
    fieldnames = [item.name for item in fields(record_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow({key: _flatten(payload[key]) for key in fieldnames})


def write_gate9_d2_artifacts(
    output_dir: str | Path,
    result: Gate9D2Result,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": target / "summary.json",
        "cells": target / "focused_cell_stage_history.csv",
        "interfaces": target / "focused_interface_flux_decomposition.csv",
        "acoustic": target / "acoustic_attempt_history.csv",
        "candidate": target / "candidate_summary.json",
        "digest": target / "artifact_sha256.txt",
    }
    paths["summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_dataclass_rows(
        paths["cells"],
        Gate9CellStageRecord,
        result.d1_diagnostics.cell_stage_records,
    )
    _write_dataclass_rows(
        paths["interfaces"],
        Gate9InterfaceFluxRecord,
        result.interface_flux_records,
    )
    _write_dataclass_rows(
        paths["acoustic"],
        Gate9AcousticAttemptRecord,
        result.d1_diagnostics.acoustic_attempt_records,
    )
    paths["candidate"].write_text(
        json.dumps(
            asdict(result.d1_diagnostics.candidate_summary),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    digest_lines = []
    for path in sorted(
        (value for key, value in paths.items() if key != "digest"),
        key=lambda value: value.name,
    ):
        digest_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        )
    paths["digest"].write_text(
        "\n".join(digest_lines) + "\n",
        encoding="utf-8",
    )
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    _, _, result = run_gate9_d2_identity_pair(
        case,
        HEMPipelineDepressurizationConfig(),
    )
    paths = write_gate9_d2_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
