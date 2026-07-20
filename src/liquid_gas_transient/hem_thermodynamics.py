"""Verification-first homogeneous-equilibrium thermodynamic helpers.

This module does not connect to ``FvmSolver``.  It wraps the existing real-fluid
property backend contract with explicit HEM-oriented validation and provides a
deterministic zero-dimensional saturation-path exercise.  The backend-reported
sound speed is retained only as a diagnostic in this increment; a reviewed
equilibrium two-phase sound-speed closure remains a separate gate.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .properties import (
    PropertyEvaluationError,
    RealFluidPropertyBackend,
    SurrogateLCO2PropertyBackend,
)


class HEMThermodynamicError(RuntimeError):
    """Raised when a backend result is unusable for the HEM scaffold."""


@dataclass(frozen=True)
class HEMThermodynamicConfig:
    """Validation settings for the zero-dimensional HEM scaffold."""

    quality_tolerance: float = 1.0e-10
    alpha_tolerance: float = 1.0e-10
    minimum_pressure_pa: float = 0.0
    minimum_temperature_K: float = 0.0
    minimum_reported_sound_speed_m_s: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.quality_tolerance,
            self.alpha_tolerance,
            self.minimum_pressure_pa,
            self.minimum_temperature_K,
            self.minimum_reported_sound_speed_m_s,
        )
        if not all(np.isfinite(value) for value in values):
            raise ValueError("HEM thermodynamic configuration values must be finite")
        if self.quality_tolerance < 0.0:
            raise ValueError("quality_tolerance must be non-negative")
        if self.alpha_tolerance < 0.0:
            raise ValueError("alpha_tolerance must be non-negative")
        if self.minimum_pressure_pa < 0.0:
            raise ValueError("minimum_pressure_pa must be non-negative")
        if self.minimum_temperature_K < 0.0:
            raise ValueError("minimum_temperature_K must be non-negative")
        if self.minimum_reported_sound_speed_m_s < 0.0:
            raise ValueError("minimum_reported_sound_speed_m_s must be non-negative")


@dataclass(frozen=True)
class HEMThermodynamicState:
    """Validated array-valued equilibrium state returned by one backend call."""

    backend_name: str
    rho: np.ndarray
    e: np.ndarray
    p: np.ndarray
    T: np.ndarray
    quality: np.ndarray
    alpha: np.ndarray
    reported_sound_speed: np.ndarray
    quality_regime: np.ndarray

    def __post_init__(self) -> None:
        expected = self.rho.shape
        for name in (
            "e",
            "p",
            "T",
            "quality",
            "alpha",
            "reported_sound_speed",
            "quality_regime",
        ):
            value = getattr(self, name)
            if value.shape != expected:
                raise ValueError(
                    f"{name} must have shape {expected}; received {value.shape}"
                )


@dataclass(frozen=True)
class HEMZeroDFlashPath:
    """One deterministic 0-D liquid/two-phase/vapor path."""

    coordinate: np.ndarray
    state: HEMThermodynamicState

    def __post_init__(self) -> None:
        if self.coordinate.shape != self.state.rho.shape:
            raise ValueError("coordinate shape must match thermodynamic state shape")


def classify_quality_regime(
    quality: np.ndarray | float,
    *,
    tolerance: float = 1.0e-10,
) -> np.ndarray:
    """Classify quality endpoints and the open two-phase interval.

    This is deliberately a quality-regime classification rather than a complete
    thermodynamic phase classifier.  Supercritical and solid-region guards remain
    separate future work.
    """

    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and non-negative")
    values = np.asarray(quality, dtype=float)
    if not np.all(np.isfinite(values)):
        raise HEMThermodynamicError("quality must contain only finite values")
    if np.any(values < -tolerance) or np.any(values > 1.0 + tolerance):
        raise HEMThermodynamicError("quality lies outside [0, 1] beyond tolerance")

    regime = np.full(values.shape, "two_phase", dtype="<U16")
    regime[values <= tolerance] = "liquid_endpoint"
    regime[values >= 1.0 - tolerance] = "vapor_endpoint"
    return regime


def _as_broadcast_array(
    value: np.ndarray | float,
    shape: tuple[int, ...],
    *,
    name: str,
) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    try:
        broadcast = np.broadcast_to(array, shape)
    except ValueError as exc:
        raise HEMThermodynamicError(
            f"backend field {name!r} cannot broadcast to input shape {shape}"
        ) from exc
    return np.array(broadcast, dtype=float, copy=True)


def evaluate_hem_thermodynamic_state(
    backend: RealFluidPropertyBackend,
    rho: np.ndarray | float,
    e: np.ndarray | float,
    *,
    config: HEMThermodynamicConfig | None = None,
) -> HEMThermodynamicState:
    """Evaluate and validate one backend ``rho/e`` HEM state.

    Internal energy is required to be finite but is not required to be positive,
    because absolute real-fluid internal-energy values depend on the backend
    reference state.
    """

    cfg = config or HEMThermodynamicConfig()
    rho_arr, e_arr = np.broadcast_arrays(
        np.asarray(rho, dtype=float),
        np.asarray(e, dtype=float),
    )
    rho_arr = np.array(rho_arr, dtype=float, copy=True)
    e_arr = np.array(e_arr, dtype=float, copy=True)

    if not np.all(np.isfinite(rho_arr)) or np.any(rho_arr <= 0.0):
        raise HEMThermodynamicError("rho must be finite and strictly positive")
    if not np.all(np.isfinite(e_arr)):
        raise HEMThermodynamicError("e must contain only finite values")

    backend_name = str(getattr(backend, "name", type(backend).__name__))
    try:
        raw = backend.state_from_rho_e(rho_arr, e_arr)
    except PropertyEvaluationError as exc:
        raise HEMThermodynamicError(
            f"{backend_name} failed to evaluate the requested rho/e state"
        ) from exc
    except Exception as exc:
        raise HEMThermodynamicError(
            f"{backend_name} raised an unexpected rho/e evaluation error"
        ) from exc

    shape = rho_arr.shape
    backend_rho = _as_broadcast_array(raw.rho, shape, name="rho")
    backend_e = _as_broadcast_array(raw.e, shape, name="e")
    p = _as_broadcast_array(raw.p, shape, name="p")
    T = _as_broadcast_array(raw.T, shape, name="T")
    quality = _as_broadcast_array(raw.quality, shape, name="quality")
    alpha = _as_broadcast_array(raw.alpha, shape, name="alpha")
    reported_c = _as_broadcast_array(raw.c, shape, name="c")

    if not np.array_equal(backend_rho, rho_arr):
        raise HEMThermodynamicError(
            "backend returned rho values inconsistent with the requested state"
        )
    if not np.array_equal(backend_e, e_arr):
        raise HEMThermodynamicError(
            "backend returned e values inconsistent with the requested state"
        )

    finite_fields = {
        "p": p,
        "T": T,
        "quality": quality,
        "alpha": alpha,
        "reported sound speed": reported_c,
    }
    for name, values in finite_fields.items():
        if not np.all(np.isfinite(values)):
            raise HEMThermodynamicError(f"{name} contains NaN or infinity")

    if np.any(p <= cfg.minimum_pressure_pa):
        raise HEMThermodynamicError(
            "pressure does not exceed the configured minimum"
        )
    if np.any(T <= cfg.minimum_temperature_K):
        raise HEMThermodynamicError(
            "temperature does not exceed the configured minimum"
        )
    if np.any(reported_c <= cfg.minimum_reported_sound_speed_m_s):
        raise HEMThermodynamicError(
            "backend-reported sound speed does not exceed the configured minimum"
        )
    if np.any(quality < -cfg.quality_tolerance) or np.any(
        quality > 1.0 + cfg.quality_tolerance
    ):
        raise HEMThermodynamicError("quality lies outside [0, 1]")
    if np.any(alpha < -cfg.alpha_tolerance) or np.any(
        alpha > 1.0 + cfg.alpha_tolerance
    ):
        raise HEMThermodynamicError("void fraction lies outside [0, 1]")

    regime = classify_quality_regime(
        quality,
        tolerance=cfg.quality_tolerance,
    )
    return HEMThermodynamicState(
        backend_name=backend_name,
        rho=backend_rho,
        e=backend_e,
        p=p,
        T=T,
        quality=quality,
        alpha=alpha,
        reported_sound_speed=reported_c,
        quality_regime=regime,
    )


def build_surrogate_zero_d_flash_path(
    *,
    n_two_phase_points: int = 21,
    config: HEMThermodynamicConfig | None = None,
) -> HEMZeroDFlashPath:
    """Build a deterministic surrogate liquid-to-vapor 0-D path.

    The open interval is constructed from saturated mixture specific volume and
    mass-specific internal energy.  One compressed-liquid and one expanded-vapor
    endpoint are added so all three quality regimes are exercised.
    """

    if n_two_phase_points < 3:
        raise ValueError("n_two_phase_points must be at least 3")

    backend = SurrogateLCO2PropertyBackend()
    q_mix = np.linspace(0.0, 1.0, n_two_phase_points)
    rho_mix = 1.0 / (
        (1.0 - q_mix) / backend.rho_l_ref_kg_m3
        + q_mix / backend.rho_v_ref_kg_m3
    )
    e_mix = backend.e_l_ref_j_kg + q_mix * backend.latent_heat_ref_j_kg

    rho = np.concatenate(
        (
            np.array([1.02 * backend.rho_l_ref_kg_m3]),
            rho_mix,
            np.array([0.98 * backend.rho_v_ref_kg_m3]),
        )
    )
    e = np.concatenate(
        (
            np.array([backend.e_l_ref_j_kg]),
            e_mix,
            np.array(
                [
                    backend.e_l_ref_j_kg
                    + backend.latent_heat_ref_j_kg
                ]
            ),
        )
    )
    coordinate = np.concatenate(
        (
            np.array([-1.0]),
            q_mix,
            np.array([2.0]),
        )
    )
    state = evaluate_hem_thermodynamic_state(
        backend,
        rho,
        e,
        config=config,
    )
    return HEMZeroDFlashPath(coordinate=coordinate, state=state)


def _summary_records(path: HEMZeroDFlashPath) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index in range(path.coordinate.size):
        records.append(
            {
                "index": index,
                "path_coordinate": float(path.coordinate[index]),
                "rho_kg_m3": float(path.state.rho[index]),
                "e_j_kg": float(path.state.e[index]),
                "p_pa": float(path.state.p[index]),
                "T_K": float(path.state.T[index]),
                "quality": float(path.state.quality[index]),
                "alpha": float(path.state.alpha[index]),
                "backend_reported_sound_speed_m_s": float(
                    path.state.reported_sound_speed[index]
                ),
                "quality_regime": str(path.state.quality_regime[index]),
            }
        )
    return records


def write_zero_d_flash_artifacts(
    output_dir: str | Path,
    path: HEMZeroDFlashPath,
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown, and NPZ evidence for one 0-D path."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_zero_d_flash"
    records = _summary_records(path)

    payload = {
        "schema_version": "stage7_lco2_hem_zero_d_flash_v1",
        "scope": "verification_only",
        "backend_name": path.state.backend_name,
        "production_solver_connected": False,
        "production_solver_behavior_changed": False,
        "pure_co2_hem_thermodynamic_core_complete": False,
        "equilibrium_two_phase_sound_speed_closure_approved": False,
        "backend_reported_sound_speed_is_diagnostic_only": True,
        "solid_phase_supported": False,
        "critical_region_validated": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
        "results": records,
    }

    json_path = destination / f"{stem}.json"
    csv_path = destination / f"{stem}.csv"
    markdown_path = destination / f"{stem}.md"
    npz_path = destination / f"{stem}.npz"

    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    fieldnames = list(records[0])
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    lines = [
        "# Stage 7 LCO2 HEM 0-D Flash Scaffold",
        "",
        "`VERIFICATION ONLY; NOT PRODUCTION ACTIVATION`",
        "",
        f"- backend: `{path.state.backend_name}`",
        f"- states: `{len(records)}`",
        "- production solver connected: `False`",
        "- pure-CO2 HEM thermodynamic core complete: `False`",
        "- equilibrium two-phase sound-speed closure approved: `False`",
        "- physical Validation: `False`",
        "- design-use acceptance: `False`",
        "",
        "| index | regime | rho [kg/m3] | e [J/kg] | p [Pa] | T [K] | q | alpha | backend c [m/s] |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for record in records:
        lines.append(
            "| {index} | {quality_regime} | {rho_kg_m3:.8g} | "
            "{e_j_kg:.8g} | {p_pa:.8g} | {T_K:.8g} | "
            "{quality:.8g} | {alpha:.8g} | "
            "{backend_reported_sound_speed_m_s:.8g} |".format(**record)
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    np.savez_compressed(
        npz_path,
        coordinate=path.coordinate,
        rho=path.state.rho,
        e=path.state.e,
        p=path.state.p,
        T=path.state.T,
        quality=path.state.quality,
        alpha=path.state.alpha,
        reported_sound_speed=path.state.reported_sound_speed,
        quality_regime=path.state.quality_regime,
    )
    return {
        "json": json_path,
        "csv": csv_path,
        "markdown": markdown_path,
        "npz": npz_path,
    }


def run_surrogate_zero_d_flash_verification(
    output_dir: str | Path,
    *,
    n_two_phase_points: int = 21,
) -> dict[str, Path]:
    """Run and persist the deterministic dependency-free 0-D scaffold."""

    path = build_surrogate_zero_d_flash_path(
        n_two_phase_points=n_two_phase_points
    )
    return write_zero_d_flash_artifacts(output_dir, path)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Stage 7 dependency-free HEM 0-D flash evidence."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--points", type=int, default=21)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = run_surrogate_zero_d_flash_verification(
        args.output_dir,
        n_two_phase_points=args.points,
    )
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
