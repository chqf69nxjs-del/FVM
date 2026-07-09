"""Initial smoke tests for the Ver.0.2 skeleton."""

from __future__ import annotations

from pathlib import Path
import numpy as np

from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.flux import physical_flux, rusanov_flux
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import make_conserved
from liquid_gas_transient.cases.case_c import CaseCParameters, build_case_c_solver


def test_rusanov_equals_physical_flux_for_identical_states() -> None:
    eos = LinearLiquidEOS()
    U = make_conserved(rho=np.array([1000.0]), u=np.array([1.0]), e=np.array([1.0e5]), xv=np.array([0.0]))
    prim = eos.primitive_from_conserved(U)
    np.testing.assert_allclose(rusanov_flux(U, U, eos), physical_flux(U, prim), rtol=1e-12, atol=1e-12)


def test_uniform_field_remains_uniform_for_one_step() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=20)
    eos = LinearLiquidEOS()
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.full(grid.n_cells, 1.0),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    solver = FvmSolver(grid=grid, eos=eos, U=U, cfl=0.5)
    solver.step()
    np.testing.assert_allclose(solver.U, U, rtol=1e-12, atol=1e-9)


def test_case_c_skeleton_builds_and_steps() -> None:
    params = CaseCParameters(n_cells=50, t_end_s=0.005)
    solver = build_case_c_solver(params)
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    assert history[-1]["time_s"] == params.t_end_s
    assert history[-1]["rho_min_kg_m3"] > 0.0

from liquid_gas_transient.boundary import ValveOutletBoundary
from liquid_gas_transient.valve import ConstantOpening, KvLiquidValve, LinearRampOpening


def test_linear_ramp_opening_closes_monotonically() -> None:
    schedule = LinearRampOpening(t_start_s=1.0, duration_s=2.0)
    assert schedule.opening(0.0) == 1.0
    assert schedule.opening(2.0) == 0.5
    assert schedule.opening(4.0) == 0.0


def test_kv_liquid_valve_matches_target_flow() -> None:
    rho = 930.0
    dp = 1.0e5
    q = 0.10602875205865553
    kv = KvLiquidValve.kv_for_target_flow(q_m3_s=q, delta_p_pa=dp, rho_kg_m3=rho)
    valve = KvLiquidValve(kv_m3_per_h=kv)
    np.testing.assert_allclose(
        valve.flow_rate_m3_s(p_up_pa=2.0e6, p_down_pa=1.9e6, rho_kg_m3=rho, opening=1.0),
        q,
        rtol=1e-12,
        atol=1e-12,
    )


def test_closed_valve_boundary_reduces_to_reflective_wall() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=4)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.full(grid.n_cells, 2.0),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    bc = ValveOutletBoundary(
        downstream_pressure_pa=1.0e5,
        area_m2=geometry.area_m2,
        valve=KvLiquidValve(kv_m3_per_h=100.0),
        opening_schedule=ConstantOpening(0.0),
    )
    solver = FvmSolver(grid=grid, eos=eos, U=U, right_boundary=bc)
    U_ext = solver.extend_with_ghosts(t=0.0)
    interior_momentum = U_ext[-solver.n_ghost - 1, 1]
    ghost_momentum = U_ext[-1, 1]
    np.testing.assert_allclose(ghost_momentum, -interior_momentum, rtol=1e-12, atol=1e-12)

from liquid_gas_transient.interfaces import InternalValveInterface
from liquid_gas_transient.boundary import ReflectiveBoundary
from liquid_gas_transient.state import inventory


def test_closed_internal_valve_reduces_to_two_reflective_walls() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=6)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.array([1.0, 1.0, 2.0, -3.0, -1.0, -1.0]),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    interface = InternalValveInterface(
        left_cell=2,
        area_m2=geometry.area_m2,
        valve=KvLiquidValve(kv_m3_per_h=100.0),
        opening_schedule=ConstantOpening(0.0),
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        internal_interfaces=(interface,),
    )
    U_ext = solver.extend_with_ghosts(0.0)
    flux = solver.flux_function(U_ext[:-1], U_ext[1:], eos)
    i0 = solver.n_ghost
    i1 = solver.n_ghost + grid.n_cells
    flux_left = flux[i0 - 1 : i1 - 1].copy()
    flux_right = flux[i0:i1].copy()
    interface.apply(flux_left=flux_left, flux_right=flux_right, U=U, eos=eos, t=0.0, flux_function=solver.flux_function)

    # Closed valve must block mass transfer on both sides.
    assert abs(flux_right[2, 0]) < 1.0e-12
    assert abs(flux_left[3, 0]) < 1.0e-12
    # But the two momentum fluxes are allowed to differ because each side sees
    # its own hydraulic wall state.
    assert flux_right[2, 1] > 0.0
    assert flux_left[3, 1] > 0.0


def test_open_internal_valve_conserves_total_mass_in_closed_domain() -> None:
    geometry = PipeGeometry(length_m=20.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=20)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    p0 = np.r_[np.full(10, 1.1e5), np.full(10, 1.0e5)]
    rho0 = eos.density_from_pressure(p0)
    U = make_conserved(rho=rho0, u=np.zeros(grid.n_cells), e=np.full(grid.n_cells, 1.0e5), xv=0.0)
    interface = InternalValveInterface(
        left_cell=9,
        area_m2=geometry.area_m2,
        valve=KvLiquidValve(kv_m3_per_h=50.0),
        opening_schedule=ConstantOpening(1.0),
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        internal_interfaces=(interface,),
    )
    m0 = inventory(solver.U, grid.dx, geometry.area_m2)["mass_total"]
    solver.run(0.002, max_steps=1000)
    m1 = inventory(solver.U, grid.dx, geometry.area_m2)["mass_total"]
    np.testing.assert_allclose(m1, m0, rtol=1e-12, atol=1e-9)


def test_case_c_internal_valve_builds_and_steps() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, build_case_c_solver

    params = CaseCParameters(n_cells=80, t_end_s=0.005, esd_valve_position_m=1200.0)
    solver = build_case_c_solver(params)
    assert len(solver.internal_interfaces) == 1
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    assert history[-1]["time_s"] == params.t_end_s
    assert history[-1]["rho_min_kg_m3"] > 0.0

from liquid_gas_transient.cases.case_c import build_case_c_network, build_discretized_case_c_network
from liquid_gas_transient.network import allocate_cells_by_length


def test_network_cell_allocation_sums_to_total() -> None:
    network = build_case_c_network(CaseCParameters(n_cells=40))
    counts = allocate_cells_by_length(network.pipe_segments, total_cells=40)
    assert sum(counts) == 40
    assert len(counts) == 3
    assert all(c > 0 for c in counts)


def test_case_c_network_topology_places_esd_between_jetty_and_loading_arm() -> None:
    params = CaseCParameters(n_cells=400)
    discretized = build_discretized_case_c_network(params)
    jetty_faces = discretized.segment_faces("jetty_line")
    loading_faces = discretized.segment_faces("loading_arm")
    esd_face = discretized.device_face("land_side_esd_valve")
    assert jetty_faces[1] == loading_faces[0] == esd_face
    assert discretized.segment_slice("onshore_line").start == 0
    assert discretized.segment_slice("loading_arm").stop == params.n_cells


def test_case_c_solver_is_built_from_network_interface_location() -> None:
    params = CaseCParameters(n_cells=80, t_end_s=0.005, esd_valve_position_m=1200.0)
    discretized = build_discretized_case_c_network(params)
    solver = build_case_c_solver(params)
    valve_face = discretized.device_face("land_side_esd_valve")
    assert solver.internal_interfaces[0].left_cell == valve_face - 1
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    assert history[-1]["time_s"] == params.t_end_s
    assert history[-1]["rho_min_kg_m3"] > 0.0

from liquid_gas_transient.source_terms import CellwisePipeSourceTerms


def test_cellwise_friction_decay_matches_exact_scalar_update() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.2)
    grid = UniformGrid(geometry=geometry, n_cells=4)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    u0 = np.array([1.0, 2.0, -1.5, 0.5])
    f = np.array([0.01, 0.02, 0.03, 0.04])
    diameter = np.array([0.2, 0.2, 0.3, 0.4])
    U = make_conserved(rho=np.full(grid.n_cells, 1000.0), u=u0, e=np.full(grid.n_cells, 1.0e5), xv=0.0)
    src = CellwisePipeSourceTerms(
        diameter_m=diameter,
        darcy_friction_factor=f,
        dzdx=0.0,
        include_gravity_energy_source=False,
    )
    dt = 0.25
    out = src.apply(U, grid, eos, dt, t=0.0)
    u1 = eos.primitive_from_conserved(out).u
    expected = u0 / (1.0 + (f / (2.0 * diameter)) * np.abs(u0) * dt)
    np.testing.assert_allclose(u1, expected, rtol=1e-12, atol=1e-12)


def test_cellwise_gravity_source_acceleration() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.2)
    grid = UniformGrid(geometry=geometry, n_cells=4)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    u0 = np.full(grid.n_cells, 2.0)
    dzdx = np.array([0.0, 0.1, -0.2, 0.3])
    U = make_conserved(rho=np.full(grid.n_cells, 1000.0), u=u0, e=np.full(grid.n_cells, 1.0e5), xv=0.0)
    src = CellwisePipeSourceTerms(
        diameter_m=geometry.diameter_m,
        darcy_friction_factor=0.0,
        dzdx=dzdx,
        gravity_m_s2=9.80665,
        include_gravity_energy_source=False,
    )
    dt = 0.1
    out = src.apply(U, grid, eos, dt, t=0.0)
    u1 = eos.primitive_from_conserved(out).u
    expected = u0 - 9.80665 * dzdx * dt
    np.testing.assert_allclose(u1, expected, rtol=1e-12, atol=1e-12)


def test_case_c_network_builds_segment_source_arrays() -> None:
    params = CaseCParameters(
        n_cells=100,
        onshore_darcy_friction_factor=0.011,
        jetty_darcy_friction_factor=0.022,
        loading_arm_darcy_friction_factor=0.033,
        onshore_elevation_start_m=0.0,
        onshore_elevation_end_m=1.0,
        jetty_elevation_start_m=1.0,
        jetty_elevation_end_m=4.0,
        loading_arm_elevation_start_m=4.0,
        loading_arm_elevation_end_m=9.0,
    )
    discretized = build_discretized_case_c_network(params)
    for name, expected_f in [
        ("onshore_line", 0.011),
        ("jetty_line", 0.022),
        ("loading_arm", 0.033),
    ]:
        sl = discretized.segment_slice(name)
        np.testing.assert_allclose(discretized.cell_darcy_friction_factor[sl], expected_f)
    assert np.isclose(discretized.total_static_head_change_m(), 9.0)
    assert np.max(discretized.cell_dzdx) > 0.0

from liquid_gas_transient.pump import ConstantPumpHead, LinearPumpTrip, PumpInletBoundary
from liquid_gas_transient.cases.case_c import pump_discharge_pressure_pa


def test_constant_pump_head_schedule() -> None:
    schedule = ConstantPumpHead(delta_p_pa=2.5e5)
    assert schedule.head_rise_pa(0.0) == 2.5e5
    assert schedule.head_rise_pa(100.0) == 2.5e5


def test_linear_pump_trip_schedule() -> None:
    schedule = LinearPumpTrip(
        delta_p_initial_pa=4.0e5,
        trip_start_s=1.0,
        trip_duration_s=2.0,
        delta_p_final_pa=5.0e4,
    )
    assert schedule.head_rise_pa(0.0) == 4.0e5
    np.testing.assert_allclose(schedule.head_rise_pa(2.0), 2.25e5, rtol=1e-12, atol=1e-12)
    assert schedule.head_rise_pa(4.0) == 5.0e4


def test_pump_inlet_boundary_sets_discharge_pressure_density() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=4)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.full(grid.n_cells, 1.0),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    bc = PumpInletBoundary(
        suction_pressure_pa=1.0e5,
        head_schedule=ConstantPumpHead(delta_p_pa=2.0e5),
    )
    solver = FvmSolver(grid=grid, eos=eos, U=U, left_boundary=bc)
    U_ext = solver.extend_with_ghosts(t=0.0)
    prim_g = eos.primitive_from_conserved(U_ext[: solver.n_ghost])
    np.testing.assert_allclose(prim_g.p, np.full(solver.n_ghost, 3.0e5), rtol=1e-12, atol=1e-9)


def test_case_c_pump_discharge_pressure_and_solver_build() -> None:
    params = CaseCParameters(
        n_cells=80,
        t_end_s=0.005,
        pump_delta_p_nominal_pa=2.5e5,
        esd_valve_position_m=1200.0,
    )
    assert pump_discharge_pressure_pa(params, 0.0) == params.upstream_initial_pressure_pa + 2.5e5
    solver = build_case_c_solver(params)
    assert hasattr(solver.left_boundary, "discharge_pressure_pa")
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    assert history[-1]["time_s"] == params.t_end_s
    assert history[-1]["rho_min_kg_m3"] > 0.0

from liquid_gas_transient.boundary import ConstantPressure, LinearPressureRamp, PressureTankBoundary
from liquid_gas_transient.state import IDX_MOM


def test_linear_pressure_ramp_schedule() -> None:
    schedule = LinearPressureRamp(p_initial_pa=2.0e5, p_final_pa=1.0e5, t_start_s=1.0, duration_s=2.0)
    assert schedule.pressure_pa(0.0) == 2.0e5
    np.testing.assert_allclose(schedule.pressure_pa(2.0), 1.5e5, rtol=1e-12, atol=1e-12)
    assert schedule.pressure_pa(4.0) == 1.0e5


def test_pressure_tank_boundary_sets_pressure_and_preserves_internal_energy() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=4)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.full(grid.n_cells, 3.0),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    bc = PressureTankBoundary(
        pressure_schedule=ConstantPressure(2.0e5),
        flow_direction="bidirectional",
        velocity_policy="zero",
    )
    solver = FvmSolver(grid=grid, eos=eos, U=U, right_boundary=bc)
    U_ext = solver.extend_with_ghosts(t=0.0)
    prim_g = eos.primitive_from_conserved(U_ext[-solver.n_ghost:])
    np.testing.assert_allclose(prim_g.p, np.full(solver.n_ghost, 2.0e5), rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose(prim_g.u, np.zeros(solver.n_ghost), rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(prim_g.e, np.full(solver.n_ghost, 1.0e5), rtol=1e-12, atol=1e-12)


def test_pressure_tank_outlet_only_blocks_reverse_flow_as_reflective_wall() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=4)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.full(grid.n_cells, -2.0),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    bc = PressureTankBoundary(
        pressure_schedule=ConstantPressure(2.0e5),
        flow_direction="outlet_only",
        velocity_policy="copy",
    )
    solver = FvmSolver(grid=grid, eos=eos, U=U, right_boundary=bc)
    U_ext = solver.extend_with_ghosts(t=0.0)
    interior_momentum = U_ext[-solver.n_ghost - 1, IDX_MOM]
    ghost_momentum = U_ext[-1, IDX_MOM]
    np.testing.assert_allclose(ghost_momentum, -interior_momentum, rtol=1e-12, atol=1e-12)


def test_case_c_uses_robust_downstream_tank_boundary() -> None:
    params = CaseCParameters(n_cells=80, t_end_s=0.005, esd_valve_position_m=1200.0)
    solver = build_case_c_solver(params)
    assert isinstance(solver.right_boundary, PressureTankBoundary)
    assert solver.right_boundary.flow_direction == "outlet_only"
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    assert history[-1]["time_s"] == params.t_end_s
    assert history[-1]["rho_min_kg_m3"] > 0.0

from liquid_gas_transient.budget import BoundaryBudgetTracker
from liquid_gas_transient.boundary import TransmissiveBoundary


def test_boundary_budget_closed_domain_mass_residual_is_zero() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=20)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.zeros(grid.n_cells),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
    )
    history = solver.run(0.002, max_steps=1000, sample_every=1)
    assert abs(history[-1]["budget_mass_residual"]) < 1.0e-12
    assert abs(history[-1]["budget_energy_residual"]) < 1.0e-6


def test_boundary_budget_open_domain_matches_uniform_outflow() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.2)
    grid = UniformGrid(geometry=geometry, n_cells=20)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(
        rho=np.full(grid.n_cells, 1000.0),
        u=np.full(grid.n_cells, 1.0),
        e=np.full(grid.n_cells, 1.0e5),
        xv=np.zeros(grid.n_cells),
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.5,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
    )
    # Uniform flow with transmissive boundaries remains uniform; left inflow and
    # right outflow should cancel in the net domain budget.
    history = solver.run(0.003, max_steps=1000, sample_every=1)
    final = history[-1]
    np.testing.assert_allclose(final["mass_total"], history[0]["mass_total"], rtol=1e-12, atol=1e-12)
    assert abs(final["budget_mass_net_boundary"]) < 1.0e-12
    assert abs(final["budget_mass_residual"]) < 1.0e-12
    assert final["budget_mass_left_cumulative"] > 0.0
    assert final["budget_mass_right_cumulative"] > 0.0


def test_case_c_budget_diagnostics_are_reported() -> None:
    params = CaseCParameters(n_cells=80, t_end_s=0.005, esd_valve_position_m=1200.0)
    solver = build_case_c_solver(params)
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    final = history[-1]
    assert "budget_mass_left_cumulative" in final
    assert "budget_energy_right_cumulative" in final
    assert np.isfinite(final["budget_mass_residual"])
    # Mass has no source term, so this residual is the primary conservation check.
    assert abs(final["budget_mass_relative_residual"]) < 1.0e-12


from liquid_gas_transient.eos import ToyHEMEOS
from liquid_gas_transient.phase_change import HEMPhaseChange, HNERelaxationPhaseChange
from liquid_gas_transient.state import vapor_mass_fraction


def test_toy_hem_equilibrium_vapor_fraction_from_density() -> None:
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0)
    rho_l = np.array([900.0])
    rho_v = np.array([30.0])
    rho_mid = 1.0 / (0.25 / 30.0 + 0.75 / 900.0)
    np.testing.assert_allclose(eos.equilibrium_vapor_mass_fraction_from_density(rho_l), [0.0])
    np.testing.assert_allclose(eos.equilibrium_vapor_mass_fraction_from_density(rho_v), [1.0])
    np.testing.assert_allclose(eos.equilibrium_vapor_mass_fraction_from_density(rho_mid), [0.25])


def test_hem_phase_change_projects_vapor_mass_to_equilibrium() -> None:
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0)
    rho = np.array([900.0, 1.0 / (0.2 / 30.0 + 0.8 / 900.0), 30.0])
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=0.0)
    out = HEMPhaseChange().apply(U, eos, dt=0.0, t=0.0)
    np.testing.assert_allclose(vapor_mass_fraction(out), [0.0, 0.2, 1.0], rtol=1e-12, atol=1e-12)
    # HEM skeleton changes only vapor mass; mass, momentum and total energy stay conservative.
    np.testing.assert_allclose(out[:, :3], U[:, :3], rtol=1e-12, atol=1e-12)


def test_toy_hem_void_fraction_and_sound_speed_diagnostics() -> None:
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0, c_liquid=1000.0, c_two_phase_min=80.0)
    rho = np.array([900.0, 1.0 / (0.1 / 30.0 + 0.9 / 900.0)])
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=[0.0, 0.1])
    prim = eos.primitive_from_conserved(U)
    assert prim.alpha[0] == 0.0
    assert prim.alpha[1] > prim.xv[1]
    assert prim.c[1] < prim.c[0]


def test_hem_solver_closed_domain_preserves_mass_and_updates_xv() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=10)
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0, c_liquid=1000.0)
    rho = np.full(grid.n_cells, 900.0)
    rho[4:6] = 1.0 / (0.15 / 30.0 + 0.85 / 900.0)
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=0.0)
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        phase_change=HEMPhaseChange(),
    )
    m0 = inventory(solver.U, grid.dx, geometry.area_m2)["mass_total"]
    solver.step(dt=1.0e-5)
    m1 = inventory(solver.U, grid.dx, geometry.area_m2)["mass_total"]
    np.testing.assert_allclose(m1, m0, rtol=1e-12, atol=1e-9)
    assert np.max(vapor_mass_fraction(solver.U)) > 0.1
    assert solver.diagnostics(dt=1.0e-5)["alpha_max"] > 0.0


def test_hne_relaxation_moves_toward_hem_equilibrium() -> None:
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0)
    rho = np.array([1.0 / (0.4 / 30.0 + 0.6 / 900.0)])
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=0.0)
    out = HNERelaxationPhaseChange(tau_s=0.5).apply(U, eos, dt=0.5, t=0.0)
    x = vapor_mass_fraction(out)[0]
    assert 0.0 < x < 0.4


def test_case_c_hem_solver_reports_hem_diagnostics() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    params = CaseCParameters(enable_hem=True, n_cells=80, t_end_s=0.01)
    history = run_case_c(params)
    final = history[-1]
    assert "hem_xv_max" in final
    assert "hem_alpha_max" in final
    assert "hem_vapor_mass_inventory_kg" in final
    assert final["hem_xv_max"] == final["xv_max"]
    assert final["hem_alpha_max"] == final["alpha_max"]
    assert final["hem_vapor_mass_inventory_kg"] == final["vapor_mass_total"]


def test_case_c_hem_disabled_keeps_legacy_diagnostics_shape() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    params = CaseCParameters(enable_hem=False, n_cells=80, t_end_s=0.005)
    final = run_case_c(params)[-1]
    assert "hem_xv_max" not in final
    assert final["xv_max"] == 0.0


def test_high_elevation_two_phase_flag_detects_flashed_high_cells() -> None:
    from liquid_gas_transient.cases.case_c import (
        CaseCParameters,
        build_case_c_solver,
        build_discretized_case_c_network,
        build_hem_diagnostics_config,
    )
    from liquid_gas_transient.hem_diagnostics import summarize_hem_state
    from liquid_gas_transient.phase_change import HEMPhaseChange
    from liquid_gas_transient.state import IDX_RHO, IDX_RHOE, IDX_MOM

    params = CaseCParameters(enable_hem=True, n_cells=80, t_end_s=0.005, hem_high_elevation_min_m=10.0)
    discretized = build_discretized_case_c_network(params)
    solver = build_case_c_solver(params)
    high = discretized.cell_elevation_m >= params.hem_high_elevation_min_m
    assert high.any()

    # Force a few high-elevation cells into the toy HEM two-phase density band.
    solver.U[high, IDX_RHO] = 700.0
    solver.U[high, IDX_MOM] = 0.0
    solver.U[high, IDX_RHOE] = 700.0 * params.internal_energy_j_kg
    solver.U = HEMPhaseChange().apply(solver.U, solver.eos, dt=0.0, t=solver.t)
    diag = summarize_hem_state(solver, discretized, build_hem_diagnostics_config(params))
    assert diag["hem_high_elevation_two_phase_flag"] == 1.0
    assert diag["hem_high_elevation_alpha_max"] > 0.0


def test_case_c_phase_change_model_selector_preserves_auto_compatibility() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, effective_phase_change_model

    assert effective_phase_change_model(CaseCParameters(enable_hem=False)) == "none"
    assert effective_phase_change_model(CaseCParameters(enable_hem=True)) == "hem"
    assert effective_phase_change_model(CaseCParameters(phase_change_model="hne")) == "hne"


def test_case_c_hne_solver_uses_relaxation_operator() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, build_case_c_hne_solver
    from liquid_gas_transient.phase_change import HNERelaxationPhaseChange

    params = CaseCParameters(n_cells=80, t_end_s=0.005, hne_tau_s=0.03)
    solver = build_case_c_hne_solver(params)
    assert isinstance(solver.phase_change, HNERelaxationPhaseChange)
    assert solver.phase_change.tau_s == 0.03


def test_case_c_hne_reports_hne_prefixed_diagnostics() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    params = CaseCParameters(phase_change_model="hne", n_cells=80, t_end_s=0.1, hne_tau_s=0.05)
    final = run_case_c(params)[-1]
    assert "hne_xv_max" in final
    assert "hne_alpha_max" in final
    assert "hne_vapor_mass_inventory_kg" in final
    assert "hem_xv_max" not in final
    assert final["hne_xv_max"] == final["xv_max"]
    assert final["hne_vapor_mass_inventory_kg"] == final["vapor_mass_total"]


def test_case_c_hne_lags_hem_under_same_case_conditions() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    base = dict(n_cells=80, t_end_s=0.1, hne_tau_s=0.05)
    hem = run_case_c(CaseCParameters(**base, phase_change_model="hem"))[-1]
    hne = run_case_c(CaseCParameters(**base, phase_change_model="hne"))[-1]
    assert hne["hne_xv_max"] > 0.0
    assert hem["hem_xv_max"] > hne["hne_xv_max"]
    assert hem["hem_vapor_mass_inventory_kg"] > hne["hne_vapor_mass_inventory_kg"]

from liquid_gas_transient.phase_budget import PhaseChangeBudgetTracker


def test_phase_budget_tracks_hem_vapor_source_in_closed_domain() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=10)
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0, c_liquid=1000.0)
    rho = np.full(grid.n_cells, 900.0)
    rho[4:6] = 1.0 / (0.15 / 30.0 + 0.85 / 900.0)
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=0.0)
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        phase_change=HEMPhaseChange(),
    )
    solver.step(dt=1.0e-5)
    diag = solver.diagnostics(dt=1.0e-5)
    assert diag["phase_vapor_mass_source_cumulative_kg"] > 0.0
    np.testing.assert_allclose(
        diag["budget_vapor_mass_residual"],
        diag["phase_vapor_mass_source_cumulative_kg"],
        rtol=1e-12,
        atol=1e-12,
    )
    assert abs(diag["phase_vapor_mass_balance_residual_kg"]) < 1.0e-12


def test_case_c_hne_phase_budget_closes_vapor_inventory() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    params = CaseCParameters(phase_change_model="hne", n_cells=80, t_end_s=0.1, hne_tau_s=0.05)
    final = run_case_c(params)[-1]
    assert final["phase_vapor_mass_source_cumulative_kg"] > 0.0
    assert final["hne_vapor_mass_inventory_kg"] == final["vapor_mass_total"]
    np.testing.assert_allclose(
        final["budget_vapor_mass_residual"],
        final["phase_vapor_mass_source_cumulative_kg"],
        rtol=1e-10,
        atol=1e-10,
    )
    assert abs(final["phase_vapor_mass_balance_residual_kg"]) < 1.0e-10

from liquid_gas_transient.energy_budget import EnergySourceBudgetTracker


def test_energy_budget_tracks_gravity_source_delta() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.2)
    grid = UniformGrid(geometry=geometry, n_cells=6)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    dzdx = np.full(grid.n_cells, 0.1)
    U = make_conserved(rho=np.full(grid.n_cells, 1000.0), u=np.full(grid.n_cells, 2.0), e=np.full(grid.n_cells, 1.0e5), xv=0.0)
    src = CellwisePipeSourceTerms(
        diameter_m=geometry.diameter_m,
        darcy_friction_factor=0.0,
        dzdx=dzdx,
        gravity_m_s2=9.80665,
        include_gravity_energy_source=True,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        source_term=src,
    )
    solver.step(dt=1.0e-4)
    diag = solver.diagnostics(dt=1.0e-4)
    assert diag["energy_budget_source_delta_cumulative_j"] < 0.0
    np.testing.assert_allclose(
        diag["energy_budget_source_delta_cumulative_j"],
        diag["energy_source_gravity_cumulative_j"],
        rtol=1e-7,
        atol=1e-8,
    )
    assert abs(diag["energy_budget_balance_residual_j"]) < 1.0e-8


def test_energy_budget_reports_friction_dissipation_proxy() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.2)
    grid = UniformGrid(geometry=geometry, n_cells=6)
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    U = make_conserved(rho=np.full(grid.n_cells, 1000.0), u=np.full(grid.n_cells, 2.0), e=np.full(grid.n_cells, 1.0e5), xv=0.0)
    src = CellwisePipeSourceTerms(
        diameter_m=geometry.diameter_m,
        darcy_friction_factor=0.02,
        dzdx=0.0,
        include_gravity_energy_source=False,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        source_term=src,
    )
    solver.step(dt=1.0e-3)
    diag = solver.diagnostics(dt=1.0e-3)
    assert diag["energy_source_friction_dissipation_proxy_cumulative_j"] > 0.0
    assert diag["energy_source_drag_dissipation_proxy_cumulative_j"] > 0.0
    # The toy source model keeps total conservative energy unchanged during drag.
    np.testing.assert_allclose(diag["energy_budget_source_delta_cumulative_j"], 0.0, atol=1.0e-12)
    assert abs(diag["energy_budget_balance_residual_j"]) < 1.0e-8


def test_energy_budget_reports_latent_placeholder_for_hem() -> None:
    geometry = PipeGeometry(length_m=10.0, diameter_m=0.1)
    grid = UniformGrid(geometry=geometry, n_cells=10)
    eos = ToyHEMEOS(rho_l_sat=900.0, rho_v_sat=30.0, c_liquid=1000.0)
    rho = np.full(grid.n_cells, 900.0)
    rho[4:6] = 1.0 / (0.15 / 30.0 + 0.85 / 900.0)
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=0.0)
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        phase_change=HEMPhaseChange(),
        latent_heat_placeholder_j_kg=2.0e5,
    )
    solver.step(dt=1.0e-5)
    diag = solver.diagnostics(dt=1.0e-5)
    assert diag["phase_vapor_mass_source_cumulative_kg"] > 0.0
    assert diag["energy_phase_latent_requirement_cumulative_j"] > 0.0
    np.testing.assert_allclose(
        diag["energy_phase_latent_requirement_cumulative_j"],
        2.0e5 * diag["phase_vapor_mass_source_cumulative_kg"],
        rtol=1e-12,
        atol=1e-12,
    )
    # The placeholder is diagnostic only; the toy HEM operator leaves rhoE unchanged.
    np.testing.assert_allclose(diag["energy_budget_phase_delta_cumulative_j"], 0.0, atol=1.0e-12)


from liquid_gas_transient.interface_budget import pump_work_from_boundary_flux, valve_loss_from_dp_q


def test_interface_budget_helper_computes_pump_work() -> None:
    terms = pump_work_from_boundary_flux(
        mass_flux=930.0 * 1.5,
        area_m2=0.25,
        rho_boundary=930.0,
        delta_p_pa=2.0e5,
    )
    np.testing.assert_allclose(terms["pump_q_m3_s"], 0.25 * 1.5, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(terms["pump_hydraulic_power_w"], 2.0e5 * 0.25 * 1.5, rtol=1e-12, atol=1e-12)


def test_interface_budget_helper_computes_valve_loss() -> None:
    terms = valve_loss_from_dp_q(delta_p_pa=1.0e5, q_m3_s=0.12)
    np.testing.assert_allclose(terms["valve_loss_power_w"], 1.2e4, rtol=1e-12, atol=1e-12)
    reverse = valve_loss_from_dp_q(delta_p_pa=-1.0e5, q_m3_s=0.12)
    assert reverse["valve_loss_power_w"] == 0.0


def test_case_c_reports_pump_and_valve_interface_energy_budget() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    params = CaseCParameters(
        n_cells=80,
        t_end_s=0.05,
        pump_delta_p_nominal_pa=2.0e5,
        valve_close_start_s=0.04,
        valve_close_time_s=0.02,
    )
    final = run_case_c(params)[-1]
    assert final["energy_interface_pump_hydraulic_work_cumulative_j"] > 0.0
    assert final["energy_interface_valve_loss_proxy_cumulative_j"] > 0.0
    np.testing.assert_allclose(
        final["energy_interface_net_diagnostic_cumulative_j"],
        final["energy_interface_pump_hydraulic_work_cumulative_j"] - final["energy_interface_valve_loss_proxy_cumulative_j"],
        rtol=1e-12,
        atol=1e-9,
    )


def test_case_c_report_generator_creates_markdown_csv_and_figures(tmp_path) -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters
    from liquid_gas_transient.reporting import CaseCReportConfig, generate_case_c_report

    params = CaseCParameters(
        n_cells=60,
        t_end_s=0.02,
        pump_delta_p_nominal_pa=1.0e5,
        valve_close_start_s=0.01,
        valve_close_time_s=0.01,
        latent_heat_placeholder_j_kg=2.0e5,
    )
    result = generate_case_c_report(
        tmp_path,
        base_params=params,
        config=CaseCReportConfig(sample_every=5),
    )
    assert Path(result["report_path"]).exists()
    assert len(result["summary_rows"]) == 3
    variants = {row["variant"] for row in result["summary_rows"]}
    assert variants == {"none", "hem", "hne"}
    assert any(Path(p).name == "case_c_summary_comparison_v0_4_4.csv" for p in result["data_paths"])
    assert all(Path(p).exists() for p in result["data_paths"])
    assert all(Path(p).exists() for p in result["figure_paths"])

from liquid_gas_transient.eos import LCO2PropertyEOSAdapter
from liquid_gas_transient.properties import SurrogateLCO2PropertyBackend, coolprop_available


def test_surrogate_lco2_backend_returns_finite_mixture_state() -> None:
    backend = SurrogateLCO2PropertyBackend(rho_l_ref_kg_m3=930.0, rho_v_ref_kg_m3=40.0)
    rho_mix = 1.0 / (0.2 / 40.0 + 0.8 / 930.0)
    state = backend.state_from_rho_e(np.array([930.0, rho_mix]), np.array([1.0e5, 1.0e5]))
    assert np.all(np.isfinite(state.p))
    assert state.quality[0] == 0.0
    assert 0.19 < state.quality[1] < 0.21
    assert state.alpha[1] > state.quality[1]
    assert state.c[1] < state.c[0]


def test_lco2_property_eos_adapter_uses_transported_quality_for_diagnostics() -> None:
    backend = SurrogateLCO2PropertyBackend(rho_l_ref_kg_m3=930.0, rho_v_ref_kg_m3=40.0)
    eos = LCO2PropertyEOSAdapter(backend=backend, quality_source="transported")
    rho = np.array([930.0, 930.0])
    U = make_conserved(rho=rho, u=0.0, e=1.0e5, xv=np.array([0.0, 0.1]))
    prim = eos.primitive_from_conserved(U)
    np.testing.assert_allclose(prim.xv, [0.0, 0.1], rtol=1e-12, atol=1e-12)
    assert prim.alpha[1] > prim.alpha[0]
    rho_b = eos.density_from_pressure(np.array([1.9e6, 2.0e6]))
    assert np.all(rho_b > 0.0)


def test_case_c_lco2_surrogate_property_adapter_builds_and_steps() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, build_case_c_solver, effective_eos_model

    params = CaseCParameters(eos_model="lco2_surrogate", phase_change_model="none", n_cells=80, t_end_s=0.005)
    assert effective_eos_model(params) == "lco2_surrogate"
    solver = build_case_c_solver(params)
    assert isinstance(solver.eos, LCO2PropertyEOSAdapter)
    history = solver.run(params.t_end_s, max_steps=1000, sample_every=5)
    final = history[-1]
    assert final["time_s"] == params.t_end_s
    assert final["rho_min_kg_m3"] > 0.0
    assert abs(final["budget_mass_relative_residual"]) < 1.0e-12


def test_case_c_lco2_surrogate_hne_uses_property_equilibrium_quality() -> None:
    from liquid_gas_transient.cases.case_c import CaseCParameters, run_case_c

    params = CaseCParameters(
        eos_model="lco2_surrogate",
        phase_change_model="hne",
        hne_tau_s=0.05,
        n_cells=80,
        t_end_s=0.05,
        pump_delta_p_nominal_pa=1.0e5,
        latent_heat_placeholder_j_kg=2.0e5,
    )
    final = run_case_c(params)[-1]
    assert "hne_xv_max" in final
    assert final["hne_xv_max"] >= 0.0
    assert np.isfinite(final["energy_budget_balance_residual_j"])
    assert abs(final["phase_vapor_mass_balance_residual_kg"]) < 1.0e-8


def test_optional_coolprop_availability_probe_is_boolean() -> None:
    assert isinstance(coolprop_available(), bool)

from liquid_gas_transient.property_verification import (
    PropertyBackendVerificationConfig,
    generate_property_backend_verification,
    mixture_reconstruction_table,
    saturation_table,
    summarize_property_verification,
)


def test_property_backend_saturation_table_has_ordered_phases() -> None:
    backend = SurrogateLCO2PropertyBackend()
    rows = saturation_table(backend, [1.5e6, 1.9e6, 2.3e6])
    assert len(rows) == 3
    assert all(row["rho_l_kg_m3"] > row["rho_v_kg_m3"] for row in rows)
    assert all(row["h_lv_j_kg"] > 0.0 for row in rows)


def test_property_backend_mixture_reconstruction_is_consistent() -> None:
    backend = SurrogateLCO2PropertyBackend()
    sat_rows = saturation_table(backend, [1.9e6])
    mix_rows = mixture_reconstruction_table(backend, [1.9e6], [0.0, 0.1, 0.5, 0.9, 1.0])
    pT_rows = []
    # Use a minimal pT sample so the summary can also check density positivity.
    for dT in [-2.0, 2.0]:
        rho = backend.density_from_pT(np.array([1.9e6]), np.array([backend.T_sat_ref_K + dT]))
        pT_rows.append({"rho_from_pT_kg_m3": float(rho[0])})
    metrics = summarize_property_verification(
        backend,
        sat_rows,
        mix_rows,
        pT_rows,
        PropertyBackendVerificationConfig(pressures_pa=(1.9e6,), quality_points=(0.0, 0.1, 0.5, 0.9, 1.0)),
    )
    assert metrics["quality_reconstruction_pass"]
    assert metrics["mixture_pressure_consistency_pass"]
    assert metrics["overall_pass"]


def test_property_backend_verification_generator_creates_artifacts(tmp_path) -> None:
    result = generate_property_backend_verification(
        tmp_path,
        config=PropertyBackendVerificationConfig(
            pressures_pa=(1.5e6, 1.9e6, 2.3e6),
            quality_points=(0.0, 0.1, 0.5, 0.9, 1.0),
            pT_temperature_offsets_K=(-2.0, 2.0),
            include_optional_coolprop=False,
        ),
    )
    assert result["overall_pass"] is True
    paths = result["paths"]
    assert Path(paths["report_md"]).exists()
    assert Path(paths["saturation_table_csv"]).exists()
    assert Path(paths["mixture_reconstruction_csv"]).exists()
    assert Path(paths["density_pT_table_csv"]).exists()
    assert Path(paths["metrics_json"]).exists()

from liquid_gas_transient.properties import (
    CoolPropCO2Backend,
    make_property_backend,
    property_backend_availability,
)
from liquid_gas_transient.external_reference import (
    build_surrogate_self_reference_rows,
    compare_backend_to_reference_rows,
    summarize_reference_comparison,
)


def test_property_backend_factory_and_availability_are_safe_without_optional_deps() -> None:
    availability = property_backend_availability()
    assert availability["surrogate_lco2"] is True
    assert "coolprop_co2" in availability
    assert make_property_backend("surrogate_lco2").name == "surrogate_lco2"
    # Instantiation must be safe even when CoolProp is not installed. Evaluation
    # may raise ImportError, which is the intended optional-dependency behavior.
    assert CoolPropCO2Backend().name == "coolprop_co2"


def test_surrogate_external_reference_comparison_closes_exactly() -> None:
    backend = make_property_backend("surrogate_lco2")
    rows = build_surrogate_self_reference_rows(backend, pressures_pa=(1.9e6,), qualities=(0.0, 0.5, 1.0))
    results = compare_backend_to_reference_rows(backend, rows)
    summary = summarize_reference_comparison(results)
    assert summary["overall_pass"] is True
    assert summary["failed_count"] == 0
    assert summary["comparison_count"] > 0

from liquid_gas_transient.project_reference import (
    ProjectReferenceIngestionConfig,
    build_surrogate_project_reference_demo_rows,
    generate_project_reference_ingestion_artifacts,
    ingest_project_reference_rows,
)


def test_project_reference_ingestion_normalizes_demo_units() -> None:
    manifest, raw_rows = build_surrogate_project_reference_demo_rows()
    canonical_rows, issues = ingest_project_reference_rows(raw_rows, manifest)
    assert issues == []
    assert len(canonical_rows) == len(raw_rows)
    first_sat = next(row for row in canonical_rows if row["mode"] == "saturation")
    assert float(first_sat["p_pa"]) > 1.0e6
    assert float(first_sat["ref_T_sat_K"]) > 200.0
    assert float(first_sat["ref_h_lv_j_kg"]) > 0.0
    assert first_sat["approved_for_design_use"] is False


def test_project_reference_ingestion_artifact_generator(tmp_path) -> None:
    result = generate_project_reference_ingestion_artifacts(
        tmp_path,
        backend_name="surrogate_lco2",
        config=ProjectReferenceIngestionConfig(version="0.5.3", require_design_approved_reference=False),
    )
    assert result["overall_pass"] is True
    assert result["design_reference_available"] is False
    assert result["comparison_summary"]["failed_count"] == 0
    paths = result["paths"]
    assert Path(paths["canonical_csv"]).exists()
    assert Path(paths["comparison_csv"]).exists()
    assert Path(paths["report_md"]).exists()

from liquid_gas_transient.reference_acceptance import (
    ReferenceAcceptanceGateConfig,
    build_approved_surrogate_reference_for_gate_demo,
    evaluate_reference_acceptance,
    generate_reference_acceptance_gate_artifacts,
)


def test_reference_acceptance_gate_rehearsal_is_not_design_accepted(tmp_path) -> None:
    result = generate_reference_acceptance_gate_artifacts(
        tmp_path,
        backend_name="surrogate_lco2",
        config=ReferenceAcceptanceGateConfig(version="0.5.4", fail_if_not_design_approved=False),
    )
    assert result["decision"]["status"] == "REHEARSAL_PASS_NOT_DESIGN_REFERENCE"
    assert result["decision"]["accepted_for_design_use"] is False
    assert Path(result["paths"]["report_md"]).exists()
    assert Path(result["paths"]["decision_csv"]).exists()


def test_reference_acceptance_gate_rejects_non_approved_reference_when_required(tmp_path) -> None:
    result = generate_reference_acceptance_gate_artifacts(
        tmp_path,
        backend_name="surrogate_lco2",
        config=ReferenceAcceptanceGateConfig(
            version="0.5.4",
            require_design_approved_reference=True,
            fail_if_not_design_approved=True,
        ),
    )
    assert result["decision"]["status"] == "REJECTED"
    assert result["decision"]["accepted_for_design_use"] is False
    assert result["decision"]["blocking_issue_count"] >= 1


def test_reference_acceptance_gate_accepts_approved_demo_reference(tmp_path) -> None:
    raw_csv, manifest_json = build_approved_surrogate_reference_for_gate_demo(tmp_path / "approved_input")
    result = generate_reference_acceptance_gate_artifacts(
        tmp_path / "gate",
        backend_name="surrogate_lco2",
        raw_reference_csv=raw_csv,
        manifest_json=manifest_json,
        config=ReferenceAcceptanceGateConfig(
            version="0.5.4",
            require_design_approved_reference=True,
            fail_if_not_design_approved=True,
        ),
    )
    assert result["decision"]["status"] == "ACCEPTED_FOR_DESIGN_USE"
    assert result["decision"]["accepted_for_design_use"] is True
    assert result["overall_pass"] is True
