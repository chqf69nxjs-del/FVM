from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.plot_boundary_reflection_results import (
    generate_boundary_reflection_plots,
    plotting_available,
)


def _write_artifacts(output_dir: Path, stem: str = "synthetic_boundary_reflection") -> None:
    metrics = {
        "case_name": stem,
        "initial_pressure_pa": 8.0e6,
        "boundary_kind": "rigid_wall",
        "property_backend_design_status": "not_approved_for_design_use",
        "probes": [
            {
                "probe_name": "x_over_L_0.75",
                "incident_window_start_s": 0.08,
                "incident_window_end_s": 0.16,
                "reflected_window_start_s": 0.26,
                "reflected_window_end_s": 0.34,
            },
            {
                "probe_name": "x_over_L_0.9",
                "incident_window_start_s": 0.13,
                "incident_window_end_s": 0.21,
                "reflected_window_start_s": 0.21,
                "reflected_window_end_s": 0.29,
            },
        ],
    }
    (output_dir / f"{stem}_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )

    probe_fields = [
        "time_s",
        "probe_name",
        "pressure_pa",
        "A_plus_pa",
        "A_minus_pa",
    ]
    probe_rows = []
    for probe_name, scale in (("x_over_L_0.75", 1.0), ("x_over_L_0.9", 0.8)):
        for time_s, a_plus, a_minus in (
            (0.0, 0.0, 0.0),
            (0.1, 1000.0 * scale, 0.0),
            (0.2, 0.0, 0.0),
            (0.3, 0.0, 900.0 * scale),
            (0.4, 0.0, 0.0),
        ):
            probe_rows.append(
                {
                    "time_s": time_s,
                    "probe_name": probe_name,
                    "pressure_pa": 8.0e6 + a_plus + a_minus,
                    "A_plus_pa": a_plus,
                    "A_minus_pa": a_minus,
                }
            )
    with (output_dir / f"{stem}_probe_history.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=probe_fields)
        writer.writeheader()
        writer.writerows(probe_rows)

    boundary_fields = [
        "side",
        "flux_evaluation_time_s",
        "boundary_face_pressure_pa",
        "boundary_face_velocity_m_s",
    ]
    boundary_rows = []
    for time_s, delta_p, velocity in (
        (0.0, 0.0, 0.0),
        (0.1, 200.0, 0.0),
        (0.2, 1500.0, 0.0),
        (0.3, 300.0, 0.0),
        (0.4, 0.0, 0.0),
    ):
        boundary_rows.extend(
            [
                {
                    "side": "left",
                    "flux_evaluation_time_s": time_s,
                    "boundary_face_pressure_pa": 8.0e6,
                    "boundary_face_velocity_m_s": 0.0,
                },
                {
                    "side": "right",
                    "flux_evaluation_time_s": time_s,
                    "boundary_face_pressure_pa": 8.0e6 + delta_p,
                    "boundary_face_velocity_m_s": velocity,
                },
            ]
        )
    with (output_dir / f"{stem}_boundary_history.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=boundary_fields)
        writer.writeheader()
        writer.writerows(boundary_rows)


def test_plotting_available_returns_bool() -> None:
    assert isinstance(plotting_available(), bool)


def test_generate_boundary_reflection_plots_from_existing_artifacts(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    stem = "synthetic_boundary_reflection"
    _write_artifacts(tmp_path, stem)

    generated = generate_boundary_reflection_plots(tmp_path, stem)

    expected = {
        tmp_path / f"{stem}_probe_pressure_history.png",
        tmp_path / f"{stem}_characteristic_history.png",
        tmp_path / f"{stem}_boundary_face_history.png",
    }
    assert set(generated) == expected
    assert all(path.is_file() and path.stat().st_size > 0 for path in expected)


def test_generate_boundary_reflection_plots_auto_detects_unique_case(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    stem = "synthetic_boundary_reflection"
    _write_artifacts(tmp_path, stem)

    generated = generate_boundary_reflection_plots(tmp_path)

    assert len(generated) == 3
    assert all(path.name.startswith(stem) for path in generated)


def test_generate_boundary_reflection_plots_requires_unambiguous_case(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    _write_artifacts(tmp_path, "case_a")
    _write_artifacts(tmp_path, "case_b")

    with pytest.raises(ValueError, match="case_name is required"):
        generate_boundary_reflection_plots(tmp_path)
