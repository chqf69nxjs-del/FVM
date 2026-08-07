from __future__ import annotations

import json
import math
from pathlib import Path


CONTRACT = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
)
SPECIFICATION = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_specification.md"
)


def _load() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_identity_preconditions_and_lock_state() -> None:
    contract = _load()
    assert contract["schema_version"] == (
        "stage7_u3_b2_fvm_discharge_coupling_contract_v1"
    )
    assert contract["status"] == "LOCKED_BEFORE_RESULTS"
    assert contract["scope"] == (
        "verification_only_single_phase_fvm_discharge_face_and_finite_pipe_"
        "coupling_benchmark"
    )
    assert contract["issue"] == 135
    assert contract["fluid"] == "CO2"
    assert contract["property_backend"] == {
        "name": "CoolProp",
        "version": "8.0.0",
    }

    dependencies = contract["depends_on"]
    assert dependencies["u3_b0"]["required_state"] == (
        "u3_component_benchmark_accepted=true"
    )
    assert dependencies["u3_b1"]["required_state"] == (
        "u3_b1_component_benchmark_accepted=true"
    )
    assert dependencies["central_record_sync"] == {
        "pr": 134,
        "required_state_before_implementation": "MERGED",
    }


def test_b1_component_is_immutable_and_direct_flux_mapping_is_locked() -> None:
    contract = _load()
    b1 = contract["immutable_b1_component"]
    assert b1["contract_schema"] == "stage7_u3_b1_critical_state_contract_v1"
    assert b1["critical_search"]["coarse_node_count"] == 4097
    assert b1["critical_search"]["final_pressure_bracket_tolerance_pa"] == 1.0
    assert b1["law"]["effective_velocity_m_s"] == "Cd*ideal_velocity_m_s"
    assert b1["law"]["energy_transfer_outward_W"] == (
        "mass_transfer_outward_kg_s*h0"
    )
    assert b1["change_policy"].startswith("no B1 equation")

    fvm = contract["fvm_baseline"]
    assert fvm["numerical_flux"] == "first_order_rusanov"
    assert fvm["time_integrator"] == "explicit_forward_euler"
    assert fvm["right_boundary_mode"] == "direct_external_face_flux_override"
    assert fvm["discharge_ghost_state_synthesis"] is False
    assert fvm["right_boundary_scaffold"].startswith("TransmissiveBoundary")
    assert "external numerical flux is discarded" in fvm["right_boundary_scaffold"]
    assert "before boundary-budget recording" in (
        fvm["right_boundary_application_order"]
    )


def test_geometry_matches_b1_reference_area_and_fixes_mesh_cfl_matrix() -> None:
    contract = _load()
    geometry = contract["geometry"]
    assert geometry["pipe_length_m"] == 1.0
    assert geometry["pipe_area_m2"] == 1.0e-4
    assert math.isclose(
        geometry["pipe_diameter_m"],
        math.sqrt(4.0e-4 / math.pi),
        rel_tol=0.0,
        abs_tol=1.0e-15,
    )
    assert geometry["b1_reference_area_equals_pipe_area"] is True
    assert geometry["baseline_cells"] == 32
    assert geometry["baseline_cfl"] == 0.10
    assert geometry["fixed_mesh_sequence"] == [16, 32, 64]
    assert geometry["fixed_cfl_sequence"] == [0.10, 0.05, 0.025]


def test_stagnation_reconstruction_and_reverse_flow_rule_are_fixed() -> None:
    contract = _load()
    reconstruction = contract["adjacent_cell_to_stagnation_state"]
    assert reconstruction["static_property_pair"] == (
        "CoolProp Dmass,Umass using rho_i,e_i"
    )
    assert reconstruction["stagnation_enthalpy_J_kg"] == (
        "h0_i=h_i+0.5*u_i^2"
    )
    assert reconstruction["stagnation_entropy_J_kg_K"] == "s0_i=s_i"
    assert reconstruction["stagnation_state_reconstruction"] == (
        "CoolProp Hmass,Smass -> p0_i,T0_i"
    )
    assert reconstruction["reverse_adjacent_velocity_rule"].startswith(
        "u_i < -velocity_zero_tolerance_m_s is refused"
    )


def test_face_flux_decomposition_separates_stream_and_pressure_force() -> None:
    contract = _load()
    mapping = contract["right_face_flux_mapping"]
    areas = mapping["areas"]
    assert areas["A_open"] == "B1 effective_area_m2=A_pipe*opening_fraction"
    assert areas["A_closed"] == "A_pipe-A_open"

    transfers = mapping["transfer_decomposition"]
    assert transfers["advective_momentum_rate_out_N"] == (
        "M_dot_stream_B1=m_dot_B1*u_eff_B1"
    )
    assert transfers["open_static_pressure_force_out_N"] == "p_d*A_open"
    assert transfers["closed_static_pressure_force_out_N"] == "p_i*A_closed"
    assert transfers["total_momentum_rate_out_N"] == (
        "M_dot_stream_B1+p_d*A_open+p_i*A_closed"
    )
    assert transfers["vapor_mass_rate_out_kg_s"] == 0.0

    flux = mapping["per_pipe_area_flux"]
    assert flux == {
        "F_rho": "m_dot_B1/A_pipe",
        "F_rho_u": (
            "(M_dot_stream_B1+p_d*A_open+p_i*A_closed)/A_pipe"
        ),
        "F_rho_E": "E_dot_B1/A_pipe",
        "F_rho_xv": 0.0,
    }
    assert mapping["closed_identity"].endswith("[0,p_i,0,0] exactly")
    assert mapping["zero_drop_identity"].endswith("[0,p_i,0,0] exactly")
    assert mapping["guard_policy"].startswith(
        "any B1 or B2 guard fails atomically"
    )


def test_update_inventory_and_acoustic_rules_are_predeclared() -> None:
    contract = _load()
    update = contract["time_step_and_update"]
    assert update["boundary_mass_removal_fraction_limit"] == 0.10
    assert update["boundary_energy_removal_fraction_limit"] == 0.10
    assert update["deterministic_halving"] == {
        "enabled": True,
        "maximum_halvings": 12,
        "failure_outcome": "BOUNDARY_UPDATE_POSITIVITY_FAILURE",
        "no_tolerance_relaxation": True,
    }
    assert update["quadrature"].startswith("left-endpoint rectangular rule")

    inventory = contract["inventory_and_budget"]
    assert inventory["mass_residual_kg"] == (
        "M_pipe(t)+M_out(t)-M_pipe(0)"
    )
    assert inventory["energy_residual_J"] == (
        "E_pipe(t)+E_out(t)-E_pipe(0)"
    )
    assert inventory["vapor_identity"].endswith("remain exact zero")

    acoustic = contract["acoustic_reference"]
    assert acoustic["probe_normalized_positions"] == [0.25, 0.50, 0.75]
    assert acoustic["direct_rarefaction_reference_time"] == (
        "(L-x_probe)/c0"
    )
    assert acoustic["reflected_rarefaction_reference_time"] == (
        "(L+x_probe)/c0"
    )
    assert acoustic["direct_event_signs"] == {
        "pressure_perturbation": "negative",
        "velocity_perturbation": "positive_outward",
        "arrival_order": "probe 0.75, then 0.50, then 0.25",
    }
    detection = acoustic["event_detection"]
    assert detection["history_sampling"] == "every accepted time step"
    assert detection["expected_window_half_width_L_over_c0"] == 0.20
    assert detection["centered_pressure_slope"] == (
        "(p[k+1]-p[k-1])/(t[k+1]-t[k-1])"
    )
    assert detection["direct_sign_check"].endswith("u[k+1]-u[k-1] > 0")
    assert detection["reflected_sign_check"].endswith("u[k+1]-u[k-1] < 0")
    assert detection["unresolved_outcome"] == "ACOUSTIC_EVENT_NOT_RESOLVED"
    assert detection["no_post_result_window_or_threshold_change"] is True

    matrix = contract["mesh_cfl_characterization"]
    assert matrix["fixed_horizon"] == "2.0*L/c0 for LIQUID_SMALL_DROP"
    assert {
        "formal_outcome",
        "cumulative_mass_out_kg",
        "cumulative_energy_out_J",
        "mass_inventory_residual",
        "energy_inventory_residual",
        "direct_rarefaction_arrival_times",
        "reflected_rarefaction_arrival_times",
        "event_signs_and_probe_order",
        "minimum_pressure_pa",
        "maximum_outward_velocity_m_s",
    } == set(matrix["required_metrics"])
    assert "no formal convergence order" in matrix["claim_limit"]


def test_fixed_case_matrix_and_guard_matrix_are_complete() -> None:
    contract = _load()
    cases = contract["benchmark_cases"]
    case_ids = [row["case_id"] for row in cases]
    assert len(case_ids) == 26
    assert len(case_ids) == len(set(case_ids))

    physical = [case_id for case_id in case_ids if not case_id.startswith("G-")]
    guards = [case_id for case_id in case_ids if case_id.startswith("G-")]
    assert len(physical) == 19
    assert len(guards) == 7
    assert set(guards) == {
        "G-01_REVERSE_PRESSURE",
        "G-02_REVERSE_ADJACENT_VELOCITY",
        "G-03_NONFINITE_ADJACENT_STATE",
        "G-04_SINGLE_PHASE_SCOPE_FAILURE",
        "G-05_STAGNATION_RECONSTRUCTION_FAILURE",
        "G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE",
        "G-07_INVENTORY_ORIENTATION_MISMATCH",
    }

    required_physical = {
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
        "B2-04_SMALL_DROP_RECOVERS_B0_FACE_LIMIT",
        "B2-05_UNCHOKED_INITIAL_FACE_MATCHES_B1",
        "B2-06_CRITICAL_TRANSITION_FACE_MAPPING",
        "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE",
        "B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE",
        "B2-10B_FINITE_PIPE_GAS_UNCHOKED_SHORT",
        "B2-10C_FINITE_PIPE_GAS_CHOKED_SHORT",
        "B2-11A_DIRECT_RAREFACTION_PROBE_ORDER",
        "B2-11B_RIGID_WALL_REFLECTION",
        "B2-12_FIXED_MESH_CFL_CHARACTERIZATION",
    }
    assert required_physical <= set(physical)

    matrix = next(
        row
        for row in cases
        if row["case_id"] == "B2-12_FIXED_MESH_CFL_CHARACTERIZATION"
    )
    assert matrix["mesh_sequence"] == [16, 32, 64]
    assert matrix["cfl_sequence"] == [0.10, 0.05, 0.025]
    assert "no formal convergence order" in matrix["claim_limit"]


def test_tolerances_independence_artifacts_and_approval_boundary() -> None:
    contract = _load()
    tolerances = contract["acceptance_tolerances"]
    assert tolerances["exact_zero_absolute"] == 0.0
    assert tolerances["one_step_normalized_state_absolute"] == 5.0e-12
    assert tolerances["mass_inventory_relative"] == 1.0e-10
    assert tolerances["energy_inventory_relative"] == 1.0e-9
    assert tolerances["direct_rarefaction_arrival_relative"] == 0.08
    assert tolerances["reflected_rarefaction_arrival_relative"] == 0.12
    assert tolerances["below_critical_face_plateau_relative"] == 5.0e-6

    independent = contract["independent_paths"]
    assert independent["contract_before_results"] is True
    assert independent["reference_first"] is True
    assert independent["b1_component_shared_as_upstream_authority"] is True
    for key, value in independent.items():
        if key.startswith("shared_b2_") or key == (
            "adapter_imports_b2_reference_module"
        ):
            assert value is False, key

    required = set(contract["required_artifacts"])
    assert {
        "runtime_and_git_provenance.json",
        "face_flux_decomposition.csv",
        "one_step_conservative_update_comparison.csv",
        "cumulative_discharge_and_inventory.csv",
        "momentum_impulse_budget.csv",
        "acoustic_probe_events.csv",
        "reference_adapter_comparison.csv",
        "artifact_sha256.txt",
        "full_repository_junit.xml",
    } <= required

    provenance = contract["runtime_and_provenance"]
    assert provenance["authoritative_runner"] == "ubuntu-24.04"
    assert provenance["python_version"] == "3.12.13"
    assert provenance["numpy_version"] == "2.5.1"
    assert provenance["matplotlib_version"] == "3.11.1"
    assert provenance["pytest_version"] == "9.1.1"
    assert provenance["property_backend"] == "CoolProp"
    assert provenance["property_backend_version"] == "8.0.0"
    assert provenance["reference_and_adapter_source_shas_separate"] is True
    assert provenance["contract_sha256_required"] is True
    assert provenance["artifact_manifest_rule"].startswith("artifact_sha256.txt covers")
    assert "analysis source SHA" in provenance["report_provenance_required"]
    assert "workflow run ID" in provenance["figure_provenance_required"]

    assert all(value is False for value in contract["immutable_scope"].values())

    approval = contract["approval_boundary"]
    assert approval["u3_b2_contract_locked"] is True
    for key, value in approval.items():
        if key != "u3_b2_contract_locked":
            assert value is False, key

    specification = SPECIFICATION.read_text(encoding="utf-8")
    assert "LOCKED_BEFORE_RESULTS" in specification
    assert "direct external-face flux override" in specification
    assert "ACOUSTIC_EVENT_NOT_RESOLVED" in specification
    assert "Runtime and provenance contract" in specification
    assert "physical_discharge_boundary_approved" in specification
    assert "two-phase critical-discharge workを開始しない" in specification
