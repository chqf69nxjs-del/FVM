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
    normalize_phase,
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


def _complete_root_row_dynamic_v4(
    *,
    root: dict[str, Any],
    evaluate,
    adapter: Any,
    area_m2: float,
    quadrature_order: int,
) -> dict[str, Any]:
    """V4 root completion with an admissible-domain-aware 1 Pa slope probe.

    The retained robustness diagnostic uses a central +/-1 Pa derivative.  In
    an evolving finite-pipe cell the physical root may approach the interior
    pressure from below, making p_root + 1 Pa lie outside the characteristic
    outflow domain even though the connected root itself remains admissible.

    This function keeps the same retained 1 Pa probe distance.  It uses the
    central stencil when both sides are admissible and a one-sided 1 Pa stencil
    only when one side is outside the admissible domain.  No root, energy,
    momentum, phase, conservation, or physics tolerance is changed.
    """

    pressure = float(root["pressure_pa"])
    delta = float(robustness.SLOPE_DELTA_P_PA)
    lower = evaluate(pressure - delta)
    upper = evaluate(pressure + delta)
    root_residual = float(root["residual_kg_s"])
    lower_ok = bool(lower.get("evaluation_succeeded"))
    upper_ok = bool(upper.get("evaluation_succeeded"))
    if lower_ok and upper_ok:
        slope = (
            float(upper["residual_kg_s"]) - float(lower["residual_kg_s"])
        ) / (2.0 * delta)
        slope_scheme = "central_retained_1_pa"
    elif lower_ok:
        slope = (root_residual - float(lower["residual_kg_s"])) / delta
        slope_scheme = "backward_admissible_retained_1_pa"
    elif upper_ok:
        slope = (float(upper["residual_kg_s"]) - root_residual) / delta
        slope_scheme = "forward_admissible_retained_1_pa"
    else:
        raise RuntimeError(
            "both retained 1 Pa slope probes around the root are inadmissible"
        )

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

    row: dict[str, Any] = {
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
        "root_mass_residual_kg_s": root_residual,
        "local_residual_slope_kg_s_Pa": slope,
        "local_residual_slope_scheme": slope_scheme,
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

    pipe_mass_rate = float(row["pipe_mass_rate_kg_s"])
    b1_mass_rate = float(row["b1_mass_rate_kg_s"])
    if pipe_mass_rate <= 0.0 or b1_mass_rate <= 0.0:
        raise AssertionError("A1 dynamic root must have positive mass rates")

    h0_pipe = pipe_energy_rate / pipe_mass_rate
    h0_b1 = b1_energy_rate / b1_mass_rate
    h0_round_trip_residual = h0_pipe - h0_b1
    expected_from_mass_residual = h0_pipe * root_residual
    energy_mass_consistency_residual = energy_residual - expected_from_mass_residual
    roundoff_allowed = (
        robustness_v4.ENERGY_CONSISTENCY_ROUNDOFF_FACTOR
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
        * robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
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
            "stagnation_enthalpy_round_trip_residual_J_kg": h0_round_trip_residual,
            "locked_stagnation_enthalpy_round_trip_absolute_J_kg": (
                robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
            "energy_expected_from_mass_residual_W": expected_from_mass_residual,
            "energy_mass_consistency_residual_W": energy_mass_consistency_residual,
            "energy_consistency_roundoff_allowed_W": roundoff_allowed,
            "energy_h0_round_trip_allowed_W": h0_round_trip_energy_allowed,
            "energy_mass_consistency_allowed_W": consistency_allowed,
            "energy_allowed_from_locked_root_and_h0_tolerances_W": (
                total_energy_allowed
            ),
            "stagnation_enthalpy_round_trip_passed": bool(
                abs(h0_round_trip_residual)
                <= robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
            "energy_mass_consistency_passed": bool(
                abs(energy_mass_consistency_residual) <= consistency_allowed
            ),
            "energy_port_closure_passed": bool(
                abs(energy_residual) <= total_energy_allowed
                and abs(energy_mass_consistency_residual) <= consistency_allowed
                and abs(h0_round_trip_residual)
                <= robustness_v4.STAGNATION_ENTHALPY_ROUND_TRIP_ABSOLUTE_J_KG
            ),
        }
    )
    return row


def _solve_two_l_over_c0_root(
    *,
    contract: dict[str, Any],
    case_id: str,
    state_id: str,
    provider: Any,
    adapter: Any,
    area_m2: float,
    outlet_conserved: np.ndarray,
    solver_time_s: float,
    previous_root_pressure_pa: float | None,
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
            f"outlet phase {static.phase!r} is outside {sorted(allowed_phases)}"
        )
    if static.velocity_m_s < -velocity_tolerance:
        raise DynamicDiagnosticStop(
            f"reverse outlet-cell velocity before root solve: {static.velocity_m_s} m/s"
        )

    back_pressure = float(adapter.back_pressure_pa)
    if not static.pressure_pa > back_pressure:
        raise DynamicDiagnosticStop(
            "root domain disappeared because outlet pressure is not above "
            f"back pressure: p_i={static.pressure_pa}, p_back={back_pressure}"
        )

    tolerances = contract["acceptance_tolerances"]
    if abs(reconstruction.enthalpy_round_trip_residual_J_kg) > float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    ) or abs(reconstruction.entropy_round_trip_residual_J_kg_K) > float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    ):
        raise DynamicDiagnosticStop(
            "outlet stagnation-state round trip exceeds locked tolerance"
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

    pressures = list(
        np.linspace(
            float(static.pressure_pa),
            back_pressure,
            CONNECTED_SCAN_NODE_COUNT,
        )
    )
    previous = previous_root_pressure_pa
    if previous is not None and back_pressure < previous < static.pressure_pa:
        pressures.append(float(previous))
    pressures = sorted(set(float(value) for value in pressures), reverse=True)

    scan_rows: list[dict[str, Any]] = []
    scan_stop_reason: str | None = None
    for pressure in pressures:
        scan = evaluate(pressure)
        if not scan.get("evaluation_succeeded"):
            scan_stop_reason = (
                f"inadmissible connected scan node p={pressure}: "
                f"{scan.get('formal_outcome')} {scan.get('formal_message')}"
            )
            break
        mach = float(scan["mach"])
        if not 0.0 <= mach < 1.0:
            scan_stop_reason = (
                f"connected scan left subsonic branch at p={pressure}, Mach={mach}"
            )
            break
        scan_rows.append(scan)

    if len(scan_rows) < 2:
        raise DynamicDiagnosticStop(
            "connected subsonic scan has fewer than two admissible nodes; "
            f"stop={scan_stop_reason}"
        )
    residuals = [float(scan["residual_kg_s"]) for scan in scan_rows]
    monotone = all(
        residuals[index + 1] >= residuals[index]
        for index in range(len(residuals) - 1)
    )
    brackets = diagnostic.find_sign_change_brackets(scan_rows)
    if not monotone:
        raise DynamicDiagnosticStop(
            "connected residual scan is non-monotone; unique root branch is inconclusive"
        )
    if len(brackets) != 1:
        raise DynamicDiagnosticStop(
            "connected subsonic scan did not retain exactly one root branch: "
            f"sign_changes={len(brackets)}, stop={scan_stop_reason}"
        )

    root = robustness._bisection_root(
        lower_pressure_pa=brackets[0][0],
        upper_pressure_pa=brackets[0][1],
        evaluate=evaluate,
    )
    completed = _complete_root_row_dynamic_v4(
        root=root,
        evaluate=evaluate,
        adapter=adapter,
        area_m2=area_m2,
        quadrature_order=ROOT_QUADRATURE_ORDER,
    )
    merged = dict(root)
    merged.update(completed)

    if abs(float(merged["root_mass_residual_kg_s"])) > float(
        robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    ):
        raise DynamicDiagnosticStop("root mass residual exceeds retained limit")
    if float(merged["local_residual_slope_kg_s_Pa"]) >= 0.0:
        raise DynamicDiagnosticStop("root local residual slope is not negative")
    if not 0.0 <= float(merged["mach"]) < 1.0:
        raise DynamicDiagnosticStop("root is outside the subsonic branch")
    if float(merged["velocity_m_s"]) < -velocity_tolerance:
        raise DynamicDiagnosticStop("root velocity is reverse-directed")
    if not bool(merged["stagnation_enthalpy_round_trip_passed"]):
        raise DynamicDiagnosticStop(
            "root stagnation-enthalpy round trip exceeds locked B2 tolerance"
        )
    if not bool(merged["energy_mass_consistency_passed"]):
        raise DynamicDiagnosticStop(
            "root energy/mass ledger decomposition does not close"
        )
    if not bool(merged["energy_port_closure_passed"]):
        raise DynamicDiagnosticStop(
            "root energy-port ledger does not close under retained mass-root and "
            "locked h0 round-trip tolerances"
        )
    if abs(float(merged["momentum_ledger_residual_N"])) > float(
        robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    ):
        raise DynamicDiagnosticStop("restriction reaction ledger does not close")

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
        "connected_scan_base_node_count": CONNECTED_SCAN_NODE_COUNT,
        "connected_scan_requested_nodes": len(pressures),
        "connected_scan_admissible_subsonic_nodes": len(scan_rows),
        "connected_scan_lowest_pressure_pa": float(scan_rows[-1]["pressure_pa"]),
        "connected_scan_stop_reason": scan_stop_reason,
        "connected_scan_residual_monotone": monotone,
        "connected_scan_sign_change_count": len(brackets),
        "root": merged,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
    }


class A1TwoLOverC0Hook(A1DynamicShortHook):
    """A1 hook with dynamic-domain-aware slope diagnostics only."""

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        context = _solve_two_l_over_c0_root(
            contract=self.contract,
            case_id=self.case_id,
            state_id=self.state_id,
            provider=self.provider,
            adapter=self.adapter,
            area_m2=self.area_m2,
            outlet_conserved=U[-1],
            solver_time_s=t,
            previous_root_pressure_pa=self._previous_root_pressure_pa,
        )
        self.root_context = context
        self.flux = np.array(context["flux"], copy=True)
        self._cache_t = float(t)
        self._cache_outlet = np.array(U[-1], copy=True)
        self.trial_dts_s = []


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
        right_external_face_flux_override=A1TwoLOverC0Hook(
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
    if not isinstance(hook, A1TwoLOverC0Hook):
        raise AssertionError("A1 two-L-over-c0 hook was not installed")

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
                    "local_residual_slope_scheme": root_context["root"][
                        "local_residual_slope_scheme"
                    ],
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
        "local_residual_slope_scheme_counts": dict(
            Counter(str(row["local_residual_slope_scheme"]) for row in complete_rows)
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
        "schema_version": "stage7_u3_b2_characteristic_port_two_l_over_c0_v2",
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
            "local_slope_probe_distance_pa": robustness.SLOPE_DELTA_P_PA,
            "local_slope_scheme": (
                "central retained 1 Pa when admissible; otherwise one-sided "
                "retained 1 Pa entirely inside the admissible characteristic domain"
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
        "For the local residual-slope sign check, the retained 1 Pa probe is "
        "central when both sides are inside the characteristic domain and "
        "one-sided when a central probe would leave that admissible domain. "
        "The probe distance and negative-slope requirement are unchanged.\n\n"
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
