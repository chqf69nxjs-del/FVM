from pathlib import Path
import importlib.util

import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_closing_ramp import (
    run_coolprop_internal_valve_closing_ramp,
)
from liquid_gas_transient.cases.internal_valve_closing_ramp_config import (
    CoolPropInternalValveClosingRampConfig,
)
from liquid_gas_transient.plot_internal_valve_closing_ramp_results import (
    PLOT_SUFFIXES,
    plot_internal_valve_closing_ramp_results,
)
from liquid_gas_transient.properties import coolprop_available


HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp unavailable")
@pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib unavailable")
def test_v012d_artifacts_generate_nine_review_plots(tmp_path: Path) -> None:
    cfg = CoolPropInternalValveClosingRampConfig(
        n_cells=20,
        probe_fractions=(0.45, 0.55),
        ramp_start_s=0.001,
        ramp_duration_s=0.002,
        post_closure_hold_s=0.005,
        t_end_s=0.015,
        max_steps=1000,
        relative_budget_tolerance=1.0e-8,
    )
    metrics = run_coolprop_internal_valve_closing_ramp(tmp_path, cfg)
    result = plot_internal_valve_closing_ramp_results(tmp_path, cfg.case_name)

    assert metrics["overall_observation_execution_pass"] is True
    assert result["verification_item"] == "V-012D"
    assert result["plot_count"] == len(PLOT_SUFFIXES) == 9
    assert result["solver_rerun"] is False
    assert result["numerical_results_changed"] is False
    for suffix in PLOT_SUFFIXES:
        assert (tmp_path / f"{cfg.case_name}_{suffix}.png").stat().st_size > 0
