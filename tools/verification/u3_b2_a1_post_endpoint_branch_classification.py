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
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import CoolPropB2StateProvider, CoolPropSinglePhaseEOS, build_uniform_initial_state, load_b1_contract, load_contract, normalize_phase
from u3_b2_a1_neutral_endpoint_resume import _run_resume, _solve_neutral_endpoint
from u3_b2_a1_wave_curve_model import CASE_ID, PRESSURE_OFFSETS_PA, _brackets, _inventory_array, _scan_row
from u3_b2_characteristic_port_dynamic_short_metrics import build_step_row, inventory
from u3_b2_characteristic_port_dynamic_short_model import CONNECTED_SCAN_NODE_COUNT, DynamicDiagnosticStop
robustness = robustness_v4.robustness
PARENT_SOURCE_SHA = 'b91832d44e1697fc8d78be2a3bee9c64a9defd72'
STARTING_ACCEPTED_SOLVER_STEP = 337
MAX_POST_ENDPOINT_ACCEPTED_STEPS = 32
OUTCOME_A = 'OUTCOME_A_NEUTRAL_RAREFACTION_STABLE_32_STEPS'
OUTCOME_B = 'OUTCOME_B_LOCAL_COMPRESSION_REQUIRED'

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        raise ValueError(f'no rows for {path}')
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None

def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None

class BranchClassificationStop(DynamicDiagnosticStop):

    def __init__(self, classification: str, message: str, diagnostics: dict[str, Any] | None=None) -> None:
        super().__init__(message)
        self.classification = classification
        self.diagnostics = diagnostics or {}

def _connected_rarefaction_scan(*, contract: dict[str, Any], case_id: str, state_id: str, provider: Any, adapter: Any, area_m2: float, outlet_conserved: np.ndarray, previous_root_pressure_pa: float | None) -> dict[str, Any]:
    reconstruction = provider.reconstruct_from_conserved(outlet_conserved)
    static = reconstruction.static
    back_pressure = float(adapter.back_pressure_pa)
    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))

    def evaluate(pressure_pa: float) -> dict[str, Any]:
        return diagnostic.evaluate_pressure(pressure_pa=float(pressure_pa), static=static, isentrope=isentrope, adapter=adapter, area_m2=area_m2, case_id=case_id, state_id=state_id)
    if not float(static.pressure_pa) > back_pressure:
        return {'rows': [], 'requested_nodes': 0, 'admissible_subsonic_nodes': 0, 'lowest_pressure_pa': None, 'stop_reason': f'outlet pressure is not above retained back pressure: p_i={static.pressure_pa}, p_back={back_pressure}', 'residual_monotone': False, 'sign_change_brackets': [], 'sign_change_count': 0}
    pressures = list(np.linspace(float(static.pressure_pa), back_pressure, CONNECTED_SCAN_NODE_COUNT))
    previous = previous_root_pressure_pa
    if previous is not None and back_pressure < previous < float(static.pressure_pa):
        pressures.append(float(previous))
    pressures = sorted(set((float(value) for value in pressures)), reverse=True)
    rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    for pressure in pressures:
        row = evaluate(pressure)
        if not row.get('evaluation_succeeded'):
            stop_reason = f"inadmissible connected scan node p={pressure}: {row.get('formal_outcome')} {row.get('formal_message')}"
            break
        mach = float(row['mach'])
        if not 0.0 <= mach < 1.0:
            stop_reason = f'connected rarefaction scan left the subsonic branch at p={pressure}, Mach={mach}'
            break
        rows.append(row)
    residuals = [float(row['residual_kg_s']) for row in rows]
    monotone = bool(len(residuals) >= 2 and all((residuals[index + 1] >= residuals[index] for index in range(len(residuals) - 1))))
    brackets = diagnostic.find_sign_change_brackets(rows) if len(rows) >= 2 else []
    return {'rows': rows, 'requested_nodes': len(pressures), 'admissible_subsonic_nodes': len(rows), 'lowest_pressure_pa': float(rows[-1]['pressure_pa']) if rows else None, 'stop_reason': stop_reason, 'residual_monotone': monotone, 'sign_change_brackets': brackets, 'sign_change_count': len(brackets)}

def _classification_diagnostics(*, hook: Any, U: np.ndarray, solver_time_s: float) -> dict[str, Any]:
    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    allowed_phases = {normalize_phase(value) for value in diagnostic._family(hook.contract, hook.state_id)['allowed_normalized_phases']}
    velocity_tolerance = float(hook.contract['acceptance_tolerances']['velocity_zero_tolerance_m_s'])
    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))
    local_rows = [_scan_row(offset_pa=float(offset), static=static, isentrope=isentrope, hook=hook, area_m2=hook.area_m2, allowed_phases=allowed_phases, velocity_tolerance=velocity_tolerance) for offset in PRESSURE_OFFSETS_PA]
    endpoint = next((row for row in local_rows if float(row['pressure_offset_pa']) == 0.0))
    negative_rows = [row for row in local_rows if float(row['pressure_offset_pa']) <= 0.0]
    positive_rows = [row for row in local_rows if float(row['pressure_offset_pa']) >= 0.0]
    negative_evaluable = _brackets(negative_rows, admissible_only=False)
    negative_admissible = _brackets(negative_rows, admissible_only=True)
    positive_evaluable = _brackets(positive_rows, admissible_only=False)
    positive_admissible = _brackets(positive_rows, admissible_only=True)
    connected = _connected_rarefaction_scan(contract=hook.contract, case_id=hook.case_id, state_id=hook.state_id, provider=hook.provider, adapter=hook.adapter, area_m2=hook.area_m2, outlet_conserved=U[-1], previous_root_pressure_pa=hook._previous_root_pressure_pa)
    return {'solver_time_s': float(solver_time_s), 'interior_pressure_pa': float(static.pressure_pa), 'interior_velocity_m_s': float(static.velocity_m_s), 'interior_phase': static.phase, 'interior_mach': float(static.velocity_m_s / static.sound_speed_m_s), 'interior_stagnation_pressure_pa': float(reconstruction.stagnation_pressure_pa), 'back_pressure_pa': float(hook.adapter.back_pressure_pa), 'endpoint': endpoint, 'endpoint_residual_kg_s': endpoint.get('compatibility_residual_kg_s'), 'endpoint_within_locked_root_mass_tolerance': endpoint.get('within_locked_root_mass_tolerance'), 'endpoint_admissible': endpoint.get('local_candidate_admissible'), 'endpoint_root_closure_passed': endpoint.get('root_closure_passed'), 'retained_root_mass_tolerance_kg_s': float(robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S), 'local_scan_rows': local_rows, 'rarefaction_side_local_evaluable_brackets': negative_evaluable, 'rarefaction_side_local_admissible_brackets': negative_admissible, 'rarefaction_side_local_sign_change_count': len(negative_admissible), 'positive_side_local_evaluable_brackets': positive_evaluable, 'positive_side_local_admissible_brackets': positive_admissible, 'positive_side_local_sign_change_count': len(positive_admissible), 'connected_rarefaction': connected, 'positive_pressure_continuation_flux_applied': False, 'finite_compression_branch_approved': False}

def _check_branch_chatter(history: list[str], candidate: str, diagnostics: dict[str, Any]) -> None:
    if candidate not in {'NEUTRAL_ENDPOINT', 'RAREFACTION'}:
        return
    if len(history) >= 2 and history[-2] == candidate and (history[-1] != candidate) and (history[-1] in {'NEUTRAL_ENDPOINT', 'RAREFACTION'}):
        enriched = dict(diagnostics)
        enriched.update({'accepted_branch_history': list(history), 'candidate_branch': candidate, 'positive_pressure_continuation_flux_applied': False})
        raise BranchClassificationStop('UNEXPLAINED_BRANCH_CHATTER', 'candidate branch forms a consecutive A -> B -> A pattern', enriched)

def _solve_classified_boundary(*, hook: Any, U: np.ndarray, solver_time_s: float) -> dict[str, Any]:
    details = _classification_diagnostics(hook=hook, U=U, solver_time_s=solver_time_s)
    endpoint = details['endpoint']
    if not endpoint.get('evaluation_succeeded'):
        raise BranchClassificationStop('ENDPOINT_EVALUATION_FAILURE', 'endpoint evaluation did not succeed', details)
    if not endpoint.get('local_candidate_admissible'):
        raise BranchClassificationStop('LOCAL_ROOT_INADMISSIBLE', 'endpoint state is outside the retained admissible branch', details)
    classification: str
    if endpoint.get('root_closure_passed'):
        classification = 'NEUTRAL_ENDPOINT'
        try:
            context = _solve_neutral_endpoint(contract=hook.contract, case_id=hook.case_id, state_id=hook.state_id, provider=hook.provider, adapter=hook.adapter, area_m2=hook.area_m2, outlet_conserved=U[-1], solver_time_s=solver_time_s)
        except Exception as exc:
            raise BranchClassificationStop('ROOT_OR_LEDGER_FAILURE', f'neutral endpoint completion failed: {type(exc).__name__}: {exc}', details) from exc
    else:
        connected = details['connected_rarefaction']
        rarefaction_count = int(connected['sign_change_count'])
        negative_local_count = int(details['rarefaction_side_local_sign_change_count'])
        positive_count = int(details['positive_side_local_sign_change_count'])
        if int(connected['admissible_subsonic_nodes']) < 2:
            raise BranchClassificationStop('LOCAL_ROOT_INADMISSIBLE', 'connected rarefaction scan has fewer than two admissible subsonic nodes', details)
        if not connected['residual_monotone']:
            raise BranchClassificationStop('CONNECTED_RAREFACTION_NON_MONOTONE', 'connected rarefaction residual is not monotone', details)
        if rarefaction_count > 1 or negative_local_count > 1 or positive_count > 1:
            raise BranchClassificationStop('MULTIPLE_LOCAL_ROOTS', 'more than one admissible root bracket was observed', details)
        if rarefaction_count == 1 and positive_count == 1:
            raise BranchClassificationStop('MULTIPLE_LOCAL_ROOTS', 'admissible root brackets exist on both sides of the endpoint', details)
        if rarefaction_count == 1 and positive_count == 0:
            classification = 'RAREFACTION'
            try:
                context = horizon._solve_two_l_over_c0_root(contract=hook.contract, case_id=hook.case_id, state_id=hook.state_id, provider=hook.provider, adapter=hook.adapter, area_m2=hook.area_m2, outlet_conserved=U[-1], solver_time_s=solver_time_s, previous_root_pressure_pa=hook._previous_root_pressure_pa)
            except Exception as exc:
                raise BranchClassificationStop('ROOT_OR_LEDGER_FAILURE', f'rarefaction root completion failed: {type(exc).__name__}: {exc}', details) from exc
            if not float(context['root']['pressure_pa']) < float(context['interior_pressure_pa']):
                raise BranchClassificationStop('BRANCH_JUMP', 'selected rarefaction root is not below the current endpoint', details)
        elif rarefaction_count == 0 and negative_local_count == 0 and (positive_count == 1):
            raise BranchClassificationStop('LOCAL_COMPRESSION_REQUIRED', 'endpoint is outside the retained tolerance and the only local root bracket is on the positive-pressure side', details)
        elif rarefaction_count == 0 and negative_local_count == 1:
            raise BranchClassificationStop('BRANCH_JUMP', 'a local rarefaction-side bracket was observed but the connected approved scan did not retain it', details)
        else:
            positive_evaluable = len(details['positive_side_local_evaluable_brackets'])
            positive_admissible = len(details['positive_side_local_admissible_brackets'])
            if positive_evaluable > positive_admissible:
                raise BranchClassificationStop('LOCAL_ROOT_INADMISSIBLE', 'a positive-side local root bracket is evaluable but inadmissible', details)
            raise BranchClassificationStop('NO_LOCAL_COMPATIBLE_ROOT', 'neither an approved rarefaction root nor a unique admissible positive-side local root was found', details)
    _check_branch_chatter(hook.accepted_branch_history, classification, details)
    root = context['root']
    context.update({'branch_classification': classification, 'endpoint_residual_kg_s': details['endpoint_residual_kg_s'], 'endpoint_within_locked_root_mass_tolerance': details['endpoint_within_locked_root_mass_tolerance'], 'endpoint_admissible': details['endpoint_admissible'], 'endpoint_root_closure_passed': details['endpoint_root_closure_passed'], 'retained_root_mass_tolerance_kg_s': details['retained_root_mass_tolerance_kg_s'], 'rarefaction_side_local_sign_change_count': details['rarefaction_side_local_sign_change_count'], 'positive_side_local_sign_change_count': details['positive_side_local_sign_change_count'], 'connected_rarefaction_sign_change_count': details['connected_rarefaction']['sign_change_count'], 'connected_rarefaction_residual_monotone': details['connected_rarefaction']['residual_monotone'], 'connected_rarefaction_stop_reason': details['connected_rarefaction']['stop_reason'], 'local_scan_rows': details['local_scan_rows'], 'local_rarefaction_brackets': details['rarefaction_side_local_admissible_brackets'], 'local_positive_brackets': details['positive_side_local_admissible_brackets'], 'p_P_minus_p_i_pa': float(root['pressure_pa'] - context['interior_pressure_pa']), 'p0_minus_back_pressure_pa': float(root['stagnation_pressure_pa'] - hook.adapter.back_pressure_pa), 'positive_pressure_continuation_flux_applied': False, 'finite_compression_branch_approved': False, 'accepted_branch_history_before': list(hook.accepted_branch_history)})
    return context

class A1PostEndpointBranchHook(horizon.A1TwoLOverC0Hook):
    """Diagnostic-only branch-aware hook after the accepted step 337."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.accepted_branch_history: list[str] = ['NEUTRAL_ENDPOINT']
        self.pending_branch_classification: str | None = None
        self.requested_solver_step: int | None = None

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(self._cache_t == float(t) and self._cache_outlet is not None and np.array_equal(self._cache_outlet, U[-1]) and (self.root_context is not None))
        if cached:
            return
        context = _solve_classified_boundary(hook=self, U=U, solver_time_s=t)
        self.root_context = context
        self.flux = np.array(context['flux'], copy=True)
        self.pending_branch_classification = str(context['branch_classification'])
        self._cache_t = float(t)
        self._cache_outlet = np.array(U[-1], copy=True)
        self.trial_dts_s = []

    def accept_current_root(self) -> None:
        if self.pending_branch_classification is None:
            raise AssertionError('no pending post-endpoint classification')
        super().accept_current_root()
        self.accepted_branch_history.append(self.pending_branch_classification)
        self.pending_branch_classification = None

def _flatten_local_scan(*, rows: list[dict[str, Any]], requested_solver_step: int, solver_time_s: float, classification: str) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update({'requested_solver_step': int(requested_solver_step), 'solver_time_s': float(solver_time_s), 'attempt_classification': classification, 'positive_pressure_continuation_flux_applied': False})
        flattened.append(item)
    return flattened

def _stop_row(*, requested_solver_step: int, solver: FvmSolver, exc: BranchClassificationStop) -> dict[str, Any]:
    details = exc.diagnostics
    endpoint = details.get('endpoint', {})
    connected = details.get('connected_rarefaction', {})
    return {'requested_step': int(requested_solver_step), 'accepted_step': False, 'solver_step_count': int(solver.step_count), 'time_before_s': float(solver.t), 'time_after_s': float(solver.t), 'accepted_dt_s': None, 'halving_count': 0, 'branch_classification': exc.classification, 'interior_pressure_before_root_pa': details.get('interior_pressure_pa'), 'interior_velocity_before_root_m_s': details.get('interior_velocity_m_s'), 'interior_mach_before_root': details.get('interior_mach'), 'interior_phase_before_root': details.get('interior_phase'), 'endpoint_residual_kg_s': details.get('endpoint_residual_kg_s'), 'retained_root_mass_tolerance_kg_s': details.get('retained_root_mass_tolerance_kg_s'), 'endpoint_within_locked_root_mass_tolerance': details.get('endpoint_within_locked_root_mass_tolerance'), 'endpoint_admissible': details.get('endpoint_admissible'), 'endpoint_root_closure_passed': details.get('endpoint_root_closure_passed'), 'rarefaction_side_local_sign_change_count': details.get('rarefaction_side_local_sign_change_count'), 'positive_side_local_sign_change_count': details.get('positive_side_local_sign_change_count'), 'connected_rarefaction_sign_change_count': connected.get('sign_change_count'), 'connected_rarefaction_residual_monotone': connected.get('residual_monotone'), 'connected_rarefaction_stop_reason': connected.get('stop_reason'), 'positive_pressure_continuation_flux_applied': False, 'reverse_flow_guard_triggered': False, 'guard_status': 'DIAGNOSTIC_STOP', 'step_passed': False, 'stop_reason': f'{type(exc).__name__}: {exc}', 'endpoint_formal_outcome': endpoint.get('formal_outcome'), 'endpoint_formal_message': endpoint.get('formal_message')}

def _run_post_endpoint(contract: dict[str, Any], b1_contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], np.ndarray, np.ndarray]:
    resume_row, resume_summary, _, U_step337 = _run_resume(contract, b1_contract)
    if not bool(resume_summary['neutral_endpoint_one_step_gate_passed']):
        raise BranchClassificationStop('CHECKPOINT_REPRODUCTION_MISMATCH', 'the parent neutral-endpoint step-337 reproduction did not pass')
    if int(resume_summary['resumed_solver_step']) != STARTING_ACCEPTED_SOLVER_STEP:
        raise BranchClassificationStop('CHECKPOINT_REPRODUCTION_MISMATCH', 'the reproduced solver step is not 337')
    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case['state_id'])
    geometry = contract['geometry']
    pipe = PipeGeometry(length_m=float(geometry['pipe_length_m']), diameter_m=float(geometry['pipe_diameter_m']), roughness_m=float(geometry['roughness_m']))
    grid = UniformGrid(pipe, int(geometry['baseline_cells']))
    provider = CoolPropB2StateProvider()
    U_initial, initial_static = build_uniform_initial_state(contract, provider, state_id, grid.n_cells)
    time_after_step337 = float(resume_row['time_after_s'])
    hook = A1PostEndpointBranchHook(contract=contract, b1_contract=b1_contract, case_id=CASE_ID, provider=provider)
    hook._previous_root_pressure_pa = float(resume_summary['endpoint_pressure_pa'])
    solver = FvmSolver(grid=grid, eos=CoolPropSinglePhaseEOS(provider, boundary_temperature_K=initial_static.temperature_K), U=np.asarray(U_step337, dtype=float), cfl=float(geometry['baseline_cfl']), n_ghost=int(geometry['ghost_cells_each_side']), left_boundary=ReflectiveBoundary(), right_boundary=TransmissiveBoundary(), right_external_face_flux_override=hook, enable_boundary_budget=True, enable_phase_budget=False, enable_energy_budget=False, enable_interface_budget=False, t=time_after_step337, step_count=STARTING_ACCEPTED_SOLVER_STEP)
    initial = inventory(U_initial, dx=grid.dx, area_m2=grid.geometry.area_m2)
    current = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
    current_minus_initial = _inventory_array(current) - _inventory_array(initial)
    cumulative_expected_delta = np.asarray([current_minus_initial[0] - float(resume_row['cumulative_mass_residual_kg']), current_minus_initial[1] - float(resume_row['cumulative_momentum_residual_kg_m_s']), current_minus_initial[2] - float(resume_row['cumulative_energy_residual_J']), 0.0], dtype=float)
    rows: list[dict[str, Any]] = []
    local_scan_rows: list[dict[str, Any]] = []
    stop_classification: str | None = None
    stop_reason: str | None = None
    for post_index in range(1, MAX_POST_ENDPOINT_ACCEPTED_STEPS + 1):
        requested_solver_step = STARTING_ACCEPTED_SOLVER_STEP + post_index
        hook.requested_solver_step = requested_solver_step
        before = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
        try:
            candidate_dt = float(solver.compute_dt())
            dt_limits = dict(hook.last_dt_limits)
            if hook.root_context is None:
                raise AssertionError('post-endpoint root was not prepared')
            root_context = hook.root_context
            local_scan_rows.extend(_flatten_local_scan(rows=list(root_context['local_scan_rows']), requested_solver_step=requested_solver_step, solver_time_s=float(solver.t), classification=str(root_context['branch_classification'])))
            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)
            accepted_dt = float(solver.step(candidate_dt))
            hook.accept_current_root()
            after = inventory(solver.U, dx=grid.dx, area_m2=grid.geometry.area_m2)
            expected_step_delta = accepted_dt * grid.geometry.area_m2 * (left_flux - right_flux)
            cumulative_expected_delta += expected_step_delta
            primitive_after = solver.primitive()
            post_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
            row = build_step_row(case_id=CASE_ID, state_id=state_id, requested_step=requested_solver_step, solver=solver, hook=hook, root_context=root_context, dt_limits=dt_limits, candidate_dt=candidate_dt, accepted_dt=accepted_dt, before=before, after=after, initial=initial, expected_step_delta=expected_step_delta, cumulative_expected_delta=cumulative_expected_delta, left_flux=left_flux, right_flux=right_flux, post_reconstruction=post_reconstruction, primitive_after=primitive_after, tolerances=contract['acceptance_tolerances'])
            row.update({'post_endpoint_index': post_index, 'branch_classification': root_context['branch_classification'], 'p_P_minus_p_i_pa': root_context['p_P_minus_p_i_pa'], 'endpoint_residual_kg_s': root_context['endpoint_residual_kg_s'], 'retained_root_mass_tolerance_kg_s': root_context['retained_root_mass_tolerance_kg_s'], 'endpoint_within_locked_root_mass_tolerance': root_context['endpoint_within_locked_root_mass_tolerance'], 'endpoint_admissible': root_context['endpoint_admissible'], 'endpoint_root_closure_passed': root_context['endpoint_root_closure_passed'], 'rarefaction_side_local_sign_change_count': root_context['rarefaction_side_local_sign_change_count'], 'positive_side_local_sign_change_count': root_context['positive_side_local_sign_change_count'], 'connected_rarefaction_sign_change_count': root_context['connected_rarefaction_sign_change_count'], 'connected_rarefaction_residual_monotone': root_context['connected_rarefaction_residual_monotone'], 'connected_rarefaction_stop_reason': root_context['connected_rarefaction_stop_reason'], 'p0_minus_back_pressure_pa': root_context['p0_minus_back_pressure_pa'], 'local_residual_slope_scheme': root_context['root']['local_residual_slope_scheme'], 'positive_pressure_continuation_flux_applied': False, 'finite_compression_branch_approved': False, 'accepted_branch_history': json.dumps(hook.accepted_branch_history)})
            rows.append(row)
            if int(solver.step_count) != requested_solver_step:
                raise BranchClassificationStop('FVM_STEP_DIAGNOSTIC_FAILURE', 'accepted solver step count does not match the requested step')
            if not bool(row['step_passed']):
                raise BranchClassificationStop('FVM_STEP_DIAGNOSTIC_FAILURE', f'accepted solver step {requested_solver_step} failed a retained check')
        except BranchClassificationStop as exc:
            details = exc.diagnostics
            if details.get('local_scan_rows'):
                local_scan_rows.extend(_flatten_local_scan(rows=list(details['local_scan_rows']), requested_solver_step=requested_solver_step, solver_time_s=float(solver.t), classification=exc.classification))
            rows.append(_stop_row(requested_solver_step=requested_solver_step, solver=solver, exc=exc))
            stop_classification = exc.classification
            stop_reason = f'{type(exc).__name__}: {exc}'
            break
        except Exception as exc:
            wrapped = BranchClassificationStop('FVM_STEP_DIAGNOSTIC_FAILURE', f'{type(exc).__name__}: {exc}')
            rows.append(_stop_row(requested_solver_step=requested_solver_step, solver=solver, exc=wrapped))
            stop_classification = wrapped.classification
            stop_reason = f'{type(exc).__name__}: {exc}'
            break
    accepted = [row for row in rows if row.get('accepted_step') is True]
    if stop_classification is None and len(accepted) == MAX_POST_ENDPOINT_ACCEPTED_STEPS and all((row.get('step_passed') is True for row in accepted)) and all((row.get('branch_classification') in {'NEUTRAL_ENDPOINT', 'RAREFACTION'} for row in accepted)):
        outcome = OUTCOME_A
        gate_passed = True
    elif stop_classification == 'LOCAL_COMPRESSION_REQUIRED':
        stop = rows[-1]
        outcome = OUTCOME_B
        gate_passed = bool(stop.get('accepted_step') is False and stop.get('endpoint_within_locked_root_mass_tolerance') is False and (int(stop.get('connected_rarefaction_sign_change_count') or 0) == 0) and (int(stop.get('rarefaction_side_local_sign_change_count') or 0) == 0) and (int(stop.get('positive_side_local_sign_change_count') or 0) == 1) and (stop.get('positive_pressure_continuation_flux_applied') is False))
    else:
        outcome = 'INCONCLUSIVE_DIAGNOSTIC_STOP'
        gate_passed = False
    summary = {'schema_version': 'stage7_u3_b2_a1_post_endpoint_branch_classification_v1', 'scope': 'model_review_only_post_endpoint_short_branch_classification', 'parent_source_sha': PARENT_SOURCE_SHA, 'case_id': CASE_ID, 'cells': int(grid.n_cells), 'cfl': float(geometry['baseline_cfl']), 'starting_accepted_solver_step': STARTING_ACCEPTED_SOLVER_STEP, 'requested_additional_accepted_steps': MAX_POST_ENDPOINT_ACCEPTED_STEPS, 'accepted_additional_steps': len(accepted), 'final_solver_step': int(solver.step_count), 'start_time_s': time_after_step337, 'final_time_s': float(solver.t), 'fixed_local_pressure_offsets_pa': list(PRESSURE_OFFSETS_PA), 'checkpoint_reproduction_ok': bool(resume_summary['checkpoint_reproduction_ok']), 'neutral_endpoint_step337_gate_passed': bool(resume_summary['neutral_endpoint_one_step_gate_passed']), 'step337_summary': resume_summary, 'outcome': outcome, 'stop_classification': stop_classification, 'stop_reason': stop_reason, 'post_endpoint_classification_gate_passed': gate_passed, 'outcome_a_stable_32_steps': outcome == OUTCOME_A, 'outcome_b_local_compression_required': outcome == OUTCOME_B, 'accepted_branch_sequence_including_step337': list(hook.accepted_branch_history), 'accepted_branch_counts_after_step337': dict(Counter((str(row['branch_classification']) for row in accepted))), 'maximum_halving_count': max((int(row['halving_count']) for row in accepted)) if accepted else None, 'minimum_root_velocity_m_s': _minimum(accepted, 'root_velocity_m_s'), 'minimum_outlet_velocity_after_step_m_s': _minimum(accepted, 'outlet_velocity_after_step_m_s'), 'maximum_absolute_endpoint_residual_kg_s': _max_abs(accepted, 'endpoint_residual_kg_s'), 'maximum_absolute_root_mass_residual_kg_s': _max_abs(accepted, 'root_mass_residual_kg_s'), 'maximum_absolute_restriction_reaction_ledger_residual_N': _max_abs(accepted, 'restriction_reaction_ledger_residual_N'), 'maximum_absolute_cumulative_mass_residual_kg': _max_abs(accepted, 'cumulative_mass_residual_kg'), 'maximum_absolute_cumulative_momentum_residual_kg_m_s': _max_abs(accepted, 'cumulative_momentum_residual_kg_m_s'), 'maximum_absolute_cumulative_energy_residual_J': _max_abs(accepted, 'cumulative_energy_residual_J'), 'all_accepted_steps_passed': bool(accepted and all((row.get('step_passed') is True for row in accepted))), 'all_accepted_rho_xv_exact_zero': bool(accepted and all((row.get('rho_xv_exact_zero') is True for row in accepted))), 'any_reverse_velocity_detected': bool(any((row.get('reverse_velocity_detected') is True for row in accepted))), 'any_reverse_flow_guard_triggered': bool(any((row.get('reverse_flow_guard_triggered') is True for row in accepted))), 'positive_pressure_continuation_flux_applied': False, 'finite_compression_branch_approved': False, 'post_endpoint_multi_step_passed': False, 'full_two_l_over_c0_passed': False, 'formal_state_promoted': False, 'u3_b2_finite_pipe_execution_complete': False, 'single_phase_finite_pipe_coupling_verified': False, 'u3_b2_verification_benchmark_accepted': False, 'physical_validation': False, 'design_use_acceptance': False, 'production_hem_activation_approved': False}
    return (rows, local_scan_rows, resume_row, summary, np.asarray(U_step337, dtype=float), np.asarray(solver.U, dtype=float))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--b1-contract', type=Path, required=True)
    parser.add_argument('--model-review-spec', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-git-sha', required=True)
    args = parser.parse_args()
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    rows, local_scan_rows, resume_row, summary, U_step337, U_final = _run_post_endpoint(contract, b1_contract)
    summary['source_git_sha'] = args.source_git_sha
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / 'post_endpoint_steps.csv', rows)
    _write_csv(output / 'local_pressure_scans.csv', local_scan_rows or [{'status': 'NO_LOCAL_SCAN_ROWS', 'positive_pressure_continuation_flux_applied': False}])
    _write_csv(output / 'resume_step_337.csv', [resume_row])
    np.savez_compressed(output / 'post_endpoint_states.npz', U_step337=U_step337, U_final=U_final, starting_solver_step=np.asarray([STARTING_ACCEPTED_SOLVER_STEP], dtype=np.int64), final_solver_step=np.asarray([summary['final_solver_step']], dtype=np.int64), starting_time_s=np.asarray([summary['start_time_s']]), final_time_s=np.asarray([summary['final_time_s']]))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (output / 'report.md').write_text(f"# U3 B2 A1 post-endpoint branch classification\n\nMODEL_REVIEW_ONLY. The exact parent checkpoint and accepted neutral step 337 were reproduced before a maximum of 32 additional branch-aware FvmSolver steps were attempted. The endpoint was evaluated before any sign-change requirement. Positive-pressure isentropic continuation was used only as a local classification observation and never as an applied FVM flux. No finite compression branch, Contract change, production Adapter change, solver change, formal finite-pipe verification, Physical Validation, design use, or production activation is approved.\n\nsource Git SHA: `{args.source_git_sha}`\n\noutcome: `{summary['outcome']}`\n\n```json\n" + json.dumps(summary, indent=2, sort_keys=True) + '\n```\n', encoding='utf-8')
    names = ('post_endpoint_steps.csv', 'local_pressure_scans.csv', 'resume_step_337.csv', 'post_endpoint_states.npz', 'summary.json', 'report.md')
    (output / 'artifact_sha256.txt').write_text(''.join((f'{_sha256(output / name)}  {name}\n' for name in names)), encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary['post_endpoint_classification_gate_passed']:
        raise SystemExit('A1 post-endpoint branch classification gate did not pass')
if __name__ == '__main__':
    main()
