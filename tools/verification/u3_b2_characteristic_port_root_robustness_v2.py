from __future__ import annotations

import numpy as np

import u3_b2_characteristic_port_root_robustness as robustness


def _choked_connected_subsonic_scan_v2(
    *,
    contract,
    b1_contract,
):
    """Correct the adjacent-pair iteration used by the retained V1 script.

    The original diagnostic used ``zip(..., strict=True)`` on sequences of
    lengths N and N-1 while counting adjacent sign changes.  That is a Python
    iteration-contract error, not a model error.  This wrapper preserves every
    fixed physical and numerical choice and changes only that adjacent-pair
    iteration.
    """

    case_id = "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT"
    evaluate, static, _, _ = robustness._build_evaluator(
        contract=contract,
        b1_contract=b1_contract,
        case_id=case_id,
        quadrature_order=32,
    )
    pressures = np.linspace(
        float(static.pressure_pa),
        robustness.CHOKED_SUBSONIC_LOWER_PRESSURE_PA,
        robustness.CHOKED_SUBSONIC_SCAN_NODES,
    )
    rows = [evaluate(float(pressure)) for pressure in pressures]
    if not all(row.get("evaluation_succeeded") for row in rows):
        raise AssertionError("choked connected-subsonic scan contains a failed node")

    residuals = [float(row["residual_kg_s"]) for row in rows]
    machs = [float(row["mach"]) for row in rows]
    monotone = all(
        residuals[index + 1] >= residuals[index]
        for index in range(len(residuals) - 1)
    )
    sign_changes = sum(
        1
        for first, second in zip(residuals, residuals[1:])
        if robustness._sign(first) == 0
        or robustness._sign(second) == 0
        or robustness._sign(first) != robustness._sign(second)
    )
    summary = {
        "case_id": case_id,
        "quadrature_order": 32,
        "scan_nodes": robustness.CHOKED_SUBSONIC_SCAN_NODES,
        "upper_pressure_pa": float(static.pressure_pa),
        "lower_pressure_pa": robustness.CHOKED_SUBSONIC_LOWER_PRESSURE_PA,
        "all_nodes_admissible": True,
        "all_nodes_subsonic": all(0.0 <= mach < 1.0 for mach in machs),
        "maximum_mach": max(machs),
        "residual_monotone_non_decreasing_as_pressure_drops": monotone,
        "sign_change_count": sign_changes,
        "unique_root_branch_passed": bool(
            monotone
            and sign_changes == 1
            and all(0.0 <= mach < 1.0 for mach in machs)
        ),
    }
    return rows, summary


robustness._choked_connected_subsonic_scan = (
    _choked_connected_subsonic_scan_v2
)


if __name__ == "__main__":
    robustness.main()
