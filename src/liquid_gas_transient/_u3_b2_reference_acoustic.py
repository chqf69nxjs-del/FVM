"""Independent fixed-probe and linear-acoustic references for U3 B2."""
from __future__ import annotations
from typing import Any, Sequence
from ._u3_b2_reference_contract import SUCCESS_FIXED_MESH_CFL_CHARACTERIZATION
from ._u3_b2_reference_types import AcousticArrivalReference

def probe_map(
    extension: dict[str, Any],
    cells: int,
    probe_x_over_L: float,
) -> dict[str, Any]:
    mappings = extension["acoustic_event_detection"]["spatial_probe_sampling"][
        "fixed_mesh_probe_map"
    ]
    for row in mappings:
        if int(row["cells"]) != cells:
            continue
        for probe in row["entries"]:
            if float(probe["xi_probe"]) == float(probe_x_over_L):
                return {
                    "requested_x_over_L": float(probe["xi_probe"]),
                    "left_cell_index_zero_based": int(probe["left_internal_index"]),
                    "right_cell_index_zero_based": int(probe["right_internal_index"]),
                    "left_center_x_over_L": float(probe["left_center_xi"]),
                    "right_center_x_over_L": float(probe["right_center_xi"]),
                    "interpolation_weight_right": float(probe["lambda"]),
                }
    raise KeyError((cells, probe_x_over_L))
def interpolate_probe(
    values: Sequence[float],
    mapping: dict[str, Any],
) -> float:
    left = int(mapping["left_cell_index_zero_based"])
    right = int(mapping["right_cell_index_zero_based"])
    weight = float(mapping["interpolation_weight_right"])
    if left < 0 or right >= len(values) or right != left + 1:
        raise ValueError("Invalid locked probe bracket")
    return (1.0 - weight) * float(values[left]) + weight * float(values[right])
def acoustic_arrival_rows(
    contract: dict[str, Any],
    extension: dict[str, Any],
    liquid_sound_speed_m_s: float,
) -> list[AcousticArrivalReference]:
    length = float(contract["geometry"]["pipe_length_m"])
    probes = [float(value) for value in contract["acoustic_reference"]["probe_normalized_positions"]]
    direct_order = {0.75: 1, 0.5: 2, 0.25: 3}
    reflected_order = {0.25: 1, 0.5: 2, 0.75: 3}
    rows: list[AcousticArrivalReference] = []
    for cells in contract["geometry"]["fixed_mesh_sequence"]:
        for probe in probes:
            mapping = probe_map(extension, int(cells), probe)
            rows.append(
                AcousticArrivalReference(
                    case_id="B2-11_ACOUSTIC_REFERENCE",
                    cells=int(cells),
                    cfl=None,
                    probe_x_over_L=probe,
                    left_cell_index_zero_based=int(
                        mapping["left_cell_index_zero_based"]
                    ),
                    right_cell_index_zero_based=int(
                        mapping["right_cell_index_zero_based"]
                    ),
                    left_center_x_over_L=float(mapping["left_center_x_over_L"]),
                    right_center_x_over_L=float(mapping["right_center_x_over_L"]),
                    interpolation_weight_right=float(
                        mapping["interpolation_weight_right"]
                    ),
                    direct_arrival_time_s=(length - probe * length)
                    / liquid_sound_speed_m_s,
                    reflected_arrival_time_s=(length + probe * length)
                    / liquid_sound_speed_m_s,
                    direct_pressure_sign="negative",
                    direct_velocity_sign="positive_outward",
                    reflected_pressure_sign="negative",
                    reflected_velocity_sign="negative_inward",
                    direct_order_rank=direct_order[probe],
                    reflected_order_rank=reflected_order[probe],
                )
            )
    return rows
def mesh_cfl_reference_rows(
    contract: dict[str, Any],
    acoustic_rows: list[AcousticArrivalReference],
) -> list[dict[str, Any]]:
    by_mesh_probe = {
        (row.cells, row.probe_x_over_L): row for row in acoustic_rows
    }
    rows: list[dict[str, Any]] = []
    for cells in contract["geometry"]["fixed_mesh_sequence"]:
        for cfl in contract["geometry"]["fixed_cfl_sequence"]:
            for probe in contract["acoustic_reference"]["probe_normalized_positions"]:
                acoustic = by_mesh_probe[(int(cells), float(probe))]
                rows.append(
                    {
                        "case_id": "B2-12_FIXED_MESH_CFL_CHARACTERIZATION",
                        "cells": int(cells),
                        "cfl": float(cfl),
                        "probe_x_over_L": float(probe),
                        "direct_arrival_reference_s": acoustic.direct_arrival_time_s,
                        "reflected_arrival_reference_s": acoustic.reflected_arrival_time_s,
                        "mass_energy_inventory_target": "within locked tolerance",
                        "formal_outcome_target": SUCCESS_FIXED_MESH_CFL_CHARACTERIZATION,
                        "claim_limit": (
                            "characterization only; no convergence order or "
                            "mesh/CFL independence approval"
                        ),
                    }
                )
    return rows
