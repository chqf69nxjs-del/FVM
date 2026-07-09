"""Numerical fluxes for the conservative FVM solver."""

from __future__ import annotations

from typing import Protocol
import numpy as np

from .eos import EOSModel
from .state import IDX_RHO, IDX_MOM, IDX_RHOE, IDX_RHO_XV, N_VARS, PrimitiveState


class NumericalFlux(Protocol):
    """Numerical flux interface."""

    def __call__(self, U_left: np.ndarray, U_right: np.ndarray, eos: EOSModel) -> np.ndarray:
        """Return interface fluxes for left/right states."""


def physical_flux(U: np.ndarray, prim: PrimitiveState) -> np.ndarray:
    """Return Euler-type physical flux for conservative variables."""

    F = np.empty_like(U)
    rho_u = U[..., IDX_MOM]
    F[..., IDX_RHO] = rho_u
    F[..., IDX_MOM] = rho_u * prim.u + prim.p
    F[..., IDX_RHOE] = prim.u * (U[..., IDX_RHOE] + prim.p)
    F[..., IDX_RHO_XV] = U[..., IDX_RHO_XV] * prim.u
    return F


def rusanov_flux(U_left: np.ndarray, U_right: np.ndarray, eos: EOSModel) -> np.ndarray:
    """Local Lax-Friedrichs / Rusanov flux.

    Parameters
    ----------
    U_left, U_right:
        Arrays with shape (..., N_VARS). They represent the states on each
        side of an interface.
    eos:
        Equation-of-state model used to compute pressure and sound speed.
    """

    if U_left.shape[-1] != N_VARS or U_right.shape[-1] != N_VARS:
        raise ValueError("U_left and U_right must have last dimension N_VARS")

    prim_l = eos.primitive_from_conserved(U_left)
    prim_r = eos.primitive_from_conserved(U_right)
    F_l = physical_flux(U_left, prim_l)
    F_r = physical_flux(U_right, prim_r)
    s_max = np.maximum(np.abs(prim_l.u) + prim_l.c, np.abs(prim_r.u) + prim_r.c)
    return 0.5 * (F_l + F_r) - 0.5 * s_max[..., np.newaxis] * (U_right - U_left)
