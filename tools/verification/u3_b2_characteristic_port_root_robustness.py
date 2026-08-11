from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic


CASE_BRACKETS_PA: dict[str, tuple[float, float]] = {
    "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE": (
        4_950_000.0,
        4_950_781.249999695,
    ),
    "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT": (
        850_000.0,
        853_125.0,
    ),
    "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT": (
        732_812.5,
        746_875.0,
    ),
}

QUADRATURE_ORDERS = (16, 32, 64)
BISECTION_ITERATIONS = 28
SLOPE_DELTA_P_PA = 1.0
CHOKED_SUBSONIC_LOWER_PRESSURE_PA = 339_062.5
CHOKED_SUBSONIC_SCAN_NODES = 33

PRESSURE_STABILITY_ABSOLUTE_PA = 25.0
VELOCITY_STABILITY_RELATIVE = 1.0e-4
MASS_RATE_STABILITY_RELATIVE = 1.0e-4
MACH_STABILITY_ABSOLUTE = 1.0e-4
ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S = 1.0e-8
ENERGY_PORT_RESIDUAL_ABSOLUTE_W = 1.0e-6
MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N = 1.0e-12


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sign(value: float) -> int:
    if value < 0.0:
        return -1
    if value > 0.0:
        return 1
    return 0


def _relative_spread(values: list[float]) -> float:
    scale = max(max(abs(value) for value in values), 1.0e-300)
    return (max(values) - min(values)) / scale


def _build_evaluator(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    case_id: str,
    quadrature_order: int,
) -> tuple[Callable[[float], dict[str, Any]], Any, Any, float]:
    case = diagnostic._case(contract, case_id)
    state_id = str(case["state_id"])
    provider = diagnostic.CoolPropB2StateProvider()
    _, static = diagnostic.build_uniform_initial_state(
        contract,
        provider,
        state_id,
        1,
    )
    area_m2 = float(contract["geometry"]["pipe_area_m2"])
    adapter = diagnostic.adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=provider,
    )

    diagnostic.QUADRATURE_ORDER = int(quadrature_order)
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))

    def evaluate(pressure_pa: float) -> dict[str, Any]:
        return diagnostic.evaluate_pressure(
            pressure_pa=float(pressure_pa),
            static=static,
            isentrope=isentrope,
            adapter=adapter,
            area_m2=area_m2,
            case_id=case_id,
            state_id=state_id,
        )

    return evaluate, static, adapter, area_m2


def _bisection_root(
    *,
    lower_pressure_pa: float,
    upper_pressure_pa: float,
    evaluate: Callable[[float], dict[str, Any]],
) -> dict[str, Any]:
    lower = float(min(lower_pressure_pa, upper_pressure_pa))
    upper = float(max(lower_pressure_pa, upper_pressure_pa))
    row_lower = evaluate(lower)
    row_upper = evaluate(upper)
    if not row_lower.get("evaluation_succeeded"):
        raise RuntimeError(
            f"inadmissible lower root bracket: {row_lower.get('formal_outcome')} "
            f"{row_lower.get('formal_message')}"
        )
    if not row_upper.get("evaluation_succeeded"):
        raise RuntimeError(
            f"inadmissible upper root bracket: {row_upper.get('formal_outcome')} "
            f"{row_upper.get('formal_message')}"
        )

    residual_lower = float(row_lower["residual_kg_s"])
    residual_upper = float(row_upper["residual_kg_s"])
    if _sign(residual_lower) == 0:
        return row_lower
    if _sign(residual_upper) == 0:
        return row_upper
    if _sign(residual_lower) == _sign(residual_upper):
        raise RuntimeError(
            "fixed root bracket does not change sign: "
            f"lower={residual_lower}, upper={residual_upper}"
        )

    best = row_lower if abs(residual_lower) <= abs(residual_upper) else row_upper
    a_p, a_r = lower, residual_lower
    b_p, b_r = upper, residual_upper
    for _ in range(BISECTION_ITERATIONS):
        mid_p = 0.5 * (a_p + b_p)
        mid = evaluate(mid_p)
        if not mid.get("evaluation_succeeded"):
            raise RuntimeError(
                f"inadmissible midpoint p={mid_p}: "
                f"{mid.get('formal_outcome')} {mid.get('formal_message')}"
            )
        mid_r = float(mid["residual_kg_s"])
        if abs(mid_r) < abs(float(best["residual_kg_s"])):
            best = mid
        if _sign(mid_r) == 0:
            return mid
        if _sign(mid_r) == _sign(a_r):
            a_p, a_r = mid_p, mid_r
        else:
            b_p, b_r = mid_p, mid_r
    return best


def _complete_root_row(
    *,
    root: dict[str, Any],
    evaluate: Callable[[float], dict[str, Any]],
    adapter: Any,
    area_m2: float,
    quadrature_order: int,
) -> dict[str, Any]:
    pressure = float(root["pressure_pa"])
    lower = evaluate(pressure - SLOPE_DELTA_P_PA)
    upper = evaluate(pressure + SLOPE_DELTA_P_PA)
    if not lower.get("evaluation_succeeded") or not upper.get("evaluation_succeeded"):
        raise RuntimeError("slope evaluation around root is inadmissible")
    slope = (
        float(upper["residual_kg_s"]) - float(lower["residual_kg_s"])
    ) / (2.0 * SLOPE_DELTA_P_PA)

    rho = float(root["density_kg_m3"])
    velocity = float(root["velocity_m_s"])
    internal_energy = float(root["internal_energy_J_kg"])
    conserved = np.asarray(
        [
            rho,
            rho * velocity,
            rho * (internal_energy + 0.5 * velocity * velocity),
            0.0,
        ],
        dtype=float,
    )
    evaluation = adapter.evaluate(conserved, area_m2)
    if not evaluation.succeeded or evaluation.face is None:
        raise RuntimeError(
            f"root face reevaluation failed: {evaluation.formal_outcome}"
        )
    face = evaluation.face

    pipe_energy_rate = float(root["pipe_mass_rate_kg_s"]) * float(root["h0_J_kg"])
    b1_energy_rate = float(face.energy_transfer_outward_W)
    energy_residual = pipe_energy_rate - b1_energy_rate

    pipe_momentum_port = float(root["pipe_momentum_port_N"])
    downstream_port = float(root["downstream_stream_pressure_port_N"])
    reaction = float(root["restriction_reaction_on_fluid_N"])
    momentum_ledger_residual = downstream_port - pipe_momentum_port - reaction

    return {
        "case_id": root["case_id"],
        "state_id": root["state_id"],
        "quadrature_order": int(quadrature_order),
        "pressure_pa": pressure,
        "stagnation_pressure_pa": float(root["stagnation_pressure_pa"]),
        "velocity_m_s": velocity,
        "mach": float(root["mach"]),
        "density_kg_m3": rho,
        "phase": root["phase"],
        "formal_outcome": root["formal_outcome"],
        "pipe_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "b1_mass_rate_kg_s": float(root["b1_mass_rate_kg_s"]),
        "root_mass_residual_kg_s": float(root["residual_kg_s"]),
        "local_residual_slope_kg_s_Pa": slope,
        "pipe_energy_rate_W": pipe_energy_rate,
        "b1_energy_rate_W": b1_energy_rate,
        "energy_port_residual_W": energy_residual,
        "pipe_momentum_port_N": pipe_momentum_port,
        "downstream_stream_pressure_port_N": downstream_port,
        "restriction_reaction_on_fluid_N": reaction,
        "momentum_ledger_residual_N": momentum_ledger_residual,
        "b1_effective_velocity_m_s": float(root["b1_effective_velocity_m_s"]),
        "b1_discharge_state_pressure_pa": float(
            root["b1_discharge_state_pressure_pa"]
        ),
        "b1_critical_pressure_pa": root["b1_critical_pressure_pa"],
    }


def _stability_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for case_id in CASE_BRACKETS_PA:
        group = [row for row in rows if row["case_id"] == case_id]
        if len(group) != len(QUADRATURE_ORDERS):
            raise AssertionError(f"unexpected robustness row count for {case_id}")
        pressures = [float(row["pressure_pa"]) for row in group]
        velocities = [float(row["velocity_m_s"]) for row in group]
        mass_rates = [float(row["pipe_mass_rate_kg_s"]) for row in group]
        machs = [float(row["mach"]) for row in group]
        summary = {
            "case_id": case_id,
            "quadrature_orders": list(QUADRATURE_ORDERS),
            "pressure_spread_pa": max(pressures) - min(pressures),
            "velocity_relative_spread": _relative_spread(velocities),
            "mass_rate_relative_spread": _relative_spread(mass_rates),
            "mach_spread": max(machs) - min(machs),
            "all_roots_subsonic": all(0.0 <= mach < 1.0 for mach in machs),
            "all_root_mass_residuals_pass": all(
                abs(float(row["root_mass_residual_kg_s"]))
                <= ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
                for row in group
            ),
            "all_local_slopes_negative": all(
                float(row["local_residual_slope_kg_s_Pa"]) < 0.0
                for row in group
            ),
            "all_energy_ports_close": all(
                abs(float(row["energy_port_residual_W"]))
                <= ENERGY_PORT_RESIDUAL_ABSOLUTE_W
                for row in group
            ),
            "all_momentum_ledgers_close": all(
                abs(float(row["momentum_ledger_residual_N"]))
                <= MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
                for row in group
            ),
        }
        summary["stability_passed"] = bool(
            summary["pressure_spread_pa"] <= PRESSURE_STABILITY_ABSOLUTE_PA
            and summary["velocity_relative_spread"]
            <= VELOCITY_STABILITY_RELATIVE
            and summary["mass_rate_relative_spread"]
            <= MASS_RATE_STABILITY_RELATIVE
            and summary["mach_spread"] <= MACH_STABILITY_ABSOLUTE
            and summary["all_roots_subsonic"]
            and summary["all_root_mass_residuals_pass"]
            and summary["all_local_slopes_negative"]
            and summary["all_energy_ports_close"]
            and summary["all_momentum_ledgers_close"]
        )
        summaries.append(summary)
    return summaries


def _choked_connected_subsonic_scan(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_id = "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT"
    evaluate, static, _, _ = _build_evaluator(
        contract=contract,
        b1_contract=b1_contract,
        case_id=case_id,
        quadrature_order=32,
    )
    pressures = np.linspace(
        float(static.pressure_pa),
        CHOKED_SUBSONIC_LOWER_PRESSURE_PA,
        CHOKED_SUBSONIC_SCAN_NODES,
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
        for first, second in zip(residuals, residuals[1:], strict=True)
        if _sign(first) == 0
        or _sign(second) == 0
        or _sign(first) != _sign(second)
    )
    summary = {
        "case_id": case_id,
        "quadrature_order": 32,
        "scan_nodes": CHOKED_SUBSONIC_SCAN_NODES,
        "upper_pressure_pa": float(static.pressure_pa),
        "lower_pressure_pa": CHOKED_SUBSONIC_LOWER_PRESSURE_PA,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = diagnostic.load_contract(args.contract)
    b1_contract = diagnostic.load_b1_contract(args.b1_contract)

    root_rows: list[dict[str, Any]] = []
    for case_id, bracket in CASE_BRACKETS_PA.items():
        for quadrature_order in QUADRATURE_ORDERS:
            evaluate, _, adapter, area_m2 = _build_evaluator(
                contract=contract,
                b1_contract=b1_contract,
                case_id=case_id,
                quadrature_order=quadrature_order,
            )
            root = _bisection_root(
                lower_pressure_pa=bracket[0],
                upper_pressure_pa=bracket[1],
                evaluate=evaluate,
            )
            root_rows.append(
                _complete_root_row(
                    root=root,
                    evaluate=evaluate,
                    adapter=adapter,
                    area_m2=area_m2,
                    quadrature_order=quadrature_order,
                )
            )

    stability = _stability_summary(root_rows)
    choked_scan_rows, choked_scan_summary = _choked_connected_subsonic_scan(
        contract=contract,
        b1_contract=b1_contract,
    )

    summary = {
        "schema_version": "stage7_u3_b2_characteristic_port_root_robustness_v1",
        "scope": "model_review_only_no_contract_or_tolerance_change",
        "source_git_sha": args.source_git_sha,
        "fixed_method": {
            "root_brackets_pa": {
                key: list(value) for key, value in CASE_BRACKETS_PA.items()
            },
            "quadrature_orders": list(QUADRATURE_ORDERS),
            "bisection_iterations": BISECTION_ITERATIONS,
            "slope_delta_p_pa": SLOPE_DELTA_P_PA,
            "choked_connected_subsonic_lower_pressure_pa": (
                CHOKED_SUBSONIC_LOWER_PRESSURE_PA
            ),
            "choked_connected_subsonic_scan_nodes": CHOKED_SUBSONIC_SCAN_NODES,
        },
        "fixed_thresholds": {
            "pressure_stability_absolute_pa": PRESSURE_STABILITY_ABSOLUTE_PA,
            "velocity_stability_relative": VELOCITY_STABILITY_RELATIVE,
            "mass_rate_stability_relative": MASS_RATE_STABILITY_RELATIVE,
            "mach_stability_absolute": MACH_STABILITY_ABSOLUTE,
            "root_mass_residual_absolute_kg_s": (
                ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            "energy_port_residual_absolute_W": ENERGY_PORT_RESIDUAL_ABSOLUTE_W,
            "momentum_ledger_residual_absolute_N": (
                MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
            ),
        },
        "root_rows": root_rows,
        "case_stability": stability,
        "choked_connected_subsonic_scan": choked_scan_summary,
        "root_robustness_gate_passed": bool(
            all(row["stability_passed"] for row in stability)
            and choked_scan_summary["unique_root_branch_passed"]
        ),
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "root_robustness.csv", root_rows)
    _write_csv(output / "choked_connected_subsonic_scan.csv", choked_scan_rows)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 characteristic upstream-port root robustness\n\n"
        "MODEL_REVIEW_ONLY. No Contract, Adapter, solver, tolerance or formal "
        "state is changed.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    manifest_names = (
        "summary.json",
        "root_robustness.csv",
        "choked_connected_subsonic_scan.csv",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n" for name in manifest_names
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["root_robustness_gate_passed"]:
        raise SystemExit("A1 root robustness gate did not pass")


if __name__ == "__main__":
    main()
