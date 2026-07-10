import json
from pathlib import Path

from liquid_gas_transient.case_c_trial_evaluation import (
    DEFAULT_TRIAL_VARIANTS,
    CaseCTrialEvaluationConfig,
    generate_case_c_trial_evaluation,
    standard_trial_parameters,
)


def test_case_c_trial_parameters_use_lco2_surrogate_and_esd_closure():
    p = standard_trial_parameters()
    assert p.eos_model == "lco2_surrogate"
    assert p.phase_change_model == "none"
    assert p.pump_trip_start_s is None
    assert p.valve_close_start_s < p.valve_close_start_s + p.valve_close_time_s < p.t_end_s


def test_case_c_trial_variant_set_contains_single_phase_hem_hne():
    names = {v.name for v in DEFAULT_TRIAL_VARIANTS}
    assert names == {"single_phase", "hem", "hne_tau005"}


def test_case_c_trial_config_is_non_design_by_default():
    cfg = CaseCTrialEvaluationConfig()
    assert cfg.backend_name == "surrogate_lco2"
    assert cfg.require_design_accepted_reference is False


def test_case_c_trial_evaluation_outputs_backend_traceability(tmp_path: Path):
    metrics = generate_case_c_trial_evaluation(
        tmp_path,
        config=CaseCTrialEvaluationConfig(sample_every=20, include_figures=False),
    )

    assert metrics["base_backend_metadata"] == {
        "eos_model": "lco2_surrogate",
        "property_backend_name": "surrogate_lco2",
        "property_backend_design_status": "not_approved_for_design_use",
    }
    rows = metrics["summary_rows"]
    assert rows
    assert all("eos_model" in row for row in rows)
    assert all("property_backend_name" in row for row in rows)
    assert all("property_backend_design_status" in row for row in rows)

    summary_csv = tmp_path / "case_c_trial_summary_v0_6_0.csv"
    assert summary_csv.exists()
    header = summary_csv.read_text(encoding="utf-8").splitlines()[0]
    assert "eos_model" in header
    assert "property_backend_name" in header
    assert "property_backend_design_status" in header

    metrics_json = tmp_path / "case_c_trial_metrics_v0_6_0.json"
    payload = json.loads(metrics_json.read_text(encoding="utf-8"))
    assert payload["base_backend_metadata"] == metrics["base_backend_metadata"]
    assert all("property_backend_name" in row for row in payload["summary_rows"])

    report = (tmp_path / "case_c_trial_evaluation_report_v0_6_0.md").read_text(encoding="utf-8")
    assert "`eos_model`: `lco2_surrogate`" in report
    assert "`property_backend_name`: `surrogate_lco2`" in report
    assert "`property_backend_design_status`: `not_approved_for_design_use`" in report

