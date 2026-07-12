"""Pure helpers for Stage 5 single-phase boundary-reflection verification.

These helpers encode the specification's linear-acoustic sign convention,
theoretical travel times, and non-overlapping evaluation windows. They do not
run the FVM solver and do not constitute physical validation or design-use
acceptance.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

ReflectionBoundaryKind = Literal["rigid_wall", "fixed_pressure"]


def acoustic_impedance(rho0_kg_m3: float, c0_m_s: float) -> float:
    """Return ``Z0 = rho0 * c0`` after strict positivity checks."""

    rho0 = _positive_finite(rho0_kg_m3, "rho0_kg_m3")
    c0 = _positive_finite(c0_m_s, "c0_m_s")
    return float(rho0 * c0)


def characteristic_amplitudes(
    delta_pressure_pa: np.ndarray | float,
    velocity_perturbation_m_s: np.ndarray | float,
    rho0_kg_m3: float,
    c0_m_s: float,
) -> tuple[np.ndarray | float, np.ndarray | float]:
    """Return pressure-like ``A_plus`` and ``A_minus`` diagnostics.

    ``A_plus = 0.5 * (p' + Z0 u')`` and
    ``A_minus = 0.5 * (p' - Z0 u')``.
    """

    p, u = np.broadcast_arrays(
        np.asarray(delta_pressure_pa, dtype=float),
        np.asarray(velocity_perturbation_m_s, dtype=float),
    )
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(u)):
        raise ValueError("delta pressure and velocity perturbation must be finite")
    z0 = acoustic_impedance(rho0_kg_m3, c0_m_s)
    a_plus = 0.5 * (p + z0 * u)
    a_minus = 0.5 * (p - z0 * u)
    if a_plus.ndim == 0:
        return float(a_plus), float(a_minus)
    return a_plus, a_minus


def expected_reflection_coefficients(boundary_kind: ReflectionBoundaryKind) -> dict[str, float]:
    """Return ideal linear-acoustic pressure and velocity coefficients."""

    if boundary_kind == "rigid_wall":
        return {"pressure_reflection_coefficient": 1.0, "velocity_reflection_coefficient": -1.0}
    if boundary_kind == "fixed_pressure":
        return {"pressure_reflection_coefficient": -1.0, "velocity_reflection_coefficient": 1.0}
    raise ValueError("boundary_kind must be 'rigid_wall' or 'fixed_pressure'")


def theoretical_reflection_timing(
    *,
    pipe_length_m: float,
    pulse_center_x_m: float,
    probe_x_m: float,
    c0_m_s: float,
    pulse_sigma_m: float,
) -> dict[str, float]:
    """Return theoretical first-arrival and contamination times for one probe."""

    length = _positive_finite(pipe_length_m, "pipe_length_m")
    c0 = _positive_finite(c0_m_s, "c0_m_s")
    sigma = _positive_finite(pulse_sigma_m, "pulse_sigma_m")
    x0 = _finite(pulse_center_x_m, "pulse_center_x_m")
    xp = _finite(probe_x_m, "probe_x_m")
    if not 0.0 <= x0 < xp < length:
        raise ValueError("coordinates must satisfy 0 <= pulse_center_x_m < probe_x_m < pipe_length_m")

    incident = (xp - x0) / c0
    boundary = (length - x0) / c0
    reflected = (2.0 * length - x0 - xp) / c0
    roundtrip = 2.0 * (length - xp) / c0
    left_return = (x0 + xp) / c0
    sigma_time = sigma / c0
    return {
        "theoretical_incident_time_s": float(incident),
        "theoretical_boundary_time_s": float(boundary),
        "theoretical_reflected_time_s": float(reflected),
        "theoretical_roundtrip_delay_s": float(roundtrip),
        "theoretical_left_return_contamination_time_s": float(left_return),
        "sigma_time_s": float(sigma_time),
    }


def evaluation_windows(
    timing: dict[str, float],
    *,
    half_width_sigma: float = 2.5,
) -> dict[str, Any]:
    """Build incident, boundary, and reflected windows with midpoint clipping.

    Candidate windows are centred on the three theoretical times and have half
    width ``half_width_sigma * sigma_time``. Adjacent overlaps are clipped at
    the midpoint between their centres, and the reason is retained in metadata.
    """

    width_factor = _positive_finite(half_width_sigma, "half_width_sigma")
    sigma_time = _positive_finite(timing["sigma_time_s"], "timing['sigma_time_s']")
    half_width = width_factor * sigma_time
    names = ("incident", "boundary", "reflected")
    centres = {
        "incident": _nonnegative_finite(timing["theoretical_incident_time_s"], "incident time"),
        "boundary": _nonnegative_finite(timing["theoretical_boundary_time_s"], "boundary time"),
        "reflected": _nonnegative_finite(timing["theoretical_reflected_time_s"], "reflected time"),
    }
    if not centres["incident"] < centres["boundary"] < centres["reflected"]:
        raise ValueError("timing centres must satisfy incident < boundary < reflected")

    windows: dict[str, dict[str, Any]] = {}
    for name in names:
        centre = centres[name]
        windows[name] = {
            "center_s": float(centre),
            "candidate_start_s": float(max(0.0, centre - half_width)),
            "candidate_end_s": float(centre + half_width),
            "start_s": float(max(0.0, centre - half_width)),
            "end_s": float(centre + half_width),
            "clip_reasons": [],
        }

    for left_name, right_name in zip(names[:-1], names[1:]):
        left = windows[left_name]
        right = windows[right_name]
        if left["end_s"] > right["start_s"]:
            midpoint = 0.5 * (left["center_s"] + right["center_s"])
            left["end_s"] = float(midpoint)
            right["start_s"] = float(midpoint)
            reason = f"{left_name}_{right_name}_overlap_clipped_at_midpoint"
            left["clip_reasons"].append(reason)
            right["clip_reasons"].append(reason)

    left_return = _nonnegative_finite(
        timing["theoretical_left_return_contamination_time_s"],
        "left-return contamination time",
    )
    safe_limit = left_return - half_width
    reflected_end = windows["reflected"]["end_s"]
    flat: dict[str, Any] = {
        "window_half_width_sigma": float(width_factor),
        "window_half_width_s": float(half_width),
    }
    all_reasons: list[str] = []
    for name in names:
        window = windows[name]
        flat.update(
            {
                f"{name}_window_center_s": window["center_s"],
                f"{name}_window_candidate_start_s": window["candidate_start_s"],
                f"{name}_window_candidate_end_s": window["candidate_end_s"],
                f"{name}_window_start_s": window["start_s"],
                f"{name}_window_end_s": window["end_s"],
                f"{name}_window_clip_reasons": tuple(window["clip_reasons"]),
            }
        )
        all_reasons.extend(window["clip_reasons"])
    flat.update(
        {
            "window_clip_applied": bool(all_reasons),
            "window_clip_reasons": tuple(dict.fromkeys(all_reasons)),
            "left_return_safe_limit_s": float(safe_limit),
            "recommended_evaluation_end_s": float(reflected_end),
            "evaluation_window_contaminated": bool(reflected_end >= safe_limit),
        }
    )
    return flat


def _finite(value: float, name: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _positive_finite(value: float, name: str) -> float:
    out = _finite(value, name)
    if out <= 0.0:
        raise ValueError(f"{name} must be positive")
    return out


def _nonnegative_finite(value: float, name: str) -> float:
    out = _finite(value, name)
    if out < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return out
