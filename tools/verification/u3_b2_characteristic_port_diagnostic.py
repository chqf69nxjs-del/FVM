from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import CoolProp.CoolProp as CP
from CoolProp import AbstractState

from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    adapter_for_case,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
)

BASELINE_CASE_IDS = (
    "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE",
    "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT",
    "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT",
)

SCAN_NODE_COUNT = 65
QUADRATURE_ORDER = 32
BISECTION_ITERATIONS = 48


def _case(contract: dict[str, Any], case_id: str) -> dict[str, Any]:
    for row in contract["benchmark_cases"]:
        if row["case_id"] == case_id:
            return dict(row)
    raise KeyError(case_id)


def _family(contract: dict[str, Any], state_id: str) -> dict[str, Any]:
    for row in contract["fixed_state_families"]:
        if row["state_id"] == state_id:
            return dict(row)
    raise KeyError(state_id)


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


class Isentrope:
    def __init__(self, entropy_J_kg_K: float):
        self.s = float(entropy_J_kg_K)
        self.state = AbstractState("HEOS", "CO2")
        self.nodes, self.weights = np.polynomial.legendre.leggauss(QUADRATURE_ORDER)

    def props(self, pressure_pa: float) -> dict[str, float | str]:
        self.state.update(CP.PSmass_INPUTS, float(pressure_pa), self.s)
        p = float(self.state.p())
        T = float(self.state.T())
        rho = float(self.state.rhomass())
        h = float(self.state.hmass())
        e = float(self.state.umass())
        c = float(self.state.speed_sound())
        phase = str(CP.PhaseSI("P", p, "Smass", self.s, "CO2"))
        if not all(math.isfinite(value) for value in (p, T, rho, h, e, c)):
            raise ValueError("nonfinite isentropic property")
        if rho <= 0.0 or c <= 0.0:
            raise ValueError("nonpositive density or sound speed")
        return {
            "pressure_pa": p,
            "temperature_K": T,
            "density_kg_m3": rho,
            "enthalpy_J_kg": h,
            "internal_energy_J_kg": e,
            "sound_speed_m_s": c,
            "phase": phase,
        }

    def characteristic_velocity(
        self,
        pressure_pa: float,
        *,
        interior_pressure_pa: float,
        interior_velocity_m_s: float,
    ) -> float:
        p = float(pressure_pa)
        p_i = float(interior_pressure_pa)
        if p > p_i:
            raise ValueError("diagnostic only supports p_P <= p_i")
        if p == p_i:
            return float(interior_velocity_m_s)
        midpoint = 0.5 * (p_i + p)
        half = 0.5 * (p_i - p)
        integral = 0.0
        for node, weight in zip(self.nodes, self.weights, strict=True):
            sample_p = midpoint + half * float(node)
            props = self.props(sample_p)
            integral += float(weight) / (
                float(props["density_kg_m3"])
                * float(props["sound_speed_m_s"])
            )
        integral *= half
        return float(interior_velocity_m_s + integral)


def evaluate_pressure(
    *,
    pressure_pa: float,
    static: Any,
    isentrope: Isentrope,
    adapter: Any,
    area_m2: float,
    case_id: str,
    state_id: str,
) -> dict[str, Any]:
    try:
        props = isentrope.props(pressure_pa)
        velocity = isentrope.characteristic_velocity(
            pressure_pa,
            interior_pressure_pa=float(static.pressure_pa),
            interior_velocity_m_s=float(static.velocity_m_s),
        )
        rho = float(props["density_kg_m3"])
        internal_energy = float(props["internal_energy_J_kg"])
        enthalpy = float(props["enthalpy_J_kg"])
        sound_speed = float(props["sound_speed_m_s"])
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
            return {
                "case_id": case_id,
                "state_id": state_id,
                "pressure_pa": float(pressure_pa),
                "evaluation_succeeded": False,
                "formal_outcome": evaluation.formal_outcome,
                "formal_message": evaluation.formal_message,
                "residual_kg_s": None,
            }
        face = evaluation.face
        pipe_mass_rate = rho * velocity * area_m2
        b1_mass_rate = float(face.mass_transfer_outward_kg_s)
        residual = pipe_mass_rate - b1_mass_rate
        h0 = enthalpy + 0.5 * velocity * velocity
        pipe_momentum_port = pipe_mass_rate * velocity + float(pressure_pa) * area_m2
        downstream_port = (
            float(face.advective_momentum_rate_out_N)
            + float(face.discharge_state_pressure_pa) * float(face.open_area_m2)
        )
        return {
            "case_id": case_id,
            "state_id": state_id,
            "pressure_pa": float(pressure_pa),
            "evaluation_succeeded": True,
            "formal_outcome": evaluation.formal_outcome,
            "formal_message": evaluation.formal_message,
            "temperature_K": float(props["temperature_K"]),
            "density_kg_m3": rho,
            "enthalpy_J_kg": enthalpy,
            "internal_energy_J_kg": internal_energy,
            "entropy_J_kg_K": float(static.entropy_J_kg_K),
            "sound_speed_m_s": sound_speed,
            "phase": props["phase"],
            "velocity_m_s": velocity,
            "mach": velocity / sound_speed,
            "h0_J_kg": h0,
            "stagnation_pressure_pa": float(face.stagnation_pressure_pa),
            "stagnation_temperature_K": float(face.stagnation_temperature_K),
            "pipe_mass_rate_kg_s": pipe_mass_rate,
            "b1_mass_rate_kg_s": b1_mass_rate,
            "residual_kg_s": residual,
            "b1_effective_velocity_m_s": float(face.effective_velocity_m_s),
            "b1_discharge_state_pressure_pa": float(
                face.discharge_state_pressure_pa
            ),
            "b1_critical_pressure_pa": (
                None
                if face.critical_pressure_pa is None
                else float(face.critical_pressure_pa)
            ),
            "pipe_momentum_port_N": pipe_momentum_port,
            "downstream_stream_pressure_port_N": downstream_port,
            "restriction_reaction_on_fluid_N": downstream_port - pipe_momentum_port,
            "open_area_m2": float(face.open_area_m2),
        }
    except Exception as exc:
        return {
            "case_id": case_id,
            "state_id": state_id,
            "pressure_pa": float(pressure_pa),
            "evaluation_succeeded": False,
            "formal_outcome": type(exc).__name__,
            "formal_message": str(exc),
            "residual_kg_s": None,
        }


def _sign(value: float) -> int:
    if value < 0.0:
        return -1
    if value > 0.0:
        return 1
    return 0


def find_sign_change_brackets(
    rows: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    brackets: list[tuple[float, float]] = []
    previous: dict[str, Any] | None = None
    for row in rows:
        if not row.get("evaluation_succeeded") or row.get("residual_kg_s") is None:
            continue
        if previous is not None:
            r0 = float(previous["residual_kg_s"])
            r1 = float(row["residual_kg_s"])
            if _sign(r0) == 0:
                brackets.append(
                    (
                        float(previous["pressure_pa"]),
                        float(previous["pressure_pa"]),
                    )
                )
            elif _sign(r1) == 0 or _sign(r0) != _sign(r1):
                brackets.append(
                    (
                        float(previous["pressure_pa"]),
                        float(row["pressure_pa"]),
                    )
                )
        previous = row
    return brackets


def bisect_root(*, p0: float, p1: float, evaluate) -> dict[str, Any]:
    row0 = evaluate(p0)
    row1 = evaluate(p1)
    if not row0.get("evaluation_succeeded") or not row1.get("evaluation_succeeded"):
        raise RuntimeError("root bracket endpoint is not admissible")
    r0 = float(row0["residual_kg_s"])
    r1 = float(row1["residual_kg_s"])
    if r0 == 0.0:
        return row0
    if r1 == 0.0:
        return row1
    if _sign(r0) == _sign(r1):
        raise RuntimeError("root bracket does not change sign")

    a_p, a_r = float(p0), r0
    b_p, b_r = float(p1), r1
    best = row0 if abs(r0) <= abs(r1) else row1
    for _ in range(BISECTION_ITERATIONS):
        mid_p = 0.5 * (a_p + b_p)
        mid = evaluate(mid_p)
        if not mid.get("evaluation_succeeded"):
            raise RuntimeError(
                f"inadmissible state inside root bracket at p={mid_p}: "
                f"{mid.get('formal_outcome')} {mid.get('formal_message')}"
            )
        mid_r = float(mid["residual_kg_s"])
        if abs(mid_r) < abs(float(best["residual_kg_s"])):
            best = mid
        if mid_r == 0.0:
            return mid
        if _sign(mid_r) == _sign(a_r):
            a_p, a_r = mid_p, mid_r
        else:
            b_p, b_r = mid_p, mid_r
    return best


def exact_identity_checks(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    provider: CoolPropB2StateProvider,
    area_m2: float,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for case_id in (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
    ):
        case = _case(contract, case_id)
        conserved, static = build_uniform_initial_state(
            contract,
            provider,
            str(case["state_id"]),
            1,
        )
        adapter = adapter_for_case(
            contract,
            b1_contract,
            case,
            provider=provider,
        )
        evaluation = adapter.evaluate(conserved[0], area_m2)
        if not evaluation.succeeded or evaluation.face is None:
            raise AssertionError(f"{case_id}: {evaluation.formal_outcome}")
        flux = evaluation.face.flux_vector()
        expected = np.asarray(
            [0.0, float(static.pressure_pa), 0.0, 0.0],
            dtype=float,
        )
        results[case_id] = {
            "formal_outcome": evaluation.formal_outcome,
            "flux": [float(value) for value in flux],
            "expected": [float(value) for value in expected],
            "exact_identity": bool(np.array_equal(flux, expected)),
        }
        assert results[case_id]["exact_identity"] is True
    return results


def run_case(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    case_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case = _case(contract, case_id)
    state_id = str(case["state_id"])
    provider = CoolPropB2StateProvider()
    _, static = build_uniform_initial_state(contract, provider, state_id, 1)
    area = float(contract["geometry"]["pipe_area_m2"])
    adapter = adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=provider,
    )
    isentrope = Isentrope(float(static.entropy_J_kg_K))
    back_pressure = float(adapter.back_pressure_pa)
    initial_pressure = float(static.pressure_pa)

    pressures = np.linspace(initial_pressure, back_pressure, SCAN_NODE_COUNT)
    scan_rows = [
        evaluate_pressure(
            pressure_pa=float(pressure),
            static=static,
            isentrope=isentrope,
            adapter=adapter,
            area_m2=area,
            case_id=case_id,
            state_id=state_id,
        )
        for pressure in pressures
    ]
    brackets = find_sign_change_brackets(scan_rows)

    def evaluate(pressure: float) -> dict[str, Any]:
        return evaluate_pressure(
            pressure_pa=float(pressure),
            static=static,
            isentrope=isentrope,
            adapter=adapter,
            area_m2=area,
            case_id=case_id,
            state_id=state_id,
        )

    roots = [
        bisect_root(p0=first, p1=second, evaluate=evaluate)
        for first, second in brackets
    ]
    successful = [row for row in scan_rows if row.get("evaluation_succeeded")]
    residuals = [float(row["residual_kg_s"]) for row in successful]
    monotone = all(
        residuals[index + 1] >= residuals[index]
        for index in range(len(residuals) - 1)
    )
    summary = {
        "case_id": case_id,
        "state_id": state_id,
        "initial_pressure_pa": initial_pressure,
        "back_pressure_pa": back_pressure,
        "scan_node_count": SCAN_NODE_COUNT,
        "quadrature_order": QUADRATURE_ORDER,
        "bisection_iterations": BISECTION_ITERATIONS,
        "successful_scan_nodes": len(successful),
        "failed_scan_nodes": len(scan_rows) - len(successful),
        "fixed_scan_sign_change_count": len(brackets),
        "residual_monotone_non_decreasing_as_pressure_drops": monotone,
        "unique_root_on_fixed_scan": len(roots) == 1,
        "root": roots[0] if len(roots) == 1 else None,
        "all_roots": roots,
        "expected_original_case_outcome": case["expected_outcome"],
        "formal_state_promoted": False,
    }
    return summary, scan_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    provider = CoolPropB2StateProvider()
    identities = exact_identity_checks(
        contract,
        b1_contract,
        provider,
        float(contract["geometry"]["pipe_area_m2"]),
    )

    summaries: list[dict[str, Any]] = []
    all_scan_rows: list[dict[str, Any]] = []
    for case_id in BASELINE_CASE_IDS:
        summary, rows = run_case(contract, b1_contract, case_id)
        summaries.append(summary)
        all_scan_rows.extend(rows)

    payload = {
        "schema_version": "stage7_u3_b2_characteristic_upstream_port_diagnostic_v1",
        "scope": "model_review_only_no_contract_or_tolerance_change",
        "source_git_sha": args.source_git_sha,
        "contract_source": str(args.contract),
        "b1_contract_source": str(args.b1_contract),
        "runtime": {
            "numpy": importlib.metadata.version("numpy"),
            "CoolProp": importlib.metadata.version("CoolProp"),
        },
        "fixed_method": {
            "scan_node_count": SCAN_NODE_COUNT,
            "quadrature_order": QUADRATURE_ORDER,
            "bisection_iterations": BISECTION_ITERATIONS,
            "pressure_scan": "linear from initial static pressure to external back pressure",
            "characteristic_integral": "fixed Gauss-Legendre quadrature on inherited entropy",
        },
        "exact_identities": identities,
        "cases": summaries,
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    (output / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(output / "residual_scan.csv", all_scan_rows)

    root_rows: list[dict[str, Any]] = []
    for case in summaries:
        row: dict[str, Any] = {
            "case_id": case["case_id"],
            "state_id": case["state_id"],
            "fixed_scan_sign_change_count": case["fixed_scan_sign_change_count"],
            "unique_root_on_fixed_scan": case["unique_root_on_fixed_scan"],
            "residual_monotone_non_decreasing_as_pressure_drops": case[
                "residual_monotone_non_decreasing_as_pressure_drops"
            ],
        }
        root = case["root"]
        if root:
            for key in (
                "pressure_pa",
                "temperature_K",
                "density_kg_m3",
                "velocity_m_s",
                "mach",
                "h0_J_kg",
                "stagnation_pressure_pa",
                "pipe_mass_rate_kg_s",
                "b1_mass_rate_kg_s",
                "residual_kg_s",
                "formal_outcome",
                "b1_discharge_state_pressure_pa",
                "b1_critical_pressure_pa",
                "pipe_momentum_port_N",
                "downstream_stream_pressure_port_N",
                "restriction_reaction_on_fluid_N",
            ):
                row[key] = root.get(key)
        root_rows.append(row)
    _write_csv(output / "root_summary.csv", root_rows)

    report_lines = [
        "# U3 B2 characteristic-compatible upstream port diagnostic",
        "",
        "MODEL_REVIEW_ONLY. No Contract, tolerance, Adapter, solver or formal state is changed.",
        "",
        f"source Git SHA: `{args.source_git_sha}`",
        "",
        "## Exact identities",
        "",
        "```json",
        json.dumps(identities, indent=2, sort_keys=True),
        "```",
        "",
        "## Root summaries",
        "",
        "```json",
        json.dumps(summaries, indent=2, sort_keys=True),
        "```",
        "",
        "Formal finite-pipe, Physical Validation, design-use and production flags remain false.",
        "",
    ]
    (output / "report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    manifest_names = [
        "summary.json",
        "residual_scan.csv",
        "root_summary.csv",
        "report.md",
    ]
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n"
            for name in manifest_names
        ),
        encoding="utf-8",
    )

    if not all(case["unique_root_on_fixed_scan"] for case in summaries):
        raise SystemExit(
            "A1 diagnostic did not find exactly one root on the fixed scan for every baseline case"
        )


if __name__ == "__main__":
    main()
