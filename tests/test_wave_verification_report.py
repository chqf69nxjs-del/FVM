import csv
import json
from pathlib import Path

from liquid_gas_transient.reporting_wave_verification import (
    generate_coolprop_small_amplitude_wave_verification_report,
)

FORBIDDEN = [
    "validated model",
    "approved for design use",
    "production-ready thermodynamic model",
    "exact solution",
    "fully converged waveform",
]


def _write_synthetic_inputs(tmp_path: Path):
    rows = []
    data = [
        (50, 2.0, 0.5, 0.4553800128186122, 2.190060202200722, 0.0861239270194091, 8.430136233444699e-06, 0.029374780269285354, 0.04549523995349944, 0.44370205402325547),
        (100, 1.0, 0.5, 0.5846173597369343, 1.7084165543899732, 0.054850051676234905, 1.1067211212296402e-05, 0.012231108577913484, 0.022919789014997225, 0.2746404473234001),
        (200, 0.5, 0.5, 0.7130140873556957, 1.4016966321299833, 0.033470164649422623, 1.3817667285120004e-05, 0.003754118078367246, 0.00916599998481389, 0.11995409640205147),
        (400, 0.25, 0.5, 0.8207045770296827, 1.21821098523697, 0.01946331543604777, 1.6299980056317806e-05, 0.0007994348541787551, 0.006981309471038414, 0.0),
        (100, 1.0, 0.25, 0.52, 1.9, 0.06, 1.2e-5, 0.015, 0.03, 0.33),
    ]
    for n, dx, cfl, amp, fwhm, eth, ep, ecen, ecc, wl2 in data:
        case_id = f"n{n:04d}_cfl{int(round(cfl*100)):03d}"
        rows.append({
            "case_id": case_id,
            "n_cells": n,
            "dx_m": dx,
            "cfl": cfl,
            "step_count": 100 + n,
            "runtime_seconds": 0.1 + n / 1000,
            "c0": 500.0,
            "overall_observation_run_pass": True,
            "remained_single_phase": True,
            "budget_mass_relative_residual": 1e-15,
            "energy_budget_balance_relative_residual": 2e-15,
            "primary_probe_amplitude_ratio_L2": amp,
            "primary_probe_amplitude_ratio_3L4": amp * 0.95,
            "primary_probe_fwhm_broadening_ratio_L2": fwhm,
            "primary_probe_fwhm_broadening_ratio_3L4": fwhm * 1.05,
            "interprobe_threshold_speed_m_s": 500 * (1 + eth),
            "interprobe_peak_speed_m_s": 500 * (1 + ep),
            "interprobe_centroid_speed_m_s": 500 * (1 + ecen),
            "interprobe_cross_correlation_speed_m_s": 500 * (1 + ecc),
            "interprobe_threshold_speed_relative_error": eth,
            "interprobe_peak_speed_relative_error": ep,
            "interprobe_centroid_speed_relative_error": ecen,
            "interprobe_cross_correlation_speed_relative_error": ecc,
            "cross_correlation_coefficient": 0.99,
            "waveform_l1_difference_vs_finest": wl2 * 0.9,
            "waveform_l2_difference_vs_finest": wl2,
            "eos_model": "coolprop_lco2",
            "property_backend_name": "coolprop_co2",
            "property_backend_design_status": "not_approved_for_design_use",
            "coolprop_version": "synthetic-coolprop",
            "output_version": "coolprop_small_amplitude_wave_sweep_v1",
            "vapor_mass_budget_balance_relative_residual": 0.0,
            "missing_budget_fields": "",
        })
    summary_path = tmp_path / "coolprop_small_amplitude_wave_sweep_sweep_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    metrics = {
        "output_version": "coolprop_small_amplitude_wave_sweep_v1",
        "design_evaluation": False,
        "run_plan": [
            {"case_id": "n0050_cfl050", "comparison_groups": ["mesh_comparison"]},
            {"case_id": "n0100_cfl050", "comparison_groups": ["cfl_comparison", "mesh_comparison"]},
            {"case_id": "n0200_cfl050", "comparison_groups": ["mesh_comparison"]},
            {"case_id": "n0400_cfl050", "comparison_groups": ["mesh_comparison"]},
            {"case_id": "n0100_cfl025", "comparison_groups": ["cfl_comparison"]},
        ],
        "summary_rows": rows,
        "mesh_comparison_summary_rows": rows[:4],
        "overall_sweep_execution_pass": True,
        "numerical_convergence_observation": "monotonic_shape_improvement_with_phase_speed_at_error_floor",
        "finest_grid_comparison_reference": "n0400_cfl050",
        "convergence_by_metric": {
            "threshold_speed": {"classification": "monotonic_improvement", "optional_local_orders": {"local_order_estimates": [0.6509, 0.7126, 0.7821]}},
            "peak_speed": {"classification": "at_error_floor_or_non_monotonic", "optional_local_orders": {"local_order_estimates": []}},
            "centroid_speed": {"classification": "monotonic_improvement", "optional_local_orders": {"local_order_estimates": [1.2640, 1.7040, 2.2314]}},
            "cross_correlation_speed": {"classification": "monotonic_improvement", "optional_local_orders": {"local_order_estimates": [0.9891, 1.3222, 0.3928]}},
            "amplitude_retention": {"classification": "monotonic_improvement", "optional_local_orders": {"local_order_estimates": [0.3908, 0.5335, 0.6786]}},
            "fwhm_broadening": {"classification": "monotonic_improvement", "optional_local_orders": {"local_order_estimates": [0.7484, 0.8185, 0.8804]}},
            "waveform_difference": {"classification": "monotonic_improvement_against_finest_reference", "optional_local_orders": {"local_order_estimates": []}},
            "overall_classification": "monotonic_shape_improvement_with_phase_speed_at_error_floor",
        },
        "generated_plots": ["coolprop_small_amplitude_wave_sweep_mesh_overlay_L2.png"],
    }
    metrics_path = tmp_path / "coolprop_small_amplitude_wave_sweep_sweep_metrics.json"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    (tmp_path / "coolprop_small_amplitude_wave_sweep_mesh_overlay_L2.png").write_bytes(b"fake plot")
    (tmp_path / "coolprop_small_amplitude_wave_sweep_sweep_report.md").write_text("existing report", encoding="utf-8")
    (tmp_path / "coolprop_small_amplitude_wave_sweep_comparison_plot.png").write_bytes(b"fake comparison")
    for row in rows:
        case_dir = tmp_path / row["case_id"] / "nested"
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "coolprop_small_amplitude_wave_probe_pressure_history.png").write_bytes(b"probe png")
        (case_dir / "coolprop_small_amplitude_wave_probe_history.csv").write_text("t,p\n0,1\n", encoding="utf-8")
    return metrics_path, summary_path


def test_generate_wave_verification_report_from_synthetic_sweep(tmp_path, monkeypatch):
    metrics_path, summary_path = _write_synthetic_inputs(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "coolprop_small_amplitude_wave_verification_report_v1.md"

    meta = generate_coolprop_small_amplitude_wave_verification_report(metrics_path, summary_path, out, artifact_root=tmp_path)

    assert Path(meta["report_path"]).exists()
    text = out.read_text(encoding="utf-8")
    for heading in [
        "# CoolProp単相小振幅波 Numerical Verification Report",
        "## 1. Executive summary",
        "## 5. Test matrix",
        "### Mesh comparison",
        "### CFL comparison",
        "## 9. Mesh convergence observation",
        "## 11. Figures and artifact index",
        "## 12. Verification conclusion",
    ]:
        assert heading in text
    for token in ["n0050_cfl050", "n0100_cfl050", "n0200_cfl050", "n0400_cfl050", "n0100_cfl025"]:
        assert token in text
    assert "monotonic_shape_improvement_with_phase_speed_at_error_floor" in text
    assert "error floor" in text
    assert "finest-grid comparison reference" in text
    assert "真の解ではなく" in text
    assert "- eos_model: coolprop_lco2" in text
    assert "- property_backend_name: coolprop_co2" in text
    assert "- property_backend_design_status: not_approved_for_design_use" in text
    assert "property_backend_design_status = not_approved_for_design_use" in text
    assert "design_evaluation = false" in text
    assert "acceptance_gate = false" in text
    assert "validation = false" in text
    assert "overall_sweep_execution_pass: True" in text
    assert "overall_sweep_execution_pass: 1" not in text
    assert "mass relative residual" in text
    assert "energy balance relative residual" in text
    assert "vapor mass balance relative residual" in text
    assert "missing budget fields" in text
    assert "probe pressure history" in text
    assert "probe history CSV" in text
    assert "n0050_cfl050/nested/coolprop_small_amplitude_wave_probe_pressure_history.png" in text
    assert "n0050_cfl050/nested/coolprop_small_amplitude_wave_probe_history.csv" in text
    assert "not found / not included" in text
    assert "](missing" not in text
    assert "git_commit_hash | unknown" in text
    for phrase in FORBIDDEN:
        assert phrase not in text.lower()

    manifest = json.loads(Path(meta["manifest_path"]).read_text(encoding="utf-8"))
    artifact_paths = [a["relative_path"] for a in manifest["artifacts"]]
    assert any(p.endswith("coolprop_small_amplitude_wave_sweep_sweep_metrics.json") for p in artifact_paths)
    assert any(p.endswith("coolprop_small_amplitude_wave_sweep_sweep_summary.csv") for p in artifact_paths)
    assert any(p.endswith("coolprop_small_amplitude_wave_sweep_sweep_report.md") for p in artifact_paths)
    assert any(p.endswith("coolprop_small_amplitude_wave_sweep_comparison_plot.png") for p in artifact_paths)
    assert any(p.endswith("coolprop_small_amplitude_wave_verification_report_v1.md") for p in artifact_paths)
    assert all(len(a["sha256"]) == 64 for a in manifest["artifacts"])


def test_wave_report_marks_inconsistent_run_traceability(tmp_path, monkeypatch):
    metrics_path, summary_path = _write_synthetic_inputs(tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["summary_rows"][0]["eos_model"] = "alternate_eos"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "report.md"

    generate_coolprop_small_amplitude_wave_verification_report(metrics_path, summary_path, out, artifact_root=tmp_path)

    text = out.read_text(encoding="utf-8")
    assert "- eos_model: inconsistent: alternate_eos, coolprop_lco2" in text
    assert "](missing" not in text
