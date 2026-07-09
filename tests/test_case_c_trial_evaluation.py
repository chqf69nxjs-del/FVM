from liquid_gas_transient.case_c_trial_evaluation import (
    DEFAULT_TRIAL_VARIANTS,
    CaseCTrialEvaluationConfig,
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
