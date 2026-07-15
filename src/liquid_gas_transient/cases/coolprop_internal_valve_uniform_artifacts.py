from __future__ import annotations

import argparse
import json
from pathlib import Path

from .coolprop_internal_valve_uniform import CoolPropInternalValveUniformConfig, run_coolprop_internal_valve_uniform
from ..plot_internal_valve_results import plot_internal_valve_results


def run_coolprop_internal_valve_uniform_artifacts(output_dir: Path | str, config: CoolPropInternalValveUniformConfig | None = None) -> dict:
    cfg = config or CoolPropInternalValveUniformConfig()
    metrics = run_coolprop_internal_valve_uniform(output_dir, cfg)
    plots = plot_internal_valve_results(output_dir, cfg.case_name)
    return {
        "metrics": metrics,
        "plots": plots,
        "solver_rerun_for_plotting": False,
        "numerical_results_changed_by_plotting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run V-012A and generate review plots")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run_coolprop_internal_valve_uniform_artifacts(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
