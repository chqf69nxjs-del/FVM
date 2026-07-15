from pathlib import Path
import importlib.util
import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_uniform import CoolPropInternalValveUniformConfig, run_coolprop_internal_valve_uniform
from liquid_gas_transient.plot_internal_valve_results import plot_internal_valve_results
from liquid_gas_transient.properties import coolprop_available


HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp unavailable")
@pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib unavailable")
def test_v012a_artifacts_generate_review_plots(tmp_path: Path) -> None:
    cfg = CoolPropInternalValveUniformConfig(
        n_cells=20,
        probe_fractions=(0.25, 0.75),
        t_end_s=5.0e-3,
        max_steps=1000,
    )
    metrics = run_coolprop_internal_valve_uniform(tmp_path, cfg)
    result = plot_internal_valve_results(tmp_path, cfg.case_name)
    assert metrics["overall_observation_execution_pass"] is True
    assert result["plot_count"] == 4
    for filename in result["plot_files"]:
        assert (tmp_path / filename).stat().st_size > 0
