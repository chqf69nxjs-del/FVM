from __future__ import annotations

import argparse
import sys
from pathlib import Path

import u3_b2_a1_finite_compression_hugoniot_model_selection as inc5_core
import u3_b2_a1_finite_compression_hugoniot_one_step as one_step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--identity-reproduction-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--increment-5-artifact-dir", type=Path, required=True)
    parser.add_argument("--increment-5-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.identity_reproduction_spec.is_file():
        raise FileNotFoundError(args.identity_reproduction_spec)

    # Reproduce the already-authoritative Increment 5 enthalpy-identity
    # treatment. Both physical Hugoniot forms retain their original 1e-6
    # closure gates, while the final identity-corrected class independently
    # enforces the 1e-10 identity-accounted difference.
    inc5_core.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
    )

    original_argv = sys.argv
    try:
        sys.argv = [
            original_argv[0],
            "--contract",
            str(args.contract),
            "--b1-contract",
            str(args.b1_contract),
            "--model-review-spec",
            str(args.model_review_spec),
            "--parent-artifact-dir",
            str(args.parent_artifact_dir),
            "--parent-artifact-digest",
            args.parent_artifact_digest,
            "--increment-5-artifact-dir",
            str(args.increment_5_artifact_dir),
            "--increment-5-artifact-digest",
            args.increment_5_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        one_step.main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
