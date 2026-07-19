"""V-013A saved-artifact plot adapter with corrected mesh-spacing axes."""
from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any, Mapping

from . import _plot_v013_incident_propagation_results_impl as _impl


EXPECTED_PLOT_COUNT = _impl.EXPECTED_PLOT_COUNT
_MISSING = object()


def plot_v013_incident_propagation_results(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate the seven saved-artifact figures without rerunning a solver."""

    previous_sorted = getattr(_impl, "sorted", _MISSING)

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

    _impl.sorted = increasing_mesh_sorted
    axes_type: Any | None = None
    original_set_xlabel: Any | None = None
    try:
        from matplotlib.axes import Axes

        axes_type = Axes
        original_set_xlabel = Axes.set_xlabel

        def corrected_set_xlabel(self: Any, xlabel: str, *args: Any, **kwargs: Any) -> Any:
            if xlabel == "dx [m] (coarse to fine)":
                xlabel = "mesh spacing Δx [m]"
            return original_set_xlabel(self, xlabel, *args, **kwargs)

        Axes.set_xlabel = corrected_set_xlabel
    except Exception:  # pragma: no cover - original plotter reports import errors
        pass

    try:
        return _impl.plot_v013_incident_propagation_results(output_dir)
    finally:
        if previous_sorted is _MISSING:
            delattr(_impl, "sorted")
        else:
            _impl.sorted = previous_sorted
        if axes_type is not None and original_set_xlabel is not None:
            axes_type.set_xlabel = original_set_xlabel


__all__ = ["EXPECTED_PLOT_COUNT", "plot_v013_incident_propagation_results"]
