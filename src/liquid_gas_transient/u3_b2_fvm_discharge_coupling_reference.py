"""Independent U3 B2 FVM discharge-coupling Reference and CLI."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from ._u3_b2_reference_contract import *  # noqa: F401,F403
from ._u3_b2_reference_types import *  # noqa: F401,F403
from ._u3_b2_reference_properties import *  # noqa: F401,F403
from ._u3_b2_reference_b1 import *  # noqa: F401,F403
from ._u3_b2_reference_face import *  # noqa: F401,F403
from ._u3_b2_reference_balance import *  # noqa: F401,F403
from ._u3_b2_reference_acoustic import *  # noqa: F401,F403
from ._u3_b2_reference_checks import *  # noqa: F401,F403
from ._u3_b2_reference_io import *  # noqa: F401,F403
from ._u3_b2_reference_runner import write_artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--extension-contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()
    summary = write_artifact(
        args.contract,
        args.extension_contract,
        args.b1_contract,
        args.output_dir,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["all_expected_outcomes_match"]:
        raise SystemExit("Expected formal outcomes did not all match")
    if not summary["all_locked_checks_passed"]:
        raise SystemExit("One or more locked B2 Reference checks failed")


if __name__ == "__main__":
    main()
