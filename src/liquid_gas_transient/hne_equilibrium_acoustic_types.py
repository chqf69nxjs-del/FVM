"""Types and authority contract for the A2.4-2R acoustic surrogate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

SCHEMA_VERSION = "stage7_p2_hne_equilibrium_acoustic_closure_a2_4_2r_v1"
SOURCE_A2_4_1_SHA = "3001480c5c4235c898be866c71335464f5d112d7"
MODEL_FORM = "PRESSURE_DEPENDENT_LINEAR_SATURATION_MANIFOLD"
PHASE_BRANCH = "OPEN_TWO_PHASE_EQUILIBRIUM_VERIFICATION_MANIFOLD"
DERIVATIVE_METHOD = "IMPLICIT_ANALYTIC_WITH_CENTERED_ISENTROPIC_DIRECTIONAL_CROSSCHECK"
ACOUSTIC_AUTHORITY = "READ_ONLY_VERIFICATION_DIAGNOSTIC_ONLY"
FORMAL_OUTCOME = "A2_4_2R_WORKING_VERIFICATION_SLICE_WITH_SOLVER_AUTHORITY_CLOSED"
NEXT_ACTION = "PROCEED_TO_A2_4_3_FINITE_PIPELINE_READ_ONLY_ACOUSTIC_SHADOW"

FORMAL_STATUS = {
    "implemented": True,
    "working_verification_slice": True,
    "working_vertical_slice": False,
    "finite_pipeline_acoustic_shadow": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

SOLVER_AUTHORITY = {
    "equilibrium_c2_to_cfl": False,
    "equilibrium_c2_to_rusanov": False,
    "equilibrium_pressure_to_flux": False,
    "equilibrium_c2_to_boundary_characteristics": False,
    "equilibrium_state_to_fvm_state": False,
    "hydrodynamic_coupling_allowed": False,
}


class EquilibriumAcousticClosureError(RuntimeError):
    """Raised when the verification manifold cannot form a guarded state."""


@dataclass(frozen=True)
class EquilibriumAcousticConfig:
    """Model parameters, numerical guards, and the narrow claimed domain."""

    # Reference values intentionally match SurrogateLCO2PropertyBackend.
    p_ref_pa: float = 1.9e6
    T_ref_K: float = 253.15
    rho_l_ref_kg_m3: float = 930.0
    rho_v_ref_kg_m3: float = 40.0
    c_liquid_m_s: float = 750.0
    c_vapor_m_s: float = 250.0
    cv_liquid_j_kgK: float = 2100.0
    e_l_ref_j_kg: float = 1.0e5
    latent_heat_j_kg: float = 2.0e5
    saturation_pressure_per_kelvin_pa: float = 2.0e5

    # Recovery scope is wider than the claimed acoustic domain so centered
    # finite-difference stencils can be formed near a claimed-domain edge.
    recovery_pressure_min_pa: float = 1.0e6
    recovery_pressure_max_pa: float = 5.5e6
    claimed_pressure_min_pa: float = 1.5e6
    claimed_pressure_max_pa: float = 5.0e6
    claimed_quality_min: float = 0.02
    claimed_quality_max: float = 0.45
    claimed_boundary_pressure_guard_pa: float = 1.0e-3
    claimed_boundary_quality_guard: float = 1.0e-10

    pressure_tolerance_pa: float = 1.0e-7
    volume_residual_tolerance_m3_kg: float = 2.0e-13
    maximum_bisection_iterations: int = 180
    minimum_abs_jacobian_determinant: float = 1.0e-12

    finite_difference_relative_density_step: float = 1.0e-5
    finite_difference_minimum_density_step_kg_m3: float = 1.0e-6
    finite_difference_maximum_halvings: int = 16
    derivative_relative_tolerance: float = 2.0e-5
    subcharacteristic_relative_tolerance: float = 1.0e-10

    def __post_init__(self) -> None:
        numeric_values = asdict(self)
        for name, value in numeric_values.items():
            if name == "maximum_bisection_iterations" or name == "finite_difference_maximum_halvings":
                continue
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.p_ref_pa <= 0.0 or self.T_ref_K <= 0.0:
            raise ValueError("reference pressure and temperature must be positive")
        if self.rho_l_ref_kg_m3 <= self.rho_v_ref_kg_m3 or self.rho_v_ref_kg_m3 <= 0.0:
            raise ValueError("reference densities must satisfy rho_l > rho_v > 0")
        if min(self.c_liquid_m_s, self.c_vapor_m_s) <= 0.0:
            raise ValueError("constituent sound-speed parameters must be positive")
        if min(self.cv_liquid_j_kgK, self.latent_heat_j_kg) <= 0.0:
            raise ValueError("heat-capacity and latent-heat parameters must be positive")
        if self.saturation_pressure_per_kelvin_pa <= 0.0:
            raise ValueError("saturation pressure scale must be positive")
        if not (
            0.0 < self.recovery_pressure_min_pa
            < self.claimed_pressure_min_pa
            < self.claimed_pressure_max_pa
            < self.recovery_pressure_max_pa
        ):
            raise ValueError("pressure scopes must be strictly nested and positive")
        if not (0.0 < self.claimed_quality_min < self.claimed_quality_max < 1.0):
            raise ValueError("claimed quality interval must be inside the open interval (0,1)")
        if min(
            self.claimed_boundary_pressure_guard_pa,
            self.claimed_boundary_quality_guard,
            self.pressure_tolerance_pa,
            self.volume_residual_tolerance_m3_kg,
            self.minimum_abs_jacobian_determinant,
            self.finite_difference_relative_density_step,
            self.finite_difference_minimum_density_step_kg_m3,
            self.derivative_relative_tolerance,
            self.subcharacteristic_relative_tolerance,
        ) <= 0.0:
            raise ValueError("numerical tolerances must be positive")
        if self.maximum_bisection_iterations <= 0:
            raise ValueError("maximum_bisection_iterations must be positive")
        if self.finite_difference_maximum_halvings < 0:
            raise ValueError("finite_difference_maximum_halvings must be nonnegative")

    @property
    def de_l_dp_j_kg_pa(self) -> float:
        return self.cv_liquid_j_kgK / self.saturation_pressure_per_kelvin_pa


@dataclass(frozen=True)
class EquilibriumManifoldState:
    pressure_pa: float
    temperature_K: float
    vapor_mass_fraction: float
    rho_kg_m3: float
    e_j_kg: float
    liquid_density_kg_m3: float
    vapor_density_kg_m3: float
    void_fraction: float
    pressure_recovery_iterations: int
    volume_residual_m3_kg: float
    within_claimed_domain: bool
    phase_branch: str = PHASE_BRANCH


@dataclass(frozen=True)
class EquilibriumAcousticDiagnostic:
    valid: bool
    failure_reason: str
    state: EquilibriumManifoldState | None
    equilibrium_sound_speed_squared_m2_s2: float | None
    equilibrium_sound_speed_m_s: float | None
    frozen_sound_speed_squared_m2_s2: float | None
    frozen_sound_speed_m_s: float | None
    dq_drho_kg_m3_inverse: float | None
    finite_difference_sound_speed_squared_m2_s2: float | None
    derivative_relative_error: float | None
    subcharacteristic_satisfied: bool | None
    derivative_crosscheck_satisfied: bool | None
    positive_hyperbolicity_satisfied: bool | None
    model_form: str = MODEL_FORM
    derivative_method: str = DERIVATIVE_METHOD
    acoustic_authority: str = ACOUSTIC_AUTHORITY
    solver_authority_granted: bool = False


@dataclass(frozen=True)
class VerificationCase:
    case_id: str
    pressure_pa: float
    vapor_mass_fraction: float


DEFAULT_CONFIG = EquilibriumAcousticConfig()
