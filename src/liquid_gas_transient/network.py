"""Network-level component definitions for Ver.0.2.6.

The Ver.0.2.0--0.2.2 solver treated Case C as one equivalent pipe with
an optional internal ESD valve. Ver.0.2.4 keeps the same conservative FVM core
but adds cell-wise segment source profiles for friction and gravity:

    tank -- pump -- pipe segment -- pipe segment -- ESD valve -- pipe segment -- tank

This module deliberately does **not** implement a general graph solver yet.
Instead it implements a validated one-dimensional, ordered component chain. The
new Ver.0.2.4 responsibility is to map segment properties onto per-cell source
arrays so pressure-loss and elevation effects can be verified without hiding
them inside case scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
import math
import numpy as np

from .config import PipeGeometry
from .grid import UniformGrid


@dataclass(frozen=True)
class PipeSegmentSpec:
    """Ordered one-dimensional pipe segment.

    Parameters
    ----------
    name:
        Stable component name used in diagnostics and case definitions.
    length_m:
        Segment centerline length [m].
    diameter_m:
        Inner diameter [m]. Ver.0.2.3 supports a single uniform diameter in the
        FVM core, but the field is placed at segment level for future area-change
        interfaces.
    n_cells:
        Optional fixed cell count for the segment. If omitted, cells are
        allocated proportionally from the case-level total.
    roughness_m:
        Segment absolute roughness [m]. Stored for future friction correlations.
    darcy_friction_factor:
        Prescribed Darcy friction factor [-] for Ver.0.2.4 source verification.
        Later versions may compute this from Reynolds number and roughness.
    elevation_start_m, elevation_end_m:
        Segment endpoint elevations [m]. Used to construct the cell-wise slope
        dz/dx for gravity source terms.
    """

    name: str
    length_m: float
    diameter_m: float
    n_cells: int | None = None
    roughness_m: float = 0.0
    darcy_friction_factor: float = 0.0
    elevation_start_m: float = 0.0
    elevation_end_m: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("pipe segment name must be non-empty")
        if self.length_m <= 0.0:
            raise ValueError(f"pipe segment {self.name}: length_m must be positive")
        if self.diameter_m <= 0.0:
            raise ValueError(f"pipe segment {self.name}: diameter_m must be positive")
        if self.n_cells is not None and self.n_cells <= 0:
            raise ValueError(f"pipe segment {self.name}: n_cells must be positive if provided")
        if self.roughness_m < 0.0:
            raise ValueError(f"pipe segment {self.name}: roughness_m must be non-negative")
        if self.darcy_friction_factor < 0.0:
            raise ValueError(f"pipe segment {self.name}: darcy_friction_factor must be non-negative")
        if not math.isfinite(self.elevation_start_m) or not math.isfinite(self.elevation_end_m):
            raise ValueError(f"pipe segment {self.name}: elevations must be finite")

    @property
    def area_m2(self) -> float:
        return math.pi * self.diameter_m**2 / 4.0


@dataclass(frozen=True)
class TankBoundarySpec:
    """Pressure-reservoir tank boundary used by Ver.0.2.3."""

    name: str
    pressure_pa: float
    side: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tank name must be non-empty")
        if self.pressure_pa <= 0.0:
            raise ValueError(f"tank {self.name}: pressure_pa must be positive")
        if self.side not in {"left", "right"}:
            raise ValueError("tank side must be 'left' or 'right'")


@dataclass(frozen=True)
class PumpInterfaceSpec:
    """Quasi-steady pump component for the ordered network chain.

    Ver.0.2.6 still does not solve rotating-inertia pump dynamics.  It stores
    the pump location and pressure-rise schedule parameters so the case builder
    can construct a verified pump-discharge inlet boundary.
    """

    name: str
    after_component: str
    delta_p_nominal_pa: float = 0.0
    trip_time_s: float | None = None
    trip_duration_s: float = 0.0
    delta_p_final_pa: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("pump name must be non-empty")
        if not self.after_component:
            raise ValueError("pump after_component must be non-empty")
        if self.delta_p_nominal_pa < 0.0:
            raise ValueError("pump delta_p_nominal_pa must be non-negative")
        if self.trip_time_s is not None and self.trip_time_s < 0.0:
            raise ValueError("pump trip_time_s must be non-negative when provided")
        if self.trip_duration_s < 0.0:
            raise ValueError("pump trip_duration_s must be non-negative")
        if self.delta_p_final_pa < 0.0:
            raise ValueError("pump delta_p_final_pa must be non-negative")


@dataclass(frozen=True)
class ValveInterfaceSpec:
    """Internal valve connecting two adjacent pipe segments."""

    name: str
    upstream_segment: str
    downstream_segment: str
    kv_m3_h: float | None
    close_start_s: float
    close_time_s: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("valve name must be non-empty")
        if not self.upstream_segment or not self.downstream_segment:
            raise ValueError("valve segment names must be non-empty")
        if self.upstream_segment == self.downstream_segment:
            raise ValueError("valve upstream and downstream segments must differ")
        if self.kv_m3_h is not None and self.kv_m3_h <= 0.0:
            raise ValueError("valve kv_m3_h must be positive when provided")
        if self.close_start_s < 0.0:
            raise ValueError("valve close_start_s must be non-negative")
        if self.close_time_s < 0.0:
            raise ValueError("valve close_time_s must be non-negative")


@dataclass(frozen=True)
class ComponentNetwork:
    """Ordered one-dimensional hydraulic network description."""

    name: str
    inlet_tank: TankBoundarySpec
    outlet_tank: TankBoundarySpec
    pipe_segments: tuple[PipeSegmentSpec, ...]
    esd_valve: ValveInterfaceSpec
    pump: PumpInterfaceSpec | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("network name must be non-empty")
        if len(self.pipe_segments) == 0:
            raise ValueError("network must contain at least one pipe segment")
        names = [segment.name for segment in self.pipe_segments]
        if len(set(names)) != len(names):
            raise ValueError("pipe segment names must be unique")
        if self.inlet_tank.side != "left":
            raise ValueError("inlet_tank must be on left side")
        if self.outlet_tank.side != "right":
            raise ValueError("outlet_tank must be on right side")
        if self.esd_valve.upstream_segment not in names:
            raise ValueError("ESD upstream segment is not in pipe_segments")
        if self.esd_valve.downstream_segment not in names:
            raise ValueError("ESD downstream segment is not in pipe_segments")

    @property
    def total_length_m(self) -> float:
        return float(sum(segment.length_m for segment in self.pipe_segments))

    @property
    def reference_diameter_m(self) -> float:
        return self.pipe_segments[0].diameter_m

    def require_uniform_diameter(self, *, rtol: float = 1.0e-12) -> float:
        """Return common diameter or raise for unsupported area changes."""

        d0 = self.reference_diameter_m
        for segment in self.pipe_segments:
            if not math.isclose(segment.diameter_m, d0, rel_tol=rtol, abs_tol=0.0):
                raise NotImplementedError(
                    "Ver.0.2.6 FVM core supports only uniform-diameter ordered networks; "
                    f"segment {segment.name} has D={segment.diameter_m}, reference D={d0}"
                )
        return d0

    def ordered_segment_names(self) -> tuple[str, ...]:
        return tuple(segment.name for segment in self.pipe_segments)


@dataclass(frozen=True)
class DiscretizedNetwork:
    """Flattened grid mapping derived from a ComponentNetwork."""

    network: ComponentNetwork
    geometry: PipeGeometry
    grid: UniformGrid
    segment_slices: Mapping[str, slice]
    segment_face_indices: Mapping[str, tuple[int, int]]
    device_face_indices: Mapping[str, int]
    cell_segment_names: tuple[str, ...]
    cell_diameter_m: np.ndarray
    cell_area_m2: np.ndarray
    cell_darcy_friction_factor: np.ndarray
    cell_dzdx: np.ndarray
    cell_elevation_m: np.ndarray

    def segment_slice(self, name: str) -> slice:
        return self.segment_slices[name]

    def segment_faces(self, name: str) -> tuple[int, int]:
        return self.segment_face_indices[name]

    def device_face(self, name: str) -> int:
        return self.device_face_indices[name]

    def cell_centers_by_segment(self, name: str) -> np.ndarray:
        return self.grid.cell_centers[self.segment_slice(name)]

    def source_arrays_by_segment(self, name: str) -> dict[str, np.ndarray]:
        """Return cell-wise source arrays for one named segment."""

        sl = self.segment_slice(name)
        return {
            "diameter_m": self.cell_diameter_m[sl],
            "area_m2": self.cell_area_m2[sl],
            "darcy_friction_factor": self.cell_darcy_friction_factor[sl],
            "dzdx": self.cell_dzdx[sl],
            "elevation_m": self.cell_elevation_m[sl],
        }

    def total_static_head_change_m(self) -> float:
        """Return outlet elevation minus inlet elevation based on segment endpoints."""

        return float(self.network.pipe_segments[-1].elevation_end_m - self.network.pipe_segments[0].elevation_start_m)

    def summary(self) -> dict[str, object]:
        return {
            "network": self.network.name,
            "total_length_m": self.geometry.length_m,
            "diameter_m": self.geometry.diameter_m,
            "n_cells": self.grid.n_cells,
            "dx_m": self.grid.dx,
            "segments": [
                {
                    "name": segment.name,
                    "length_m": segment.length_m,
                    "diameter_m": segment.diameter_m,
                    "roughness_m": segment.roughness_m,
                    "darcy_friction_factor": segment.darcy_friction_factor,
                    "elevation_start_m": segment.elevation_start_m,
                    "elevation_end_m": segment.elevation_end_m,
                    "dzdx": (segment.elevation_end_m - segment.elevation_start_m) / segment.length_m,
                    "cell_start": self.segment_slices[segment.name].start,
                    "cell_stop": self.segment_slices[segment.name].stop,
                    "n_cells": self.segment_slices[segment.name].stop - self.segment_slices[segment.name].start,
                    "face_start": self.segment_face_indices[segment.name][0],
                    "face_stop": self.segment_face_indices[segment.name][1],
                }
                for segment in self.network.pipe_segments
            ],
            "devices": dict(self.device_face_indices),
            "inlet_tank": self.network.inlet_tank.name,
            "outlet_tank": self.network.outlet_tank.name,
            "pump": None if self.network.pump is None else {
                "name": self.network.pump.name,
                "face": self.device_face_indices.get(self.network.pump.name),
                "delta_p_nominal_pa": self.network.pump.delta_p_nominal_pa,
                "trip_time_s": self.network.pump.trip_time_s,
                "trip_duration_s": self.network.pump.trip_duration_s,
                "delta_p_final_pa": self.network.pump.delta_p_final_pa,
            },
            "static_head_change_m": self.total_static_head_change_m(),
            "friction_factor_min": float(np.min(self.cell_darcy_friction_factor)),
            "friction_factor_max": float(np.max(self.cell_darcy_friction_factor)),
            "dzdx_min": float(np.min(self.cell_dzdx)),
            "dzdx_max": float(np.max(self.cell_dzdx)),
        }


def allocate_cells_by_length(segments: tuple[PipeSegmentSpec, ...], total_cells: int) -> tuple[int, ...]:
    """Allocate cell counts to segments by length using largest remainder.

    Segments with explicit ``n_cells`` keep that value; remaining cells are
    distributed in proportion to length among unspecified segments.
    """

    if total_cells < len(segments):
        raise ValueError("total_cells must be at least the number of pipe segments")

    fixed = [segment.n_cells for segment in segments]
    fixed_sum = sum(n for n in fixed if n is not None)
    unspecified_indices = [i for i, n in enumerate(fixed) if n is None]
    if fixed_sum > total_cells:
        raise ValueError("fixed segment cell counts exceed total_cells")
    if not unspecified_indices:
        if fixed_sum != total_cells:
            raise ValueError("sum of fixed segment cell counts must equal total_cells")
        return tuple(int(n) for n in fixed if n is not None)

    remaining = total_cells - fixed_sum
    if remaining < len(unspecified_indices):
        raise ValueError("not enough cells remain to give each unspecified segment at least one cell")

    lengths = np.array([segments[i].length_m for i in unspecified_indices], dtype=float)
    raw = remaining * lengths / float(np.sum(lengths))
    counts = np.floor(raw).astype(int)
    counts = np.maximum(counts, 1)

    # Correct any overshoot caused by the at-least-one rule.
    while int(np.sum(counts)) > remaining:
        candidates = np.where(counts > 1)[0]
        if candidates.size == 0:
            raise ValueError("cannot satisfy minimum cell allocation")
        # remove from the segment with the smallest fractional need among candidates
        j = candidates[np.argmin(raw[candidates] - np.floor(raw[candidates]))]
        counts[j] -= 1

    # Largest remainder for remaining cells.
    remainders = raw - np.floor(raw)
    while int(np.sum(counts)) < remaining:
        j = int(np.argmax(remainders))
        counts[j] += 1
        remainders[j] = -1.0  # prevent repeated bias before all get a turn
        if np.all(remainders < 0.0) and int(np.sum(counts)) < remaining:
            remainders = raw - np.floor(raw)

    out: list[int] = []
    cursor = 0
    for n in fixed:
        if n is None:
            out.append(int(counts[cursor]))
            cursor += 1
        else:
            out.append(int(n))
    if sum(out) != total_cells:
        raise AssertionError("internal allocation error")
    return tuple(out)


def discretize_network(network: ComponentNetwork, *, total_cells: int) -> DiscretizedNetwork:
    """Flatten a validated ordered network onto the current uniform FVM grid."""

    diameter_m = network.require_uniform_diameter()
    roughness_m = max(segment.roughness_m for segment in network.pipe_segments)
    geometry = PipeGeometry(length_m=network.total_length_m, diameter_m=diameter_m, roughness_m=roughness_m)
    grid = UniformGrid(geometry=geometry, n_cells=total_cells)

    cell_counts = allocate_cells_by_length(network.pipe_segments, total_cells)
    segment_slices: dict[str, slice] = {}
    segment_face_indices: dict[str, tuple[int, int]] = {}
    cell_segment_names: list[str] = []
    cell_diameter_m = np.empty(total_cells, dtype=float)
    cell_area_m2 = np.empty(total_cells, dtype=float)
    cell_darcy_friction_factor = np.empty(total_cells, dtype=float)
    cell_dzdx = np.empty(total_cells, dtype=float)
    cell_elevation_m = np.empty(total_cells, dtype=float)
    cell_cursor = 0
    for segment, n_cells in zip(network.pipe_segments, cell_counts, strict=True):
        start = cell_cursor
        stop = cell_cursor + n_cells
        segment_slices[segment.name] = slice(start, stop)
        segment_face_indices[segment.name] = (start, stop)
        sl = slice(start, stop)
        cell_segment_names.extend([segment.name] * n_cells)
        cell_diameter_m[sl] = segment.diameter_m
        cell_area_m2[sl] = segment.area_m2
        cell_darcy_friction_factor[sl] = segment.darcy_friction_factor
        dzdx = (segment.elevation_end_m - segment.elevation_start_m) / segment.length_m
        cell_dzdx[sl] = dzdx
        local_x = (np.arange(n_cells, dtype=float) + 0.5) / n_cells
        cell_elevation_m[sl] = segment.elevation_start_m + local_x * (segment.elevation_end_m - segment.elevation_start_m)
        cell_cursor = stop

    if cell_cursor != total_cells:
        raise AssertionError("internal discretization error")

    u = network.esd_valve.upstream_segment
    d = network.esd_valve.downstream_segment
    u_faces = segment_face_indices[u]
    d_faces = segment_face_indices[d]
    if u_faces[1] != d_faces[0]:
        raise NotImplementedError(
            "Ver.0.2.6 supports an ESD valve only between adjacent ordered pipe segments"
        )

    device_faces = {network.esd_valve.name: u_faces[1]}
    if network.pump is not None:
        if network.pump.after_component == network.inlet_tank.name:
            device_faces[network.pump.name] = 0
        elif network.pump.after_component in segment_face_indices:
            device_faces[network.pump.name] = segment_face_indices[network.pump.after_component][1]
        else:
            raise ValueError("pump after_component must be inlet tank name or a pipe segment name")

    return DiscretizedNetwork(
        network=network,
        geometry=geometry,
        grid=grid,
        segment_slices=segment_slices,
        segment_face_indices=segment_face_indices,
        device_face_indices=device_faces,
        cell_segment_names=tuple(cell_segment_names),
        cell_diameter_m=cell_diameter_m,
        cell_area_m2=cell_area_m2,
        cell_darcy_friction_factor=cell_darcy_friction_factor,
        cell_dzdx=cell_dzdx,
        cell_elevation_m=cell_elevation_m,
    )
