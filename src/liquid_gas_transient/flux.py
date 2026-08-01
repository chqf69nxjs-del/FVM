"""Numerical fluxes for the conservative FVM solver."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, Iterator, Protocol

import numpy as np

from .eos import EOSModel
from .state import IDX_RHO, IDX_MOM, IDX_RHOE, IDX_RHO_XV, N_VARS, PrimitiveState


class NumericalFlux(Protocol):
    """Numerical flux interface."""

    def __call__(self, U_left: np.ndarray, U_right: np.ndarray, eos: EOSModel) -> np.ndarray:
        """Return interface fluxes for left/right states."""


@dataclass(frozen=True)
class RusanovFluxEvaluation:
    """Read-only snapshot of one production Rusanov array evaluation.

    Every array is copied after the unchanged production flux has been computed
    and marked non-writeable before it is exposed to an observer.  The snapshot
    is diagnostic evidence only; it cannot replace or modify the returned flux.
    """

    left_conserved_state: np.ndarray
    right_conserved_state: np.ndarray
    left_physical_flux: np.ndarray
    right_physical_flux: np.ndarray
    maximum_wave_speed: np.ndarray
    production_flux: np.ndarray


RusanovFluxObserver = Callable[[RusanovFluxEvaluation], None]
_RUSANOV_FLUX_OBSERVER: ContextVar[RusanovFluxObserver | None] = ContextVar(
    "liquid_gas_transient_rusanov_flux_observer",
    default=None,
)


def _readonly_copy(values: np.ndarray) -> np.ndarray:
    copied = np.array(values, dtype=float, copy=True)
    copied.setflags(write=False)
    return copied


@contextmanager
def observe_rusanov_flux(observer: RusanovFluxObserver) -> Iterator[None]:
    """Temporarily observe exact production Rusanov evaluations in this context.

    The observer is task/thread-context local through :class:`ContextVar`.  The
    default path remains unobserved, and nested contexts restore the previous
    observer exactly when they exit.
    """

    if not callable(observer):
        raise TypeError("Rusanov observer must be callable")
    token = _RUSANOV_FLUX_OBSERVER.set(observer)
    try:
        yield
    finally:
        _RUSANOV_FLUX_OBSERVER.reset(token)


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
    production_flux = (
        0.5 * (F_l + F_r)
        - 0.5 * s_max[..., np.newaxis] * (U_right - U_left)
    )

    observer = _RUSANOV_FLUX_OBSERVER.get()
    if observer is not None:
        observer(
            RusanovFluxEvaluation(
                left_conserved_state=_readonly_copy(U_left),
                right_conserved_state=_readonly_copy(U_right),
                left_physical_flux=_readonly_copy(F_l),
                right_physical_flux=_readonly_copy(F_r),
                maximum_wave_speed=_readonly_copy(s_max),
                production_flux=_readonly_copy(production_flux),
            )
        )
    return production_flux
