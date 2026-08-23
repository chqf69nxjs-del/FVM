"""Analytic state recovery and acoustic derivatives for A2.4-2R."""

from __future__ import annotations

import math

from .hne_equilibrium_acoustic_types import (
    DEFAULT_CONFIG,
    EquilibriumAcousticClosureError,
    EquilibriumAcousticConfig,
    EquilibriumAcousticDiagnostic,
    EquilibriumManifoldState,
    VerificationCase,
)

def _constituent_state(
    pressure_pa: float,
    config: EquilibriumAcousticConfig,
) -> tuple[float, float, float, float, float, float, float]:
    """Return T, rho_l, rho_v, e_l, v_l, v_v and d(e_l)/dp."""

    p = float(pressure_pa)
    if not math.isfinite(p) or p <= 0.0:
        raise EquilibriumAcousticClosureError("pressure must be finite and positive")
    dp = p - config.p_ref_pa
    rho_l = config.rho_l_ref_kg_m3 + dp / config.c_liquid_m_s**2
    rho_v = config.rho_v_ref_kg_m3 + dp / config.c_vapor_m_s**2
    if not math.isfinite(rho_l) or not math.isfinite(rho_v) or min(rho_l, rho_v) <= 0.0:
        raise EquilibriumAcousticClosureError("constituent density is nonfinite or nonpositive")
    temperature = config.T_ref_K + dp / config.saturation_pressure_per_kelvin_pa
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise EquilibriumAcousticClosureError("saturation temperature is nonfinite or nonpositive")
    e_l = config.e_l_ref_j_kg + config.cv_liquid_j_kgK * (temperature - config.T_ref_K)
    return temperature, rho_l, rho_v, e_l, 1.0 / rho_l, 1.0 / rho_v, config.de_l_dp_j_kg_pa


def state_from_pressure_quality(
    pressure_pa: float,
    vapor_mass_fraction: float,
    *,
    config: EquilibriumAcousticConfig | None = None,
) -> EquilibriumManifoldState:
    """Construct an exact point on the analytic equilibrium manifold."""

    cfg = config or DEFAULT_CONFIG
    p = float(pressure_pa)
    q = float(vapor_mass_fraction)
    if not math.isfinite(q) or q < 0.0 or q > 1.0:
        raise EquilibriumAcousticClosureError("quality must be finite and within [0,1]")
    temperature, rho_l, rho_v, e_l, v_l, v_v, _ = _constituent_state(p, cfg)
    specific_volume = (1.0 - q) * v_l + q * v_v
    if not math.isfinite(specific_volume) or specific_volume <= 0.0:
        raise EquilibriumAcousticClosureError("mixture specific volume is invalid")
    rho = 1.0 / specific_volume
    e = e_l + q * cfg.latent_heat_j_kg
    alpha = (q * v_v) / specific_volume if q > 0.0 else 0.0
    within = _within_claimed_domain(p, q, cfg)
    return EquilibriumManifoldState(
        pressure_pa=p,
        temperature_K=temperature,
        vapor_mass_fraction=q,
        rho_kg_m3=rho,
        e_j_kg=e,
        liquid_density_kg_m3=rho_l,
        vapor_density_kg_m3=rho_v,
        void_fraction=alpha,
        pressure_recovery_iterations=0,
        volume_residual_m3_kg=0.0,
        within_claimed_domain=within,
    )


def _within_claimed_domain(
    pressure_pa: float,
    vapor_mass_fraction: float,
    config: EquilibriumAcousticConfig,
) -> bool:
    return (
        config.claimed_pressure_min_pa + config.claimed_boundary_pressure_guard_pa
        < pressure_pa
        < config.claimed_pressure_max_pa - config.claimed_boundary_pressure_guard_pa
        and config.claimed_quality_min + config.claimed_boundary_quality_guard
        < vapor_mass_fraction
        < config.claimed_quality_max - config.claimed_boundary_quality_guard
    )


def _quality_from_pressure_energy(
    pressure_pa: float,
    e_j_kg: float,
    config: EquilibriumAcousticConfig,
) -> float:
    _, _, _, e_l, _, _, _ = _constituent_state(presssure_pa, config)
    return (e_j_kg - e_l) / config.latent_heat_j_kg


def _volume_residual(
    pressure_pa: float,
    rho_kg_m3: float,
    e_j_kg: float,
    config: EquilibriumAcousticConfig,
) -> float:
    _, _, _, _, v_l, v_v, _ = _constituent_state(pressure_pa, config)
    q = _quality_from_pressure_energy(pressure_pa, e_j_kg, config)
    return (1.0 - q) * v_l + q * v_v - 1.0 / rho_kg_m3


def recover_equilibrium_state(
    rho_kg_m3: float,
    e_j_kg: float,
    *,
    config: EquilibriumAcousticConfig | None = None,
) -> EquilibriumManifoldState:
    """Recover the unique pressure/quality root inside the configured scope."""

    cfg = config or DEFAULT_CONFIG
    rho = float(rho_kg_m3)
    e = float(e_j_kg)
    if not math.isfinite(rho) or rho <= 0.0:
        raise EquilibriumAcousticClosureError("rho must be finite and positive")
    if not math.isfinite(e):
        raise EquilibriumAcousticClosureError("e must be finite")

    # q decreases linearly with p at fixed e.  Intersect the configured pressure
    # scope with the mathematical open-mixture interval 0 <= q <= 1.
    chi = cfg.de_l_dp_j_kg_pa
    pressure_at_q_one = cfg.p_ref_pa + (
        e - cfg.e_l_ref_j_kg - cfg.latent_heat_j_kg
    ) / chi
    pressure_at_q_zero = cfg.p_ref_pa + (e - cfg.e_l_ref_j_kg) / chi
    low = max(cfg.recovery_pressure_min_pa, pressure_at_q_one)
    high = min(cfg.recovery_pressure_max_pa, pressure_at_q_zero)
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        raise EquilibriumAcousticClosureError(
            "rho/e state has no open-mixture pressure interval in recovery scope"
        )

    f_low = _volume_residual(low, rho, e, cfg)
    f_high = _volume_residual(high, rho, e, cfg)
    if abs(f_low) <= cfg.volume_residual_tolerance_m3_kg:
        root = low
        iterations = 0
    elif abs(f_high) <= cfg.volume_residual_tolerance_m3_kg:
        root = high
        iterations = 0
    else:
        # F(p) is strictly decreasing when the guarded Jacobian determinant is
        # negative.  A physical root therefore requires F(low)>0>F(high).
        if not (f_low > 0.0 and f_high < 0.0):
            raise EquilibriumAcousticClosureError(
                "equilibrium volume closure has no bracketed unique pressure root"
            )
        root = math.nan
        iterations = 0
        for iterations in range(1, cfg.maximum_bisection_iterations + 1):
            mid = 0.5 * (low + high)
            f_mid = _volume_residual(mid, rho, e, cfg)
            root = mid
            if (
                abs(f_mid) <= cfg.volume_residual_tolerance_m3_kg
                or high - low <= cfg.pressure_tolerance_pa
            ):
                break
            if f_mid > 0.0:
                low = mid
            else:
                high = mid
        else:
            raise EquilibriumAcousticClosureError(
                "equilibrium pressure recovery did not converge deterministically"
            )

    q = _quality_from_pressure_energy(root, e, cfg)
    if q < -1.0e-12 or q > 1.0 + 1.0e-12:
        raise EquilibriumAcousticClosureError("recovered quality lies outside [0,1]")
    q = min(max(q, 0.0), 1.0)
    exact = state_from_pressure_quality(root, q, config=cfg)
    residual = _volume_residual(root, rho, e, cfg)
    if abs(residual) > cfg.volume_residual_tolerance_m3_kg:
        raise EquilibriumAcousticClosureError(
            "equilibrium pressure recovery residual exceeds configured tolerance"
        )
    rho_error = exact.rho_kg_m3 - rho
    e_error = exact.e_j_kg - e
    if abs(rho_error) > max(1.0e-9, 2.0e-10 * rho):
        raise EquilibriumAcousticClosureError("recovered manifold density is inconsistent")
    if abs(e_error) > 2.0e-7:
        raise EquilibriumAcousticClosureError("recovered manifold energy is inconsistent")
    return EquilibriumManifoldState(
        pressure_pa=root,
        temperature_K=exact.temperature_K,
        vapor_mass_fraction=q,
        rho_kg_m3=rho,
        e_j_kg=e,
        liquid_density_kg_m3=exact.liquid_density_kg_m3,
        vapor_density_kg_m3=exact.vapor_density_kg_m3,
        void_fraction=exact.void_fraction,
        pressure_recovery_iterations=iterations,
        volume_residual_m3_kg=residual,
        within_claimed_domain=_within_claimed_domain(root, q, cfg),
    )


def _analytic_derivatives(
    state: EquilibriumManifoldState,
    config: EquilibriumAcousticConfig,
) -> tuple[float, float, float, float]:
    """Return c_eq^2, dq/drho, c_frozen^2, and the Jacobian determinant."""

    rho = state.rho_kg_m3
    p = state.pressure_pa
    q = state.vapor_mass_fraction
    rho_l = state.liquid_density_kg_m3
    rho_v = state.vapor_density_kg_m3
    v_l = 1.0 / rho_l
    v_v = 1.0 / rho_v
    dv_l_dp = -1.0 / (config.c_liquid_m_s**2 * rho_l**2)
    dv_v_dp = -1.0 / (config.c_vapor_m_s**2 * rho_v**2)
    dv_dp_at_q = (1.0 - q) * dv_l_dp + q * dv_v_dp
    dv_dq_at_p = v_v - v_l
    de_dp_at_q = config.de_l_dp_j_kg_pa
    de_dq_at_p = config.latent_heat_j_kg
    determinant = dv_dp_at_q * de_dq_at_p - dv_dq_at_p * de_dp_at_q
    if not math.isfinite(determinant) or abs(determinant) < config.minimum_abs_jacobian_determinant:
        raise EquilibriumAcousticClosureError(
            "equilibrium manifold Jacobian is singular or insufficiently conditioned"
        )

    rhs_specific_volume = -1.0 / rho**2
    rhs_energy = p / rho**2
    c_eq_squared = (
        rhs_specific_volume * de_dq_at_p - dv_dq_at_p * rhs_energy
    ) / determinant
    dq_drho = (
        dv_dp_at_q * rhs_energy - rhs_specific_volume * de_dp_at_q
    ) / determinant
    frozen_c_squared = rhs_specific_volume / dv_dp_at_q
    if not all(math.isfinite(x) for x in (c_eq_squared, dq_drho, frozen_c_squared)):
        raise EquilibriumAcousticClosureError("analytic acoustic derivative is nonfinite")
    return c_eq_squared, dq_drho, frozen_c_squared, determinant


def _finite_difference_c2(
    state: EquilibriumManifoldState,
    config: EquilibriumAcousticConfig,
) -> tuple[float, float, int]:
    """Independent centered derivative along the local isentropic tangent."""

    rho = state.rho_kg_m3
    e = state.e_j_kg
    p = state.pressure_pa
    initial_step = max(
        config.finite_difference_relative_density_step * rho,
        config.finite_difference_minimum_density_step_kg_m3,
    )
    de_drho = p / rho**2
    for halvings in range(config.finite_difference_maximum_halvings + 1):
        step = initial_step / (2.0**halvings)
        if rho - step <= 0.0:
            continue
        try:
            minus = recover_equilibrium_state(
                rho - step,
                e - step * de_drho,
                config=config,
            )
            plus = recover_equilibrium_state(
                rho + step,
                e + step * de_drho,
                config=config,
            )
        except EquilibriumAcousticClosureError:
            continue
        if not minus.within_claimed_domain or not plus.within_claimed_domain:
            continue
        fd = (plus.pressure_pa - minus.pressure_pa) / (2.0 * step)
        if math.isfinite(fd):
            return fd, step, halvings
    raise EquilibriumAcousticClosureError(
        "no guarded centered finite-difference stencil exists in the claimed domain"
    )


def evaluate_equilibrium_acoustic(
    rho_kg_m3: float,
    e_j_kg: float,
    *,
    config: EquilibriumAcousticConfig | None = None,
) -> EquilibriumAcousticDiagnostic:
    """Evaluate the guarded equilibrium/frozen acoustic verification pair."""

    cfg = config or DEFAULT_CONFIG
    try:
        state = recover_equilibrium_state(rho_kg_m3, e_j_kg, config=cfg)
        if not state.within_claimed_domain:
            return EquilibriumAcousticDiagnostic(
                valid=False,
                failure_reason="OUTSIDE_CLAIMED_LIQUID_RICH_DOMAIN",
                state=state,
                equilibrium_sound_speed_squared_m2_s2=None,
                equilibrium_sound_speed_m_s=None,
                frozen_sound_speed_squared_m2_s2=None,
                frozen_sound_speed_m_s=None,
                dq_drho_kg_m3_inverse=None,
                finite_difference_sound_speed_squared_m2_s2=None,
                derivative_relative_error=None,
                subcharacteristic_satisfied=None,
                derivative_crosscheck_satisfied=None,
                positive_hyperbolicity_satisfied=None,
            )
        c_eq_squared, dq_drho, c_frozen_squared, _ = _analytic_derivatives(state, cfg)
        fd_c_squared, _, _ = _finite_difference_c2(state, cfg)
        relative_error = abs(fd_c_squared - c_eq_squared) / max(abs(c_eq_squared), 1.0)
        positive = c_eq_squared > 0.0 and c_frozen_squared > 0.0
        derivative_ok = relative_error <= cfg.derivative_relative_tolerance
        subcharacteristic = c_eq_squared <= c_frozen_squared * (
            1.0 + cfg.subcharacteristic_relative_tolerance
        )
        failures: list[str] = []
        if not positive:
            failures.append("NONPOSITIVE_HYPERBOLIC_ACOUSTIC_DERIVATIVE")
        if not derivative_ok:
            failures.append("ANALYTIC_FINITE_DIFFERENCE_MISMATCH")
        if not subcharacteristic:
            failures.append("SUBCHARACTERISTIC_RELATION_NOT_SATISFIED")
        valid = not failures
        return EquilibriumAcousticDiagnostic(
            valid=valid,
            failure_reason="" if valid else ";".join(failures),
            state=state,
            equilibrium_sound_speed_squared_m2_s2=c_eq_squared,
            equilibrium_sound_speed_m_s=math.sqrt(c_eq_squared) if c_eq_squared > 0.0 else None,
            frozen_sound_speed_squared_m2_s2=c_frozen_squared,
            frozen_sound_speed_m_s=math.sqrt(c_frozen_squared) if c_frozen_squared > 0.0 else None,
            dq_drho_kg_m3_inverse=dq_drho,
            finite_difference_sound_speed_squared_m2_s2=fd_c_squared,
            derivative_relative_error=relative_error,
            subcharacteristic_satisfied=subcharacteristic,
            derivative_crosscheck_satisfied=derivative_ok,
            positive_hyperbolicity_satisfied=positive,
        )
    except EquilibriumAcousticClosureError as exc:
        return EquilibriumAcousticDiagnostic(
            valid=False,
            failure_reason=str(exc),
            state=None,
            equilibrium_sound_speed_squared_m2_s2=None,
            equilibrium_sound_speed_m_s=None,
            frozen_sound_speed_squared_m2_s2=None,
            frozen_sound_speed_m_s=None,
            dq_drho_kg_m3_inverse=None,
            finite_difference_sound_speed_squared_m2_s2=None,
            derivative_relative_error=None,
            subcharacteristic_satisfied=None,
            derivative_crosscheck_satisfied=None,
            positive_hyperbolicity_satisfied=None,
        )


def representative_cases() -> tuple[VerificationCase, ...]:
    """Focused coverage of early-flashing and liquid-rich two-phase states."""

    return (
        VerificationCase("LOW_QUALITY_REFERENCE", 1.9e6, 0.05),
        VerificationCase("EARLY_FLASHING", 2.5e6, 0.10),
        VerificationCase("MID_QUALITY", 3.5e6, 0.30),
        VerificationCase("UPPER_QUALITY_MARGIN", 1.6e6, 0.44),
        VerificationCase("HIGH_PRESSURE_MARGIN", 4.8e6, 0.30),
    )

