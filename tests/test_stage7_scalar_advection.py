from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.verification_scalar_advection import (
    DEFAULT_COMPARISON_VARIANTS,
    ScalarAdvectionConfig,
    gaussian_profile,
    periodic_signed_distance,
    run_default_gaussian_comparison,
    run_scalar_advection,
    write_comparison_artifacts,
)


@pytest.fixture(scope="module")
def comparison_results():
    return run_default_gaussian_comparison(mesh_cells=(100, 200))


def _lookup(results, n_cells: int, variant_name: str):
    for result in results:
        if result.config.n_cells == n_cells and result.variant_name == variant_name:
            return result
    raise AssertionError(f"missing result for n={n_cells}, variant={variant_name}")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("n_cells", 7),
        ("domain_length", 0.0),
        ("velocity", 0.0),
        ("cfl", 1.1),
        ("t_end", 0.0),
        ("gaussian_center", 1.0),
        ("gaussian_sigma", 0.3),
        ("gaussian_amplitude", 0.0),
        ("n_ghost", 1),
        ("time_integrator", "unknown"),
    ],
)
def test_scalar_advection_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        ScalarAdvectionConfig(**{field: value})


def test_wrapped_gaussian_and_periodic_distance_are_consistent():
    domain_length = 1.0
    points = np.array([0.99, 0.01])
    distance = periodic_signed_distance(points, 0.0, domain_length)
    assert distance == pytest.approx([-0.01, 0.01])

    values = gaussian_profile(
        points,
        center=0.0,
        sigma=0.05,
        amplitude=1.0,
        background=0.0,
        domain_length=domain_length,
    )
    assert values[0] == pytest.approx(values[1])


def test_default_comparison_inventory_is_fixed(comparison_results):
    assert len(comparison_results) == 2 * len(DEFAULT_COMPARISON_VARIANTS)
    assert {result.config.n_cells for result in comparison_results} == {100, 200}
    assert {result.variant_name for result in comparison_results} == {
        variant.name for variant in DEFAULT_COMPARISON_VARIANTS
    }


def test_comparison_paths_conserve_mass_and_create_no_new_extrema(
    comparison_results,
):
    for result in comparison_results:
        metrics = result.metrics
        assert abs(metrics.pulse_mass_relative_error) < 1.0e-12
        assert metrics.overshoot < 1.0e-12
        assert metrics.undershoot < 1.0e-12
        assert metrics.total_variation_ratio <= 1.0 + 1.0e-12
        assert metrics.cfl_actual_max <= result.config.cfl + 1.0e-14


def test_muscl_ssprk2_improves_over_same_time_integrator(comparison_results):
    first_order = _lookup(comparison_results, 200, "first_order_ssprk2")
    for name in (
        "muscl_minmod_ssprk2",
        "muscl_mc_ssprk2",
        "muscl_van_leer_ssprk2",
    ):
        muscl = _lookup(comparison_results, 200, name)
        assert muscl.metrics.peak_retention > first_order.metrics.peak_retention
        assert muscl.metrics.l2_error < 0.25 * first_order.metrics.l2_error
        assert abs(muscl.metrics.width_growth_ratio - 1.0) < abs(
            first_order.metrics.width_growth_ratio - 1.0
        )


def test_mc_and_van_leer_resolve_gaussian_better_than_minmod(
    comparison_results,
):
    minmod = _lookup(comparison_results, 200, "muscl_minmod_ssprk2")
    mc = _lookup(comparison_results, 200, "muscl_mc_ssprk2")
    van_leer = _lookup(comparison_results, 200, "muscl_van_leer_ssprk2")

    assert mc.metrics.peak_retention > minmod.metrics.peak_retention
    assert van_leer.metrics.peak_retention > minmod.metrics.peak_retention
    assert mc.metrics.l2_error < minmod.metrics.l2_error
    assert van_leer.metrics.l2_error < minmod.metrics.l2_error


def test_refinement_improves_every_comparison_variant(comparison_results):
    for variant in DEFAULT_COMPARISON_VARIANTS:
        coarse = _lookup(comparison_results, 100, variant.name)
        fine = _lookup(comparison_results, 200, variant.name)
        assert fine.metrics.peak_retention > coarse.metrics.peak_retention
        assert fine.metrics.l2_error < coarse.metrics.l2_error
        assert abs(fine.metrics.width_growth_ratio - 1.0) < abs(
            coarse.metrics.width_growth_ratio - 1.0
        )


def test_negative_velocity_uses_right_upwind_state():
    first_order = run_scalar_advection(
        ScalarAdvectionConfig(
            n_cells=160,
            velocity=-1.0,
            t_end=1.0,
            gaussian_center=0.75,
            reconstruction_method="first_order",
            time_integrator="forward_euler",
        ),
        variant_name="negative_first_order",
    )
    muscl = run_scalar_advection(
        ScalarAdvectionConfig(
            n_cells=160,
            velocity=-1.0,
            t_end=1.0,
            gaussian_center=0.75,
            reconstruction_method="muscl",
            limiter="mc",
            time_integrator="ssprk2",
        ),
        variant_name="negative_muscl_mc",
    )

    assert abs(first_order.metrics.pulse_mass_relative_error) < 1.0e-12
    assert abs(muscl.metrics.pulse_mass_relative_error) < 1.0e-12
    assert muscl.metrics.l2_error < first_order.metrics.l2_error
    assert abs(muscl.metrics.phase_error_cells) < 0.1


def test_artifact_writer_emits_traceable_unapproved_evidence(tmp_path):
    results = run_default_gaussian_comparison(mesh_cells=(64,))
    paths = write_comparison_artifacts(tmp_path, results)

    assert set(paths) == {"json", "csv", "markdown", "npz"}
    assert all(path.is_file() for path in paths.values())

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "stage7_scalar_advection_comparison_v1"
    assert payload["scope"] == "verification_only"
    assert payload["production_solver_connected"] is False
    assert payload["production_solver_behavior_changed"] is False
    assert payload["production_time_integrator_approved"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert payload["numeric_accuracy_band_approved"] is False
    assert len(payload["results"]) == len(DEFAULT_COMPARISON_VARIANTS)

    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "VERIFICATION ONLY; NOT PRODUCTION ACTIVATION" in markdown
    assert "muscl_mc_ssprk2" in markdown

    with np.load(paths["npz"]) as profiles:
        assert "n64_first_order_euler_x" in profiles
        assert "n64_muscl_mc_ssprk2_final" in profiles
