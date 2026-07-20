from __future__ import annotations

import json
from pathlib import Path

import pytest


BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "verification"
    / "v013_baseline_definition_v1.json"
)


def _load_baseline() -> dict[str, object]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _values(case: dict[str, object], key: str) -> list[float]:
    rows = case["mesh_observations"]
    assert isinstance(rows, list)
    return [float(row[key]) for row in rows]


def test_v013_baseline_definition_preserves_scope_and_sources() -> None:
    baseline = _load_baseline()

    assert baseline["baseline_version"] == "v013_baseline_v1"
    assert baseline["baseline_kind"] == "software_numerical_observation_baseline"
    assert baseline["formalization_status"] == "DRAFT_REVIEW_REQUIRED"
    assert baseline["stage_status"] == "IN_PROGRESS"
    assert baseline["production_solver_behavior_changed"] is False
    assert baseline["physical_validation"] is False
    assert baseline["design_use_acceptance"] is False
    assert baseline["property_backend_design_status"] == "not_approved_for_design_use"
    assert baseline["formal_fvm_regression_band_applied"] is False
    assert baseline["design_accuracy_band_applied"] is False

    sources = baseline["sources"]
    assert isinstance(sources, dict)
    assert set(sources) == {"V-013A", "V-013B", "V-013C"}
    assert sources["V-013A"]["merge_commit"] == (
        "613b21622b22402fbf7b8d77b1d881db7ff5f28e"
    )
    assert sources["V-013B"]["merge_commit"] == (
        "bc874193de6a4c019073b6cf629e99ec5dfa6602"
    )
    assert sources["V-013C"]["merge_commit"] == (
        "f403103c46a1d618ce2f2345c986e29b921b664a"
    )


def test_v013_baseline_common_case_and_case_matrix_are_fixed() -> None:
    baseline = _load_baseline()
    common = baseline["common_case"]
    assert common["fvm_mesh_cells"] == [100, 200, 400]
    assert common["fvm_cfl"] == pytest.approx(0.5)
    assert common["moc_cfl"] == pytest.approx(1.0)
    assert common["pressure_amplitude_pa"] == pytest.approx(100.0)
    assert common["pulse_center_m"] == pytest.approx(65.0)
    assert common["pulse_sigma_m"] == pytest.approx(2.0)
    assert common["time_shift_applied"] is False
    assert common["parameter_tuning_applied"] is False

    cases = baseline["cases"]
    assert set(cases) == {"V-013A", "V-013B", "V-013C"}
    for case in cases.values():
        assert case["state"] == "OBSERVED_MERGED"
        rows = case["mesh_observations"]
        assert [row["n_cells"] for row in rows] == [100, 200, 400]
        assert [row["dx_m"] for row in rows] == pytest.approx([1.0, 0.5, 0.25])


def test_v013_baseline_preserves_signs_and_monotonic_refinement() -> None:
    baseline = _load_baseline()
    cases = baseline["cases"]
    incident = cases["V-013A"]
    rigid = cases["V-013B"]
    fixed = cases["V-013C"]

    assert _values(incident, "final_pressure_peak_ratio") == sorted(
        _values(incident, "final_pressure_peak_ratio")
    )

    rigid_pressure = _values(rigid, "pressure_reflection_coefficient")
    rigid_velocity = _values(rigid, "velocity_reflection_coefficient")
    rigid_peak = _values(rigid, "final_reflected_pressure_peak_ratio")
    rigid_l2 = _values(rigid, "maximum_pressure_l2_relative_difference")
    assert all(value > 0.0 for value in rigid_pressure)
    assert all(value < 0.0 for value in rigid_velocity)
    assert rigid_pressure == sorted(rigid_pressure)
    assert [abs(value) for value in rigid_velocity] == sorted(
        abs(value) for value in rigid_velocity
    )
    assert rigid_peak == sorted(rigid_peak)
    assert rigid_l2 == sorted(rigid_l2, reverse=True)

    fixed_pressure = _values(fixed, "pressure_reflection_coefficient")
    fixed_velocity = _values(fixed, "velocity_reflection_coefficient")
    fixed_residual = _values(fixed, "normalized_fixed_pressure_residual")
    fixed_velocity_ratio = _values(fixed, "boundary_velocity_amplification_ratio")
    fixed_peak = _values(fixed, "final_reflected_pressure_peak_ratio")
    fixed_l2 = _values(fixed, "maximum_pressure_l2_relative_difference")
    assert all(value < 0.0 for value in fixed_pressure)
    assert all(value > 0.0 for value in fixed_velocity)
    assert [abs(value) for value in fixed_pressure] == sorted(
        abs(value) for value in fixed_pressure
    )
    assert fixed_velocity == sorted(fixed_velocity)
    assert fixed_residual == sorted(fixed_residual, reverse=True)
    assert fixed_velocity_ratio == sorted(fixed_velocity_ratio)
    assert fixed_peak == sorted(fixed_peak)
    assert fixed_l2 == sorted(fixed_l2, reverse=True)


def test_v013_baseline_does_not_create_accuracy_or_ci_approval() -> None:
    baseline = _load_baseline()
    ci_light = baseline["ci_light"]

    assert ci_light["status"] == "PROPOSED_NOT_APPROVED"
    assert ci_light["numeric_regression_bands"] is None
    assert ci_light["current_peak_ratios_are_design_accuracy"] is False
    assert "physical_validation" in baseline["prohibited_interpretations"]
    assert "design_use_acceptance" in baseline["prohibited_interpretations"]
    assert "approved_accuracy_or_regression_band" in baseline[
        "prohibited_interpretations"
    ]
