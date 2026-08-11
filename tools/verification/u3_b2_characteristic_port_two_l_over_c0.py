from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
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
from u3_b2_characteristic_port_dynamic_short_metrics import build_step_row, inventory
from u3_b2_characteristic_port_dynamic_short_model import (
    CONNECTED_SCAN_NODE_COUNT,
    DynamicDiagnosticStop,
    ROOT_QUADRATURE_ORDER,
)


robustness = robustness_v4.robustness

CASE_ID = "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE"
HORIZON_MULTIPLIER = 2.0
MAX_ACCEPTED_STEPS = 10000
PROBE_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


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


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _probe_indices(n_cells: int) -> list[int]:
    return sorted(
        {
            min(n_cells - 1, max(0, int(round(fraction * (n_cells - 1)))))
            for fraction in PROBE_FRACTIONS
        }
    )


def _run_case(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case = diagnostic._case(contract, CASE_ID)
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
    initial_sound_speed = float(initial_static.sound_speed_m_s)
    if not np.isfinite(initial_sound_speed) or initial_sound_speed <= 0.0:
        raise DynamicDiagnosticStop(
            f"initial sound speed is not positive and finite: {initial_sound_speed}"
        )
    one_way_time_s = float(pipe.length_m / initial_sound_speed)
    target_time_s = float(HORIZON_MULTIPLIER * one_way_time_s)

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
            case_id=CASE_ID,
            provider=provider,
        ),
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    hook = solver.right_external_face_flux_override
    if not isinstance(hook, A1DynamicShortHook):
        raise AssertionError("A1 evolving-cell hook was not installed")

    initial = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    cumulative_expected_delta = np.zeros(4, dtype=float)
    rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    probes = _probe_indices(grid.n_cells)

    requested_step = 0
    while float(solver.t) < target_time_s:
        requested_step += 1
        if requested_step > MAX_ACCEPTED_STEPS:
            stop_reason = (
                f"DynamicDiagnosticStop: exceeded fail-closed operational step cap "
                f"{MAX_ACCEPTED_STEPS} before reaching 2L/c0"
            )
            break

        accepted_dt_for_stop: float | None = None
        time_before_for_stop = float(solver.t)
        try:
            before = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            computed_dt = float(solver.compute_dt())
            dt_limits = dict(hook.last_dt_limits)
            if hook.root_context is None:
                raise AssertionError("dynamic root was not prepared by compute_dt")
            root_context = hook.root_context
            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)

            remaining_time = float(target_time_s - solver.t)
            candidate_dt = min(computed_dt, remaining_time)
            if not np.isfinite(candidate_dt) or candidate_dt <= 0.0:
                raise DynamicDiagnosticStop(
                    f"non-positive final-horizon candidate dt: {candidate_dt}"
                )

            accepted_dt = float(solver.step(candidate_dt))
            accepted_dt_for_stop = accepted_dt
            if not np.isfinite(accepted_dt) or accepted_dt <= 0.0:
                raise DynamicDiagnosticStop(
                    f"accepted dt is not positive and finite: {accepted_dt}"
                )
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
            primitive_after = solver.primitive()
            post_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
            row = build_step_row(
                case_id=CASE_ID,
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
                post_reconstruction=post_reconstruction,
                primitive_after=primitive_after,
                tolerances=contract["acceptance_tolerances"],
            )
            row.update(
                {
                    "initial_sound_speed_m_s": initial_sound_speed,
                    "one_way_acoustic_time_s": one_way_time_s,
                    "target_two_l_over_c0_time_s": target_time_s,
                    "horizon_fraction_before": float(
                        root_context["solver_time_s"] / target_time_s
                    ),
                    "horizon_fraction_after": float(solver.t / target_time_s),
                    "reached_one_way_l_over_c0": bool(solver.t >= one_way_time_s),
                    "reached_two_way_two_l_over_c0": bool(solver.t >= target_time_s),
                }
            )
            for index in probes:
                row[f"probe_cell_{index}_x_m"] = float((index + 0.5) * grid.dx)
                row[f"probe_cell_{index}_pressure_pa"] = float(primitive_after.p[index])
                row[f"probe_cell_{index}_velocity_m_s"] = float(primitive_after.u[index])
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
                        "case_id": CASE_ID,
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

    complete_rows = [
        row for row in rows if row.get("accepted_step") is True and "root_mach" in row
    ]
    horizon_reached = bool(
        stop_reason is None
        and complete_rows
        and float(solver.t) >= target_time_s
        and all(row.get("step_passed") is True for row in complete_rows)
    )
    probe_summary: dict[str, Any] = {}
    for index in probes:
        pressure_key = f"probe_cell_{index}_pressure_pa"
        velocity_key = f"probe_cell_{index}_velocity_m_s"
        pressures = [float(row[pressure_key]) for row in complete_rows]
        velocities = [float(row[velocity_key]) for row in complete_rows]
        probe_summary[f"cell_{index}"] = {
            "x_m": float((index + 0.5) * grid.dx),
            "minimum_pressure_pa": min(pressures) if pressures else None,
            "maximum_pressure_pa": max(pressures) if pressures else None,
            "minimum_velocity_m_s": min(velocities) if velocities else None,
            "maximum_velocity_m_s": max(velocities) if velocities else None,
        }

    summary = {
        "case_id": CASE_ID,
        "state_id": state_id,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "pipe_length_m": float(pipe.length_m),
        "initial_sound_speed_m_s": initial_sound_speed,
        "one_way_acoustic_time_s": one_way_time_s,
        "target_two_l_over_c0_time_s": target_time_s,
        "final_solver_time_s": float(solver.t),
        "horizon_fraction_reached": float(solver.t / target_time_s),
        "accepted_steps_completed": len(complete_rows),
        "maximum_accepted_steps_operational_cap": MAX_ACCEPTED_STEPS,
        "stop_reason": stop_reason,
        "two_l_over_c0_horizon_case_passed": horizon_reached,
        "b1_outcome_counts": dict(
            Counter(str(row["b1_formal_outcome"]) for row in complete_rows)
        ),
        "maximum_root_mach": _maximum(complete_rows, "root_mach"),
        "minimum_root_velocity_m_s": _minimum(complete_rows, "root_velocity_m_s"),
        "minimum_outlet_velocity_after_step_m_s": _minimum(
            complete_rows, "outlet_velocity_after_step_m_s"
        ),
        "maximum_halving_count": (
            max(int(row["halving_count"]) for row in complete_rows)
            if complete_rows
            else None
        ),
        "maximum_absolute_cumulative_mass_residual_kg": _max_abs(
            complete_rows, "cumulative_mass_residual_kg"
        ),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": _max_abs(
            complete_rows, "cumulative_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_cumulative_energy_residual_J": _max_abs(
            complete_rows, "cumulative_energy_residual_J"
        ),
        "maximum_absolute_root_mass_residual_kg_s": _max_abs(
            complete_rows, "root_mass_residual_kg_s"
        ),
        "maximum_absolute_restriction_reaction_ledger_residual_N": _max_abs(
            complete_rows, "restriction_reaction_ledger_residual_N"
        ),
        "maximum_absolute_energy_mass_consistency_residual_W": _max_abs(
            complete_rows, "energy_mass_consistency_residual_W"
        ),
        "maximum_absolute_energy_port_residual_W": _max_abs(
            complete_rows, "energy_port_residual_W"
        ),
        "maximum_absolute_stagnation_enthalpy_round_trip_residual_J_kg": _max_abs(
            complete_rows, "stagnation_enthalpy_round_trip_residual_J_kg"
        ),
        "all_connected_scans_monotone": bool(
            complete_rows
            and all(row["connected_scan_residual_monotone"] for row in complete_rows)
        ),
        "all_connected_scans_have_one_sign_change": bool(
            complete_rows
            and all(
                int(row["connected_scan_sign_change_count"]) == 1
                for row in complete_rows
            )
        ),
        "all_roots_subsonic": bool(
            complete_rows and all(0.0 <= float(row["root_mach"]) < 1.0 for row in complete_rows)
        ),
        "all_outlet_phases_passed": bool(
            complete_rows and all(row["outlet_phase_passed"] for row in complete_rows)
        ),
        "all_rho_xv_exact_zero": bool(
            complete_rows and all(row["rho_xv_exact_zero"] for row in complete_rows)
        ),
        "any_reverse_velocity_detected": bool(
            any(row["reverse_velocity_detected"] for row in complete_rows)
        ),
        "any_reverse_flow_guard_triggered": bool(
            any(row["reverse_flow_guard_triggered"] for row in complete_rows)
        ),
        "probe_observation": probe_summary,
        "acoustic_timing_validation_performed": False,
        "acoustic_probe_series_purpose": (
            "observation_only_for_follow-on_direct_reflected_acoustic_validation"
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

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    rows, case_summary = _run_case(contract=contract, b1_contract=b1_contract)
    gate_passed = bool(case_summary["two_l_over_c0_horizon_case_passed"])

    summary = {
        "schema_version": "stage7_u3_b2_characteristic_port_two_l_over_c0_v1",
        "scope": "model_review_only_two_l_over_c0_no_contract_or_production_change",
        "source_git_sha": args.source_git_sha,
        "fixed_method": {
            "case": CASE_ID,
            "horizon_definition": "2 * pipe_length_m / initial_sound_speed_m_s",
            "horizon_multiplier": HORIZON_MULTIPLIER,
            "cells": int(contract["geometry"]["baseline_cells"]),
            "cfl": float(contract["geometry"]["baseline_cfl"]),
            "root_quadrature_order": ROOT_QUADRATURE_ORDER,
            "connected_scan_node_count": CONNECTED_SCAN_NODE_COUNT,
            "root_bisection_iterations": robustness.BISECTION_ITERATIONS,
            "root_mass_residual_absolute_kg_s": (
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
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
            "new_physics_tolerance_introduced": False,
            "final_step_is_clipped_to_target_horizon": True,
            "probe_fractions": list(PROBE_FRACTIONS),
        },
        "case_summary": case_summary,
        "two_l_over_c0_horizon_gate_passed": gate_passed,
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
    _write_csv(output / "horizon_steps.csv", rows)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 B2-10A full 2L/c0 horizon diagnostic\n\n"
        "MODEL_REVIEW_ONLY. The A1 characteristic-compatible pipe-side port is "
        "recomputed from the evolving B2-10A outlet cell until the nominal "
        "two-way acoustic horizon `2 * L / c0`, where `c0` is the initial "
        "single-phase sound speed. Retained root, conservation, phase, reverse-"
        "flow, energy-decomposition, and restriction-reaction checks remain "
        "active at every accepted step. No new physics tolerance is introduced.\n\n"
        "The five pressure/velocity probe series are observation-only evidence "
        "for the later direct/reflected acoustic validation; this diagnostic "
        "does not claim acoustic timing validation, finite-pipe verification, "
        "benchmark acceptance, Physical Validation, design use, or production "
        "activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    manifest_names = ("summary.json", "horizon_steps.csv", "report.md")
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in manifest_names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not gate_passed:
        raise SystemExit("A1 B2-10A full 2L/c0 horizon diagnostic did not pass")


if __name__ == "__main__":
    main()
