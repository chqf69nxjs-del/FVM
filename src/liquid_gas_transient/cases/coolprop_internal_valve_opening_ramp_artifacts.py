from __future__ import annotations

import argparse
import json
from pathlib import Path

from .coolprop_internal_valve_opening_ramp import run_coolprop_internal_valve_opening_ramp
from .internal_valve_opening_ramp_config import CoolPropInternalValveOpeningRampConfig
from ..plot_internal_valve_opening_ramp_results import plot_internal_valve_opening_ramp_results


def run_coolprop_internal_valve_opening_ramp_artifacts(output_dir: Path | str, config: CoolPropInternalValveOpeningRampConfig | None = None) -> dict:
    cfg = config or CoolPropInternalValveOpeningRampConfig()
    metrics = run_coolprop_internal_valve_opening_ramp(output_dir, cfg)
    plots = plot_internal_valve_opening_ramp_results(output_dir, cfg.case_name)
    return {
        "metrics": metrics,
        "plots": plots,
        "solver_rerun_for_plotting": False,
        "numerical_results_changed_by_plotting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate V-012C artifacts")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run_coolprop_internal_valve_opening_ramp_artifacts(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
