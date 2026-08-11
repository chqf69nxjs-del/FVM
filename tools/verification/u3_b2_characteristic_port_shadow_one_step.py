from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_characteristic_port_root_robustness as robustness
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
)
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    BOUNDARY_UPDATE_POSITIVITY_FAILURE,
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
    normalize_phase,
)


CASE_IDS = (
    "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE",
    "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT",
    "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT",
)
ROOT_QUADRATURE_ORDER = 32


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


def _inventory(U: np.ndarray, *, dx: float, area_m2: float) -> dict[str, float]:
    volume = float(dx) * float(area_m2)
    return {
        "mass_kg": float(np.sum(U[:, IDX_RHO]) * volume),
        "momentum_kg_m_s": float(np.sum(U[:, IDX_MOM]) * volume),
        "energy_J": float(np.sum(U[:, IDX_RHOE]) * volume),
        "vapor_mass_kg": float(np.sum(U[:, IDX_RHO_XV]) * volume),
    }


class A1ShadowOneStepHook:
    """Diagnostic-only fixed A1 port for one actual FvmSolver step."""

    failure_outcome = BOUNDARY_UPDATE_POSITIVITY_FAILURE

    def __init__(
        self,
        *,
        contract: dict[str, Any],
        state_id: str,
        provider: CoolPropB2StateProvider,
        root: dict[str, Any],
    ) -> None:
        self.contract = contract
        self.state_id = state_id
        self.provider = provider
        self.root = dict(root)
        self.maximum_halvings = int(
            contract["time_step_and_update"]["deterministic_halving"][
                "maximum_halvings"
            ]
        )
        self.area_m2 = float(contract["geometry"]["pipe_area_m2"])

        mass_rate = float(root["pipe_mass_rate_kg_s"])
        velocity = float(root["velocity_m_s"])
        pressure = float(root["pressure_pa"])
        h0 = float(root["h0_J_kg"])
        self.pipe_momentum_port_N = mass_rate * velocity + pressure * self.area_m2
        self.pipe_energy_rate_W = mass_rate * h0
        self.flux = np.asarray(
            [
                mass_rate / self.area_m2,
                self.pipe_momentum_port_N / self.area_m2,
                self.pipe_energy_rate_W / self.area_m2,
                0.0,
            ],
            dtype=float,
        )
        self.last_dt_limits: dict[str, float] = {}

    def limit_dt(
        self,
        *,
        U: np.ndarray,
        eos,
        grid: UniformGrid,
        t: float,
        candidate_dt: float,
    ) -> float:
        del eos, t
        if not math.isfinite(candidate_dt) or candidate_dt <= 0.0:
            raise ValueError("candidate_dt must be positive and finite")

        mass_rate = float(self.flux[IDX_RHO] * self.area_m2)
        energy_rate = float(self.flux[IDX_RHOE] * self.area_m2)
        cell_volume = self.area_m2 * grid.dx

        mass_dt = math.inf
        if mass_rate > 0.0:
            mass_dt = (
                float(
                    self.contract["time_step_and_update"][
                        "boundary_mass_removal_fraction_limit"
                    ]
                )
                * float(U[-1, IDX_RHO])
                * cell_volume
                / mass_rate
            )

        energy_dt = math.inf
        if energy_rate > 0.0:
            energy_dt = (
                float(
                    self.contract["time_step_and_update"][
                        "boundary_energy_removal_fraction_limit"
                    ]
                )
                * float(U[-1, IDX_RHOE])
                * cell_volume
                / energy_rate
            )

        accepted = min(float(candidate_dt), mass_dt, energy_dt)
        self.last_dt_limits = {
            "candidate_dt_s": float(candidate_dt),
            "mass_removal_dt_s": float(mass_dt),
            "energy_removal_dt_s": float(energy_dt),
            "accepted_dt_s": float(accepted),
        }
        return float(accepted)

    def evaluate_flux(
        self,
        *,
        U: np.ndarray,
        eos,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> np.ndarray:
        del U, eos, grid, t, dt
        return np.array(self.flux, copy=True)

    def validate_trial(
        self,
        *,
        U_before: np.ndarray,
        U_trial: np.ndarray,
        eos,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> None:
        del U_before, eos, grid, t, dt
        if not np.all(np.isfinite(U_trial)):
            raise ValueError("trial conserved state contains a nonfinite value")

        rho = U_trial[:, IDX_RHO]
        if np.any(rho <= 0.0):
            raise ValueError("trial density must be positive")
        velocity = U_trial[:, IDX_MOM] / rho
        internal = U_trial[:, IDX_RHOE] / rho - 0.5 * velocity * velocity
        if np.any(~np.isfinite(internal)) or np.any(internal <= 0.0):
            raise ValueError("trial internal energy must be positive")
        if not np.all(U_trial[:, IDX_RHO_XV] == 0.0):
            raise ValueError("single-phase rho*xv identity must remain exact zero")

        family = robustness.diagnostic._family(self.contract, self.state_id)
        allowed = {
            normalize_phase(value)
            for value in family["allowed_normalized_phases"]
        }
        for row in U_trial:
            reconstruction = self.provider.reconstruct_from_conserved(row)
            if normalize_phase(reconstruction.static.phase) not in allowed:
                raise ValueError(
                    f"trial phase {reconstruction.static.phase!r} is outside "
                    f"{sorted(allowed)}"
                )


def _solve_initial_root(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    case_id: str,
) -> tuple[dict[str, Any], CoolPropB2StateProvider]:
    evaluate, _, _, _ = robustness._build_evaluator(
        contract=contract,
        b1_contract=b1_contract,
        case_id=case_id,
        quadrature_order=ROOT_QUADRATURE_ORDER,
    )
    bracket = robustness.CASE_BRACKETS_PA[case_id]
    root = robustness._bisection_root(
        lower_pressure_pa=bracket[0],
        upper_pressure_pa=bracket[1],
        evaluate=evaluate,
    )
    provider = CoolPropB2StateProvider()
    return root, provider


def _run_case(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    case = robustness.diagnostic._case(contract, case_id)
    state_id = str(case["state_id"])
    root, provider = _solve_initial_root(
        contract=contract,
        b1_contract=b1_contract,
        case_id=case_id,
    )

    geometry = contract["geometry"]
    cells = int(geometry["baseline_cells"])
    cfl = float(geometry["baseline_cfl"])
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, cells)
    U_initial, static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        cells,
    )
    eos = CoolPropSinglePhaseEOS(
        provider,
        boundary_temperature_K=static.temperature_K,
    )
    hook = A1ShadowOneStepHook(
        contract=contract,
        state_id=state_id,
        provider=provider,
        root=root,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U_initial,
        cfl=cfl,
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )

    initial_inventory = _inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    flux_left, _ = solver._base_fluxes()
    left_external_flux = np.asarray(flux_left[0], dtype=float)
    right_external_flux = np.asarray(hook.flux, dtype=float)

    candidate_dt = float(solver.compute_dt())
    accepted_dt = float(solver.step(candidate_dt))

    final_inventory = _inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    primitive_after = solver.primitive()
    last_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])

    area = grid.geometry.area_m2
    expected_delta = accepted_dt * area * (
        left_external_flux - right_external_flux
    )
    mass_residual = (
        final_inventory["mass_kg"]
        - initial_inventory["mass_kg"]
        - float(expected_delta[IDX_RHO])
    )
    momentum_residual = (
        final_inventory["momentum_kg_m_s"]
        - initial_inventory["momentum_kg_m_s"]
        - float(expected_delta[IDX_MOM])
    )
    energy_residual = (
        final_inventory["energy_J"]
        - initial_inventory["energy_J"]
        - float(expected_delta[IDX_RHOE])
    )

    tolerances = contract["acceptance_tolerances"]
    allowed_phases = {
        normalize_phase(value)
        for value in robustness.diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    outlet_phase_passed = (
        normalize_phase(last_reconstruction.static.phase) in allowed_phases
    )

    downstream_port = float(root["downstream_stream_pressure_port_N"])
    pipe_port = float(root["pipe_momentum_port_N"])
    reaction = float(root["restriction_reaction_on_fluid_N"])
    reaction_residual = downstream_port - pipe_port - reaction

    root_mass_residual = float(root["residual_kg_s"])
    pipe_energy_rate = float(root["pipe_mass_rate_kg_s"]) * float(root["h0_J_kg"])
    root_conserved = np.asarray(
        [
            float(root["density_kg_m3"]),
            float(root["density_kg_m3"]) * float(root["velocity_m_s"]),
            float(root["density_kg_m3"])
            * (
                float(root["internal_energy_J_kg"])
                + 0.5 * float(root["velocity_m_s"]) ** 2
            ),
            0.0,
        ],
        dtype=float,
    )
    # Re-evaluate through the retained B1 adapter to record the corresponding
    # energy port without changing the immutable B1 law.
    _, _, adapter, _ = robustness._build_evaluator(
        contract=contract,
        b1_contract=b1_contract,
        case_id=case_id,
        quadrature_order=ROOT_QUADRATURE_ORDER,
    )
    root_evaluation = adapter.evaluate(root_conserved, area)
    if not root_evaluation.succeeded or root_evaluation.face is None:
        raise RuntimeError(
            f"root B1 reevaluation failed: {root_evaluation.formal_outcome}"
        )
    b1_energy_rate = float(root_evaluation.face.energy_transfer_outward_W)
    root_energy_residual = pipe_energy_rate - b1_energy_rate

    row = {
        "case_id": case_id,
        "state_id": state_id,
        "cells": cells,
        "cfl": cfl,
        "candidate_dt_s": candidate_dt,
        "accepted_dt_s": accepted_dt,
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_pipe_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "root_b1_mass_rate_kg_s": float(root["b1_mass_rate_kg_s"]),
        "root_mass_residual_kg_s": root_mass_residual,
        "root_pipe_energy_rate_W": pipe_energy_rate,
        "root_b1_energy_rate_W": b1_energy_rate,
        "root_energy_residual_W": root_energy_residual,
        "left_external_mass_flux_kg_m2_s": float(left_external_flux[IDX_RHO]),
        "right_external_mass_flux_kg_m2_s": float(right_external_flux[IDX_RHO]),
        "left_external_momentum_flux_pa": float(left_external_flux[IDX_MOM]),
        "right_external_momentum_flux_pa": float(right_external_flux[IDX_MOM]),
        "left_external_energy_flux_W_m2": float(left_external_flux[IDX_RHOE]),
        "right_external_energy_flux_W_m2": float(right_external_flux[IDX_RHOE]),
        "initial_mass_kg": initial_inventory["mass_kg"],
        "final_mass_kg": final_inventory["mass_kg"],
        "mass_update_residual_kg": mass_residual,
        "initial_momentum_kg_m_s": initial_inventory["momentum_kg_m_s"],
        "final_momentum_kg_m_s": final_inventory["momentum_kg_m_s"],
        "momentum_update_residual_kg_m_s": momentum_residual,
        "initial_energy_J": initial_inventory["energy_J"],
        "final_energy_J": final_inventory["energy_J"],
        "energy_update_residual_J": energy_residual,
        "initial_vapor_mass_kg": initial_inventory["vapor_mass_kg"],
        "final_vapor_mass_kg": final_inventory["vapor_mass_kg"],
        "outlet_velocity_after_step_m_s": float(primitive_after.u[-1]),
        "outlet_pressure_after_step_pa": float(primitive_after.p[-1]),
        "outlet_phase_after_step": last_reconstruction.static.phase,
        "outlet_phase_passed": outlet_phase_passed,
        "downstream_stream_pressure_port_N": downstream_port,
        "pipe_side_momentum_port_N": pipe_port,
        "restriction_reaction_on_fluid_N": reaction,
        "restriction_reaction_ledger_residual_N": reaction_residual,
        "reverse_flow_guard_triggered": False,
    }

    row["shadow_one_step_passed"] = bool(
        float(root["velocity_m_s"])
        > -float(tolerances["velocity_zero_tolerance_m_s"])
        and row["outlet_velocity_after_step_m_s"]
        > -float(tolerances["velocity_zero_tolerance_m_s"])
        and abs(mass_residual)
        <= float(tolerances["mass_inventory_absolute_kg"])
        and abs(momentum_residual)
        <= float(tolerances["momentum_inventory_absolute_kg_m_s"])
        and abs(energy_residual)
        <= float(tolerances["energy_inventory_absolute_J"])
        and final_inventory["vapor_mass_kg"]
        == float(tolerances["vapor_mass_exact_zero_absolute_kg"])
        and outlet_phase_passed
        and abs(reaction_residual) <= 1.0e-12
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    rows = [
        _run_case(
            contract=contract,
            b1_contract=b1_contract,
            case_id=case_id,
        )
        for case_id in CASE_IDS
    ]

    summary = {
        "schema_version": "stage7_u3_b2_characteristic_port_shadow_one_step_v1",
        "scope": "model_review_only_no_contract_or_production_change",
        "source_git_sha": args.source_git_sha,
        "root_quadrature_order": ROOT_QUADRATURE_ORDER,
        "cases": rows,
        "shadow_one_step_gate_passed": all(
            row["shadow_one_step_passed"] for row in rows
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
    _write_csv(output / "shadow_one_step.csv", rows)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 characteristic-port shadow one-step\n\n"
        "MODEL_REVIEW_ONLY. This is an actual FvmSolver one-step diagnostic "
        "using an A1 pipe-side Euler port. No Contract, Adapter, solver or "
        "formal state is modified.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    manifest_names = ("summary.json", "shadow_one_step.csv", "report.md")
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n" for name in manifest_names
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["shadow_one_step_gate_passed"]:
        raise SystemExit("A1 shadow one-step gate did not pass")


if __name__ == "__main__":
    main()
