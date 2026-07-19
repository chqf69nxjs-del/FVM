"""Public V-013A adapter with compatibility and artifact traceability guards.

The numerical implementation remains isolated in
``_v013_incident_propagation_impl``.  This adapter does not alter production
solver physics; it only supplies the project-supported NumPy integration
fallback and records the installed CoolProp distribution version in V-013A
verification artifacts.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike

from . import _v013_incident_propagation_impl as _impl


def _installed_coolprop_version() -> str:
    try:
        return distribution_version("CoolProp")
    except PackageNotFoundError as exc:  # pragma: no cover - FVM setup requires it
        raise RuntimeError("CoolProp package metadata is unavailable") from exc


def _trapezoidal_integral(values: ArrayLike, x_m: ArrayLike) -> float:
    """Integrate with NumPy 1.x/2.x compatibility."""

    integrate = getattr(np, "trapezoid", None)
    if integrate is None:
        integrate = np.trapz
    return float(
        integrate(
            np.asarray(values, dtype=float),
            np.asarray(x_m, dtype=float),
        )
    )


def normalized_error_norms(
    x_m: ArrayLike,
    candidate: ArrayLike,
    reference: ArrayLike,
    *,
    normalization_reference: ArrayLike | None = None,
) -> dict[str, float]:
    """Return normalized L1/L2/Linf and absolute Linf errors on a fixed grid."""

    x = np.asarray(x_m, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    ref = np.asarray(reference, dtype=float)
    scale = ref if normalization_reference is None else np.asarray(
        normalization_reference, dtype=float
    )
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be a 1-D increasing grid with at least two samples")
    if cand.shape != x.shape or ref.shape != x.shape or scale.shape != x.shape:
        raise ValueError(
            "candidate, reference, and normalization arrays must match x_m"
        )
    if not (
        np.all(np.isfinite(x))
        and np.all(np.diff(x) > 0.0)
        and np.all(np.isfinite(cand))
        and np.all(np.isfinite(ref))
        and np.all(np.isfinite(scale))
    ):
        raise ValueError("error-norm inputs must be finite on an increasing grid")
    diff = cand - ref
    l1_num = _trapezoidal_integral(np.abs(diff), x)
    l2_num = float(np.sqrt(_trapezoidal_integral(diff * diff, x)))
    linf_num = float(np.max(np.abs(diff)))
    l1_den = _trapezoidal_integral(np.abs(scale), x)
    l2_den = float(np.sqrt(_trapezoidal_integral(scale * scale, x)))
    linf_den = float(np.max(np.abs(scale)))
    floor = np.finfo(float).tiny
    return {
        "l1_relative": 0.0 if l1_num == 0.0 else l1_num / max(l1_den, floor),
        "l2_relative": 0.0 if l2_num == 0.0 else l2_num / max(l2_den, floor),
        "linf_relative": (
            0.0 if linf_num == 0.0 else linf_num / max(linf_den, floor)
        ),
        "linf_absolute": linf_num,
    }


_original_run_fvm = _impl._run_fvm
_original_write_json = _impl._write_json
_original_runner = _impl.run_v013_incident_propagation


def _run_fvm(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
    metrics, history, probes, source = _original_run_fvm(*args, **kwargs)
    metrics = dict(metrics)
    metrics["coolprop_version"] = _installed_coolprop_version()
    return metrics, history, probes, source


def _write_json(path: Path, value: Any) -> None:
    if path.name in {
        "fvm_metrics.json",
        "v013a_reference_constants.json",
        "v013a_metrics.json",
    } and isinstance(value, Mapping):
        value = dict(value)
        value["coolprop_version"] = _installed_coolprop_version()
    _original_write_json(path, value)



def run_v013_incident_propagation(
    output_dir: str | Path | None = None,
    config: Any | None = None,
) -> dict[str, Any]:
    result = _original_runner(output_dir, config)
    result["coolprop_version"] = _installed_coolprop_version()
    return result


_impl.normalized_error_norms = normalized_error_norms
_impl._run_fvm = _run_fvm
_impl._write_json = _write_json
_impl.run_v013_incident_propagation = run_v013_incident_propagation

V013IncidentPropagationConfig = _impl.V013IncidentPropagationConfig
build_run_plan = _impl.build_run_plan
case_id_for = _impl.case_id_for
leading_fraction_crossings = _impl.leading_fraction_crossings
sample_spacetime_history = _impl.sample_spacetime_history


def main(argv: Sequence[str] | None = None) -> int:
    return _impl.main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "V013IncidentPropagationConfig",
    "build_run_plan",
    "case_id_for",
    "leading_fraction_crossings",
    "normalized_error_norms",
    "run_v013_incident_propagation",
    "sample_spacetime_history",
]
