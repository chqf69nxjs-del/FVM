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
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from u3_b2_a1_wave_curve_checkpoint_review import _capture_checkpoint
from u3_b2_a1_wave_curve_model import (
    CASE_ID,
    EXPECTED_ACCEPTED_STEPS,
    _inventory_array,
)
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
)
from u3_b2_characteristic_port_dynamic_short_model import DynamicDiagnosticStop


robustness = robustness_v4.robustness
PARENT_EVIDENCE_SOURCE_SHA = "5fa69e2b1dff91095ea852057bbe19222b8c68ce"
EXPECTED_RESUMED_SOLVER_STEP = 337
ROOT_QUADRATURE_ORDER = 32


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _solve_neutral_endpoint(
    *,
    contract: dict[str, Any],
    case_id: str,
    state_id: str,
    provider: Any,
    adapter: Any,
    area_m2: float,
    outlet_conserved: np.ndarray,
    solver_time_s: float,
) -> dict[str, Any]:
    reconstruction = provider.reconstruct_from_conserved(outlet_conserved)
    static = reconstruction.static
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if normalize_phase(static.phase) not in allowed_phases:
        raise DynamicDiagnosticStop(
            f"endpoint phase {static.phase!r} is outside {sorted(allowed_phases)}"
        )
    if static.velocity_m_s < -velocity_tolerance:
        raise DynamicDiagnosticStop(
            f"endpoint velocity is reverse-directed: {static.velocity_m_s} m/s"
        )
    if not static.pressure_pa > float(adapter.back_pressure_pa):
        raise DynamicDiagnosticStop(
            "checkpoint endpoint static pressure is not above the retained back pressure"
        )

    tolerances = contract["acceptance_tolerances"]
    if abs(reconstruction.enthalpy_round_trip_residual_J_kg) > float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    ) or abs(reconstruction.entropy_round_trip_residual_J_kg_K) > float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    ):
        raise DynamicDiagnosticStop(
            "checkpoint stagnation-state round trip exceeds the locked tolerance"
        )

    diagnostic.QUADRATURE_ORDER = ROOT_QUADRATURE_ORDER
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

    endpoint = evaluate(float(static.pressure_pa))
    if not endpoint.get("evaluation_succeeded"):
        raise DynamicDiagnosticStop(
            "neutral endpoint evaluation failed: "
            f"{endpoint.get('formal_outcome')} {endpoint.get('formal_message')}"
        )
    completed = horizon._complete_root_row_dynamic_v4(
        root=endpoint,
        evaluate=evaluate,
        adapter=adapter,
        area_m2=area_m2,
        quadrature_order=ROOT_QUADRATURE_ORDER,
    )
    merged = dict(endpoint)
    merged.update(completed)
    merged["boundary_root_branch"] = "NEUTRAL_ENDPOINT"
    merged["endpoint_pressure_delta_pa"] = float(
        merged["pressure_pa"] - static.pressure_pa
    )

    if abs(float(merged["root_mass_residual_kg_s"])) > float(
        robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    ):
        raise DynamicDiagnosticStop(
            "neutral endpoint mass residual exceeds the retained root tolerance"
        )
    if float(merged["local_residual_slope_kg_s_Pa"]) >= 0.0:
        raise DynamicDiagnosticStop(
            "neutral endpoint local residual slope is not negative"
        )
    if not 0.0 <= float(merged["mach"]) < 1.0:
        raise DynamicDiagnosticStop("neutral endpoint is outside the subsonic branch")
    if float(merged["velocity_m_s"]) < -velocity_tolerance:
        raise DynamicDiagnosticStop("neutral endpoint velocity is reverse-directed")
    if not bool(merged["stagnation_enthalpy_round_trip_passed"]):
        raise DynamicDiagnosticStop(
            "neutral endpoint h0 round trip exceeds the locked tolerance"
        )
    if not bool(merged["energy_mass_consistency_passed"]):
        raise DynamicDiagnosticStop(
            "neutral endpoint energy/mass decomposition does not close"
        )
    if not bool(merged["energy_port_closure_passed"]):
        raise DynamicDiagnosticStop("neutral endpoint energy port does not close")
    if abs(float(merged["momentum_ledger_residual_N"])) > float(
        robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    ):
        raise DynamicDiagnosticStop(
            "neutral endpoint restriction-reaction ledger does not close"
        )

    mass_rate = float(merged["pipe_mass_rate_kg_s"])
    velocity = float(merged["velocity_m_s"])
    pressure = float(merged["pressure_pa"])
    h0 = float(merged["h0_J_kg"])
    flux = np.asarray(
        [
            mass_rate / area_m2,
            (mass_rate * velocity + pressure * area_m2) / area_m2,
            mass_rate * h0 / area_m2,
            0.0,
        ],
        dtype=float,
    )
    return {
        "solver_time_s": float(solver_time_s),
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "interior_phase": static.phase,
        "interior_h0_round_trip_residual_J_kg": float(
            reconstruction.enthalpy_round_trip_residual_J_kg
        ),
        "interior_s0_round_trip_residual_J_kg_K": float(
            reconstruction.entropy_round_trip_residual_J_kg_K
        ),
        "connected_scan_base_node_count": 1,
        "connected_scan_requested_nodes": 1,
        "connected_scan_admissible_subsonic_nodes": 1,
        "connected_scan_lowest_pressure_pa": float(static.pressure_pa),
        "connected_scan_stop_reason": None,
        "connected_scan_residual_monotone": True,
        "connected_scan_sign_change_count": 0,
        "root": merged,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
        "boundary_root_branch": "NEUTRAL_ENDPOINT",
    }


class A1NeutralEndpointResumeHook(horizon.A1TwoLOverC0Hook):
    """Diagnostic-only hook accepting the retained-tolerance neutral endpoint."""

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        context = _solve_neutral_endpoint(
            contract=self.contract,
            case_id=self.case_id,
            state_id=self.state_id,
            provider=self.provider,
            adapter=self.adapter,
            area_m2=self.area_m2,
            outlet_conserved=U[-1],
            solver_time_s=t,
        )
        self.root_context = context
        self.flux = np.array(context["flux"], copy=True)
        self._cache_t = float(t)
        self._cache_outlet = np.array(U[-1], copy=True)
        self.trial_dts_s = []


def _run_resume(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], np.ndarray, np.ndarray]:
    capture = _capture_checkpoint(contract, b1_contract)
    if not bool(capture["reproduction_ok"]):
        raise DynamicDiagnosticStop("step-336 checkpoint reproduction did not match")

    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = capture["hook"].provider
    U_initial, initial_static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    U_before = np.asarray(capture["U"], dtype=float)
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=U_before,
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=A1NeutralEndpointResumeHook(
            contract=contract,
            b1_contract=b1_contract,
            case_id=CASE_ID,
            provider=provider,
        ),
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=float(capture["time_s"]),
        step_count=int(capture["case_summary"]["accepted_steps_completed"]),
    )
    hook = solver.right_external_face_flux_override
    if not isinstance(hook, A1NeutralEndpointResumeHook):
        raise AssertionError("neutral-endpoint resume hook was not installed")

    initial = inventory(
        U_initial,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    before = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    complete_rows = [
        row
        for row in capture["rows"]
        if row.get("accepted_step") is True and "root_mach" in row
    ]
    last_complete = complete_rows[-1]
    current_minus_initial = _inventory_array(before) - _inventory_array(initial)
    previous_expected_delta = np.asarray(
        [
            current_minus_initial[0]
            - float(last_complete["cumulative_mass_residual_kg"]),
            current_minus_initial[1]
            - float(last_complete["cumulative_momentum_residual_kg_m_s"]),
            current_minus_initial[2]
            - float(last_complete["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )

    candidate_dt = float(solver.compute_dt())
    dt_limits = dict(hook.last_dt_limits)
    if hook.root_context is None:
        raise AssertionError("neutral endpoint was not prepared by compute_dt")
    root_context = hook.root_context
    flux_left, _ = solver._base_fluxes()
    left_flux = np.asarray(flux_left[0], dtype=float)
    right_flux = np.asarray(hook.flux, dtype=float)
    accepted_dt = float(solver.step(candidate_dt))
    hook.accept_current_root()

    after = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    expected_step_delta = accepted_dt * grid.geometry.area_m2 * (
        left_flux - right_flux
    )
    cumulative_expected_delta = previous_expected_delta + expected_step_delta
    primitive_after = solver.primitive()
    post_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
    row = build_step_row(
        case_id=CASE_ID,
        state_id=state_id,
        requested_step=EXPECTED_RESUMED_SOLVER_STEP,
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
    root = root_context["root"]
    row.update(
        {
            "boundary_root_branch": "NEUTRAL_ENDPOINT",
            "endpoint_pressure_delta_pa": float(
                root["endpoint_pressure_delta_pa"]
            ),
            "endpoint_within_locked_root_mass_tolerance": bool(
                abs(float(root["root_mass_residual_kg_s"]))
                <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            "local_residual_slope_scheme": root[
                "local_residual_slope_scheme"
            ],
            "checkpoint_reproduction_ok": True,
            "checkpoint_accepted_steps": EXPECTED_ACCEPTED_STEPS,
            "checkpoint_time_s": float(capture["time_s"]),
            "previous_accepted_root_pressure_pa": capture[
                "previous_root_pressure_pa"
            ],
        }
    )
    gate = bool(
        row["accepted_step"] is True
        and row["step_passed"] is True
        and row["boundary_root_branch"] == "NEUTRAL_ENDPOINT"
        and row["endpoint_within_locked_root_mass_tolerance"] is True
        and int(row["solver_step_count"]) == EXPECTED_RESUMED_SOLVER_STEP
        and row["reverse_flow_guard_triggered"] is False
        and row["reverse_velocity_detected"] is False
        and row["outlet_phase_passed"] is True
        and row["rho_xv_exact_zero"] is True
    )
    summary = {
        "schema_version": "stage7_u3_b2_a1_neutral_endpoint_resume_v1",
        "scope": "model_review_only_neutral_endpoint_one_step_resume",
        "parent_evidence_source_sha": PARENT_EVIDENCE_SOURCE_SHA,
        "checkpoint_reproduction_ok": True,
        "checkpoint_accepted_steps": EXPECTED_ACCEPTED_STEPS,
        "checkpoint_time_s": float(capture["time_s"]),
        "resumed_solver_step": int(solver.step_count),
        "accepted_dt_s": accepted_dt,
        "boundary_root_branch": "NEUTRAL_ENDPOINT",
        "endpoint_pressure_pa": float(root["pressure_pa"]),
        "endpoint_interior_pressure_pa": float(
            root_context["interior_pressure_pa"]
        ),
        "endpoint_pressure_delta_pa": float(
            root["endpoint_pressure_delta_pa"]
        ),
        "endpoint_velocity_m_s": float(root["velocity_m_s"]),
        "endpoint_mach": float(root["mach"]),
        "endpoint_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "endpoint_b1_mass_rate_kg_s": float(root["b1_mass_rate_kg_s"]),
        "endpoint_mass_residual_kg_s": float(
            root["root_mass_residual_kg_s"]
        ),
        "retained_root_mass_tolerance_kg_s": float(
            robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        ),
        "local_residual_slope_kg_s_Pa": float(
            root["local_residual_slope_kg_s_Pa"]
        ),
        "local_residual_slope_scheme": root[
            "local_residual_slope_scheme"
        ],
        "outlet_pressure_after_step_pa": float(
            row["outlet_pressure_after_step_pa"]
        ),
        "outlet_velocity_after_step_m_s": float(
            row["outlet_velocity_after_step_m_s"]
        ),
        "outlet_phase_after_step": row["outlet_phase_after_step"],
        "step_mass_residual_kg": float(row["step_mass_residual_kg"]),
        "step_momentum_residual_kg_m_s": float(
            row["step_momentum_residual_kg_m_s"]
        ),
        "step_energy_residual_J": float(row["step_energy_residual_J"]),
        "cumulative_mass_residual_kg": float(
            row["cumulative_mass_residual_kg"]
        ),
        "cumulative_momentum_residual_kg_m_s": float(
            row["cumulative_momentum_residual_kg_m_s"]
        ),
        "cumulative_energy_residual_J": float(
            row["cumulative_energy_residual_J"]
        ),
        "restriction_reaction_ledger_residual_N": float(
            row["restriction_reaction_ledger_residual_N"]
        ),
        "halving_count": int(row["halving_count"]),
        "neutral_endpoint_one_step_gate_passed": gate,
        "finite_compression_branch_approved": False,
        "post_endpoint_multi_step_passed": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    return row, summary, U_before, np.asarray(solver.U, dtype=float)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)

    row, summary, U_before, U_after = _run_resume(contract, b1_contract)
    summary["source_git_sha"] = args.source_git_sha
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "resume_step.csv", [row])
    np.savez_compressed(
        output / "resume_state.npz",
        U_before=U_before,
        U_after=U_after,
        solver_step_before=np.asarray([EXPECTED_ACCEPTED_STEPS], dtype=np.int64),
        solver_step_after=np.asarray(
            [EXPECTED_RESUMED_SOLVER_STEP], dtype=np.int64
        ),
        checkpoint_time_s=np.asarray([summary["checkpoint_time_s"]]),
        accepted_dt_s=np.asarray([summary["accepted_dt_s"]]),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 neutral-endpoint one-step resume\n\n"
        "MODEL_REVIEW_ONLY. The exact B2-10A step-336 checkpoint was "
        "reproduced and one FvmSolver step was attempted with `p_P = p_i` "
        "accepted under the unchanged root-mass tolerance before requiring a "
        "sign-change bracket. No positive-pressure continuation constructed "
        "the applied flux. This does not approve a finite compression branch, "
        "post-endpoint continuation, the full `2L/c0` horizon, Physical "
        "Validation, design use, or production activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = ("resume_step.csv", "resume_state.npz", "summary.json", "report.md")
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n"
            for name in names
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["neutral_endpoint_one_step_gate_passed"]:
        raise SystemExit("A1 neutral-endpoint one-step resume did not pass")


if __name__ == "__main__":
    main()
