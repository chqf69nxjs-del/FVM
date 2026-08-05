"""Retain raw U3 B1 reference outcomes before aggregate checks."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .u3_b1_critical_state_reference import (
    CoolPropProvider,
    evaluate_contract,
    load_contract,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    results, candidates, criticals = evaluate_contract(contract, CoolPropProvider())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "results": [asdict(result) for result in results],
        "critical_states": {
            key: {
                "pressure_pa": value.pressure_pa,
                "pressure_ratio": value.pressure_ratio,
                "effective_mass_flux_kg_m2_s": value.stream.effective_mass_flux_kg_m2_s,
                "formal_path_termination": value.path_termination_outcome,
                "path_termination_pressure_pa": value.path_termination_pressure_pa,
                "peak_prominence_relative": value.peak_prominence_relative,
            }
            for key, value in criticals.items()
        },
        "candidate_record_count": len(candidates),
    }
    (args.output_dir / "raw_reference_diagnostic.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(result.case_id, result.formal_outcome, result.formal_message)


if __name__ == "__main__":
    main()
