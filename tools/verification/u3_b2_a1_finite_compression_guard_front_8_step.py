from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
import u3_b2_characteristic_port_diagnostic as diagnostic
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
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_hook import A1DynamicShortHook
from u3_b2_characteristic_port_dynamic_short_metrics import build_step_row, inventory


PARENT_SOURCE_SHA = "6229760e16e9588e0ef37a818af06158a4f72c06"
PARENT_RUN = 31662867986
PARENT_JOB = 94331160828
PARENT_ARTIFACT = 9166824541
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-8b-import-fix-31662867986"
)
PARENT_DIGEST = (
    "e5a126047df4d55da36e53dfc0333ea08cc339f15ca9dac9fd2b6decb0b7405f"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_8B_GUARD_FRONT_ONE_STEP_PASS"
STARTING_STEP = 494
FINAL_STEP = 502
REQUESTED_STEPS = 8
STARTING_TIME_S = 0.0033103559567215584
OUTCOME = "FINITE_COMPRESSION_INCREMENT_8C_GUARD_FRONT_8_STEP_PASS"

PARENT_REQUIRED_FILES = {
    "recomputed_fixed_scan.csv",
    "recomputed_guard_front.csv",
    "recomputed_root_topology.csv",
    "recomputed_density_search.csv",
    "selected_root.csv",
    "finite_compression_one_step.csv",
    "finite_compression_one_step_states.npz",
    "authority_verification.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


class ShortRunStop(RuntimeError):
    def __init__(
        self,
        classification: str,
        message: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.diagnostics = diagnostics or {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(U, dtype="<f8").tobytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        rows = [{"no_rows_recorded": True}]
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _inventory_array(values: dict[str, float]) -> np.ndarray:
    return np.asarray(
        [
            values["mass_kg"],
            values["momentum_kg_m_s"],
            values["energy_J"],
            values["vapor_mass_kg"],
        ],
        dtype=float,
    )


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str], dict[str, str]]:
    if artifact_digest != PARENT_DIGEST:
        raise ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH", "parent GitHub artifact digest mismatch"
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH", f"parent file set mismatch: {sorted(actual)}"
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH", "parent internal manifest names mismatch"
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH", f"parent SHA256 mismatch for {name}"
            )

    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "solver_step_before": 493,
        "solver_step_after": STARTING_STEP,
        "solver_time_after_s": STARTING_TIME_S,
        "diagnostic_authority_verified": True,
        "root_authority_comparison_passed": True,
        "increment_8b_one_step_gate_passed": True,
        "solver_step_495_authorized": False,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"parent summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(directory / "finite_compression_one_step_states.npz") as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_after.shape != (32, 4) or step_after != STARTING_STEP or time_after != STARTING_TIME_S:
        raise ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH", "parent state identity mismatch"
        )
    if not np.all(np.isfinite(U_after)):
        raise ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE", "parent state contains nonfinite values"
        )
    rho = U_after[:, 0]
    velocity = U_after[:, 1] / rho
    internal = U_after[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "parent density or internal energy is nonpositive",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH", "parent rho*xv is not exact zero"
        )

    step_rows = _read_csv(directory / "finite_compression_one_step.csv")
    root_rows = _read_csv(directory / "selected_root.csv")
    if len(step_rows) != 1 or len(root_rows) != 1:
        raise ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH", "parent step/root row count mismatch"
        )
    if step_rows[0].get("increment_8b_one_step_gate_passed") != "True":
        raise ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH", "parent step gate did not pass"
        )
    if root_rows[0].get("root_gate_passed") != "True":
        raise ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH", "parent selected-root gate did not pass"
        )
    return summary, U_after, step_rows[0], root_rows[0]


def _flatten(
    rows: list[dict[str, Any]],
    *,
    requested_step: int,
    solver_time_s: float,
    row_kind: str,
) -> list[dict[str, Any]]:
    return [
        {
            "requested_solver_step": requested_step,
            "solver_time_s": solver_time_s,
            "row_kind": row_kind,
            **row,
        }
        for row in rows
    ]


class DynamicGuardFrontHugoniotHook(A1DynamicShortHook):
    def __init__(
        self,
        *,
        contract: dict[str, Any],
        b1_contract: dict[str, Any],
        case_id: str,
        provider: CoolPropB2StateProvider,
    ) -> None:
        super().__init__(
            contract=contract,
            b1_contract=b1_contract,
            case_id=case_id,
            provider=provider,
        )

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        if self._previous_root_pressure_pa is None:
            raise ShortRunStop(
                "PARENT_ROOT_MISSING", "previous accepted root pressure is unavailable"
            )
        parent_root = {"root_pressure_pa": str(self._previous_root_pressure_pa)}
        try:
            (
                diagnostic_summary,
                fixed_rows,
                guard_rows,
                topology_rows,
                density_rows,
                root,
            ) = inc8a._run(
                contract=self.contract,
                b1_contract=self.adapter.contract,
                U=np.asarray(U, dtype=float),
                parent_root=parent_root,
            )
        except Exception as exc:
            raise ShortRunStop(
                type(exc).__name__,
                f"Guard-front Hugoniot diagnostic failed: {type(exc).__name__}: {exc}",
            ) from exc
        classification = str(diagnostic_summary["outcome"])
        if classification != inc8a.SUPPORTED or not bool(
            root.get("selected_root_present")
        ):
            raise ShortRunStop(
                classification,
                "no supported finite-compression root is available for the next step",
                {"diagnostic_summary": diagnostic_summary},
            )
        if not bool(root.get("root_gate_passed")):
            raise ShortRunStop(
                "ROOT_OR_LEDGER_FAILURE", "selected Guard-front root gate did not pass"
            )

        reconstruction = self.provider.reconstruct_from_conserved(U[-1])
        static = reconstruction.static
        allowed = {
            normalize_phase(value)
            for value in diagnostic._family(self.contract, self.state_id)[
                "allowed_normalized_phases"
            ]
        }
        velocity_tolerance = float(
            self.contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
        )
        mass_rate = float(root["pipe_mass_rate_kg_s"])
        velocity = float(root["velocity_m_s"])
        pressure = float(root["pressure_pa"])
        h0 = float(root["h0_J_kg"])
        flux = np.asarray(
            [
                mass_rate / self.area_m2,
                (mass_rate * velocity + pressure * self.area_m2) / self.area_m2,
                mass_rate * h0 / self.area_m2,
                0.0,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(flux)):
            raise ShortRunStop(
                "NONFINITE_FLUX", "selected Guard-front Hugoniot flux is nonfinite"
            )

        self.root_context = {
            "solver_time_s": float(t),
            "interior_pressure_pa": float(static.pressure_pa),
            "interior_temperature_K": float(static.temperature_K),
            "interior_density_kg_m3": float(static.density_kg_m3),
            "interior_velocity_m_s": float(static.velocity_m_s),
            "interior_sound_speed_m_s": float(static.sound_speed_m_s),
            "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
            "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
            "interior_phase": str(static.phase),
            "interior_h0_round_trip_residual_J_kg": float(
                reconstruction.enthalpy_round_trip_residual_J_kg
            ),
            "interior_s0_round_trip_residual_J_kg_K": float(
                reconstruction.entropy_round_trip_residual_J_kg_K
            ),
            "connected_scan_base_node_count": int(
                diagnostic_summary["fixed_scan_node_count"]
            ),
            "connected_scan_requested_nodes": int(
                diagnostic_summary["fixed_scan_node_count"]
                + diagnostic_summary["guard_front_iterations"]
            ),
            "connected_scan_admissible_subsonic_nodes": int(
                diagnostic_summary["root_topology_node_count"]
            ),
            "connected_scan_lowest_pressure_pa": float(root["pressure_pa"]),
            "connected_scan_stop_reason": None,
            "connected_scan_residual_monotone": bool(
                diagnostic_summary["root_topology_monotone_nonincreasing"]
            ),
            "connected_scan_sign_change_count": int(
                diagnostic_summary["root_topology_sign_change_count"]
            ),
            "root": root,
            "flux": flux,
            "allowed_phases": allowed,
            "velocity_tolerance_m_s": velocity_tolerance,
            "branch_classification": base.BRANCH,
            "root_chi": float(root["requested_chi"]),
            "root_gate_passed": True,
            "diagnostic_classification": classification,
            "guard_front_refinement_applied": bool(
                diagnostic_summary["guard_front_refinement_applied"]
            ),
            "guard_front_iterations": int(
                diagnostic_summary["guard_front_iterations"]
            ),
            "root_topology_node_count": int(
                diagnostic_summary["root_topology_node_count"]
            ),
            "root_topology_monotone_nonincreasing": bool(
                diagnostic_summary["root_topology_monotone_nonincreasing"]
            ),
            "root_topology_sign_change_count": int(
                diagnostic_summary["root_topology_sign_change_count"]
            ),
            "fixed_scan_rows": fixed_rows,
            "guard_front_rows": guard_rows,
            "root_topology_rows": topology_rows,
            "density_search_rows": density_rows,
            "failed_b1_state_used_as_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
            "finite_compression_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
        self.flux = flux.copy()
        self._cache_t = float(t)
        self._cache_outlet = np.asarray(U[-1], dtype=float).copy()
        self.trial_dts_s = []


def _root_row(context: dict[str, Any], *, requested_step: int) -> dict[str, Any]:
    root = context["root"]
    return {
        "requested_solver_step": requested_step,
        "solver_time_s": float(context["solver_time_s"]),
        "branch_classification": base.BRANCH,
        "diagnostic_classification": context["diagnostic_classification"],
        "guard_front_refinement_applied": bool(
            context["guard_front_refinement_applied"]
        ),
        "guard_front_iterations": int(context["guard_front_iterations"]),
        "root_topology_node_count": int(context["root_topology_node_count"]),
        "root_topology_monotone_nonincreasing": bool(
            context["root_topology_monotone_nonincreasing"]
        ),
        "root_topology_sign_change_count": int(
            context["root_topology_sign_change_count"]
        ),
        "root_pressure_pa": float(root["pressure_pa"]),
        "root_requested_chi": float(root["requested_chi"]),
        "root_realized_chi": float(root["realized_chi"]),
        "root_pressure_offset_pa": float(root["pressure_offset_pa"]),
        "root_density_kg_m3": float(root["density_kg_m3"]),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_mach": float(root["mach"]),
        "root_phase": str(root["phase"]),
        "root_mass_residual_kg_s": float(root["root_mass_residual_kg_s"]),
        "root_local_slope_kg_s_Pa": float(root["local_residual_slope_kg_s_Pa"]),
        "root_entropy_delta_J_kg_K": float(root["entropy_delta_J_kg_K"]),
        "root_hugoniot_closure_passed": bool(root["hugoniot_closure_passed"]),
        "root_hugoniot_identity_accounted_passed": bool(
            root["hugoniot_identity_accounted_passed"]
        ),
        "root_lax_1_shock_passed": bool(root["lax_1_shock_passed"]),
        "root_entropy_bound_passed": bool(root["entropy_bound_passed"]),
        "root_b1_formal_outcome": str(root["formal_outcome"]),
        "root_stagnation_pressure_pa": float(root["stagnation_pressure_pa"]),
        "root_stagnation_pressure_margin_above_back_pa": float(
            root["stagnation_pressure_pa"] - root["back_pressure_pa"]
        ),
        "root_stagnation_enthalpy_round_trip_passed": bool(
            root["stagnation_enthalpy_round_trip_passed"]
        ),
        "root_energy_mass_consistency_passed": bool(
            root["energy_mass_consistency_passed"]
        ),
        "root_energy_port_closure_passed": bool(
            root["energy_port_closure_passed"]
        ),
        "root_restriction_reaction_ledger_residual_N": float(
            root["momentum_ledger_residual_N"]
        ),
        "root_gate_passed": bool(root["root_gate_passed"]),
        "failed_b1_state_used_as_root_endpoint": False,
        "failed_b1_state_used_to_construct_flux": False,
    }


def _run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U_start: np.ndarray,
    parent_step: dict[str, str],
    parent_root: dict[str, str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    np.ndarray,
    np.ndarray,
]:
    case = diagnostic._case(contract, base.CASE_ID)
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
        contract, provider, state_id, grid.n_cells
    )
    hook = DynamicGuardFrontHugoniotHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(parent_root["pressure_pa"])
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider, boundary_temperature_K=initial_static.temperature_K
        ),
        U=np.asarray(U_start, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=STARTING_TIME_S,
        step_count=STARTING_STEP,
    )
    initial = inventory(U_initial, dx=grid.dx, area_m2=grid.geometry.area_m2)
    starting = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    current_minus_initial = _inventory_array(starting) - _inventory_array(initial)
    cumulative_residual = np.asarray(
        [
            float(parent_step["cumulative_mass_residual_kg"]),
            float(parent_step["cumulative_momentum_residual_kg_m_s"]),
            float(parent_step["cumulative_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )
    cumulative_expected_delta = current_minus_initial - cumulative_residual
    U_before_all = np.asarray(solver.U, dtype=float).copy()

    step_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    guard_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    density_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None

    for requested_step in range(STARTING_STEP + 1, FINAL_STEP + 1):
        try:
            before = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
            candidate_dt = float(solver.compute_dt())
            context = hook.root_context
            if context is None:
                raise ShortRunStop(
                    "ROOT_OR_LEDGER_FAILURE", "root context was not prepared"
                )
            dt_limits = dict(hook.last_dt_limits)
            root_row = _root_row(context, requested_step=requested_step)
            fixed_rows.extend(
                _flatten(
                    context["fixed_scan_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="HUGONIOT_FIXED_SCAN",
                )
            )
            guard_rows.extend(
                _flatten(
                    context["guard_front_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="B1_GUARD_FRONT_REFINEMENT",
                )
            )
            topology_rows.extend(
                _flatten(
                    context["root_topology_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="ROOT_TOPOLOGY",
                )
            )
            density_rows.extend(
                _flatten(
                    context["density_search_rows"],
                    requested_step=requested_step,
                    solver_time_s=float(solver.t),
                    row_kind="HUGONIOT_DENSITY_SEARCH",
                )
            )
            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)
            accepted_dt = float(solver.step(candidate_dt))
            hook.accept_current_root()
            after = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
            expected_step_delta = (
                accepted_dt * grid.geometry.area_m2 * (left_flux - right_flux)
            )
            cumulative_expected_delta = cumulative_expected_delta + expected_step_delta
            primitive_after = solver.primitive()
            post_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
            row = build_step_row(
                case_id=base.CASE_ID,
                state_id=state_id,
                requested_step=requested_step,
                solver=solver,
                hook=hook,
                root_context=context,
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
            rho = np.asarray(solver.U[:, 0], dtype=float)
            velocity = np.asarray(solver.U[:, 1] / rho, dtype=float)
            internal = np.asarray(
                solver.U[:, 2] / rho - 0.5 * velocity**2, dtype=float
            )
            outlet = post_reconstruction.static
            root = context["root"]
            row.update(
                {
                    "branch_classification": base.BRANCH,
                    "finite_compression_model": "GENERAL_EOS_HUGONIOT",
                    "diagnostic_classification": context[
                        "diagnostic_classification"
                    ],
                    "guard_front_refinement_applied": bool(
                        context["guard_front_refinement_applied"]
                    ),
                    "guard_front_iterations": int(
                        context["guard_front_iterations"]
                    ),
                    "root_topology_node_count": int(
                        context["root_topology_node_count"]
                    ),
                    "root_topology_monotone_nonincreasing": bool(
                        context["root_topology_monotone_nonincreasing"]
                    ),
                    "root_topology_sign_change_count": int(
                        context["root_topology_sign_change_count"]
                    ),
                    "failed_b1_state_used_as_root_endpoint": False,
                    "failed_b1_state_used_to_construct_flux": False,
                    "root_requested_chi": float(root["requested_chi"]),
                    "root_realized_chi": float(root["realized_chi"]),
                    "root_pressure_offset_pa": float(root["pressure_offset_pa"]),
                    "root_entropy_delta_J_kg_K": float(
                        root["entropy_delta_J_kg_K"]
                    ),
                    "root_hugoniot_identity_accounted_passed": bool(
                        root["hugoniot_identity_accounted_passed"]
                    ),
                    "root_lax_1_shock_passed": bool(
                        root["lax_1_shock_passed"]
                    ),
                    "root_gate_passed": bool(root["root_gate_passed"]),
                    "all_conserved_finite_after_step": bool(
                        np.all(np.isfinite(solver.U))
                    ),
                    "minimum_density_after_step_kg_m3": float(np.min(rho)),
                    "minimum_internal_energy_after_step_J_kg": float(
                        np.min(internal)
                    ),
                    "outlet_mach_after_step": float(
                        outlet.velocity_m_s / outlet.sound_speed_m_s
                    ),
                    "finite_compression_flux_applied": True,
                    "finite_compression_branch_approved": False,
                }
            )
            gate = bool(
                int(solver.step_count) == requested_step
                and accepted_dt > 0.0
                and bool(row["step_passed"])
                and bool(root["root_gate_passed"])
                and bool(row["all_conserved_finite_after_step"])
                and float(row["minimum_density_after_step_kg_m3"]) > 0.0
                and float(row["minimum_internal_energy_after_step_J_kg"]) > 0.0
                and not bool(row["reverse_velocity_detected"])
                and float(row["outlet_velocity_after_step_m_s"]) >= 0.0
                and 0.0 <= float(row["outlet_mach_after_step"]) < 1.0
                and bool(row["outlet_phase_passed"])
                and bool(row["rho_xv_exact_zero"])
                and base.WEAK_COMPRESSION_CHI_LIMIT
                < float(root["requested_chi"])
                <= base.DIAGNOSTIC_CHI_CAP
                and int(context["root_topology_sign_change_count"]) == 1
                and bool(context["root_topology_monotone_nonincreasing"])
            )
            row["increment_8c_per_step_gate_passed"] = gate
            if not gate:
                raise ShortRunStop(
                    "POST_STEP_GATE_FAILURE",
                    f"accepted step {requested_step} failed the Increment 8C gate",
                )
            step_rows.append(row)
            root_rows.append(root_row)
            branch_rows.append(
                {
                    "requested_solver_step": requested_step,
                    "solver_step_count": int(solver.step_count),
                    "time_after_s": float(solver.t),
                    "branch_classification": base.BRANCH,
                    "accepted": True,
                }
            )
        except ShortRunStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{type(exc).__name__}: {exc}"
            break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            break

    U_after_all = np.asarray(solver.U, dtype=float).copy()
    branches = [row["branch_classification"] for row in branch_rows]
    transitions = sum(a != b for a, b in zip(branches, branches[1:]))
    pass_gate = bool(
        stop_reason is None
        and len(step_rows) == REQUESTED_STEPS
        and int(solver.step_count) == FINAL_STEP
        and all(row["increment_8c_per_step_gate_passed"] for row in step_rows)
        and all(branch == base.BRANCH for branch in branches)
        and transitions == 0
    )
    final_reconstruction = provider.reconstruct_from_conserved(U_after_all[-1])
    rho_final = U_after_all[:, 0]
    velocity_final = U_after_all[:, 1] / rho_final
    internal_final = U_after_all[:, 2] / rho_final - 0.5 * velocity_final**2
    summary = {
        "schema_version": "stage7_u3_b2_a1_finite_compression_increment_8c",
        "scope": "model_review_eight_actual_guard_front_hugoniot_steps",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_run": PARENT_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_name": PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": PARENT_DIGEST,
        "parent_artifact_verified": True,
        "parent_outcome": PARENT_OUTCOME,
        "starting_solver_step": STARTING_STEP,
        "requested_accepted_steps": REQUESTED_STEPS,
        "accepted_steps_completed": len(step_rows),
        "final_solver_step": int(solver.step_count),
        "starting_solver_time_s": STARTING_TIME_S,
        "final_solver_time_s": float(solver.t),
        "branch_sequence": branches,
        "branch_counts": dict(Counter(branches)),
        "branch_transition_count": transitions,
        "minimum_root_requested_chi": _minimum(step_rows, "root_requested_chi"),
        "maximum_root_requested_chi": _maximum(step_rows, "root_requested_chi"),
        "maximum_absolute_root_mass_residual_kg_s": _max_abs(
            step_rows, "root_mass_residual_kg_s"
        ),
        "minimum_root_local_slope_kg_s_Pa": _minimum(
            step_rows, "root_local_slope_kg_s_Pa"
        ),
        "maximum_root_mach": _maximum(step_rows, "root_mach"),
        "minimum_root_velocity_m_s": _minimum(step_rows, "root_velocity_m_s"),
        "minimum_root_entropy_delta_J_kg_K": _minimum(
            step_rows, "root_entropy_delta_J_kg_K"
        ),
        "maximum_halving_count": _maximum(step_rows, "halving_count"),
        "minimum_accepted_dt_s": _minimum(step_rows, "accepted_dt_s"),
        "maximum_accepted_dt_s": _maximum(step_rows, "accepted_dt_s"),
        "maximum_absolute_step_mass_residual_kg": _max_abs(
            step_rows, "step_mass_residual_kg"
        ),
        "maximum_absolute_step_momentum_residual_kg_m_s": _max_abs(
            step_rows, "step_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_step_energy_residual_J": _max_abs(
            step_rows, "step_energy_residual_J"
        ),
        "maximum_absolute_cumulative_mass_residual_kg": _max_abs(
            step_rows, "cumulative_mass_residual_kg"
        ),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": _max_abs(
            step_rows, "cumulative_momentum_residual_kg_m_s"
        ),
        "maximum_absolute_cumulative_energy_residual_J": _max_abs(
            step_rows, "cumulative_energy_residual_J"
        ),
        "final_outlet_pressure_pa": float(
            final_reconstruction.static.pressure_pa
        ),
        "final_outlet_velocity_m_s": float(
            final_reconstruction.static.velocity_m_s
        ),
        "final_outlet_mach": float(
            final_reconstruction.static.velocity_m_s
            / final_reconstruction.static.sound_speed_m_s
        ),
        "final_outlet_phase": str(final_reconstruction.static.phase),
        "final_minimum_density_kg_m3": float(np.min(rho_final)),
        "final_minimum_internal_energy_J_kg": float(np.min(internal_final)),
        "final_rho_xv_exact_zero": bool(np.all(U_after_all[:, 3] == 0.0)),
        "starting_state_sha256": _state_sha256(U_before_all),
        "final_state_sha256": _state_sha256(U_after_all),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "increment_8c_8_step_gate_passed": pass_gate,
        "outcome": OUTCOME if pass_gate else "INCREMENT_8C_STOPPED",
        "solver_step_503_authorized": False,
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    return (
        summary,
        step_rows,
        root_rows,
        fixed_rows,
        guard_rows,
        topology_rows,
        density_rows,
        branch_rows,
        U_before_all,
        U_after_all,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_start, parent_step, parent_root = _verify_parent(
        args.parent_artifact_dir, artifact_digest=args.parent_artifact_digest
    )
    del parent_summary
    (
        summary,
        step_rows,
        root_rows,
        fixed_rows,
        guard_rows,
        topology_rows,
        density_rows,
        branch_rows,
        U_before,
        U_after,
    ) = _run(
        contract=contract,
        b1_contract=b1_contract,
        U_start=U_start,
        parent_step=parent_step,
        parent_root=parent_root,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "finite_compression_steps.csv", step_rows)
    _write_csv(output / "finite_compression_roots.csv", root_rows)
    _write_csv(output / "hugoniot_fixed_scans.csv", fixed_rows)
    _write_csv(output / "guard_front_refinement.csv", guard_rows)
    _write_csv(output / "root_topology.csv", topology_rows)
    _write_csv(output / "hugoniot_density_search.csv", density_rows)
    _write_csv(output / "branch_sequence.csv", branch_rows)
    np.savez_compressed(
        output / "finite_compression_8_step_states.npz",
        U_before=U_before,
        U_after=U_after,
        solver_step_before=np.asarray([STARTING_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
    )
    (output / "authority_verification.json").write_text(
        json.dumps(
            {
                "parent_source_sha": PARENT_SOURCE_SHA,
                "parent_run": PARENT_RUN,
                "parent_job": PARENT_JOB,
                "parent_artifact": PARENT_ARTIFACT,
                "parent_artifact_name": PARENT_ARTIFACT_NAME,
                "parent_artifact_sha256": PARENT_DIGEST,
                "verified": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "stop_evidence.json").write_text(
        json.dumps(
            {
                "classification": summary["stop_classification"],
                "reason": summary["stop_reason"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(
        "# Increment 8C Guard-front refined 8-step continuation\n\n"
        "The authoritative step-494 state was loaded. A new general-EOS "
        "Hugoniot and B1-success root were recomputed before every actual "
        "FvmSolver update. Failed B1 states remained unavailable and never "
        "formed a root endpoint or applied flux. Formal states remain false.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "finite_compression_steps.csv",
        "finite_compression_roots.csv",
        "hugoniot_fixed_scans.csv",
        "guard_front_refinement.csv",
        "root_topology.csv",
        "hugoniot_density_search.csv",
        "branch_sequence.csv",
        "finite_compression_8_step_states.npz",
        "authority_verification.json",
        "stop_evidence.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_8c_8_step_gate_passed"]:
        raise SystemExit(
            "Increment 8C 8-step gate did not pass: "
            f"{summary['stop_classification']} {summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
