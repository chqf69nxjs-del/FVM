from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
)
from u3_b2_characteristic_port_dynamic_short_hook import A1DynamicShortHook
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
    summarize_case,
)
from u3_b2_characteristic_port_dynamic_short_model import (
    ACCEPTED_STEPS_PER_CASE,
    CASE_IDS,
    CONNECTED_SCAN_NODE_COUNT,
    DynamicDiagnosticStop,
    ROOT_QUADRATURE_ORDER,
)


robustness = robustness_v4.robustness


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


def _run_case(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    case_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case = diagnostic._case(contract, case_id)
    state_id = str(case["state_id"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = CoolPropB2StateProvider()
    U_initial, initial_static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=U_initial,
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=A1DynamicShortHook(
            contract=contract,
            b1_contract=b1_contract,
            case_id=case_id,
            provider=provider,
        ),
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    hook = solver.right_external_face_flux_override
    if not isinstance(hook, A1DynamicShortHook):
        raise AssertionError("dynamic short hook was not installed")

    initial = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    cumulative_expected_delta = np.zeros(4, dtype=float)
    rows: list[dict[str, Any]] = []
    stop_reason: str | None = None

    for requested_step in range(1, ACCEPTED_STEPS_PER_CASE + 1):
        accepted_dt_for_stop: float | None = None
        time_before_for_stop = float(solver.t)
        try:
            before = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            candidate_dt = float(solver.compute_dt())
            dt_limits = dict(hook.last_dt_limits)
            if hook.root_context is None:
                raise AssertionError("dynamic root was not prepared by compute_dt")
            root_context = hook.root_context
            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)

            accepted_dt = float(solver.step(candidate_dt))
            accepted_dt_for_stop = accepted_dt
            hook.accept_current_root()
            after = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            expected_step_delta = accepted_dt * grid.geometry.area_m2 * (
                left_flux - right_flux
            )
            cumulative_expected_delta += expected_step_delta
            row = build_step_row(
                case_id=case_id,
                state_id=state_id,
                requested_step=requested_step,
                solver=solver,
                hook=hook,
                root_context=root_context,
                dt_limits=dt_limits,
                candidate_dt=candidate_dt,
                accepted_dt=accepted_dt,
                before=before,
                after=after,
                initial=initial,
                expected_step_delta=expected_step_delta,
                cumulative_expected_delta=cumulative_expected_delta,
                left_flux=left_flux,
                right_flux=right_flux,
                post_reconstruction=provider.reconstruct_from_conserved(solver.U[-1]),
                primitive_after=solver.primitive(),
                tolerances=contract["acceptance_tolerances"],
            )
            rows.append(row)
            if not row["step_passed"]:
                raise DynamicDiagnosticStop(
                    f"accepted step {requested_step} failed a retained diagnostic check"
                )
        except Exception as exc:
            stop_reason = f"{type(exc).__name__}: {exc}"
            if rows and rows[-1].get("requested_step") == requested_step:
                rows[-1]["stop_reason"] = stop_reason
                rows[-1]["guard_status"] = "DIAGNOSTIC_STOP"
            else:
                rows.append(
                    {
                        "case_id": case_id,
                        "state_id": state_id,
                        "requested_step": requested_step,
                        "accepted_step": accepted_dt_for_stop is not None,
                        "solver_step_count": solver.step_count,
                        "time_before_s": time_before_for_stop,
                        "time_after_s": float(solver.t),
                        "accepted_dt_s": accepted_dt_for_stop,
                        "step_passed": False,
                        "reverse_flow_guard_triggered": (
                            "reverse" in stop_reason.lower()
                        ),
                        "guard_status": "DIAGNOSTIC_STOP",
                        "stop_reason": stop_reason,
                    }
                )
            break

    return rows, summarize_case(
        case_id=case_id,
        state_id=state_id,
        rows=rows,
        stop_reason=stop_reason,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    all_rows: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []
    prior_stop = False
    for case_id in CASE_IDS:
        state_id = str(diagnostic._case(contract, case_id)["state_id"])
        if prior_stop:
            case_summaries.append(
                {
                    "case_id": case_id,
                    "state_id": state_id,
                    "requested_accepted_steps": ACCEPTED_STEPS_PER_CASE,
                    "accepted_steps_completed": 0,
                    "stop_reason": "NOT_RUN_DUE_PRIOR_DIAGNOSTIC_STOP",
                    "dynamic_short_case_passed": False,
                }
            )
            continue
        rows, case_summary = _run_case(
            contract=contract,
            b1_contract=b1_contract,
            case_id=case_id,
        )
        all_rows.extend(rows)
        case_summaries.append(case_summary)
        prior_stop = not bool(case_summary["dynamic_short_case_passed"])

    gate_passed = bool(
        len(case_summaries) == len(CASE_IDS)
        and all(row["dynamic_short_case_passed"] for row in case_summaries)
    )
    summary = {
        "schema_version": "stage7_u3_b2_characteristic_port_dynamic_short_v2",
        "scope": "model_review_only_dynamic_short_no_contract_or_production_change",
        "source_git_sha": args.source_git_sha,
        "fixed_method": {
            "cases": list(CASE_IDS),
            "accepted_steps_per_case": ACCEPTED_STEPS_PER_CASE,
            "cells": int(contract["geometry"]["baseline_cells"]),
            "cfl": float(contract["geometry"]["baseline_cfl"]),
            "root_quadrature_order": ROOT_QUADRATURE_ORDER,
            "connected_scan_node_count": CONNECTED_SCAN_NODE_COUNT,
            "root_bisection_iterations": robustness.BISECTION_ITERATIONS,
            "root_mass_residual_absolute_kg_s": (
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            "energy_port_closure_definition": (
                "E_pipe-E_B1 is bounded by h0_pipe times the fixed mass-root "
                "tolerance plus m_B1 times the locked B2 stagnation-enthalpy "
                "round-trip tolerance, with scale-based floating-point roundoff"
            ),
            "locked_stagnation_enthalpy_round_trip_absolute_J_kg": (
                robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
            "energy_consistency_roundoff_factor": (
                robustness_v4.ENERGY_CONSISTENCY_ROUNDOFF_FACTOR
            ),
            "energy_port_residual_absolute_W": None,
            "momentum_ledger_residual_absolute_N": (
                robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
            ),
            "inventory_tolerances": {
                key: contract["acceptance_tolerances"][key]
                for key in (
                    "mass_inventory_absolute_kg",
                    "mass_inventory_relative",
                    "momentum_inventory_absolute_kg_m_s",
                    "momentum_inventory_relative",
                    "energy_inventory_absolute_J",
                    "energy_inventory_relative",
                    "vapor_mass_exact_zero_absolute_kg",
                )
            },
        },
        "case_summaries": case_summaries,
        "dynamic_short_multi_step_gate_passed": gate_passed,
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
    _write_csv(output / "dynamic_steps.csv", all_rows)
    _write_csv(output / "case_summary.csv", case_summaries)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 dynamic short multi-step diagnostic\n\n"
        "MODEL_REVIEW_ONLY. The A1 characteristic-compatible pipe-side port is "
        "recomputed from the evolving outlet cell before every accepted step. "
        "This is a four-step-per-case diagnostic, not the locked finite-pipe "
        "benchmark, acoustic horizon, mesh/CFL matrix, Contract revision, "
        "Physical Validation, design approval, or production activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    manifest_names = (
        "summary.json",
        "dynamic_steps.csv",
        "case_summary.csv",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in manifest_names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not gate_passed:
        raise SystemExit("A1 dynamic short multi-step diagnostic did not pass")


if __name__ == "__main__":
    main()
