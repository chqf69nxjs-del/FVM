from __future__ import annotations

import numpy as np

import u3_b2_characteristic_port_root_robustness_v3 as robustness_v3


robustness = robustness_v3.robustness
_original_complete_root_row = robustness_v3._original_complete_root_row
_original_stability_summary = robustness_v3._original_stability_summary


# Locked B2 Contract acceptance tolerance.  This is not a new or relaxed
# diagnostic tolerance.
STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG = 1.0e-5
ENERGY_CONSISTENCY_ROUNDOFF_FACTOR = 128.0


def _complete_root_row_v4(**kwargs):
    """Close the energy ledger using the locked h0 round-trip tolerance.

    The pipe port and B1 port use stagnation enthalpies reconstructed through
    different but already accepted CoolProp paths.  The locked B2 Contract
    allows an absolute stagnation-enthalpy round-trip residual of 1e-5 J/kg.
    Therefore

        E_pipe - E_B1
        = h0_pipe * (m_pipe - m_B1)
          + m_B1 * (h0_pipe - h0_B1)

    and both terms must be bounded by the pre-existing mass-root and h0
    round-trip tolerances, plus scale-based floating-point roundoff.
    """

    row = _original_complete_root_row(**kwargs)

    pipe_mass_rate = float(row["pipe_mass_rate_kg_s"])
    b1_mass_rate = float(row["b1_mass_rate_kg_s"])
    pipe_energy_rate = float(row["pipe_energy_rate_W"])
    b1_energy_rate = float(row["b1_energy_rate_W"])
    mass_residual = float(row["root_mass_residual_kg_s"])
    energy_residual = float(row["energy_port_residual_W"])

    if pipe_mass_rate <= 0.0 or b1_mass_rate <= 0.0:
        raise AssertionError("A1 robustness root must have positive mass rates")

    h0_pipe = pipe_energy_rate / pipe_mass_rate
    h0_b1 = b1_energy_rate / b1_mass_rate
    h0_round_trip_residual = h0_pipe - h0_b1

    expected_from_mass_residual = h0_pipe * mass_residual
    energy_mass_consistency_residual = (
        energy_residual - expected_from_mass_residual
    )

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
    h0_round_trip_energy_allowed = (
        abs(b1_mass_rate)
        * STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
    )
    consistency_allowed = h0_round_trip_energy_allowed + roundoff_allowed
    total_energy_allowed = (
        abs(h0_pipe) * robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        + h0_round_trip_energy_allowed
        + roundoff_allowed
    )

    row.update(
        {
            "pipe_stagnation_enthalpy_J_kg": h0_pipe,
            "b1_stagnation_enthalpy_from_transfer_J_kg": h0_b1,
            "stagnation_enthalpy_round_trip_residual_J_kg": (
                h0_round_trip_residual
            ),
            "locked_stagnation_enthalpy_round_trip_absolute_J_kg": (
                STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
            "energy_expected_from_mass_residual_W": (
                expected_from_mass_residual
            ),
            "energy_mass_consistency_residual_W": (
                energy_mass_consistency_residual
            ),
            "energy_consistency_roundoff_allowed_W": roundoff_allowed,
            "energy_h0_round_trip_allowed_W": (
                h0_round_trip_energy_allowed
            ),
            "energy_mass_consistency_allowed_W": consistency_allowed,
            "energy_allowed_from_locked_root_and_h0_tolerances_W": (
                total_energy_allowed
            ),
            "stagnation_enthalpy_round_trip_passed": bool(
                abs(h0_round_trip_residual)
                <= STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
            "energy_mass_consistency_passed": bool(
                abs(energy_mass_consistency_residual)
                <= consistency_allowed
            ),
            "energy_port_closure_passed": bool(
                abs(energy_residual) <= total_energy_allowed
                and abs(energy_mass_consistency_residual)
                <= consistency_allowed
                and abs(h0_round_trip_residual)
                <= STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
        }
    )
    return row


def _stability_summary_v4(rows):
    summaries = _original_stability_summary(rows)

    for summary in summaries:
        group = [
            row for row in rows if row["case_id"] == summary["case_id"]
        ]
        summary["energy_port_closure_definition"] = (
            "E_pipe-E_B1 is bounded by h0_pipe times the fixed mass-root "
            "tolerance plus m_B1 times the locked B2 stagnation-enthalpy "
            "round-trip tolerance, with scale-based floating-point roundoff"
        )
        summary["locked_stagnation_enthalpy_round_trip_absolute_J_kg"] = (
            STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
        )
        summary["all_stagnation_enthalpy_round_trips_pass"] = all(
            bool(row["stagnation_enthalpy_round_trip_passed"])
            for row in group
        )
        summary["all_energy_mass_consistency_residuals_pass"] = all(
            bool(row["energy_mass_consistency_passed"]) for row in group
        )
        summary["all_energy_ports_close"] = all(
            bool(row["energy_port_closure_passed"]) for row in group
        )
        summary["maximum_absolute_stagnation_enthalpy_round_trip_residual_J_kg"] = max(
            abs(float(row["stagnation_enthalpy_round_trip_residual_J_kg"]))
            for row in group
        )
        summary["maximum_absolute_energy_mass_consistency_residual_W"] = max(
            abs(float(row["energy_mass_consistency_residual_W"]))
            for row in group
        )
        summary["maximum_absolute_energy_port_residual_W"] = max(
            abs(float(row["energy_port_residual_W"])) for row in group
        )
        summary["minimum_energy_allowed_from_locked_root_and_h0_tolerances_W"] = min(
            float(
                row[
                    "energy_allowed_from_locked_root_and_h0_tolerances_W"
                ]
            )
            for row in group
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
            and summary["all_stagnation_enthalpy_round_trips_pass"]
            and summary["all_energy_ports_close"]
            and summary["all_energy_mass_consistency_residuals_pass"]
            and summary["all_momentum_ledgers_close"]
        )

    # V4 uses only pre-existing mass-root and locked B2 h0 round-trip
    # tolerances.  The unused V1 scalar energy threshold is emitted as null.
    robustness.ENERGY_PORT_RESIDUAL_ABSOLUTE_W = None
    return summaries


robustness._complete_root_row = _complete_root_row_v4
robustness._stability_summary = _stability_summary_v4


if __name__ == "__main__":
    robustness.main()
