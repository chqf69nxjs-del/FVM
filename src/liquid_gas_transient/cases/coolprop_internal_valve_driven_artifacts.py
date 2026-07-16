from __future__ import annotations

import argparse
import json
from pathlib import Path

from .coolprop_internal_valve_driven import (
    CoolPropInternalValveDrivenConfig,
    run_coolprop_internal_valve_driven,
)
from ..plot_internal_valve_driven_results import plot_internal_valve_driven_results


def run_coolprop_internal_valve_driven_artifacts(
    output_dir: Path | str,
    config: CoolPropInternalValveDrivenConfig | None = None,
) -> dict:
    cfg = config or CoolPropInternalValveDrivenConfig()
    metrics = run_coolprop_internal_valve_driven(output_dir, cfg)
    plots = plot_internal_valve_driven_results(output_dir, cfg.case_name)
    return {
        "metrics": metrics,
        "plots": plots,
        "solver_rerun_for_plotting": False,
        "numerical_results_changed_by_plotting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run V-012B and generate review plots")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run_coolprop_internal_valve_driven_artifacts(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
