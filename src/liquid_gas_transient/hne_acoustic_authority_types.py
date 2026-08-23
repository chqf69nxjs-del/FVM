"""Types and acoustic-compatible verification EOS for the P2 authority gate."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .hne_equilibrium_acoustic_closure import DEFAULT_CONFIG
from .properties import SurrogateLCO2PropertyBackend
from .state import (
    IDX_RHO, IDX_RHO_XV, N_VARS, PrimitiveState, check_physical_state,
    internal_energy, vapor_mass_fraction, velocity,
)

SCHEMA_VERSION = "stage7_p2_hne_acoustic_authority_gate_v1"
SOURCE_A2_4_4_SHA = "b844741da4775f2e2970cbbe92a6b8be35fd3c79"
SOURCE_A2_4_4_RUN_ID = 32626761290
SOURCE_A2_4_4_ARTIFACT_ID = 9489909447
SOURCE_A2_4_4_ARTIFACT_SHA256 = (
    "0164a54af61696aa6c955a4f5854589f4ad9b164c095d914e3f30446c865a4b2"
)
SOURCE_A2_4_4_ANALYSIS_SHA256 = (
    "1357f0c768df7834a84d8c3d00dbb27e7524d7c9df9c6e1e744b23aca3b326cd"
)
FORMAL_OUTCOME = (
    "ACOUSTIC_AUTHORITY_GATE_PASSED_FOR_LIMITED_P2_A3_1_INTERIOR_"
    "IMPLEMENTATION_WITH_ALL_EXISTING_SOLVER_PATHS_UNCHANGED"
)
NEXT_ACTION = "PROCEED_TO_P2_A3_1_LIMITED_INTERIOR_HNE_HYDRODYNAMIC_COUPLING"
OUTPUT_FILES = (
    "summary.json",
    "case_summary.csv",
    "jacobian_eigenvalues.csv",
    "operator_report.md",
    "manifest.json",
)

FORMAL_STATUS = {
    "implemented": True,
    "working_verification_slice": True,
    "acoustic_authority_gate_passed": False,
    "limited_p2_a3_1_implementation_authorized": False,
    "hydrodynamic_coupling_implemented": False,
    "finite_pipeline_hne_coupling_implemented": False,
    "boundary_characteristics_authorized": False,
    "discharge_coupling_authorized": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

PROPOSED_AUTHORITY_GRANT = {
    "candidate_pressure_to_interior_euler_flux_in_p2_a3_1": True,
    "candidate_frozen_c_to_interior_rusanov_in_p2_a3_1": True,
    "candidate_frozen_c_to_interior_cfl_in_p2_a3_1": True,
    "equilibrium_c_to_solver": False,
    "finite_relaxation_phase_speed_to_solver": False,
    "hne_boundary_characteristics": False,
    "hne_critical_discharge": False,
    "finite_pipe_discharge_feedback": False,
    "design_use": False,
    "production_use": False,
}

CURRENT_SOLVER_EFFECT = {
    "production_eos_modified": False,
    "production_flux_modified": False,
    "production_rusanov_modified": False,
    "production_cfl_modified": False,
    "production_boundaries_modified": False,
    "hydrodynamic_coupling_active": False,
}

EQUILIBRIUM_VELOCITY_M_S = {
    "LOW_QUALITY_REFERENCE": 0.0,
    "EARLY_FLASHING": 10.0,
    "MID_QUALITY": -15.0,
    "UPPER_QUALITY_MARGIN": 5.0,
    "HIGH_PRESSURE_MARGIN": 25.0,
}
OFF_EQUILIBRIUM_CASES = (
    ("LOW_QUALITY_REFERENCE", 0.01, 5.0),
    ("EARLY_FLASHING", -0.02, 10.0),
    ("EARLY_FLASHING", 0.02, -10.0),
    ("MID_QUALITY", -0.02, 15.0),
    ("MID_QUALITY", 0.02, -15.0),
    ("HIGH_PRESSURE_MARGIN", -0.02, 20.0),
    ("HIGH_PRESSURE_MARGIN", 0.01, -20.0),
)


class HNEAcousticAuthorityGateError(RuntimeError):
    """Raised when the authority candidate leaves its declared scope."""


@dataclass(frozen=True)
class AcousticCompatibleState:
    rho_kg_m3: float
    e_j_kg: float
    vapor_mass_fraction: float
    pressure_pa: float
    temperature_K: float
    liquid_density_kg_m3: float
    vapor_density_kg_m3: float
    void_fraction: float
    frozen_c2_m2_s2: float
    frozen_c_m_s: float
    dp_drho_at_q_m2_s2: float
    dp_dq_at_rho_pa: float


@dataclass(frozen=True)
class AcousticCompatibleHNEVerificationEOS:
    """Narrow off-equilibrium extension of the A2.4-2R manifold.

    Density and transported q determine pressure through the constituent-volume
    equation.  Internal energy and q determine temperature through a common
    caloric slope chosen to recover the A2.4-2R saturation temperature exactly
    when q equals the A2.4-2R equilibrium quality.
    """

    backend: SurrogateLCO2PropertyBackend = field(
        default_factory=SurrogateLCO2PropertyBackend
    )
    pressure_residual_tolerance_m3_kg: float = 2.0e-13
    maximum_bisection_iterations: int = 180

    def __post_init__(self) -> None:
        cfg = DEFAULT_CONFIG
        checks = (
            self.backend.p_sat_ref_pa == cfg.p_ref_pa,
            self.backend.T_sat_ref_K == cfg.T_ref_K,
            self.backend.rho_l_ref_kg_m3 == cfg.rho_l_ref_kg_m3,
            self.backend.rho_v_ref_kg_m3 == cfg.rho_v_ref_kg_m3,
            self.backend.c_liquid_m_s == cfg.c_liquid_m_s,
            self.backend.c_vapor_m_s == cfg.c_vapor_m_s,
            self.backend.cv_liquid_j_kgK == cfg.cv_liquid_j_kgK,
            self.backend.e_l_ref_j_kg == cfg.e_l_ref_j_kg,
            self.backend.latent_heat_ref_j_kg == cfg.latent_heat_j_kg,
        )
        if not all(checks):
            raise ValueError("backend parameters do not match A2.4-2R")
        if self.pressure_residual_tolerance_m3_kg <= 0.0:
            raise ValueError("pressure residual tolerance must be positive")
        if self.maximum_bisection_iterations <= 0:
            raise ValueError("maximum bisection iterations must be positive")

    def _validate_rho_e_q(self, rho: float, e: float, q: float) -> None:
        if not math.isfinite(rho) or rho <= 0.0:
            raise HNEAcousticAuthorityGateError("RHO_MUST_BE_FINITE_POSITIVE")
        if not math.isfinite(e):
            raise HNEAcousticAuthorityGateError("E_MUST_BE_FINITE")
        if not math.isfinite(q) or not (
            DEFAULT_CONFIG.claimed_quality_min < q < DEFAULT_CONFIG.claimed_quality_max
        ):
            raise HNEAcousticAuthorityGateError(
                "Q_OUTSIDE_OPEN_ACOUSTIC_AUTHORITY_DOMAIN"
            )

    def _constituent_densities(self, pressure_pa: float) -> tuple[float, float]:
        cfg = DEFAULT_CONFIG
        dp = pressure_pa - cfg.p_ref_pa
        rho_l = cfg.rho_l_ref_kg_m3 + dp / cfg.c_liquid_m_s**2
        rho_v = cfg.rho_v_ref_kg_m3 + dp / cfg.c_vapor_m_s**2
        if not all(math.isfinite(v) and v > 0.0 for v in (rho_l, rho_v)):
            raise HNEAcousticAuthorityGateError("INVALID_CONSTITUENT_DENSITY")
        return rho_l, rho_v

    def _volume_residual(self, pressure_pa: float, rho: float, q: float) -> float:
        rho_l, rho_v = self._constituent_densities(pressure_pa)
        return (1.0 - q) / rho_l + q / rho_v - 1.0 / rho

    def _pressure(self, rho: float, q: float) -> float:
        cfg = DEFAULT_CONFIG
        low = cfg.claimed_pressure_min_pa
        high = cfg.claimed_pressure_max_pa
        f_low = self._volume_residual(low, rho, q)
        f_high = self._volume_residual(high, rho, q)
        if not (f_low > 0.0 and f_high < 0.0):
            raise HNEAcousticAuthorityGateError(
                "PRESSURE_ROOT_OUTSIDE_OPEN_ACOUSTIC_AUTHORITY_DOMAIN"
            )
        root = math.nan
        for _ in range(self.maximum_bisection_iterations):
            root = 0.5 * (low + high)
            f_mid = self._volume_residual(root, rho, q)
            if abs(f_mid) <= self.pressure_residual_tolerance_m3_kg:
                break
            if f_mid > 0.0:
                low = root
            else:
                high = root
        else:
            raise HNEAcousticAuthorityGateError("PRESSURE_ROOT_DID_NOT_CONVERGE")
        if not (
            cfg.claimed_pressure_min_pa < root < cfg.claimed_pressure_max_pa
        ):
            raise HNEAcousticAuthorityGateError("PRESSURE_ROOT_ON_OR_OUTSIDE_GUARD")
        return root

    def evaluate(self, rho: float, e: float, q: float) -> AcousticCompatibleState:
        self._validate_rho_e_q(rho, e, q)
        pressure = self._pressure(rho, q)
        rho_l, rho_v = self._constituent_densities(pressure)
        cfg = DEFAULT_CONFIG
        temperature = cfg.T_ref_K + (
            e - cfg.e_l_ref_j_kg - q * cfg.latent_heat_j_kg
        ) / cfg.cv_liquid_j_kgK
        if not math.isfinite(temperature) or temperature <= 0.0:
            raise HNEAcousticAuthorityGateError("INVALID_CANDIDATE_TEMPERATURE")
        specific_volume = (1.0 - q) / rho_l + q / rho_v
        alpha = (q / rho_v) / specific_volume
        dv_dp_at_q = -(
            (1.0 - q) / (cfg.c_liquid_m_s**2 * rho_l**2)
            + q / (cfg.c_vapor_m_s**2 * rho_v**2)
        )
        dv_dq_at_p = 1.0 / rho_v - 1.0 / rho_l
        c_frozen2 = (-1.0 / rho**2) / dv_dp_at_q
        dp_dq_at_rho = -dv_dq_at_p / dv_dp_at_q
        if not all(
            math.isfinite(v)
            for v in (specific_volume, alpha, c_frozen2, dp_dq_at_rho)
        ):
            raise HNEAcousticAuthorityGateError("NONFINITE_CANDIDATE_STATE")
        if abs(specific_volume - 1.0 / rho) > self.pressure_residual_tolerance_m3_kg:
            raise HNEAcousticAuthorityGateError("VOLUME_RESIDUAL_EXCEEDS_TOLERANCE")
        if not 0.0 <= alpha <= 1.0 or c_frozen2 <= 0.0:
            raise HNEAcousticAuthorityGateError("NONHYPERBOLIC_CANDIDATE_STATE")
        return AcousticCompatibleState(
            rho_kg_m3=float(rho),
            e_j_kg=float(e),
            vapor_mass_fraction=float(q),
            pressure_pa=float(pressure),
            temperature_K=float(temperature),
            liquid_density_kg_m3=float(rho_l),
            vapor_density_kg_m3=float(rho_v),
            void_fraction=float(alpha),
            frozen_c2_m2_s2=float(c_frozen2),
            frozen_c_m_s=float(math.sqrt(c_frozen2)),
            dp_drho_at_q_m2_s2=float(c_frozen2),
            dp_dq_at_rho_pa=float(dp_dq_at_rho),
        )

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        values = np.asarray(U, dtype=float)
        if values.shape[-1] != N_VARS:
            raise HNEAcousticAuthorityGateError("STATE_LAST_DIMENSION_MUST_BE_FOUR")
        check_physical_state(values, names=["acoustic authority candidate"])
        rho = np.asarray(values[..., IDX_RHO], dtype=float)
        u = np.asarray(velocity(values), dtype=float)
        e = np.asarray(internal_energy(values), dtype=float)
        q = np.asarray(vapor_mass_fraction(values), dtype=float)
        p = np.empty_like(rho)
        T = np.empty_like(rho)
        alpha = np.empty_like(rho)
        c = np.empty_like(rho)
        for index in np.ndindex(rho.shape):
            state = self.evaluate(float(rho[index]), float(e[index]), float(q[index]))
            p[index] = state.pressure_pa
            T[index] = state.temperature_K
            alpha[index] = state.void_fraction
            c[index] = state.frozen_c_m_s
        return PrimitiveState(
            rho=rho,
            u=u,
            p=p,
            e=e,
            E=e + 0.5 * u**2,
            T=T,
            xv=q,
            alpha=alpha,
            c=c,
        )
