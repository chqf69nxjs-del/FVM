"""Boundary-history sampling and CSV output for verification runners.

The sampling helper must be called immediately before ``solver.step(dt_s)``.
It reconstructs the same ghost extension and invokes the same numerical flux
function as the solver, without changing the solver state or physics update.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .boundary_telemetry import BOUNDARY_HISTORY_COLUMNS, BoundaryTelemetryRecorder
from .eos import EOSModel


class BoundaryTelemetrySolver(Protocol):
    """Minimal solver surface needed by the pre-step telemetry sampler."""

    n_ghost: int
    step_count: int
    t: float
    eos: EOSModel
    grid: Any

    def extend_with_ghosts(self, t: float) -> np.ndarray:
        """Return the conservative state including ghost cells."""

    def flux_function(self, U_left: np.ndarray, U_right: np.ndarray, eos: EOSModel) -> np.ndarray:
        """Return numerical interface fluxes."""


def record_solver_boundary_telemetry(
    solver: BoundaryTelemetrySolver,
    recorder: BoundaryTelemetryRecorder,
    dt_s: float,
) -> None:
    """Record the exact external-face inputs and numerical fluxes for one step.

    Call this function immediately before ``solver.step(dt_s)`` and do not
    mutate the solver between the two calls. The helper deliberately remains
    outside the solver core so PR-A does not alter the conservative update.
    """

    if not np.isfinite(dt_s) or dt_s <= 0.0:
        raise ValueError("dt_s must be finite and positive")
    if solver.n_ghost <= 0:
        raise ValueError("solver.n_ghost must be positive")

    U_ext = solver.extend_with_ghosts(float(solver.t))
    n_cells = int(solver.grid.n_cells)
    i0 = int(solver.n_ghost)
    i1 = i0 + n_cells
    expected_shape = (n_cells + 2 * i0, U_ext.shape[-1])
    if U_ext.shape != expected_shape:
        raise ValueError(f"unexpected ghost-extended state shape: {U_ext.shape}")

    flux = np.asarray(solver.flux_function(U_ext[:-1], U_ext[1:], solver.eos), dtype=float)
    if flux.shape[0] != U_ext.shape[0] - 1:
        raise ValueError("numerical flux array has an unexpected interface count")

    recorder.record_external_faces(
        step=int(solver.step_count) + 1,
        flux_evaluation_time_s=float(solver.t),
        dt_s=float(dt_s),
        left_face_U_left=U_ext[i0 - 1],
        left_face_U_right=U_ext[i0],
        right_face_U_left=U_ext[i1 - 1],
        right_face_U_right=U_ext[i1],
        left_flux=flux[i0 - 1],
        right_flux=flux[i1 - 1],
        eos=solver.eos,
    )


def write_boundary_history_csv(path: Path | str, rows: list[dict[str, Any]]) -> Path:
    """Write ``*_boundary_history.csv`` using the declared stable schema."""

    if not rows:
        raise ValueError("boundary history rows must not be empty")
    for index, row in enumerate(rows):
        if tuple(row.keys()) != BOUNDARY_HISTORY_COLUMNS:
            raise ValueError(f"boundary history row {index} does not match the declared schema")

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(BOUNDARY_HISTORY_COLUMNS), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    return output
