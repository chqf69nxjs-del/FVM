from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import pytest

from liquid_gas_transient.hem_pipeline_4mpa_mesh_sensitivity import (
    MeshCaseMetrics,
)
from liquid_gas_transient.hem_pipeline_cfl_sensitivity import (
    CFL_ANALYSIS_ID,
    CFL_STEP_CAPS,
    CFL_VALUES,
    FOUR_MPA_CASE_ID,
    THRESHOLD_GUARD_FAILURE_REASON,
)
from liquid_gas_transient.hem_pipeline_cfl_sensitivity_sharded_evidence import (
    CELLS_CSV_NAME,
    COMBINED_EXECUTION_MODE,
    CASES_CSV_NAME,
    HEMPipelineCflColumnResult,
    HEMPipelineCflShardedEvidenceError,
    SHARD_SUMMARY_NAME,
    STEPS_CSV_NAME,
    _resolved_cfl,
    combine_pipeline_cfl_sensitivity_shards,
    write_pipeline_cfl_sensitivity_shard,
)


TEST_PROVENANCE = {
    "analysis_id": CFL_ANALYSIS_ID,
    "analysis_model": "HEM",
    "property_backend_name": "coolprop_co2",
    "property_backend_version": "8.0.0-test",
    "source_git_sha": "source-sha",
    "checkout_git_sha": "checkout-sha",
    "git_status_porcelain": "",
    "python_version": "3.12-test",
    "numpy_version": "2.5-test",
    "verification_only": True,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}


def _metric(
    case_id: str,
    pressure_pa: float,
    cfl: float,
    index: int,
) -> MeshCaseMetrics:
    distance = 0.10 + 0.01 * index
    q = 1.0e-7 * (index + 1)
    return MeshCaseMetrics(
        run_id=f"{case_id}__n128__cfl{cfl}",
        case_id=case_id,
        role="diagnostic",
        final_boundary_pressure_pa=pressure_pa,
        n_cells=128,
        dx_m=1.0 / 128.0,
        maximum_steps=CFL_STEP_CAPS[cfl],
        cfl=cfl,
        outcome="GUARD_FAILURE",
        failure_reason=THRESHOLD_GUARD_FAILURE_REASON,
        step_count=100 + index,
        final_time_s=1.0e-3 + index * 1.0e-6,
        initial_acoustic_time_s=2.0e-3,
        maximum_horizon_s=6.0e-3,
        preflight_accepted_sample_count=65,
        raw_crossing_observed=True,
        crossing_step=100 + index,
        crossing_time_s=1.0e-3 + index * 1.0e-6,
        normalized_crossing_time=0.5 + index * 1.0e-3,
        crossing_cell_index=110 + index,
        crossing_cell_center_m=1.0 - distance,
        crossing_distance_from_outlet_m=distance,
        normalized_crossing_distance_from_outlet=distance,
        maximum_crossing_quality=q,
        maximum_projected_quality=q,
        maximum_void_fraction=7.0 * q,
        crossing_delta_u_sat_j_kg=0.01 * (index + 1),
        crossing_delta_v_sat_m3_kg=1.0e-10 * (index + 1),
        crossing_q_from_internal_energy=q,
        crossing_q_from_specific_volume=q,
        pre_crossing_liquid_sound_speed_m_s=460.0,
        raw_crossing_sound_speed_m_s=43.0,
        sound_speed_ratio_raw_to_pre=43.0 / 460.0,
        closest_liquid_step=None,
        closest_liquid_time_s=None,
        closest_liquid_cell_index=None,
        closest_liquid_distance_from_outlet_m=None,
        closest_liquid_delta_u_sat_j_kg=None,
        closest_liquid_delta_v_sat_m3_kg=None,
        closest_liquid_q_from_internal_energy=None,
        closest_liquid_q_from_specific_volume=None,
        projection_vapor_source_kg=q,
        boundary_vapor_transport_kg=0.0,
        mass_residual_kg=0.0,
        momentum_residual_kg_m_s=0.0,
        energy_residual_J=0.0,
        combined_vapor_residual_kg=0.0,
        reverse_flow_fallback_count=0,
        final_state_sha256=f"state-{cfl}-{index}",
        run_signature_sha256=f"signature-{cfl}-{index}",
    )


def _column(cfl: float) -> HEMPipelineCflColumnResult:
    cases = (
        _metric(
            "pipeline_crossing_candidate_p5m5_to_p2m5",
            2.0e6,
            cfl,
            0,
        ),
        _metric(
            "pipeline_moderate_diagnostic_p5m5_to_p3m5",
            3.0e6,
            cfl,
            1,
        ),
        _metric(FOUR_MPA_CASE_ID, 4.0e6, cfl, 2),
    )
    return HEMPipelineCflColumnResult(
        cfl=cfl,
        cases=cases,
        provenance=dict(TEST_PROVENANCE),
    )


def _write_minimal_csv(path: Path, cfl: float) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cfl", "record"])
        writer.writeheader()
        writer.writerow({"cfl": cfl, "record": "synthetic"})


def _write_synthetic_shard(path: Path, cfl: float) -> None:
    path.mkdir(parents=True)
    column = _column(cfl)
    (path / SHARD_SUMMARY_NAME).write_text(
        json.dumps(column.summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_minimal_csv(path / STEPS_CSV_NAME, cfl)
    _write_minimal_csv(path / CELLS_CSV_NAME, cfl)
    _write_minimal_csv(path / CASES_CSV_NAME, cfl)


def test_resolved_cfl_keeps_only_locked_values() -> None:
    assert _resolved_cfl("0.10") == 0.10
    assert _resolved_cfl(0.05) == 0.05
    with pytest.raises(HEMPipelineCflShardedEvidenceError):
        _resolved_cfl(0.075)


def test_shard_writer_emits_three_case_machine_readable_bundle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    column = _column(0.05)

    def fake_run(cfl, *, case_runner, on_case_result, provenance):
        assert float(cfl) == 0.05
        assert case_runner is not None
        assert provenance == TEST_PROVENANCE
        assert on_case_result is not None
        return column

    import liquid_gas_transient.hem_pipeline_cfl_sensitivity_sharded_evidence as module

    monkeypatch.setattr(
        module,
        "collect_cfl_runtime_provenance",
        lambda: dict(TEST_PROVENANCE),
    )
    monkeypatch.setattr(
        module,
        "run_fixed_pipeline_cfl_column",
        fake_run,
    )

    result, paths = write_pipeline_cfl_sensitivity_shard(
        tmp_path, 0.05
    )
    assert result is column
    summary = json.loads(
        paths["summary_json"].read_text(encoding="utf-8")
    )
    assert summary["case_count"] == 3
    assert summary["cfl"] == 0.05
    assert summary["low_cfl_result_accepted"] is False
    with paths["cases_csv"].open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert paths["steps_csv"].is_file()
    assert paths["cells_csv"].is_file()


def test_combiner_requires_all_three_locked_cfl_columns(
    tmp_path: Path,
) -> None:
    first = tmp_path / "0p100"
    second = tmp_path / "0p050"
    _write_synthetic_shard(first, 0.10)
    _write_synthetic_shard(second, 0.05)
    with pytest.raises(
        HEMPipelineCflShardedEvidenceError,
        match="expected 3 shard directories",
    ):
        combine_pipeline_cfl_sensitivity_shards(
            [first, second],
            tmp_path / "combined",
        )


def test_combiner_builds_full_bundle_without_rerunning_solver(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import liquid_gas_transient.hem_pipeline_cfl_sensitivity_sharded_evidence as module

    directories = []
    for token, cfl in (
        ("0p100", 0.10),
        ("0p050", 0.05),
        ("0p025", 0.025),
    ):
        path = tmp_path / token
        _write_synthetic_shard(path, cfl)
        directories.append(path)

    monkeypatch.setattr(
        module,
        "_assert_128_cell_cfl_0p10_baseline",
        lambda metric: None,
    )

    def fake_plots(target, result):
        assert len(result.cases) == 9
        paths = {}
        for name in module.PLOT_KEYS:
            path = target / f"{name}.png"
            path.write_bytes(b"synthetic-png")
            paths[name] = path
        return paths

    monkeypatch.setattr(module, "_generate_plots", fake_plots)

    result, paths = combine_pipeline_cfl_sensitivity_shards(
        directories,
        tmp_path / "combined",
    )
    assert len(result.cases) == 9
    assert [case.cfl for case in result.cases] == [
        0.10,
        0.10,
        0.10,
        0.05,
        0.05,
        0.05,
        0.025,
        0.025,
        0.025,
    ]

    summary = json.loads(
        paths["summary_json"].read_text(encoding="utf-8")
    )
    assert summary["case_count"] == 9
    assert summary["execution_mode"] == COMBINED_EXECUTION_MODE
    assert summary["cfl_shard_count"] == 3
    assert summary["gate4_execution_completed_in_ci"] is True
    assert summary["low_cfl_result_accepted"] is False

    with paths["steps_csv"].open(
        newline="", encoding="utf-8"
    ) as handle:
        step_rows = list(csv.DictReader(handle))
    with paths["cells_csv"].open(
        newline="", encoding="utf-8"
    ) as handle:
        cell_rows = list(csv.DictReader(handle))
    assert len(step_rows) == 3
    assert len(cell_rows) == 3


def test_sharded_module_does_not_redefine_numerical_solver() -> None:
    import liquid_gas_transient.hem_pipeline_cfl_sensitivity_sharded_evidence as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert 'production_hem_activation_approved": True' not in source
    assert 'low_cfl_result_accepted": True' not in source
