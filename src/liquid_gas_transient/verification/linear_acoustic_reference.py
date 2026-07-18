"""Independent linear-acoustic analytical and CFL=1 MOC reference helpers.

This module is a verification-only path for Stage 7 / V-013.  It deliberately
depends only on NumPy and the Python standard library.  It does not import the
production FVM solver, production numerical fluxes, production boundary
conditions, case runners, or CoolProp.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray


BoundaryType = Literal["transmissive", "rigid_wall", "fixed_pressure"]
ProfileFunction = Callable[[NDArray[np.float64]], ArrayLike]

_ALLOWED_BOUNDARIES = {"transmissive", "rigid_wall", "fixed_pressure"}


@dataclass(frozen=True)
class LinearAcousticReferenceConfig:
    """Scalar inputs for the independent linear-acoustic reference path."""

    p0_pa: float
    rho0_kg_m3: float
    c0_m_s: float
    length_m: float
    n_cells: int
    left_boundary: BoundaryType = "transmissive"
    right_boundary: BoundaryType = "transmissive"
    output_version: str = "v013_linear_acoustic_reference_v1"
    validation: bool = False
    design_evaluation: bool = False
    acceptance_gate: bool = False
    calls_coolprop: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("p0_pa", self.p0_pa),
            ("rho0_kg_m3", self.rho0_kg_m3),
            ("c0_m_s", self.c0_m_s),
            ("length_m", self.length_m),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if isinstance(self.n_cells, bool) or not isinstance(
            self.n_cells, (int, np.integer)
        ):
            raise ValueError("n_cells must be an integer")
        if int(self.n_cells) < 1:
            raise ValueError("n_cells must be at least 1")
        _validate_boundary(self.left_boundary)
        _validate_boundary(self.right_boundary)
        if self.validation or self.design_evaluation or self.acceptance_gate:
            raise ValueError("V-013 reference flags must remain false")
        if self.calls_coolprop:
            raise ValueError("the independent reference path must not call CoolProp")

    @property
    def dx_m(self) -> float:
        return float(self.length_m) / int(self.n_cells)

    @property
    def dt_s(self) -> float:
        return self.dx_m / float(self.c0_m_s)

    @property
    def cfl(self) -> float:
        return 1.0

    @property
    def n_nodes(self) -> int:
        return int(self.n_cells) + 1

    def grid(self) -> NDArray[np.float64]:
        return np.linspace(0.0, float(self.length_m), self.n_nodes, dtype=float)


def _validate_boundary(boundary: str) -> None:
    if boundary not in _ALLOWED_BOUNDARIES:
        raise ValueError(
            f"unsupported boundary {boundary!r}; expected one of "
            f"{sorted(_ALLOWED_BOUNDARIES)}"
        )


def _as_finite_array(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _broadcast_pair(
    first_name: str,
    first: ArrayLike,
    second_name: str,
    second: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    first_array = _as_finite_array(first_name, first)
    second_array = _as_finite_array(second_name, second)
    try:
        left, right = np.broadcast_arrays(first_array, second_array)
    except ValueError as exc:
        raise ValueError(
            f"{first_name} and {second_name} are not broadcast-compatible"
        ) from exc
    return np.array(left, dtype=float, copy=True), np.array(right, dtype=float, copy=True)


def _positive_reference_scalars(
    rho0_kg_m3: float,
    c0_m_s: float,
) -> tuple[float, float]:
    rho0 = float(rho0_kg_m3)
    c0 = float(c0_m_s)
    if not math.isfinite(rho0) or rho0 <= 0.0:
        raise ValueError("rho0_kg_m3 must be finite and positive")
    if not math.isfinite(c0) or c0 <= 0.0:
        raise ValueError("c0_m_s must be finite and positive")
    return rho0, c0


def characteristics_from_pressure_velocity(
    pressure_perturbation_pa: ArrayLike,
    velocity_m_s: ArrayLike,
    *,
    rho0_kg_m3: float,
    c0_m_s: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return pressure-dimension ``A+`` and ``A-`` characteristic amplitudes."""

    rho0, c0 = _positive_reference_scalars(rho0_kg_m3, c0_m_s)
    pressure, velocity = _broadcast_pair(
        "pressure_perturbation_pa",
        pressure_perturbation_pa,
        "velocity_m_s",
        velocity_m_s,
    )
    impedance_velocity = rho0 * c0 * velocity
    return 0.5 * (pressure + impedance_velocity), 0.5 * (
        pressure - impedance_velocity
    )


def pressure_velocity_from_characteristics(
    a_plus_pa: ArrayLike,
    a_minus_pa: ArrayLike,
    *,
    rho0_kg_m3: float,
    c0_m_s: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Reconstruct pressure perturbation and velocity from ``A+`` and ``A-``."""

    rho0, c0 = _positive_reference_scalars(rho0_kg_m3, c0_m_s)
    a_plus, a_minus = _broadcast_pair("a_plus_pa", a_plus_pa, "a_minus_pa", a_minus_pa)
    pressure = a_plus + a_minus
    velocity = (a_plus - a_minus) / (rho0 * c0)
    return pressure, velocity


def gaussian_profile(
    x_m: ArrayLike,
    *,
    amplitude_pa: float,
    center_m: float,
    sigma_m: float,
) -> NDArray[np.float64]:
    """Evaluate a Gaussian pressure-dimension characteristic profile."""

    x = _as_finite_array("x_m", x_m)
    amplitude = float(amplitude_pa)
    center = float(center_m)
    sigma = float(sigma_m)
    if not math.isfinite(amplitude):
        raise ValueError("amplitude_pa must be finite")
    if not math.isfinite(center):
        raise ValueError("center_m must be finite")
    if not math.isfinite(sigma) or sigma <= 0.0:
        raise ValueError("sigma_m must be finite and positive")
    return amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)


def make_gaussian_profile(
    *,
    amplitude_pa: float,
    center_m: float,
    sigma_m: float,
) -> ProfileFunction:
    """Create a stateless Gaussian profile callable."""

    gaussian_profile(
        np.asarray([center_m], dtype=float),
        amplitude_pa=amplitude_pa,
        center_m=center_m,
        sigma_m=sigma_m,
    )

    def profile(x_m: NDArray[np.float64]) -> NDArray[np.float64]:
        return gaussian_profile(
            x_m,
            amplitude_pa=amplitude_pa,
            center_m=center_m,
            sigma_m=sigma_m,
        )

    return profile


def _sample_initial_profile(
    profile: ProfileFunction,
    source_x_m: NDArray[np.float64],
    *,
    length_m: float,
) -> NDArray[np.float64]:
    source = np.asarray(source_x_m, dtype=float)
    result = np.zeros(source.shape, dtype=float)
    mask = (source >= 0.0) & (source <= float(length_m))
    if np.any(mask):
        sampled = _as_finite_array("initial profile sample", profile(source[mask]))
        try:
            result[mask] = np.broadcast_to(sampled, result[mask].shape)
        except ValueError as exc:
            raise ValueError(
                "initial profile output is not compatible with requested samples"
            ) from exc
    return result


def boundary_reflection_coefficient(boundary: BoundaryType) -> float:
    """Return the incoming/outgoing characteristic reflection coefficient."""

    _validate_boundary(boundary)
    if boundary == "rigid_wall":
        return 1.0
    if boundary == "fixed_pressure":
        return -1.0
    return 0.0


def reflected_incoming_characteristic(
    outgoing_characteristic_pa: ArrayLike,
    *,
    boundary: BoundaryType,
) -> NDArray[np.float64]:
    """Apply a right- or left-boundary characteristic reflection identity."""

    outgoing = _as_finite_array(
        "outgoing_characteristic_pa", outgoing_characteristic_pa
    )
    return boundary_reflection_coefficient(boundary) * np.array(
        outgoing, dtype=float, copy=True
    )


def evaluate_analytical_characteristics(
    x_m: ArrayLike,
    time_s: float,
    *,
    length_m: float,
    c0_m_s: float,
    initial_a_plus: ProfileFunction,
    initial_a_minus: ProfileFunction,
    left_boundary: BoundaryType = "transmissive",
    right_boundary: BoundaryType = "transmissive",
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Evaluate translated characteristics with at most one boundary reflection.

    Initial profiles are treated as zero outside ``0 <= x <= length_m``.  The
    evaluator includes one image term for each boundary and deliberately excludes
    any second reflection.
    """

    x = _as_finite_array("x_m", x_m)
    t = float(time_s)
    length = float(length_m)
    c0 = float(c0_m_s)
    if not math.isfinite(t) or t < 0.0:
        raise ValueError("time_s must be finite and non-negative")
    if not math.isfinite(length) or length <= 0.0:
        raise ValueError("length_m must be finite and positive")
    if not math.isfinite(c0) or c0 <= 0.0:
        raise ValueError("c0_m_s must be finite and positive")
    if np.any(x < 0.0) or np.any(x > length):
        raise ValueError("x_m samples must lie inside the reference domain")
    _validate_boundary(left_boundary)
    _validate_boundary(right_boundary)

    distance = c0 * t
    a_plus = _sample_initial_profile(
        initial_a_plus,
        x - distance,
        length_m=length,
    )
    a_minus = _sample_initial_profile(
        initial_a_minus,
        x + distance,
        length_m=length,
    )

    left_reflection = boundary_reflection_coefficient(left_boundary)
    if left_reflection:
        a_plus += left_reflection * _sample_initial_profile(
            initial_a_minus,
            distance - x,
            length_m=length,
        )

    right_reflection = boundary_reflection_coefficient(right_boundary)
    if right_reflection:
        a_minus += right_reflection * _sample_initial_profile(
            initial_a_plus,
            2.0 * length - x - distance,
            length_m=length,
        )

    return a_plus, a_minus


def evaluate_gaussian_reference(
    x_m: ArrayLike,
    time_s: float,
    *,
    length_m: float,
    rho0_kg_m3: float,
    c0_m_s: float,
    amplitude_pa: float,
    center_m: float,
    sigma_m: float,
    direction: Literal["right_going", "left_going"] = "right_going",
    left_boundary: BoundaryType = "transmissive",
    right_boundary: BoundaryType = "transmissive",
) -> dict[str, NDArray[np.float64]]:
    """Evaluate a pure travelling Gaussian and reconstruct pressure and velocity."""

    profile = make_gaussian_profile(
        amplitude_pa=amplitude_pa,
        center_m=center_m,
        sigma_m=sigma_m,
    )
    zero_profile: ProfileFunction = lambda source: np.zeros_like(source, dtype=float)
    if direction == "right_going":
        initial_a_plus, initial_a_minus = profile, zero_profile
    elif direction == "left_going":
        initial_a_plus, initial_a_minus = zero_profile, profile
    else:
        raise ValueError("direction must be 'right_going' or 'left_going'")

    a_plus, a_minus = evaluate_analytical_characteristics(
        x_m,
        time_s,
        length_m=length_m,
        c0_m_s=c0_m_s,
        initial_a_plus=initial_a_plus,
        initial_a_minus=initial_a_minus,
        left_boundary=left_boundary,
        right_boundary=right_boundary,
    )
    pressure, velocity = pressure_velocity_from_characteristics(
        a_plus,
        a_minus,
        rho0_kg_m3=rho0_kg_m3,
        c0_m_s=c0_m_s,
    )
    return {
        "a_plus_pa": a_plus,
        "a_minus_pa": a_minus,
        "pressure_perturbation_pa": pressure,
        "velocity_m_s": velocity,
    }


def initialize_moc_characteristics(
    config: LinearAcousticReferenceConfig,
    *,
    initial_a_plus: ProfileFunction,
    initial_a_minus: ProfileFunction,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Sample initial profiles on the independent nodal MOC grid."""

    x = config.grid()
    return (
        _sample_initial_profile(initial_a_plus, x, length_m=config.length_m),
        _sample_initial_profile(initial_a_minus, x, length_m=config.length_m),
    )


def moc_step(
    a_plus_pa: ArrayLike,
    a_minus_pa: ArrayLike,
    *,
    left_boundary: BoundaryType,
    right_boundary: BoundaryType,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Advance one exact one-cell characteristic translation at ``CFL=1``."""

    a_plus, a_minus = _broadcast_pair(
        "a_plus_pa", a_plus_pa, "a_minus_pa", a_minus_pa
    )
    if a_plus.ndim != 1:
        raise ValueError("MOC characteristic arrays must be one-dimensional")
    if a_plus.size < 2:
        raise ValueError("MOC characteristic arrays must contain at least two nodes")
    _validate_boundary(left_boundary)
    _validate_boundary(right_boundary)

    next_plus = np.empty_like(a_plus)
    next_minus = np.empty_like(a_minus)

    next_plus[1:] = a_plus[:-1]
    next_minus[:-1] = a_minus[1:]
    next_plus[0] = boundary_reflection_coefficient(left_boundary) * a_minus[1]
    next_minus[-1] = boundary_reflection_coefficient(right_boundary) * a_plus[-2]
    return next_plus, next_minus


def run_moc_reference(
    config: LinearAcousticReferenceConfig,
    *,
    initial_a_plus_pa: ArrayLike,
    initial_a_minus_pa: ArrayLike,
    n_steps: int,
) -> dict[str, Any]:
    """Run the independent nodal MOC translator and retain full history."""

    if isinstance(n_steps, bool) or not isinstance(n_steps, (int, np.integer)):
        raise ValueError("n_steps must be a non-negative integer")
    if int(n_steps) < 0:
        raise ValueError("n_steps must be a non-negative integer")
    step_count = int(n_steps)
    a_plus, a_minus = _broadcast_pair(
        "initial_a_plus_pa",
        initial_a_plus_pa,
        "initial_a_minus_pa",
        initial_a_minus_pa,
    )
    if a_plus.ndim != 1 or a_plus.shape != (config.n_nodes,):
        raise ValueError(
            "initial characteristic arrays must be one-dimensional with "
            f"shape ({config.n_nodes},)"
        )

    plus_history = np.empty((step_count + 1, config.n_nodes), dtype=float)
    minus_history = np.empty_like(plus_history)
    plus_history[0] = a_plus
    minus_history[0] = a_minus

    current_plus = np.array(a_plus, dtype=float, copy=True)
    current_minus = np.array(a_minus, dtype=float, copy=True)
    for step in range(1, step_count + 1):
        current_plus, current_minus = moc_step(
            current_plus,
            current_minus,
            left_boundary=config.left_boundary,
            right_boundary=config.right_boundary,
        )
        plus_history[step] = current_plus
        minus_history[step] = current_minus

    pressure, velocity = pressure_velocity_from_characteristics(
        plus_history,
        minus_history,
        rho0_kg_m3=config.rho0_kg_m3,
        c0_m_s=config.c0_m_s,
    )
    return {
        "x_m": config.grid(),
        "time_s": np.arange(step_count + 1, dtype=float) * config.dt_s,
        "a_plus_pa": plus_history,
        "a_minus_pa": minus_history,
        "pressure_perturbation_pa": pressure,
        "velocity_m_s": velocity,
        "n_steps": step_count,
        "dx_m": config.dx_m,
        "dt_s": config.dt_s,
        "cfl": config.cfl,
        "reference_only": True,
        "calls_coolprop": False,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
    }


def acoustic_energy_proxy(
    x_m: ArrayLike,
    pressure_perturbation_pa: ArrayLike,
    velocity_m_s: ArrayLike,
    *,
    rho0_kg_m3: float,
    c0_m_s: float,
) -> float:
    """Integrate the linear acoustic-energy proxy over one spatial profile."""

    rho0, c0 = _positive_reference_scalars(rho0_kg_m3, c0_m_s)
    x = _as_finite_array("x_m", x_m)
    pressure, velocity = _broadcast_pair(
        "pressure_perturbation_pa",
        pressure_perturbation_pa,
        "velocity_m_s",
        velocity_m_s,
    )
    if x.ndim != 1 or pressure.ndim != 1 or x.shape != pressure.shape:
        raise ValueError("x, pressure, and velocity must be matching 1-D profiles")
    if x.size < 2 or np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing with at least two samples")
    density = pressure**2 / (2.0 * rho0 * c0**2) + 0.5 * rho0 * velocity**2
    return float(np.sum(0.5 * (density[:-1] + density[1:]) * np.diff(x)))


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write_moc_reference_json(
    path: str | Path,
    *,
    config: LinearAcousticReferenceConfig,
    history: Mapping[str, Any],
) -> Path:
    """Write a deterministic UTF-8 JSON snapshot of a reference history."""

    destination = Path(path)
    payload = {
        "config": asdict(config),
        "history": _jsonable(dict(history)),
        "independence": {
            "production_solver_imported": False,
            "production_boundary_imported": False,
            "production_flux_imported": False,
            "coolprop_called": False,
        },
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination
