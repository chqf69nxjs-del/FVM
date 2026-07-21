from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from liquid_gas_transient.hem_nonuniform_quality_sync import (
    HEMNonuniformQualitySyncConfig,
    run_nonuniform_hem_quality_sync,
    write_nonuniform_quality_sync_artifacts,
    write_nonuniform_quality_sync_plots,
)

pytestmark = pytest.mark.coolprop_installed


@pytest.fixture(scope="module")
def fixed_result():
    pytest.importorskip("CoolProp")
    return run_nonuniform_hem_quality_sync()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("left_pressure_pa", 0.0),
        ("right_pressure_pa", np.nan),
        ("left_quality", 0.0),
        ("right_quality", 1.0),
        ("length_m", -1.0),
        ("diameter_m", 0.0),
        ("n_cells", 3),
        ("n_cells", 5),
        ("cfl", 0.0),
        ("n_steps", 0),
        ("quality_sync_tolerance", -1.0),
        ("budget_relative_tolerance", np.inf),
    ],
)
def test_nonuniform_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMNonuniformQualitySyncConfig(**{field: value})


def test_weak_pressure_offset_case_activates_projection_and_stays_two_phase(
    fixed_result,
):
    summary = fixed_result.summary
    cfg = fixed_result.config

    assert summary["completed_steps"] == cfg.n_steps
    assert summary["projection_ever_applied"] is True
    assert summary["projection_total_cell_updates"] >= 1
    assert summary["max_abs_delta_q"] > 0.0
    assert summary["all_projection_invariants_satisfied"] is True
    assert summary["all_projection_states_open_two_phase"] is True
    assert summary["all_sound_speeds_finite_positive"] is True
    assert summary["quality_sync_tolerance_satisfied"] is True
    assert summary["budget_tolerance_satisfied"] is True
    assert summary["maximum_post_projection_quality_mismatch"] <= cfg.quality_sync_tolerance
    assert summary["cfl_max"] == pytest.approx(cfg.cfl, rel=1.0e-12, abs=1.0e-12)
    assert summary["phase_energy_delta_max_abs_j"] == 0.0
    assert summary["production_default_changed"] is False
    assert summary["production_hem_activation_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False
    assert summary["numeric_accuracy_band_approved"] is False

    assert len(fixed_result.history) == cfg.n_steps
    assert all(row["projection_cell_count"] >= 1.0 for row in fixed_result.history)
    assert all(row["sound_speed_min_m_s"] > 0.0 for row in fixed_result.history)
    assert all(row["quality_min"] > 0.0 for row in fixed_result.history)
    assert all(row["quality_max"] < 1.0 for row in fixed_result.history)
    assert np.all(
        fixed_result.final_projection["phase_class"]
        == "liquid_vapor_two_phase"
    )
    np.testing.assert_allclose(
        fixed_result.final_projection["q_after"],
        fixed_result.final_projection["q_equilibrium"],
        rtol=0.0,
        atol=cfg.quality_sync_tolerance,
    )


def test_nonuniform_case_conservative_budgets_close(fixed_result):
    summary = fixed_result.summary
    tolerance = fixed_result.config.budget_relative_tolerance

    assert summary["mass_budget_max_relative_residual"] <= tolerance
    assert summary["momentum_budget_max_relative_residual"] <= tolerance
    assert summary["energy_budget_max_relative_residual"] <= tolerance
    assert summary["phase_vapor_budget_max_relative_residual"] <= tolerance
    assert summary["phase_energy_delta_max_abs_j"] == 0.0

    assert all(
        row["phase_energy_delta_cumulative_j"] == 0.0
        for row in fixed_result.history
    )
    assert any(
        abs(row["phase_vapor_mass_source_cumulative_kg"]) > 0.0
        for row in fixed_result.history
    )


def test_nonuniform_case_artifacts_and_human_review_plots_are_traceable(
    tmp_path,
    fixed_result,
):
    files = write_nonuniform_quality_sync_artifacts(tmp_path, fixed_result)
    files.update(write_nonuniform_quality_sync_plots(tmp_path, fixed_result))

    assert set(files) == {
        "json",
        "history_csv",
        "profile_csv",
        "markdown",
        "npz",
        "quality_snapshot_png",
        "state_profiles_png",
        "history_png",
    }
    assert all(path.is_file() and path.stat().st_size > 0 for path in files.values())

    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "stage7_lco2_hem_nonuniform_quality_sync_v1"
    assert payload["scope"] == "verification_only"
    assert payload["projection_ever_applied"] is True
    assert payload["all_projection_states_open_two_phase"] is True
    assert payload["production_hem_activation_approved"] is False
    assert len(payload["history"]) == fixed_result.config.n_steps
    assert len(payload["x_m"]) == fixed_result.config.n_cells

    with files["history_csv"].open(newline="", encoding="utf-8") as handle:
        history_rows = list(csv.DictReader(handle))
    with files["profile_csv"].open(newline="", encoding="utf-8") as handle:
        profile_rows = list(csv.DictReader(handle))
    assert len(history_rows) == fixed_result.config.n_steps
    assert len(profile_rows) == fixed_result.config.n_cells
    assert set(row["phase_class"] for row in profile_rows) == {
        "liquid_vapor_two_phase"
    }

    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION" in markdown
    assert "projection_ever_applied: True" in markdown

    archive = np.load(files["npz"])
    assert archive["initial_U"].shape == (fixed_result.config.n_cells, 4)
    assert archive["final_U"].shape == (fixed_result.config.n_cells, 4)
    assert archive["projection_delta_q"].shape == (fixed_result.config.n_cells,)
