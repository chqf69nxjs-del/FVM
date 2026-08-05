"""Retain raw U3 B1 reference outcomes before aggregate checks."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .u3_b1_critical_state_reference import (
    CoolPropProvider,
    evaluate_contract,
    load_contract,
)


def _coarse_probes(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    first_series: dict[str, list[dict[str, Any]]] = {}
    closed_keys: set[str] = set()
    for row in candidates:
        key = f"{row.get('state_id')}|Cd={float(row.get('discharge_coefficient', 0.0)):g}"
        index = int(row["coarse_index"])
        if key in closed_keys:
            continue
        if key in first_series and index == 0:
            closed_keys.add(key)
            continue
        first_series.setdefault(key, []).append(row)

    probes: dict[str, Any] = {}
    for key, rows in first_series.items():
        admissible = [row for row in rows if bool(row["admissible"])]
        if not admissible:
            probes[key] = {"admissible_count": 0}
            continue
        maximum = sorted(
            admissible,
            key=lambda row: (
                -float(row["effective_mass_flux_kg_m2_s"]),
                -float(row["pressure_pa"]),
            ),
        )[0]
        position = admissible.index(maximum)
        higher = admissible[position - 1] if position > 0 else None
        lower = admissible[position + 1] if position + 1 < len(admissible) else None
        peak = float(maximum["effective_mass_flux_kg_m2_s"])
        neighbor_fluxes = [
            float(row["effective_mass_flux_kg_m2_s"])
            for row in (higher, lower)
            if row is not None
        ]
        coarse_prominence = (
            (peak - max(neighbor_fluxes)) / peak if neighbor_fluxes and peak > 0.0 else None
        )
        termination = next((row for row in rows if not bool(row["admissible"])), None)
        probes[key] = {
            "admissible_count": len(admissible),
            "coarse_max_index": int(maximum["coarse_index"]),
            "coarse_max_pressure_pa": float(maximum["pressure_pa"]),
            "coarse_max_pressure_ratio": float(maximum["pressure_ratio"]),
            "coarse_max_effective_mass_flux_kg_m2_s": peak,
            "higher_pressure_neighbor_pa": None if higher is None else float(higher["pressure_pa"]),
            "lower_pressure_neighbor_pa": None if lower is None else float(lower["pressure_pa"]),
            "coarse_neighbor_prominence_relative": coarse_prominence,
            "retained_high_pressure_pa": float(admissible[0]["pressure_pa"]),
            "retained_low_pressure_pa": float(admissible[-1]["pressure_pa"]),
            "distance_from_retained_high_pa": float(admissible[0]["pressure_pa"]) - float(maximum["pressure_pa"]),
            "distance_from_retained_low_pa": float(maximum["pressure_pa"]) - float(admissible[-1]["pressure_pa"]),
            "termination_outcome": None if termination is None else termination["formal_outcome"],
            "termination_pressure_pa": None if termination is None else float(termination["pressure_pa"]),
        }
    return probes


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
        "coarse_search_probes": _coarse_probes(candidates),
    }
    (args.output_dir / "raw_reference_diagnostic.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(result.case_id, result.formal_outcome, result.formal_message)
    print(json.dumps(payload["coarse_search_probes"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
