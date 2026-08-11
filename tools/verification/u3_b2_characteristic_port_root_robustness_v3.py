from __future__ import annotations

import numpy as np

import u3_b2_characteristic_port_root_robustness_v2 as robustness_v2


robustness = robustness_v2.robustness
_original_complete_root_row = robustness._complete_root_row
_original_stability_summary = robustness._stability_summary


ENERGY_CONSISTENCY_ROUNDOFF_FACTOR = 128.0


def _complete_root_row_v3(**kwargs):
    """Relate energy closure to the retained mass-root residual.

    At an A1 root both ports use the same stagnation enthalpy, so

        E_pipe - E_B1 = h0 * (m_pipe - m_B1)

    up to floating-point roundoff.  A finite bisection residual therefore
    produces a finite energy-rate residual and is not an independent energy
    model defect.  This wrapper records and tests that identity explicitly.
    """

    row = _original_complete_root_row(**kwargs)

    pipe_mass_rate = float(row["pipe_mass_rate_kg_s"])
    pipe_energy_rate = float(row["pipe_energy_rate_W"])
    b1_energy_rate = float(row["b1_energy_rate_W"])
    mass_residual = float(row["root_mass_residual_kg_s"])
    energy_residual = float(row["energy_port_residual_W"])

    if pipe_mass_rate <= 0.0:
        raise AssertionError("A1 robustness root must have positive mass rate")

    h0 = pipe_energy_rate / pipe_mass_rate
    expected_from_mass_residual = h0 * mass_residual
    consistency_residual = energy_residual - expected_from_mass_residual
    roundoff_allowed = (
        ENERGY_CONSISTENCY_ROUNDOFF_FACTOR
        * np.finfo(float).eps
        * max(
            abs(pipe_energy_rate),
            abs(b1_energy_rate),
            abs(expected_from_mass_residual),
            1.0,
        )
    )
    allowed_from_root_mass = (
        abs(h0) * robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        + roundoff_allowed
    )

    row.update(
        {
            "pipe_stagnation_enthalpy_J_kg": h0,
            "energy_expected_from_mass_residual_W": (
                expected_from_mass_residual
            ),
            "energy_mass_consistency_residual_W": consistency_residual,
            "energy_consistency_roundoff_allowed_W": roundoff_allowed,
            "energy_allowed_from_root_mass_W": allowed_from_root_mass,
            "energy_mass_consistency_passed": bool(
                abs(consistency_residual) <= roundoff_allowed
            ),
            "energy_port_closure_passed": bool(
                abs(energy_residual) <= allowed_from_root_mass
                and abs(consistency_residual) <= roundoff_allowed
            ),
        }
    )
    return row


def _stability_summary_v3(rows):
    summaries = _original_stability_summary(rows)

    for summary in summaries:
        group = [
            row for row in rows if row["case_id"] == summary["case_id"]
        ]
        summary["energy_port_closure_definition"] = (
            "E_pipe-E_B1 = h0*(m_pipe-m_B1) within scale-based "
            "floating-point roundoff; absolute energy residual is bounded "
            "by h0 times the fixed mass-root tolerance"
        )
        summary["all_energy_mass_consistency_residuals_pass"] = all(
            bool(row["energy_mass_consistency_passed"]) for row in group
        )
        summary["all_energy_ports_close"] = all(
            bool(row["energy_port_closure_passed"]) for row in group
        )
        summary["maximum_absolute_energy_mass_consistency_residual_W"] = max(
            abs(float(row["energy_mass_consistency_residual_W"]))
            for row in group
        )
        summary["maximum_absolute_energy_port_residual_W"] = max(
            abs(float(row["energy_port_residual_W"])) for row in group
        )
        summary["minimum_energy_allowed_from_root_mass_W"] = min(
            float(row["energy_allowed_from_root_mass_W"]) for row in group
        )

        summary["stability_passed"] = bool(
            summary["pressure_spread_pa"]
            <= robustness.PRESSURE_STABILITY_ABSOLUTE_PA
            and summary["velocity_relative_spread"]
            <= robustness.VELOCITY_STABILITY_RELATIVE
            and summary["mass_rate_relative_spread"]
            <= robustness.MASS_RATE_STABILITY_RELATIVE
            and summary["mach_spread"]
            <= robustness.MACH_STABILITY_ABSOLUTE
            and summary["all_roots_subsonic"]
            and summary["all_root_mass_residuals_pass"]
            and summary["all_local_slopes_negative"]
            and summary["all_energy_ports_close"]
            and summary["all_energy_mass_consistency_residuals_pass"]
            and summary["all_momentum_ledgers_close"]
        )

    # The V1 scalar energy threshold is intentionally not used by V3.  The
    # summary emitted by the retained main routine will therefore mark it null;
    # the row-wise, result-independent derived criteria above are authoritative.
    robustness.ENERGY_PORT_RESIDUAL_ABSOLUTE_W = None
    return summaries


robustness._complete_root_row = _complete_root_row_v3
robustness._stability_summary = _stability_summary_v3


if __name__ == "__main__":
    robustness.main()
