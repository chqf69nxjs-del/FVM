from __future__ import annotations

import csv
from pathlib import Path

import pytest

from liquid_gas_transient.plot_boundary_reflection_fluxes import (
    generate_boundary_flux_budget_plot,
    plotting_available,
)


def _write_boundary_history(
    output_dir: Path,
    stem: str = "synthetic_boundary_reflection",
) -> None:
    fields = [
        "side",
        "flux_evaluation_time_s",
        "dt_s",
        "numerical_mass_flow_rate_kg_s",
        "numerical_energy_flow_rate_w",
    ]
    rows: list[dict[str, object]] = []
    for time_s, mass_rate, energy_rate in (
        (0.0, 0.0, 0.0),
        (0.1, 2.0, 100.0),
        (0.2, -1.0, -40.0),
        (0.3, 0.5, 20.0),
    ):
        rows.extend(
            [
                {
                    "side": "left",
                    "flux_evaluation_time_s": time_s,
                    "dt_s": 0.1,
                    "numerical_mass_flow_rate_kg_s": 0.0,
                    "numerical_energy_flow_rate_w": 0.0,
                },
                {
                    "side": "right",
                    "flux_evaluation_time_s": time_s,
                    "dt_s": 0.1,
                    "numerical_mass_flow_rate_kg_s": mass_rate,
                    "numerical_energy_flow_rate_w": energy_rate,
                },
            ]
        )
    with (output_dir / f"{stem}_boundary_history.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_flux_plotting_available_returns_bool() -> None:
    assert isinstance(plotting_available(), bool)


def test_generate_boundary_flux_budget_plot(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    stem = "synthetic_boundary_reflection"
    _write_boundary_history(tmp_path, stem)

    path = generate_boundary_flux_budget_plot(tmp_path, stem)

    assert path == tmp_path / f"{stem}_boundary_flux_budget_history.png"
    assert path.is_file()
    assert path.stat().st_size > 0


def test_generate_boundary_flux_budget_plot_auto_detects_unique_case(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    stem = "synthetic_boundary_reflection"
    _write_boundary_history(tmp_path, stem)

    path = generate_boundary_flux_budget_plot(tmp_path)

    assert path.name == f"{stem}_boundary_flux_budget_history.png"


def test_generate_boundary_flux_budget_plot_requires_unambiguous_case(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    _write_boundary_history(tmp_path, "case_a")
    _write_boundary_history(tmp_path, "case_b")

    with pytest.raises(ValueError, match="case_name is required"):
        generate_boundary_flux_budget_plot(tmp_path)


def test_generate_boundary_flux_budget_plot_requires_right_boundary_rows(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    stem = "left_only"
    path = tmp_path / f"{stem}_boundary_history.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "side",
                "flux_evaluation_time_s",
                "dt_s",
                "numerical_mass_flow_rate_kg_s",
                "numerical_energy_flow_rate_w",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "side": "left",
                "flux_evaluation_time_s": 0.0,
                "dt_s": 0.1,
                "numerical_mass_flow_rate_kg_s": 0.0,
                "numerical_energy_flow_rate_w": 0.0,
            }
        )

    with pytest.raises(ValueError, match="no right-boundary rows"):
        generate_boundary_flux_budget_plot(tmp_path, stem)
