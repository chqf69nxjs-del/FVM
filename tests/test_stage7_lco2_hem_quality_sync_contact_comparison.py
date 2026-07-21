from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from liquid_gas_transient.hem_quality_sync_contact_comparison import (
    HEMQualitySyncContactComparisonConfig,
    run_hem_quality_sync_contact_comparison,
    write_hem_quality_sync_contact_comparison_artifacts,
    write_hem_quality_sync_contact_comparison_plots,
)

pytestmark = pytest.mark.coolprop_installed


@pytest.fixture(scope="module")
def fixed_result():
    pytest.importorskip("CoolProp")
    return run_hem_quality_sync_contact_comparison()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pressure_pa", 0.0),
        ("activated_pressure_offset_pa", 0.0),
        ("activated_pressure_offset_pa", 2.00e6),
        ("left_quality", 0.0),
        ("right_quality", 1.0),
        ("length_m", -1.0),
        ("diameter_m", 0.0),
        ("n_cells", 3),
        ("n_cells", 5),
        ("cfl", 0.0),
        ("n_steps", 0),
        ("projection_activation_tolerance", -1.0),
        ("quality_sync_tolerance", -1.0),
        ("budget_relative_tolerance", np.inf),
        ("equal_pressure_span_tolerance_pa", -1.0),
        ("minimum_delta_q_contrast_ratio", 1.0),
    ],
)
def test_contact_comparison_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMQualitySyncContactComparisonConfig(**{field: value})


def test_contact_comparison_config_rejects_equal_qualities():
    with pytest.raises(ValueError):
        HEMQualitySyncContactComparisonConfig(
            left_quality=0.5,
            right_quality=0.5,
        )


def test_equal_pressure_contact_transports_without_projection(fixed_result):
    summary = fixed_result.no_op.summary
    cfg = fixed_result.config

    assert summary["completed_steps"] == cfg.n_steps
    assert summary["case_kind"] == "equal_pressure_quality_contact_no_op"
    assert summary["projection_ever_applied"] is False
    assert summary["projection_total_cell_updates"] == 0
    assert summary["max_abs_delta_q"] <= cfg.projection_activation_tolerance
    assert summary["quality_no_op_tolerance_satisfied"] is True
    assert summary["all_projection_invariants_satisfied"] is True
    assert summary["all_projection_states_open_two_phase"] is True
    assert summary["all_sound_speeds_finite_positive"] is True

    assert summary["contact_transport_exercised"] is True
    assert summary["transport_changed_cell_count"] >= 2
    assert summary["maximum_abs_conservative_change"] > 0.0
    assert summary["quality_max_jump_reduced"] is True
    assert summary["mixed_quality_cell_count"] >= 2
    assert summary["equal_pressure_span_tolerance_satisfied"] is True
    assert summary["pressure_span_max_pa"] <= cfg.equal_pressure_span_tolerance_pa

    assert summary["property_backend_name"] == "coolprop_co2"
    assert summary["property_backend_design_status"] == "not_approved_for_design_use"
    assert summary["coolprop_version"]
    assert summary["output_version"]
    assert summary["budget_tolerance_satisfied"] is True
    assert summary["phase_vapor_source_max_abs_kg"] == 0.0
    assert summary["phase_energy_delta_max_abs_j"] == 0.0
    assert summary["production_default_changed"] is False
    assert summary["production_hem_activation_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False
    assert summary["numeric_accuracy_band_approved"] is False

    assert len(fixed_result.no_op.history) == cfg.n_steps
    assert all(
        row["projection_cell_count"] == 0.0
        for row in fixed_result.no_op.history
    )
    assert all(
        row["max_abs_delta_q"] <= cfg.projection_activation_tolerance
        for row in fixed_result.no_op.history
    )
    assert all(
        row["phase_vapor_mass_source_cumulative_kg"] == 0.0
        for row in fixed_result.no_op.history
    )
    assert np.all(
        fixed_result.no_op.final_projection["phase_class"]
        == "liquid_vapor_two_phase"
    )
    assert not np.any(fixed_result.no_op.final_projection["projection_applied"])
    np.testing.assert_allclose(
        fixed_result.no_op.final_projection["q_after"],
        fixed_result.no_op.final_projection["q_equilibrium"],
        rtol=0.0,
        atol=cfg.projection_activation_tolerance,
    )


def test_pressure_offset_case_provides_activated_contrast(fixed_result):
    comparison = fixed_result.summary
    no_op = fixed_result.no_op.summary
    activated = fixed_result.activated.summary
    cfg = fixed_result.config

    assert no_op["projection_total_cell_updates"] == 0
    assert activated["projection_ever_applied"] is True
    assert activated["projection_total_cell_updates"] >= 1
    assert activated["max_abs_delta_q"] > 0.0
    assert activated["budget_tolerance_satisfied"] is True
    assert activated["all_projection_states_open_two_phase"] is True

    assert comparison["property_backend_name"] == "coolprop_co2"
    assert comparison["property_backend_design_status"] == "not_approved_for_design_use"
    assert comparison["coolprop_version"]
    assert comparison["projection_activity_contrast_satisfied"] is True
    assert comparison["delta_q_contrast_satisfied"] is True
    assert comparison["vapor_source_contrast_satisfied"] is True
    assert comparison["comparison_acceptance_satisfied"] is True
    assert (
        comparison["activated_projection_total_cell_updates"]
        > comparison["no_op_projection_total_cell_updates"]
    )
    assert (
        comparison["activated_to_no_op_delta_q_ratio"]
        >= cfg.minimum_delta_q_contrast_ratio
    )
    assert (
        comparison["activated_phase_vapor_source_abs_kg"]
        > comparison["no_op_phase_vapor_source_max_abs_kg"]
    )


def test_both_contact_comparison_budgets_close(fixed_result):
    tolerance = fixed_result.config.budget_relative_tolerance

    for case in (fixed_result.no_op, fixed_result.activated):
        summary = case.summary
        assert summary["mass_budget_max_relative_residual"] <= tolerance
        assert summary["momentum_budget_max_relative_residual"] <= tolerance
        assert summary["energy_budget_max_relative_residual"] <= tolerance
        assert summary["phase_vapor_budget_max_relative_residual"] <= tolerance
        assert summary["phase_energy_delta_max_abs_j"] == 0.0


def test_contact_comparison_artifacts_and_plots_are_traceable(
    tmp_path,
    fixed_result,
):
    files = write_hem_quality_sync_contact_comparison_artifacts(
        tmp_path,
        fixed_result,
    )
    files.update(
        write_hem_quality_sync_contact_comparison_plots(
            tmp_path,
            fixed_result,
        )
    )

    assert set(files) == {
        "json",
        "history_csv",
        "profile_csv",
        "markdown",
        "npz",
        "quality_profiles_png",
        "projection_activity_png",
        "budget_history_png",
    }
    assert all(
        path.is_file() and path.stat().st_size > 0
        for path in files.values()
    )

    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert (
        payload["schema_version"]
        == "stage7_lco2_hem_quality_sync_contact_comparison_v1"
    )
    assert payload["scope"] == "verification_only"
    assert payload["property_backend_name"] == "coolprop_co2"
    assert payload["property_backend_design_status"] == "not_approved_for_design_use"
    assert payload["coolprop_version"]
    assert payload["model_name"]
    assert payload["output_version"]
    assert payload["comparison_acceptance_satisfied"] is True
    assert payload["no_op"]["summary"]["property_backend_name"] == "coolprop_co2"
    assert payload["activated"]["summary"]["property_backend_name"] == "coolprop_co2"
    assert payload["no_op"]["summary"]["projection_ever_applied"] is False
    assert payload["activated"]["summary"]["projection_ever_applied"] is True
    assert len(payload["no_op"]["history"]) == fixed_result.config.n_steps
    assert len(payload["activated"]["history"]) == fixed_result.config.n_steps

    with files["history_csv"].open(newline="", encoding="utf-8") as handle:
        history_rows = list(csv.DictReader(handle))
    with files["profile_csv"].open(newline="", encoding="utf-8") as handle:
        profile_rows = list(csv.DictReader(handle))
    assert len(history_rows) == fixed_result.config.n_steps
    assert len(profile_rows) == fixed_result.config.n_cells
    assert all(row["property_backend_name"] == "coolprop_co2" for row in history_rows)
    assert all(
        row["property_backend_design_status"] == "not_approved_for_design_use"
        for row in profile_rows
    )
    assert all(
        float(row["no_op_projection_cell_count"]) == 0.0
        for row in history_rows
    )
    assert any(
        float(row["activated_projection_cell_count"]) > 0.0
        for row in history_rows
    )

    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION" in markdown
    assert "property_backend_name: coolprop_co2" in markdown
    assert "property_backend_design_status: not_approved_for_design_use" in markdown
    assert "comparison_acceptance_satisfied: True" in markdown

    archive = np.load(files["npz"])
    assert archive["no_op_initial_U"].shape == (fixed_result.config.n_cells, 4)
    assert archive["no_op_final_U"].shape == (fixed_result.config.n_cells, 4)
    assert archive["activated_final_U"].shape == (fixed_result.config.n_cells, 4)
    assert archive["no_op_delta_q"].shape == (fixed_result.config.n_cells,)
    assert str(archive["property_backend_name"]) == "coolprop_co2"
    assert str(archive["property_backend_design_status"]) == "not_approved_for_design_use"
