"""Optional external-boundary telemetry for the conservative FVM solver.

The numerical flux is the quantity used by the finite-volume update. Pressure
and velocity are not uniquely defined by a generic approximate Riemann solver,
so this module also exposes an explicitly diagnostic face primitive. It is the
arithmetic midpoint of the primitive states reconstructed from the exact left
and right states passed to the numerical flux at the external face.

That midpoint is not a Godunov star state and is not a replacement for either a
cell-centre value or a ghost-cell value. It is a reproducible face diagnostic
for numerical verification only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from .eos import EOSModel
from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, N_VARS

BoundarySide = Literal["left", "right"]

BOUNDARY_HISTORY_SCHEMA_VERSION = "boundary_history_v1"
BOUNDARY_FACE_DEFINITION = "primitive_arithmetic_midpoint_of_numerical_flux_input_states"
BOUNDARY_HISTORY_COLUMNS = (
    "schema_version",
    "step",
    "side",
    "flux_evaluation_time_s",
    "interval_start_time_s",
    "interval_end_time_s",
    "dt_s",
    "boundary_face_definition",
    "boundary_face_pressure_pa",
    "boundary_face_velocity_m_s",
    "boundary_face_density_kg_m3",
    "boundary_face_internal_energy_j_kg",
    "boundary_face_total_energy_j_kg",
    "boundary_face_temperature_K",
    "boundary_face_sound_speed_m_s",
    "boundary_face_vapor_mass_fraction",
    "boundary_face_alpha",
    "numerical_mass_flux_kg_m2_s",
    "numerical_momentum_flux_n_m2",
    "numerical_energy_flux_w_m2",
    "numerical_vapor_mass_flux_kg_m2_s",
    "numerical_mass_flow_rate_kg_s",
    "numerical_momentum_flow_rate_n",
    "numerical_energy_flow_rate_w",
    "numerical_vapor_mass_flow_rate_kg_s",
    "domain_mass_rate_kg_s",
    "domain_momentum_rate_n",
    "domain_energy_rate_w",
    "domain_vapor_mass_rate_kg_s",
)


def diagnostic_boundary_face_primitive(
    U_left: np.ndarray,
    U_right: np.ndarray,
    eos: EOSModel,
) -> dict[str, float]:
    """Return the documented diagnostic midpoint primitive for one face.

    ``U_left`` and ``U_right`` must be the two conservative states passed to the
    numerical flux. At an external boundary one is the adjacent ghost state and
    the other is the adjacent internal state, with ordering set by positive x.
    """

    left = _validated_state(U_left, "U_left")
    right = _validated_state(U_right, "U_right")
    prim_left = eos.primitive_from_conserved(left[np.newaxis, :])
    prim_right = eos.primitive_from_conserved(right[np.newaxis, :])

    def midpoint(name: str) -> float:
        a = float(np.asarray(getattr(prim_left, name))[0])
        b = float(np.asarray(getattr(prim_right, name))[0])
        value = 0.5 * (a + b)
        if not np.isfinite(value):
            raise ValueError(f"diagnostic boundary-face {name} must be finite")
        return float(value)

    return {
        "boundary_face_pressure_pa": midpoint("p"),
        "boundary_face_velocity_m_s": midpoint("u"),
        "boundary_face_density_kg_m3": midpoint("rho"),
        "boundary_face_internal_energy_j_kg": midpoint("e"),
        "boundary_face_total_energy_j_kg": midpoint("E"),
        "boundary_face_temperature_K": midpoint("T"),
        "boundary_face_sound_speed_m_s": midpoint("c"),
        "boundary_face_vapor_mass_fraction": midpoint("xv"),
        "boundary_face_alpha": midpoint("alpha"),
    }


@dataclass
class BoundaryTelemetryRecorder:
    """Record numerical external-face fluxes and diagnostic face primitives."""

    area_m2: float
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not np.isfinite(self.area_m2) or self.area_m2 <= 0.0:
            raise ValueError("area_m2 must be finite and positive")

    def record_external_faces(
        self,
        *,
        step: int,
        flux_evaluation_time_s: float,
        dt_s: float,
        left_face_U_left: np.ndarray,
        left_face_U_right: np.ndarray,
        right_face_U_left: np.ndarray,
        right_face_U_right: np.ndarray,
        left_flux: np.ndarray,
        right_flux: np.ndarray,
        eos: EOSModel,
    ) -> None:
        """Append left and right rows for one finite-volume time step."""

        if step <= 0:
            raise ValueError("step must be positive")
        if not np.isfinite(flux_evaluation_time_s) or flux_evaluation_time_s < 0.0:
            raise ValueError("flux_evaluation_time_s must be finite and non-negative")
        if not np.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("dt_s must be finite and positive")

        interval_end = float(flux_evaluation_time_s + dt_s)
        self.history.append(
            self._row(
                step=step,
                side="left",
                flux_evaluation_time_s=flux_evaluation_time_s,
                interval_end_time_s=interval_end,
                dt_s=dt_s,
                U_left=left_face_U_left,
                U_right=left_face_U_right,
                flux=left_flux,
                eos=eos,
            )
        )
        self.history.append(
            self._row(
                step=step,
                side="right",
                flux_evaluation_time_s=flux_evaluation_time_s,
                interval_end_time_s=interval_end,
                dt_s=dt_s,
                U_left=right_face_U_left,
                U_right=right_face_U_right,
                flux=right_flux,
                eos=eos,
            )
        )

    def rows(self) -> list[dict[str, Any]]:
        """Return defensive copies in ``BOUNDARY_HISTORY_COLUMNS`` order."""

        return [{key: row[key] for key in BOUNDARY_HISTORY_COLUMNS} for row in self.history]

    def clear(self) -> None:
        self.history.clear()

    def _row(
        self,
        *,
        step: int,
        side: BoundarySide,
        flux_evaluation_time_s: float,
        interval_end_time_s: float,
        dt_s: float,
        U_left: np.ndarray,
        U_right: np.ndarray,
        flux: np.ndarray,
        eos: EOSModel,
    ) -> dict[str, Any]:
        face = diagnostic_boundary_face_primitive(U_left, U_right, eos)
        flux_arr = _validated_flux(flux)
        rate = self.area_m2 * flux_arr
        domain_sign = 1.0 if side == "left" else -1.0
        row: dict[str, Any] = {
            "schema_version": BOUNDARY_HISTORY_SCHEMA_VERSION,
            "step": int(step),
            "side": side,
            "flux_evaluation_time_s": float(flux_evaluation_time_s),
            "interval_start_time_s": float(flux_evaluation_time_s),
            "interval_end_time_s": float(interval_end_time_s),
            "dt_s": float(dt_s),
            "boundary_face_definition": BOUNDARY_FACE_DEFINITION,
            **face,
            "numerical_mass_flux_kg_m2_s": float(flux_arr[IDX_RHO]),
            "numerical_momentum_flux_n_m2": float(flux_arr[IDX_MOM]),
            "numerical_energy_flux_w_m2": float(flux_arr[IDX_RHOE]),
            "numerical_vapor_mass_flux_kg_m2_s": float(flux_arr[IDX_RHO_XV]),
            "numerical_mass_flow_rate_kg_s": float(rate[IDX_RHO]),
            "numerical_momentum_flow_rate_n": float(rate[IDX_MOM]),
            "numerical_energy_flow_rate_w": float(rate[IDX_RHOE]),
            "numerical_vapor_mass_flow_rate_kg_s": float(rate[IDX_RHO_XV]),
            "domain_mass_rate_kg_s": float(domain_sign * rate[IDX_RHO]),
            "domain_momentum_rate_n": float(domain_sign * rate[IDX_MOM]),
            "domain_energy_rate_w": float(domain_sign * rate[IDX_RHOE]),
            "domain_vapor_mass_rate_kg_s": float(domain_sign * rate[IDX_RHO_XV]),
        }
        if tuple(row) != BOUNDARY_HISTORY_COLUMNS:
            raise RuntimeError("boundary history row does not match the declared schema")
        return row


def _validated_state(U: np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(U, dtype=float)
    if arr.shape != (N_VARS,):
        raise ValueError(f"{name} must have shape (N_VARS,)")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    if arr[IDX_RHO] <= 0.0:
        raise ValueError(f"{name} density must be positive")
    return arr


def _validated_flux(flux: np.ndarray) -> np.ndarray:
    arr = np.asarray(flux, dtype=float)
    if arr.shape != (N_VARS,):
        raise ValueError("boundary flux must have shape (N_VARS,)")
    if not np.all(np.isfinite(arr)):
        raise ValueError("boundary flux must be finite")
    return arr
