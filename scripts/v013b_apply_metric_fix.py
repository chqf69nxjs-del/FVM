"""Temporary source patch for V-013B observation-metric review findings.

This script changes only comparison normalization, tests, and figure presentation.
It does not alter the production solver, numerical flux, or boundary implementation.
Remove it after the corrected observation evidence is captured.
"""
from __future__ import annotations

from pathlib import Path


def replace_if_needed(
    path: Path,
    *,
    marker: str,
    old: str,
    new: str,
) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected exactly one replacement target, found {count}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    runner = Path("src/liquid_gas_transient/cases/v013_rigid_wall_observation.py")
    replace_if_needed(
        runner,
        marker="field_error_normalization_policy = {",
        old='''    field_rows: list[dict[str, Any]] = []
    analytical_rows: list[dict[str, Any]] = []
    field_metrics: list[dict[str, Any]] = []

    for time_index, (time_value, sample) in enumerate(
''',
        new='''    field_rows: list[dict[str, Any]] = []
    analytical_rows: list[dict[str, Any]] = []
    field_metrics: list[dict[str, Any]] = []
    field_error_normalization_policy = {
        "pressure_perturbation_pa": "analytical_pressure_perturbation_pa",
        "velocity_m_s": "analytical_pressure_perturbation_pa / (rho0 * c0)",
        "a_plus_pa": "analytical_pressure_perturbation_pa",
        "a_minus_pa": "analytical_pressure_perturbation_pa",
    }

    for time_index, (time_value, sample) in enumerate(
''',
    )
    replace_if_needed(
        runner,
        marker='"normalization_policy": dict(field_error_normalization_policy)',
        old='''            "expected_center_x_m": float(sample["expected_center_x_m"]),
            "fvm": {},
            "moc": {},
        }
        characteristic_normalizer = np.asarray(
            analytical_fields["pressure_perturbation_pa"],
            dtype=float,
        )
        for implementation, fields in (("fvm", fvm_fields), ("moc", moc_fields)):
            for key in keys:
                normalizer = (
                    characteristic_normalizer
                    if key in {"a_plus_pa", "a_minus_pa"}
                    else analytical_fields[key]
                )
''',
        new='''            "expected_center_x_m": float(sample["expected_center_x_m"]),
            "normalization_policy": dict(field_error_normalization_policy),
            "fvm": {},
            "moc": {},
        }
        pressure_normalizer = np.asarray(
            analytical_fields["pressure_perturbation_pa"],
            dtype=float,
        )
        velocity_normalizer = pressure_normalizer / (rho0 * c0)
        for implementation, fields in (("fvm", fvm_fields), ("moc", moc_fields)):
            for key in keys:
                if key == "velocity_m_s":
                    normalizer = velocity_normalizer
                elif key in {"a_plus_pa", "a_minus_pa"}:
                    normalizer = pressure_normalizer
                else:
                    normalizer = analytical_fields[key]
''',
    )
    replace_if_needed(
        runner,
        marker='"field_error_normalization_policy": field_error_normalization_policy',
        old='''        "case_role": "rigid_wall_reflection",
        "field_metrics": field_metrics,
''',
        new='''        "case_role": "rigid_wall_reflection",
        "field_error_normalization_policy": field_error_normalization_policy,
        "field_metrics": field_metrics,
''',
    )

    tests = Path("tests/test_v013_rigid_wall_observation.py")
    replace_if_needed(
        tests,
        marker="import math\n",
        old="import inspect\nimport json\n",
        new="import inspect\nimport json\nimport math\n",
    )
    replace_if_needed(
        tests,
        marker="expected_velocity_policy = (",
        old='''    assert comparison["formal_fvm_regression_band_applied"] is False
    assert len(comparison["field_metrics"]) == 7
    assert len(comparison["probe_reflection_metrics"]) == 3
    for probe in comparison["probe_reflection_metrics"]:
''',
        new='''    assert comparison["formal_fvm_regression_band_applied"] is False
    assert len(comparison["field_metrics"]) == 7
    assert len(comparison["probe_reflection_metrics"]) == 3
    expected_velocity_policy = (
        "analytical_pressure_perturbation_pa / (rho0 * c0)"
    )
    assert comparison["field_error_normalization_policy"]["velocity_m_s"] == (
        expected_velocity_policy
    )
    wall_contact = next(
        sample
        for sample in comparison["field_metrics"]
        if sample["phase"] == "wall_contact"
    )
    for sample in comparison["field_metrics"]:
        assert sample["normalization_policy"]["velocity_m_s"] == (
            expected_velocity_policy
        )
        for implementation in ("fvm", "moc"):
            velocity_metrics = sample[implementation]["velocity_m_s"]
            for metric_name in (
                "l1_relative",
                "l2_relative",
                "linf_relative",
                "linf_absolute",
            ):
                assert math.isfinite(float(velocity_metrics[metric_name]))
    assert wall_contact["fvm"]["velocity_m_s"]["l2_relative"] < 1.0e6
    assert wall_contact["moc"]["velocity_m_s"]["l2_relative"] < 1.0e6
    for probe in comparison["probe_reflection_metrics"]:
''',
    )

    plotter = Path("src/liquid_gas_transient/plot_v013_rigid_wall_results.py")
    replace_if_needed(
        plotter,
        marker='abs(float(wall["max_abs_wall_velocity_m_s"])) / velocity_scale',
        old='''        floor = np.finfo(float).tiny
        velocity_residuals: list[float] = []
        pressure_errors: list[float] = []
        for row in run_data:
            fvm = row["fvm"]
            wall = fvm["boundary_metrics"]
            velocity_scale = amplitude / (
                float(fvm["rho0_kg_m3"]) * float(fvm["c0_m_s"])
            )
            velocity_residuals.append(
                max(
                    abs(float(wall["max_abs_wall_velocity_m_s"]))
                    / velocity_scale,
                    floor,
                )
            )
            pressure_errors.append(
                max(
                    abs(float(wall["wall_pressure_amplification_ratio"]) - 2.0),
                    floor,
                )
            )
''',
        new='''        velocity_residuals: list[float] = []
        pressure_errors: list[float] = []
        for row in run_data:
            fvm = row["fvm"]
            wall = fvm["boundary_metrics"]
            velocity_scale = amplitude / (
                float(fvm["rho0_kg_m3"]) * float(fvm["c0_m_s"])
            )
            velocity_residuals.append(
                abs(float(wall["max_abs_wall_velocity_m_s"])) / velocity_scale
            )
            pressure_errors.append(
                abs(float(wall["wall_pressure_amplification_ratio"]) - 2.0)
            )
''',
    )
    replace_if_needed(
        plotter,
        marker='ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))',
        old='''        ax.set_yscale("log")
        ax.set_title("V-013B rigid-wall condition residuals")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("normalized residual [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend(fontsize=8)
''',
        new='''        ax.axhline(0.0, linewidth=0.8)
        ax.set_ylim(bottom=0.0)
        ax.set_title("V-013B rigid-wall condition residuals")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("normalized residual [-]")
        ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
