from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_driven import (
    run_coolprop_internal_valve_driven,
)
from liquid_gas_transient.cases.internal_valve_driven_config import (
    CoolPropInternalValveDrivenConfig,
)
from liquid_gas_transient.plot_internal_valve_driven_results import (
    plot_internal_valve_driven_results,
)
from liquid_gas_transient.properties import coolprop_available


HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp unavailable")
@pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib unavailable")
def test_v012b_artifacts_generate_four_review_plots(tmp_path: Path) -> None:
    cfg = CoolPropInternalValveDrivenConfig(
        n_cells=20,
        probe_fractions=(0.375, 0.625),
        t_end_s=0.01,
        max_steps=1000,
        relative_budget_tolerance=1.0e-8,
    )
    metrics = run_coolprop_internal_valve_driven(tmp_path, cfg)
    result = plot_internal_valve_driven_results(tmp_path, cfg.case_name)

    assert metrics["overall_observation_execution_pass"] is True
    assert result["verification_item"] == "V-012B"
    assert result["plot_count"] == 4
    assert result["solver_rerun"] is False
    assert result["numerical_results_changed"] is False
    for filename in result["plot_files"]:
        assert (tmp_path / filename).stat().st_size > 0
