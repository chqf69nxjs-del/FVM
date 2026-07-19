"""V-013A saved-artifact plot adapter with axes and traceability fixes."""
from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any, Mapping

from . import _plot_v013_incident_propagation_results_impl as _impl


EXPECTED_PLOT_COUNT = _impl.EXPECTED_PLOT_COUNT
_MISSING = object()
_PLOT_MODEL = (
    "production FVM + independent linear-acoustic MOC/analytical reference"
)


def _required_traceability_value(metrics: Mapping[str, Any], key: str) -> str:
    value = metrics.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"V-013A plot traceability requires {key}")
    return str(value)


def _plot_traceability(metrics: Mapping[str, Any]) -> dict[str, str]:
    """Return required case/model/backend/version metadata for every result plot."""

    return {
        "case_name": _required_traceability_value(metrics, "case_name"),
        "model": _PLOT_MODEL,
        "property_backend_name": _required_traceability_value(
            metrics, "property_backend_name"
        ),
        "coolprop_version": _required_traceability_value(
            metrics, "coolprop_version"
        ),
        "output_version": _required_traceability_value(metrics, "output_version"),
    }


def _plot_traceability_footer(metrics: Mapping[str, Any]) -> str:
    """Build the three-line footer embedded in each saved V-013A figure."""

    trace = _plot_traceability(metrics)
    return "\n".join(
        [
            f"case: {trace['case_name']} | model: {trace['model']}",
            (
                f"backend: {trace['property_backend_name']} | "
                f"CoolProp: {trace['coolprop_version']} | "
                f"output: {trace['output_version']}"
            ),
            (
                "V-013A software/numerical verification only; "
                "not physical Validation or design-use acceptance"
            ),
        ]
    )


def plot_v013_incident_propagation_results(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate seven traceable figures from saved artifacts without solver reruns."""

    base = Path(output_dir)
    metrics = json.loads((base / "v013a_metrics.json").read_text(encoding="utf-8"))
    traceability = _plot_traceability(metrics)
    footer = _plot_traceability_footer(metrics)

    previous_sorted = getattr(_impl, "sorted", _MISSING)
    original_save = _impl._save

    def increasing_mesh_sorted(iterable: Any, *args: Any, **kwargs: Any) -> list[Any]:
        items = list(iterable)
        if (
            kwargs.get("reverse") is True
            and items
            and isinstance(items[0], Mapping)
            and "dx_m" in items[0]
        ):
            kwargs = dict(kwargs)
            kwargs["reverse"] = False
        return builtins.sorted(items, *args, **kwargs)

    def traceable_save(fig: Any, output_base: Path, name: str) -> str:
        for y_position, line in zip((0.062, 0.039, 0.016), footer.splitlines()):
            fig.text(0.01, y_position, line, fontsize=7)
        fig.tight_layout(rect=(0.0, 0.11, 1.0, 1.0))
        fig.savefig(output_base / name, dpi=160, bbox_inches="tight")
        return name

    _impl.sorted = increasing_mesh_sorted
    _impl._save = traceable_save
    axes_type: Any | None = None
    original_set_xlabel: Any | None = None
    try:
        from matplotlib.axes import Axes

        axes_type = Axes
        original_set_xlabel = Axes.set_xlabel

        def corrected_set_xlabel(
            self: Any, xlabel: str, *args: Any, **kwargs: Any
        ) -> Any:
            if xlabel == "dx [m] (coarse to fine)":
                xlabel = "mesh spacing Δx [m]"
            return original_set_xlabel(self, xlabel, *args, **kwargs)

        Axes.set_xlabel = corrected_set_xlabel
    except Exception:  # pragma: no cover - original plotter reports import errors
        pass

    try:
        result = dict(_impl.plot_v013_incident_propagation_results(base))
        result["plot_traceability"] = traceability
        result["plot_traceability_footer"] = footer
        result["plot_traceability_complete"] = True
        (base / "v013a_plot_metrics.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return result
    finally:
        _impl._save = original_save
        if previous_sorted is _MISSING:
            delattr(_impl, "sorted")
        else:
            _impl.sorted = previous_sorted
        if axes_type is not None and original_set_xlabel is not None:
            axes_type.set_xlabel = original_set_xlabel


__all__ = ["EXPECTED_PLOT_COUNT", "plot_v013_incident_propagation_results"]
