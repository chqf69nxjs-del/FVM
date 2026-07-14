from __future__ import annotations

import csv
from pathlib import Path

from liquid_gas_transient.plot_internal_valve_operation_results import (
    plot_internal_valve_operation_results,
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_plot_internal_valve_operation_results(tmp_path: Path) -> None:
    stem = "synthetic_valve"
    valve_rows = []
    flux_rows = []
    probe_rows = []
    for index, time_s in enumerate((0.0, 0.01, 0.02)):
        opening = index / 2.0
        valve_rows.append(
            {
                "time_s": time_s,
                "opening": opening,
                "p_left_pa": 8.001e6,
                "p_right_pa": 8.0e6,
                "delta_p_pa": 1000.0,
                "target_q_raw_m3_s": opening * 1.0e-3,
                "target_q_limited_m3_s": opening * 1.0e-3,
                "actual_q_from_mass_flux_m3_s": opening * 1.0e-3,
                "u_face_m_s": opening * 1.0e-2,
                "face_mach": opening * 1.0e-5,
                "q_mach_limit_m3_s": 1.0,
                "mach_cap_active": False,
                "valve_loss_power_w": opening,
            }
        )
        flux_rows.append(
            {
                "time_s": time_s,
                "left_mass_flux_kg_m2_s": opening,
                "right_mass_flux_kg_m2_s": opening,
                "mass_flux_mismatch_kg_m2_s": 0.0,
                "left_momentum_flux_pa": 1.0,
                "right_momentum_flux_pa": 2.0,
                "momentum_flux_difference_pa": 1.0,
                "left_energy_flux_w_m2": opening * 10.0,
                "right_energy_flux_w_m2": opening * 10.0,
                "energy_flux_mismatch_w_m2": 0.0,
                "left_vapor_mass_flux_kg_m2_s": 0.0,
                "right_vapor_mass_flux_kg_m2_s": 0.0,
                "vapor_mass_flux_mismatch_kg_m2_s": 0.0,
            }
        )
        for name, pressure in (("left_probe", 8.001e6), ("right_probe", 8.0e6)):
            probe_rows.append(
                {
                    "time_s": time_s,
                    "probe_name": name,
                    "pressure_pa": pressure + 100.0 * index,
                }
            )

    _write(tmp_path / f"{stem}_valve_history.csv", valve_rows)
    _write(tmp_path / f"{stem}_interface_flux_history.csv", flux_rows)
    _write(tmp_path / f"{stem}_probe_history.csv", probe_rows)

    generated = plot_internal_valve_operation_results(tmp_path, stem)
    assert len(generated) == 4
    assert all((tmp_path / name).is_file() for name in generated)
