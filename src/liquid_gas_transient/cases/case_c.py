"""Case C Ver.0.5.0: component network with property-backend EOS adapters.

Ver.0.2.2 proved that an ESD valve can be placed inside the FVM domain as a
left-cell/right-cell interface. Ver.0.2.7 keeps the verified internal ESD interface, segment-wise
friction/elevation source profiles, and quasi-steady pump-discharge boundary,
then upgrades the downstream ship-tank pressure boundary to an explicit
PressureTankBoundary with a flow-direction policy:

    land tank -> pump -> onshore line -> jetty line -> ESD valve
    -> loading arm -> ship tank

The numerical core is still a uniform-diameter, one-dimensional FVM model.
Ver.0.4.2 can optionally enable the toy HEM flash model or the HNE
relaxation model and reports Case-C-level two-phase diagnostics and phase-change vapor budget diagnostics. It is still not a real-fluid
LCO2 model or a validated dynamic pump-stop model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import numpy as np

from ..boundary import ConstantPressure, PressureTankBoundary
from ..config import NumericsConfig, TimeConfig
from ..eos import EOSModel, LCO2PropertyEOSAdapter, LinearLiquidEOS, ToyHEMEOS
from ..properties import CoolPropCO2Backend, SurrogateLCO2PropertyBackend
from ..interfaces import InternalValveInterface
from ..network import (
    ComponentNetwork,
    DiscretizedNetwork,
    PipeSegmentSpec,
    PumpInterfaceSpec,
    TankBoundarySpec,
    ValveInterfaceSpec,
    discretize_network,
)
from ..hem_diagnostics import HEMDiagnosticsConfig, summarize_hem_state
from ..phase_change import HEMPhaseChange, HNERelaxationPhaseChange, NoPhaseChange
from ..pump import ConstantPumpHead, LinearPumpTrip, PumpHeadSchedule, PumpInletBoundary
from ..solver import FvmSolver
from ..source_terms import CellwisePipeSourceTerms
from ..state import make_conserved
from ..valve import KvLiquidValve, LinearRampOpening


@dataclass(frozen=True)
class CaseCParameters:
    """Simplified Case C parameters for Ver.0.4.2.

    Segment lengths define the benchmark topology. ``esd_valve_position_m`` is
    retained as a compatibility override: if provided, the upstream side is split
    equally into onshore and jetty pipe lengths and the remainder is assigned to
    the loading arm.
    """

    length_m: float = 2500.0
    diameter_m: float = 0.30
    n_cells: int = 400

    onshore_line_length_m: float = 900.0
    jetty_line_length_m: float = 900.0
    loading_arm_length_m: float = 700.0
    esd_valve_position_m: float | None = None

    rho_ref_kg_m3: float = 930.0
    p_ref_pa: float = 2.0e6
    sound_speed_m_s: float = 750.0
    upstream_initial_pressure_pa: float = 2.0e6
    downstream_initial_pressure_pa: float = 1.9e6
    initial_velocity_m_s: float = 1.5
    internal_energy_j_kg: float = 1.0e5
    # Segment-wise source-term parameters for Ver.0.2.4.
    # The legacy global friction factor is kept as a fallback override for
    # compatibility with older tests and scripts.
    darcy_friction_factor: float | None = None
    onshore_darcy_friction_factor: float = 0.010
    jetty_darcy_friction_factor: float = 0.012
    loading_arm_darcy_friction_factor: float = 0.018

    onshore_elevation_start_m: float = 0.0
    onshore_elevation_end_m: float = 2.0
    jetty_elevation_start_m: float = 2.0
    jetty_elevation_end_m: float = 5.0
    loading_arm_elevation_start_m: float = 5.0
    loading_arm_elevation_end_m: float = 15.0

    valve_kv_m3_h: float | None = None
    valve_close_start_s: float = 0.05
    valve_close_time_s: float = 0.02

    pump_delta_p_nominal_pa: float = 0.0
    pump_trip_start_s: float | None = None
    pump_trip_duration_s: float = 0.0
    pump_delta_p_final_pa: float = 0.0
    t_end_s: float = 0.20
    cfl: float = 0.5

    downstream_tank_flow_direction: str = "outlet_only"
    downstream_tank_velocity_policy: str = "copy"

    # Ver.0.3/0.4 two-phase diagnostics. Disabled by default so all Ver.0.2.x
    # single-phase verification remains a strict regression test.
    enable_hem: bool = False
    phase_change_model: str = "auto"  # auto, none, hem, hne
    hne_tau_s: float = 0.05
    hem_rho_l_sat_kg_m3: float = 930.0
    hem_rho_v_sat_kg_m3: float = 40.0
    hem_p_sat_pa: float = 1.9e6
    hem_c_two_phase_min_m_s: float = 80.0
    hem_high_elevation_min_m: float = 10.0
    hem_alpha_threshold: float = 1.0e-6
    hem_xv_threshold: float = 1.0e-8

    # Ver.0.4.2/0.4.3 energy/source/interface budget. This is diagnostic only for the toy
    # HEM/HNE model; it does not alter rhoE.
    latent_heat_placeholder_j_kg: float = 0.0

    # Ver.0.5.0 property backend adapter.  ``auto`` preserves all earlier
    # behavior: LinearLiquidEOS for phase_change_model=none and ToyHEMEOS for
    # HEM/HNE.  Explicit ``lco2_surrogate`` routes all states through the new
    # adapter without requiring external packages. ``coolprop_lco2`` is an
    # optional dependency path and is not used by default verification.
    eos_model: str = "auto"  # auto, linear, toy_hem, lco2_surrogate, coolprop_lco2
    lco2_boundary_temperature_K: float = 253.15
    lco2_quality_source: str = "transported"  # transported or backend


def _segment_lengths(p: CaseCParameters) -> tuple[float, float, float]:
    """Return onshore, jetty, loading-arm lengths for the ordered network."""

    if p.esd_valve_position_m is not None:
        if not 0.0 < p.esd_valve_position_m < p.length_m:
            raise ValueError("esd_valve_position_m must lie inside the total pipe length")
        upstream_total = p.esd_valve_position_m
        return 0.5 * upstream_total, 0.5 * upstream_total, p.length_m - upstream_total

    total = p.onshore_line_length_m + p.jetty_line_length_m + p.loading_arm_length_m
    if not np.isclose(total, p.length_m, rtol=1.0e-12, atol=1.0e-9):
        raise ValueError(
            "segment lengths must sum to length_m unless esd_valve_position_m is provided; "
            f"got segment sum {total}, length_m {p.length_m}"
        )
    return p.onshore_line_length_m, p.jetty_line_length_m, p.loading_arm_length_m


def effective_phase_change_model(p: CaseCParameters) -> str:
    """Return normalized phase-change model name for Case C.

    ``phase_change_model="auto"`` preserves Ver.0.3.1 behavior: ``enable_hem=True``
    selects HEM; otherwise no phase-change operator is applied. Explicit values
    ``none``, ``hem`` and ``hne`` are preferred for new work.
    """

    model = p.phase_change_model.lower().strip()
    if model == "auto":
        return "hem" if p.enable_hem else "none"
    if model not in {"none", "hem", "hne"}:
        raise ValueError("phase_change_model must be one of: auto, none, hem, hne")
    return model


def effective_eos_model(p: CaseCParameters) -> str:
    """Return normalized EOS selector for Case C."""

    model = p.eos_model.lower().strip()
    valid = {"auto", "linear", "toy_hem", "lco2_surrogate", "coolprop_lco2"}
    if model not in valid:
        raise ValueError(f"eos_model must be one of: {', '.join(sorted(valid))}")
    if model == "auto":
        return "toy_hem" if effective_phase_change_model(p) in {"hem", "hne"} else "linear"
    return model


def _build_eos(p: CaseCParameters) -> EOSModel:
    model = effective_eos_model(p)
    if model == "toy_hem":
        return ToyHEMEOS(
            rho_l_sat=p.hem_rho_l_sat_kg_m3,
            rho_v_sat=p.hem_rho_v_sat_kg_m3,
            p_sat=p.hem_p_sat_pa,
            c_liquid=p.sound_speed_m_s,
            c_two_phase_min=p.hem_c_two_phase_min_m_s,
            e_ref=p.internal_energy_j_kg,
        )
    if model == "lco2_surrogate":
        backend = SurrogateLCO2PropertyBackend(
            p_sat_ref_pa=p.hem_p_sat_pa,
            T_sat_ref_K=p.lco2_boundary_temperature_K,
            rho_l_ref_kg_m3=p.hem_rho_l_sat_kg_m3,
            rho_v_ref_kg_m3=p.hem_rho_v_sat_kg_m3,
            c_liquid_m_s=p.sound_speed_m_s,
            c_two_phase_min_m_s=p.hem_c_two_phase_min_m_s,
            e_l_ref_j_kg=p.internal_energy_j_kg,
            latent_heat_ref_j_kg=max(p.latent_heat_placeholder_j_kg, 2.0e5),
        )
        return LCO2PropertyEOSAdapter(
            backend=backend,
            boundary_temperature_K=p.lco2_boundary_temperature_K,
            quality_source=p.lco2_quality_source,
        )
    if model == "coolprop_lco2":
        return LCO2PropertyEOSAdapter(
            backend=CoolPropCO2Backend(),
            boundary_temperature_K=p.lco2_boundary_temperature_K,
            quality_source=p.lco2_quality_source,
        )
    return LinearLiquidEOS(
        rho_ref=p.rho_ref_kg_m3,
        p_ref=p.p_ref_pa,
        c_ref=p.sound_speed_m_s,
        e_ref=p.internal_energy_j_kg,
    )


def build_phase_change_model(p: CaseCParameters):
    """Return the operator-split phase-change model for Case C."""

    model = effective_phase_change_model(p)
    if model == "none":
        return NoPhaseChange()
    if model == "hem":
        return HEMPhaseChange()
    if model == "hne":
        return HNERelaxationPhaseChange(tau_s=p.hne_tau_s)
    raise AssertionError(f"unreachable phase_change_model: {model}")


def phase_diagnostics_prefix(p: CaseCParameters) -> str:
    """Return CSV prefix used for phase diagnostics."""

    model = effective_phase_change_model(p)
    if model == "hem":
        return "hem_"
    if model == "hne":
        return "hne_"
    return "phase_"


def build_hem_diagnostics_config(p: CaseCParameters) -> HEMDiagnosticsConfig:
    return HEMDiagnosticsConfig(
        alpha_threshold=p.hem_alpha_threshold,
        xv_threshold=p.hem_xv_threshold,
        high_elevation_min_m=p.hem_high_elevation_min_m,
    )


def build_pump_head_schedule(p: CaseCParameters) -> PumpHeadSchedule:
    """Return the quasi-steady pump-head schedule retained in Ver.0.2.6."""

    if p.pump_trip_start_s is None:
        return ConstantPumpHead(delta_p_pa=p.pump_delta_p_nominal_pa)
    return LinearPumpTrip(
        delta_p_initial_pa=p.pump_delta_p_nominal_pa,
        trip_start_s=p.pump_trip_start_s,
        trip_duration_s=p.pump_trip_duration_s,
        delta_p_final_pa=p.pump_delta_p_final_pa,
    )


def pump_discharge_pressure_pa(p: CaseCParameters, t: float) -> float:
    """Return tank pressure plus pump pressure rise at time ``t``."""

    return float(p.upstream_initial_pressure_pa + build_pump_head_schedule(p).head_rise_pa(t))


def _segment_friction_values(p: CaseCParameters) -> tuple[float, float, float]:
    """Return segment friction values, honoring the legacy global override."""

    if p.darcy_friction_factor is not None:
        return (
            p.darcy_friction_factor,
            p.darcy_friction_factor,
            p.darcy_friction_factor,
        )
    return (
        p.onshore_darcy_friction_factor,
        p.jetty_darcy_friction_factor,
        p.loading_arm_darcy_friction_factor,
    )


def build_case_c_network(params: CaseCParameters | None = None) -> ComponentNetwork:
    """Return the ordered component network for Case C."""

    p = params or CaseCParameters()
    onshore_len, jetty_len, loading_len = _segment_lengths(p)
    f_onshore, f_jetty, f_loading = _segment_friction_values(p)
    return ComponentNetwork(
        name="case_c_land_side_esd_closure",
        inlet_tank=TankBoundarySpec(
            name="land_storage_tank",
            pressure_pa=p.upstream_initial_pressure_pa,
            side="left",
        ),
        outlet_tank=TankBoundarySpec(
            name="ship_tank",
            pressure_pa=p.downstream_initial_pressure_pa,
            side="right",
        ),
        pump=PumpInterfaceSpec(
            name="transfer_pump",
            after_component="land_storage_tank",
            delta_p_nominal_pa=p.pump_delta_p_nominal_pa,
            trip_time_s=p.pump_trip_start_s,
            trip_duration_s=p.pump_trip_duration_s,
            delta_p_final_pa=p.pump_delta_p_final_pa,
        ),
        pipe_segments=(
            PipeSegmentSpec(
                name="onshore_line",
                length_m=onshore_len,
                diameter_m=p.diameter_m,
                darcy_friction_factor=f_onshore,
                elevation_start_m=p.onshore_elevation_start_m,
                elevation_end_m=p.onshore_elevation_end_m,
            ),
            PipeSegmentSpec(
                name="jetty_line",
                length_m=jetty_len,
                diameter_m=p.diameter_m,
                darcy_friction_factor=f_jetty,
                elevation_start_m=p.jetty_elevation_start_m,
                elevation_end_m=p.jetty_elevation_end_m,
            ),
            PipeSegmentSpec(
                name="loading_arm",
                length_m=loading_len,
                diameter_m=p.diameter_m,
                darcy_friction_factor=f_loading,
                elevation_start_m=p.loading_arm_elevation_start_m,
                elevation_end_m=p.loading_arm_elevation_end_m,
            ),
        ),
        esd_valve=ValveInterfaceSpec(
            name="land_side_esd_valve",
            upstream_segment="jetty_line",
            downstream_segment="loading_arm",
            kv_m3_h=p.valve_kv_m3_h,
            close_start_s=p.valve_close_start_s,
            close_time_s=p.valve_close_time_s,
        ),
        metadata={"version": f"0.5.0-{effective_phase_change_model(p)}-{effective_eos_model(p)}-property-adapter"},
    )


def build_discretized_case_c_network(params: CaseCParameters | None = None) -> DiscretizedNetwork:
    """Return the flattened FVM grid mapping for Case C."""

    p = params or CaseCParameters()
    return discretize_network(build_case_c_network(p), total_cells=p.n_cells)


def _initial_state(discretized: DiscretizedNetwork, eos: EOSModel, p: CaseCParameters) -> np.ndarray:
    valve_face = discretized.device_face("land_side_esd_valve")
    p0 = np.empty(discretized.grid.n_cells, dtype=float)
    p0[:valve_face] = pump_discharge_pressure_pa(p, t=0.0)
    p0[valve_face:] = p.downstream_initial_pressure_pa
    rho0 = eos.density_from_pressure(p0)
    return make_conserved(
        rho=rho0,
        u=np.full(discretized.grid.n_cells, p.initial_velocity_m_s),
        e=np.full(discretized.grid.n_cells, p.internal_energy_j_kg),
        xv=np.zeros(discretized.grid.n_cells),
    )


def calibrated_valve_kv(params: CaseCParameters) -> float:
    """Return default Kv that matches initial flow across the ESD valve."""

    network = build_discretized_case_c_network(params)
    eos = _build_eos(params)
    p_up0 = pump_discharge_pressure_pa(params, t=0.0)
    rho_up = float(eos.density_from_pressure(p_up0))
    q0 = params.initial_velocity_m_s * network.geometry.area_m2
    dp = p_up0 - params.downstream_initial_pressure_pa
    return KvLiquidValve.kv_for_target_flow(q_m3_s=q0, delta_p_pa=dp, rho_kg_m3=rho_up)


def build_case_c_solver(params: CaseCParameters | None = None) -> FvmSolver:
    """Build a Ver.0.5.0 Case C solver from the component network."""

    p = params or CaseCParameters()
    numerics = NumericsConfig(n_cells=p.n_cells, cfl=p.cfl)
    discretized = build_discretized_case_c_network(p)
    eos = _build_eos(p)
    U0 = _initial_state(discretized, eos, p)

    kv = calibrated_valve_kv(p) if p.valve_kv_m3_h is None else p.valve_kv_m3_h
    valve = KvLiquidValve(kv_m3_per_h=kv, allow_reverse_flow=False)
    opening = LinearRampOpening(
        t_start_s=p.valve_close_start_s,
        duration_s=p.valve_close_time_s,
        open_initial=1.0,
        open_final=0.0,
    )
    valve_face = discretized.device_face("land_side_esd_valve")
    internal_valve = InternalValveInterface(
        left_cell=valve_face - 1,
        area_m2=discretized.geometry.area_m2,
        valve=valve,
        opening_schedule=opening,
    )

    source = CellwisePipeSourceTerms.from_discretized_network(
        discretized,
        local_loss_k=0.0,
        include_gravity_energy_source=True,
    )

    return FvmSolver(
        grid=discretized.grid,
        eos=eos,
        U=U0,
        cfl=numerics.cfl,
        n_ghost=numerics.n_ghost,
        left_boundary=PumpInletBoundary(
            suction_pressure_pa=p.upstream_initial_pressure_pa,
            head_schedule=build_pump_head_schedule(p),
        ),
        right_boundary=PressureTankBoundary(
            pressure_schedule=ConstantPressure(p.downstream_initial_pressure_pa),
            flow_direction=p.downstream_tank_flow_direction,
            velocity_policy=p.downstream_tank_velocity_policy,
        ),
        source_term=source,
        phase_change=build_phase_change_model(p),
        internal_interfaces=(internal_valve,),
        latent_heat_placeholder_j_kg=p.latent_heat_placeholder_j_kg,
    )


def build_case_c_hem_solver(params: CaseCParameters | None = None) -> FvmSolver:
    """Build Case C with instantaneous toy HEM flash enabled."""

    p = params or CaseCParameters()
    return build_case_c_solver(replace(p, enable_hem=True, phase_change_model="hem"))


def build_case_c_hne_solver(params: CaseCParameters | None = None) -> FvmSolver:
    """Build Case C with finite-rate HNE relaxation enabled."""

    p = params or CaseCParameters()
    return build_case_c_solver(replace(p, phase_change_model="hne"))


def _case_c_sample(
    solver: FvmSolver,
    discretized: DiscretizedNetwork,
    p: CaseCParameters,
    dt: float,
) -> dict[str, float]:
    sample = (
        solver.diagnostics(dt=dt)
        | solver.internal_interfaces[0].diagnostics(U=solver.U, eos=solver.eos, t=solver.t)
        | solver.left_boundary.diagnostics(solver.t)
    )
    if effective_phase_change_model(p) in {"hem", "hne"}:
        sample |= summarize_hem_state(
            solver,
            discretized,
            build_hem_diagnostics_config(p),
            prefix=phase_diagnostics_prefix(p),
        )
    return sample


def run_case_c(params: CaseCParameters | None = None) -> list[dict[str, float]]:
    """Run the Case C network model and return diagnostic history."""

    p = params or CaseCParameters()
    discretized = build_discretized_case_c_network(p)
    solver = build_case_c_solver(p)
    time_cfg = TimeConfig(t_end_s=p.t_end_s)
    history: list[dict[str, float]] = [_case_c_sample(solver, discretized, p, dt=0.0)]
    while solver.t < time_cfg.t_end_s:
        dt = solver.compute_dt(time_cfg.t_end_s)
        solver.step(dt)
        if solver.step_count % 10 == 0 or solver.t >= time_cfg.t_end_s:
            history.append(_case_c_sample(solver, discretized, p, dt=dt))
    return history


def main() -> None:
    p = CaseCParameters()
    discretized = build_discretized_case_c_network(p)
    solver = build_case_c_solver(p)
    history = solver.run(p.t_end_s, max_steps=100_000, sample_every=10)
    valve = solver.internal_interfaces[0]
    summary = {
        "version": f"0.5.0-{effective_phase_change_model(p)}-{effective_eos_model(p)}-property-adapter",
        "network": discretized.summary(),
        "pump_discharge_pressure_initial_pa": pump_discharge_pressure_pa(p, 0.0),
        "pump_discharge_pressure_final_pa": pump_discharge_pressure_pa(p, solver.t),
        "calibrated_valve_kv_m3_h": calibrated_valve_kv(p),
        "valve_face_index": valve.left_cell + 1,
        "valve_left_cell": valve.left_cell,
        "n_samples": len(history),
        "initial": history[0],
        "final": history[-1],
        "final_valve": valve.diagnostics(U=solver.U, eos=solver.eos, t=solver.t),
        "final_pump": solver.left_boundary.diagnostics(solver.t),
    }
    if effective_phase_change_model(p) in {"hem", "hne"}:
        summary[f"final_{effective_phase_change_model(p)}"] = summarize_hem_state(
            solver,
            discretized,
            build_hem_diagnostics_config(p),
            prefix=phase_diagnostics_prefix(p),
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
