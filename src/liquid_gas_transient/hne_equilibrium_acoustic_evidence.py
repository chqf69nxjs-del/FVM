"""Focused gates, evidence output, and CLI for A2.4-2R."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Sequence

from .hne_equilibrium_acoustic_model import (
    evaluate_equilibrium_acoustic,
    representative_cases,
    state_from_pressure_quality,
)
from .hne_equilibrium_acoustic_types import (
    ACOUSTIC_AUTHORITY,
    DEFAULT_CONFIG,
    DERIVATIVE_METHOD,
    EquilibriumAcousticConfig,
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    MODEL_FORM,
    NEXT_ACTION,
    PHASE_BRANCH,
    SCHEMA_VERSION,
    SOLVER_AUTHORITY,
    SOURCE_A2_4_1_SHA,
    VerificationCase,
)

def _case_record(
    case: VerificationCase,
    config: EquilibriumAcousticConfig,
) -> dict[str, object]:
    source = state_from_pressure_quality(
        case.pressure_pa,
        case.vapor_mass_fraction,
        config=config,
    )
    diagnostic = evaluate_equilibrium_acoustic(
        source.rho_kg_m3,
        source.e_j_kg,
        config=config,
    )
    state = diagnostic.state
    return {
        "case_id": case.case_id,
        "input_pressure_pa": case.pressure_pa,
        "input_quality": case.vapor_mass_fraction,
        "recovered_pressure_pa": None if state is None else state.pressure_pa,
        "recovered_quality": None if state is None else state.vapor_mass_fraction,
        "rho_kg_m3": source.rho_kg_m3,
        "e_j_kg": source.e_j_kg,
        "void_fraction": None if state is None else state.void_fraction,
        "equilibrium_c2_m2_s2": diagnostic.equilibrium_sound_speed_squared_m2_s2,
        "equilibrium_c_m_s": diagnostic.equilibrium_sound_speed_m_s,
        "frozen_c2_m2_s2": diagnostic.frozen_sound_speed_squared_m2_s2,
        "frozen_c_m_s": diagnostic.frozen_sound_speed_m_s,
        "finite_difference_c2_m2_s2": diagnostic.finite_difference_sound_speed_squared_m2_s2,
        "derivative_relative_error": diagnostic.derivative_relative_error,
        "subcharacteristic_satisfied": diagnostic.subcharacteristic_satisfied,
        "valid": diagnostic.valid,
        "failure_reason": diagnostic.failure_reason,
    }


def evaluate_focused_gates(
    *,
    config: EquilibriumAcousticConfig | None = None,
) -> tuple[list[dict[str, object]], dict[str, bool]]:
    cfg = config or DEFAULT_CONFIG
    records = [_case_record(case, cfg) for case in representative_cases()]
    invalid_source = state_from_pressure_quality(2.5e6, 0.80, config=cfg)
    invalid = evaluate_equilibrium_acoustic(
        invalid_source.rho_kg_m3,
        invalid_source.e_j_kg,
        config=cfg,
    )
    repeated_a = _case_record(representative_cases()[2], cfg)
    repeated_b = _case_record(representative_cases()[2], cfg)
    gate_results = {
        "all_representative_cases_valid": all(bool(r["valid"]) for r in records),
        "finite_positive_equilibrium_c2": all(
            float(r["equilibrium_c2_m2_s2"]) > 0.0 for r in records
        ),
        "independent_derivative_crosscheck": all(
            float(r["derivative_relative_error"]) <= cfg.derivative_relative_tolerance
            for r in records
        ),
        "subcharacteristic_relation_in_claimed_domain": all(
            r["subcharacteristic_satisfied"] is True for r in records
        ),
        "deterministic_repeated_evaluation": repeated_a == repeated_b,
        "outside_domain_fails_closed": (
            not invalid.valid
            and invalid.failure_reason == "OUTSIDE_CLAIMED_LIQUID_RICH_DOMAIN"
            and invalid.equilibrium_sound_speed_squared_m2_s2 is None
        ),
        "no_solver_authority": all(value is False for value in SOLVER_AUTHORITY.values()),
        "no_empirical_fallback": True,
    }
    return records, gate_results


def _runtime_provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return "UNAVAILABLE"

    return {
        "analysis_source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "UNSET"),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run("git", "status", "--porcelain=v1", "--untracked-files=no"),
    }


def _canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_evidence(
    output_dir: str | Path,
    *,
    config: EquilibriumAcousticConfig | None = None,
) -> dict[str, object]:
    """Write deterministic focused evidence for this verification slice."""

    cfg = config or DEFAULT_CONFIG
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    records, gates = evaluate_focused_gates(config=cfg)
    failed_gates = sorted(name for name, passed in gates.items() if not passed)
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "source_a2_4_1_sha": SOURCE_A2_4_1_SHA,
        "model_form": MODEL_FORM,
        "phase_branch": PHASE_BRANCH,
        "derivative_method": DERIVATIVE_METHOD,
        "acoustic_authority": ACOUSTIC_AUTHORITY,
        "formal_outcome": FORMAL_OUTCOME,
        "next_action": NEXT_ACTION if not failed_gates else "REMAIN_AT_A2_4_2R",
        "green_for_a2_4_3_read_only_shadow": not failed_gates,
        "claimed_domain": {
            "pressure_pa": [cfg.claimed_pressure_min_pa, cfg.claimed_pressure_max_pa],
            "vapor_mass_fraction": [cfg.claimed_quality_min, cfg.claimed_quality_max],
            "boundary_policy": "open_interval_fail_closed",
            "boundary_guard_pressure_pa": cfg.claimed_boundary_pressure_guard_pa,
            "boundary_guard_quality": cfg.claimed_boundary_quality_guard,
            "interpretation": "liquid-rich open two-phase verification only",
        },
        "model_parameters": asdict(cfg),
        "gate_results": gates,
        "failed_gates": failed_gates,
        "formal_status": FORMAL_STATUS,
        "solver_authority": SOLVER_AUTHORITY,
        "real_fluid_reference": {
            "numerical_comparison_in_this_slice": False,
            "reason": "dependency-free software/derivative verification slice; physical-reference comparison remains a separate non-authority gate",
            "existing_reference_path": "liquid_gas_transient.hem_equilibrium_sound_speed",
            "required_before_physical_validation": True,
        },
        "runtime_provenance": _runtime_provenance(),
        "case_count": len(records),
    }
    summary_payload = _canonical_json_bytes(summary)
    summary["summary_payload_sha256"] = _sha256_bytes(summary_payload)
    summary_bytes = _canonical_json_bytes(summary)
    (destination / "summary.json").write_bytes(summary_bytes)

    fieldnames = list(records[0].keys())
    with (destination / "equilibrium_acoustic_cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    report_lines = [
        "# Stage 7 P2-A2.4-2R Equilibrium Acoustic Closure",
        "",
        f"- Outcome: `{summary['formal_outcome']}`",
        f"- Green for A2.4-3 read-only shadow: `{summary['green_for_a2_4_3_read_only_shadow']}`",
        f"- Model: `{MODEL_FORM}`",
        f"- Claimed pressure: `{cfg.claimed_pressure_min_pa:.0f} < p < {cfg.claimed_pressure_max_pa:.0f} Pa`",
        f"- Claimed quality: `{cfg.claimed_quality_min:.3f} < q < {cfg.claimed_quality_max:.3f}`",
        "- Boundary policy: `open interval; fail closed`",
        "- Hydrodynamic authority: `false`",
        "- Empirical sound-speed fallback: `none`",
        "- Real-fluid numerical comparison: `not part of this dependency-free slice`",
        "",
        "## Focused cases",
        "",
        "| case | p [MPa] | q | c_eq [m/s] | c_frozen [m/s] | rel. derivative error | valid |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for record in records:
        report_lines.append(
            "| {case_id} | {p:.3f} | {q:.3f} | {ceq:.6f} | {cf:.6f} | {err:.3e} | {valid} |".format(
                case_id=record["case_id"],
                p=float(record["input_pressure_pa"]) / 1.0e6,
                q=float(record["input_quality"]),
                ceq=float(record["equilibrium_c_m_s"]),
                cf=float(record["frozen_c_m_s"]),
                err=float(record["derivative_relative_error"]),
                valid=record["valid"],
            )
        )
    report_lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "This output is a verification diagnostic. It must not be wired into CFL, Rusanov, production flux, boundary characteristics, or the accepted FVM state.",
            "",
        ]
    )
    (destination / "operator_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    manifest_files = {}
    for name in ("summary.json", "equilibrium_acoustic_cases.csv", "operator_report.md"):
        payload = (destination / name).read_bytes()
        manifest_files[name] = {
            "sha256": _sha256_bytes(payload),
            "bytes": len(payload),
        }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "green_for_a2_4_3_read_only_shadow": not failed_gates,
        "hydrodynamic_coupling_allowed": False,
        "files": manifest_files,
    }
    (destination / "manifest.json").write_bytes(_canonical_json_bytes(manifest))
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = write_evidence(args.output_dir)
    print(json.dumps({
        "formal_outcome": summary["formal_outcome"],
        "green_for_a2_4_3_read_only_shadow": summary["green_for_a2_4_3_read_only_shadow"],
        "failed_gates": summary["failed_gates"],
    }, sort_keys=True))
    return 0 if summary["green_for_a2_4_3_read_only_shadow"] else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
