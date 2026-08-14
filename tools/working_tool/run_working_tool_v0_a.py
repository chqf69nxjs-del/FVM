"""Repository-local Working Tool v0-A command-line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Callable, Sequence


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    _REPOSITORY_ROOT / "tools" / "verification",
    _REPOSITORY_ROOT / "src",
):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from liquid_gas_transient.working_tool import (  # noqa: E402
    CaseFileError,
    OutputDirectoryError,
    run_case_file,
)
from u3_b2_a1_working_tool_w2_full_horizon_backend import (  # noqa: E402
    A2FullHorizonWorkingToolBackend,
    W2CaseScopeError,
)


PROVISIONAL_NOTICE = (
    "PROVISIONAL ENGINEERING MODEL: this command runs only the locked canonical "
    "single-phase case. Results are not VERIFIED, ACCEPTED, PHYSICALLY "
    "VALIDATED, DESIGN-USE APPROVED, or PRODUCTION APPROVED."
)

BackendFactory = Callable[[], A2FullHorizonWorkingToolBackend]


def _canonical_backend() -> A2FullHorizonWorkingToolBackend:
    return A2FullHorizonWorkingToolBackend(
        contract_path=(
            _REPOSITORY_ROOT
            / "docs"
            / "verification"
            / "stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
        ),
        b1_contract_path=(
            _REPOSITORY_ROOT
            / "docs"
            / "verification"
            / "stage7_u3_b1_critical_state_contract_v1.json"
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the locked canonical liquid-CO2 Working Tool v0-A case from "
            "a strict JSON file."
        )
    )
    parser.add_argument("--case", type=Path, required=True, help="UTF-8 JSON case file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new output directory; existing paths are rejected",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    backend_factory: BackendFactory = _canonical_backend,
) -> int:
    args = _parser().parse_args(argv)
    print(PROVISIONAL_NOTICE, file=sys.stderr)
    try:
        receipt = run_case_file(
            case_path=args.case,
            output_dir=args.output_dir,
            backend=backend_factory(),
        )
    except (CaseFileError, OutputDirectoryError, W2CaseScopeError) as exc:
        print(f"WORKING_TOOL_V0_A_INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"WORKING_TOOL_V0_A_RUNTIME_ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    summary = receipt.result.summary
    completion = {
        "case_id": receipt.case.case_id,
        "output_dir": str(receipt.output_dir.resolve()),
        "accepted_steps": summary.get("accepted_steps"),
        "final_solver_time_s": summary.get("final_solver_time_s"),
        "target_horizon_reached": summary.get("target_horizon_reached"),
        "warning_codes": [warning.code for warning in receipt.result.warnings],
    }
    print(json.dumps(completion, indent=2, sort_keys=True, allow_nan=False))
    print(PROVISIONAL_NOTICE, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
