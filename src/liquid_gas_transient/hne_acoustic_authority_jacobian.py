"""Representative states and flux-Jacobian checks for the P2 authority gate."""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from .flux import physical_flux
from .hne_equilibrium_acoustic_closure import representative_cases, state_from_pressure_quality
from .hne_acoustic_authority_types import (
    EQUILIBRIUM_VELOCITY_M_S, OFF_EQUILIBRIUM_CASES,
    AcousticCompatibleHNEVerificationEOS, AcousticCompatibleState,
    HNEAcousticAuthorityGateError,
)
from .state import (
    IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, N_VARS,
    make_conserved,
)

@dataclass(frozen=True)
class AuthorityCase:
    case_id: str
    source_state_id: str
    equilibrium_pressure_pa: float
    equilibrium_quality: float
    actual_quality: float
    quality_offset: float
    velocity_m_s: float
    rho_kg_m3: float
    e_j_kg: float


def authority_cases() -> tuple[AuthorityCase, ...]:
    sources: dict[str, tuple[float, float, float, float]] = {}
    cases: list[AuthorityCase] = []
    for case in representative_cases():
        state = state_from_pressure_quality(case.pressure_pa, case.vapor_mass_fraction)
        sources[case.case_id] = (
            state.rho_kg_m3,
            state.e_j_kg,
            case.pressure_pa,
            case.vapor_mass_fraction,
        )
        cases.append(
            AuthorityCase(
                case_id="EQUILIBRIUM_" + case.case_id,
                source_state_id=case.case_id,
                equilibrium_pressure_pa=case.pressure_pa,
                equilibrium_quality=case.vapor_mass_fraction,
                actual_quality=case.vapor_mass_fraction,
                quality_offset=0.0,
                velocity_m_s=EQUILIBRIUM_VELOCITY_M_S[case.case_id],
                rho_kg_m3=state.rho_kg_m3,
                e_j_kg=state.e_j_kg,
            )
        )
    for source_id, offset, velocity_m_s in OFF_EQUILIBRIUM_CASES:
        rho, e, pressure, q_eq = sources[source_id]
        cases.append(
            AuthorityCase(
                case_id=(
                    "NONEQUILIBRIUM_"
                    + source_id
                    + ("_Q_PLUS_" if offset > 0.0 else "_Q_MINUS_")
                    + str(abs(offset)).replace(".", "P")
                ),
                source_state_id=source_id,
                equilibrium_pressure_pa=pressure,
                equilibrium_quality=q_eq,
                actual_quality=q_eq + offset,
                quality_offset=offset,
                velocity_m_s=velocity_m_s,
                rho_kg_m3=rho,
                e_j_kg=e,
            )
        )
    return tuple(cases)


def candidate_conserved(case: AuthorityCase) -> np.ndarray:
    return np.asarray(
        make_conserved(
            case.rho_kg_m3,
            case.velocity_m_s,
            case.e_j_kg,
            case.actual_quality,
        ),
        dtype=float,
    )


def independent_physical_flux(U: np.ndarray, pressure_pa: float) -> np.ndarray:
    rho = float(U[IDX_RHO])
    momentum = float(U[IDX_MOM])
    rho_energy = float(U[IDX_RHOE])
    rho_q = float(U[IDX_RHO_XV])
    u = momentum / rho
    return np.array(
        [
            momentum,
            momentum * u + pressure_pa,
            u * (rho_energy + pressure_pa),
            rho_q * u,
        ],
        dtype=float,
    )


def analytic_flux_jacobian(
    U: np.ndarray,
    state: AcousticCompatibleState,
) -> np.ndarray:
    rho = float(U[IDX_RHO])
    momentum = float(U[IDX_MOM])
    rho_energy = float(U[IDX_RHOE])
    rho_q = float(U[IDX_RHO_XV])
    u = momentum / rho
    q = rho_q / rho
    A = state.dp_drho_at_q_m2_s2
    B = state.dp_dq_at_rho_pa
    dp_drho_conserved = A - B * q / rho
    dp_drho_q_conserved = B / rho
    total_enthalpy = (rho_energy + state.pressure_pa) / rho
    return np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [-u**2 + dp_drho_conserved, 2.0 * u, 0.0, dp_drho_q_conserved],
            [
                u * (dp_drho_conserved - total_enthalpy),
                total_enthalpy,
                u,
                u * dp_drho_q_conserved,
            ],
            [-q * u, q, 0.0, u],
        ],
        dtype=float,
    )


def _candidate_flux(U: np.ndarray, eos: AcousticCompatibleHNEVerificationEOS) -> np.ndarray:
    prim = eos.primitive_from_conserved(np.asarray(U, dtype=float)[np.newaxis, :])
    return np.asarray(physical_flux(np.asarray(U, dtype=float)[np.newaxis, :], prim)[0])


def numerical_flux_jacobian(
    U: np.ndarray,
    eos: AcousticCompatibleHNEVerificationEOS,
    *,
    relative_step: float = 1.0e-5,
) -> np.ndarray:
    values = np.asarray(U, dtype=float)
    if values.shape != (N_VARS,):
        raise HNEAcousticAuthorityGateError("JACOBIAN_STATE_MUST_HAVE_SHAPE_FOUR")
    scales = (
        max(abs(float(values[IDX_RHO])), 1.0),
        max(abs(float(values[IDX_MOM])), 100.0),
        max(abs(float(values[IDX_RHOE])), 1.0e6),
        max(abs(float(values[IDX_RHO_XV])), 1.0),
    )
    jacobian = np.empty((N_VARS, N_VARS), dtype=float)
    for column in range(N_VARS):
        step = relative_step * scales[column]
        basis = np.zeros(N_VARS, dtype=float)
        basis[column] = 1.0
        for _ in range(20):
            try:
                fm2 = _candidate_flux(values - 2.0 * step * basis, eos)
                fm1 = _candidate_flux(values - step * basis, eos)
                fp1 = _candidate_flux(values + step * basis, eos)
                fp2 = _candidate_flux(values + 2.0 * step * basis, eos)
                break
            except (ValueError, HNEAcousticAuthorityGateError):
                step *= 0.5
        else:
            raise HNEAcousticAuthorityGateError(
                f"NO_ADMISSIBLE_FIVE_POINT_STENCIL_COLUMN_{column}"
            )
        jacobian[:, column] = (fm2 - 8.0 * fm1 + 8.0 * fp1 - fp2) / (
            12.0 * step
        )
    return jacobian


def _matched_eigenvalue_error(
    computed: np.ndarray,
    expected: np.ndarray,
) -> float:
    return float(
        min(
            max(abs(computed[perm[index]] - expected[index]) for index in range(4))
            for perm in itertools.permutations(range(4))
        )
    )
