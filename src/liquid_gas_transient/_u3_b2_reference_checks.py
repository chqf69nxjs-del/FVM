"""Locked aggregate checks for the independent U3 B2 Reference."""
from __future__ import annotations
import math
from typing import Any
from ._u3_b2_reference_types import AcousticArrivalReference, FaceReferenceResult, OneStepReference

def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1.0e-300)
def locked_checks(
    contract: dict[str, Any],
    extension: dict[str, Any],
    results: list[FaceReferenceResult],
    one_step: OneStepReference,
    acoustic_rows: list[AcousticArrivalReference],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {row.case_id: row for row in results}
    expected = {
        row["case_id"]: row["expected_outcome"]
        for row in contract["benchmark_cases"]
    }
    outcome_matches = {
        case_id: by_id[case_id].formal_outcome == target
        for case_id, target in expected.items()
    }

    exact_ids = (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
    )
    exact_zero_passed = all(
        by_id[case_id].mass_transfer_outward_kg_s == 0.0
        and by_id[case_id].advective_momentum_rate_outward_N == 0.0
        and by_id[case_id].energy_transfer_outward_W == 0.0
        and by_id[case_id].F_rho_kg_m2_s == 0.0
        and by_id[case_id].F_rho_E_W_m2 == 0.0
        and by_id[case_id].F_rho_xv_kg_m2_s == 0.0
        and by_id[case_id].F_rho_u_pa
        == by_id[case_id].adjacent_pressure_pa
        for case_id in exact_ids
    )

    reconstruction_errors = []
    for result in results:
        if not result.succeeded:
            continue
        reconstructed = (
            result.advective_momentum_rate_outward_N
            + result.open_static_pressure_force_outward_N
            + result.closed_static_pressure_force_outward_N
        )
        reconstruction_errors.append(
            abs(reconstructed - result.total_momentum_rate_outward_N)
        )
    pressure_decomposition_passed = max(reconstruction_errors, default=0.0) <= float(
        contract["acceptance_tolerances"][
            "pressure_decomposition_reconstruction_absolute_pa"
        ]
    )

    b0 = by_id["B2-04_SMALL_DROP_RECOVERS_B0_FACE_LIMIT"]
    rho = float(b0.adjacent_density_kg_m3 or math.nan)
    h0 = float(b0.stagnation_enthalpy_J_kg or math.nan)
    dp = float(b0.adjacent_pressure_pa or math.nan) - float(
        b0.external_back_pressure_pa or math.nan
    )
    b0_velocity = b0.discharge_coefficient * math.sqrt(2.0 * dp / rho)
    b0_mass = rho * b0.open_area_m2 * b0_velocity
    b0_advective = b0_mass * b0_velocity
    b0_energy = b0_mass * h0
    inherited = extension["inherited_B1_acceptance_tolerances"]
    b0_checks = {
        "mass": relative_error(b0.mass_transfer_outward_kg_s, b0_mass)
        <= float(inherited["B0_limit_mass_flow_relative"]),
        "velocity": relative_error(b0.effective_velocity_m_s, b0_velocity)
        <= float(inherited["B0_limit_effective_velocity_relative"]),
        "advective_momentum": relative_error(
            b0.advective_momentum_rate_outward_N, b0_advective
        )
        <= float(inherited["B0_limit_momentum_transfer_relative"]),
        "energy": relative_error(b0.energy_transfer_outward_W, b0_energy)
        <= float(inherited["B0_limit_energy_transfer_relative"]),
    }

    plateau_a = by_id["B2-07A_BELOW_CRITICAL_PLATEAU_HIGH"]
    plateau_b = by_id["B2-07B_BELOW_CRITICAL_PLATEAU_LOW"]
    plateau_relative = max(
        relative_error(
            plateau_a.mass_transfer_outward_kg_s,
            plateau_b.mass_transfer_outward_kg_s,
        ),
        relative_error(
            plateau_a.advective_momentum_rate_outward_N,
            plateau_b.advective_momentum_rate_outward_N,
        ),
        relative_error(
            plateau_a.energy_transfer_outward_W,
            plateau_b.energy_transfer_outward_W,
        ),
    )
    plateau_passed = plateau_relative <= float(
        contract["acceptance_tolerances"]["below_critical_face_plateau_relative"]
    )

    area_low = by_id["B2-08A_AREA_SCALING_LOW"]
    area_high = by_id["B2-08B_AREA_SCALING_HIGH"]
    area_ratios = {
        "mass": area_high.mass_transfer_outward_kg_s
        / area_low.mass_transfer_outward_kg_s,
        "energy": area_high.energy_transfer_outward_W
        / area_low.energy_transfer_outward_W,
        "advective_momentum": area_high.advective_momentum_rate_outward_N
        / area_low.advective_momentum_rate_outward_N,
    }
    ratio_tolerance = float(
        contract["acceptance_tolerances"]["scaling_ratio_absolute"]
    )
    area_scaling_passed = all(
        abs(value - 2.0) <= ratio_tolerance for value in area_ratios.values()
    )

    cd_low = by_id["B2-08C_CD_SCALING_LOW"]
    cd_high = by_id["B2-08D_CD_SCALING_HIGH"]
    cd_mass_ratio = cd_high.mass_transfer_outward_kg_s / cd_low.mass_transfer_outward_kg_s
    cd_energy_ratio = cd_high.energy_transfer_outward_W / cd_low.energy_transfer_outward_W
    cd_advective_ratio = (
        cd_high.advective_momentum_rate_outward_N
        / cd_low.advective_momentum_rate_outward_N
    )
    cd_pressure_relative = relative_error(
        float(cd_high.critical_pressure_pa or math.nan),
        float(cd_low.critical_pressure_pa or math.nan),
    )
    cd_scaling_passed = (
        abs(cd_mass_ratio - 2.0) <= ratio_tolerance
        and abs(cd_energy_ratio - 2.0) <= ratio_tolerance
        and abs(cd_advective_ratio - 4.0) <= ratio_tolerance
        and cd_pressure_relative
        <= float(inherited["critical_pressure_Cd_independence_relative"])
    )

    one_step_passed = (
        one_step.positivity_passed
        and abs(one_step.mass_inventory_residual_kg)
        <= float(contract["acceptance_tolerances"]["mass_inventory_absolute_kg"])
        and abs(one_step.energy_inventory_residual_J)
        <= float(contract["acceptance_tolerances"]["energy_inventory_absolute_J"])
        and abs(one_step.momentum_inventory_residual_kg_m_s)
        <= float(
            contract["acceptance_tolerances"][
                "momentum_inventory_absolute_kg_m_s"
            ]
        )
        and one_step.vapor_mass_kg == 0.0
    )

    maps = extension["acoustic_event_detection"]["spatial_probe_sampling"][
        "fixed_mesh_probe_map"
    ]
    probe_map_count = sum(len(row["entries"]) for row in maps)
    probe_mapping_passed = probe_map_count == 9 and all(
        float(probe["lambda"]) == 0.5
        for row in maps
        for probe in row["entries"]
    )
    acoustic_passed = (
        len(acoustic_rows) == 9
        and sorted(
            row.probe_x_over_L
            for row in acoustic_rows
            if row.cells == 32
        )
        == [0.25, 0.5, 0.75]
        and [
            row.probe_x_over_L
            for row in sorted(
                (row for row in acoustic_rows if row.cells == 32),
                key=lambda item: item.direct_order_rank,
            )
        ]
        == [0.75, 0.5, 0.25]
        and [
            row.probe_x_over_L
            for row in sorted(
                (row for row in acoustic_rows if row.cells == 32),
                key=lambda item: item.reflected_order_rank,
            )
        ]
        == [0.25, 0.5, 0.75]
    )

    check_rows = [
        {
            "check": "expected_formal_outcomes",
            "value": sum(outcome_matches.values()),
            "target": len(outcome_matches),
            "passed": all(outcome_matches.values()),
        },
        {
            "check": "closed_zero_drop_exact_identities",
            "value": exact_zero_passed,
            "target": True,
            "passed": exact_zero_passed,
        },
        {
            "check": "pressure_decomposition_reconstruction",
            "value": max(reconstruction_errors, default=0.0),
            "target": contract["acceptance_tolerances"][
                "pressure_decomposition_reconstruction_absolute_pa"
            ],
            "passed": pressure_decomposition_passed,
        },
        {
            "check": "B0_small_drop_face_limit",
            "value": b0_checks,
            "target": "inherited B1 measure-specific tolerances",
            "passed": all(b0_checks.values()),
        },
        {
            "check": "below_critical_face_plateau",
            "value": plateau_relative,
            "target": contract["acceptance_tolerances"][
                "below_critical_face_plateau_relative"
            ],
            "passed": plateau_passed,
        },
        {
            "check": "area_scaling",
            "value": area_ratios,
            "target": 2.0,
            "passed": area_scaling_passed,
        },
        {
            "check": "Cd_scaling",
            "value": {
                "mass": cd_mass_ratio,
                "energy": cd_energy_ratio,
                "advective_momentum": cd_advective_ratio,
                "critical_pressure_relative": cd_pressure_relative,
            },
            "target": {
                "mass": 2.0,
                "energy": 2.0,
                "advective_momentum": 4.0,
                "critical_pressure_relative": inherited[
                    "critical_pressure_Cd_independence_relative"
                ],
            },
            "passed": cd_scaling_passed,
        },
        {
            "check": "one_step_inventory_and_positivity",
            "value": {
                "mass_residual": one_step.mass_inventory_residual_kg,
                "energy_residual": one_step.energy_inventory_residual_J,
                "momentum_residual": one_step.momentum_inventory_residual_kg_m_s,
                "vapor_mass": one_step.vapor_mass_kg,
            },
            "target": "locked absolute tolerances and exact zero vapor",
            "passed": one_step_passed,
        },
        {
            "check": "probe_mapping",
            "value": probe_map_count,
            "target": 9,
            "passed": probe_mapping_passed,
        },
        {
            "check": "acoustic_arrival_order",
            "value": len(acoustic_rows),
            "target": 9,
            "passed": acoustic_passed,
        },
    ]
    summary = {
        "all_expected_outcomes_match": all(outcome_matches.values()),
        "outcome_matches": outcome_matches,
        "exact_zero_identities_passed": exact_zero_passed,
        "pressure_decomposition_passed": pressure_decomposition_passed,
        "B0_limit_checks": b0_checks,
        "B0_limit_passed": all(b0_checks.values()),
        "below_critical_plateau_relative": plateau_relative,
        "below_critical_plateau_passed": plateau_passed,
        "area_scaling_ratios": area_ratios,
        "area_scaling_passed": area_scaling_passed,
        "Cd_mass_ratio": cd_mass_ratio,
        "Cd_energy_ratio": cd_energy_ratio,
        "Cd_advective_momentum_ratio": cd_advective_ratio,
        "critical_pressure_Cd_relative_difference": cd_pressure_relative,
        "Cd_scaling_passed": cd_scaling_passed,
        "one_step_reference_passed": one_step_passed,
        "probe_mapping_passed": probe_mapping_passed,
        "acoustic_reference_passed": acoustic_passed,
        "all_locked_checks_passed": all(bool(row["passed"]) for row in check_rows),
    }
    return check_rows, summary
