"""Repository-local Working Tool v0-B command-line entry point."""

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

from liquid_gas_transient.working_tool.application_v0_b import (  # noqa: E402
    V0BApplicationError,
    run_loaded_case_v0_b,
)
from liquid_gas_transient.working_tool.case_io import (  # noqa: E402
    CaseFileError,
    load_case_file,
)
from liquid_gas_transient.working_tool.operation_policy import (  # noqa: E402
    WorkingToolOperationPolicy,
)
from liquid_gas_transient.working_tool.output_size import (  # noqa: E402
    estimate_maximum_raw_state_payload,
)
from liquid_gas_transient.working_tool.output_v0_b import (  # noqa: E402
    V0BOutputError,
)
from liquid_gas_transient.working_tool.run_manifest import (  # noqa: E402
    RunManifestError,
)
from liquid_gas_transient.working_tool.storage_projection import (  # noqa: E402
    StateStorageProjectionError,
)
from u3_b2_a1_working_tool_w2_full_horizon_backend import (  # noqa: E402
    A2FullHorizonWorkingToolBackend,
    W2CaseScopeError,
)


PROVISIONAL_NOTICE = (
    "PROVISIONAL ENGINEERING MODEL: this command runs only the locked canonical "
    "single-phase case. Results are not VERIFIED, ACCEPTED, PHYSICALLY "
    "VALIDATED, DESIGN-USE ACCEPTED, or PRODUCTION APPROVED."
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


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be greater than or equal to 1")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the locked canonical liquid-CO2 Working Tool v0-B case with "
            "explicit or automatic create-only output publication."
        )
    )
    parser.add_argument("--case", type=Path, required=True, help="UTF-8 JSON case")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--output-dir",
        type=Path,
        help="exact new output directory; existing paths are rejected",
    )
    destination.add_argument(
        "--output-root",
        type=Path,
        help="root under which a collision-resistant run directory is created",
    )
    parser.add_argument(
        "--state-sample-every",
        type=_positive_int,
        default=1,
        metavar="ACCEPTED_STEPS",
        help="store state_history.npz every N accepted steps; default 1",
    )
    return parser


def _operation_policy(args: argparse.Namespace) -> WorkingToolOperationPolicy:
    if args.output_dir is not None:
        return WorkingToolOperationPolicy.explicit(
            args.output_dir,
            state_sample_interval_accepted_steps=args.state_sample_every,
        )
    return WorkingToolOperationPolicy.auto_run_directory(
        args.output_root,
        state_sample_interval_accepted_steps=args.state_sample_every,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    backend_factory: BackendFactory = _canonical_backend,
) -> int:
    args = _parser().parse_args(argv)
    print(PROVISIONAL_NOTICE, file=sys.stderr)
    try:
        case = load_case_file(args.case)
        policy = _operation_policy(args)
        estimate = estimate_maximum_raw_state_payload(
            n_cells=case.numerics.n_cells,
            max_steps=case.time.max_steps,
            state_sample_interval_accepted_steps=(
                policy.state_sample_interval_accepted_steps
            ),
        )
        pre_run = {
            "event": "WORKING_TOOL_V0_B_PRE_RUN_STORAGE_DISCLOSURE",
            "case_id": case.case_id,
            "provisional_scope": True,
            "storage_mode": policy.storage_mode.value,
            "state_sample_interval_accepted_steps": (
                policy.state_sample_interval_accepted_steps
            ),
            "maximum_state_samples": estimate.maximum_state_samples,
            "raw_state_payload_estimate": estimate.as_dict(),
            "runtime_state_capture_mode": "FULL",
            "runtime_memory_optimized": False,
            "destination_mode": policy.destination_mode.value,
            "requested_destination": str(policy.destination_path),
        }
        print(
            json.dumps(pre_run, indent=2, sort_keys=True, allow_nan=False),
            file=sys.stderr,
        )

        backend = backend_factory()
        receipt = run_loaded_case_v0_b(case, policy, backend)
    except (
        CaseFileError,
        V0BApplicationError,
        V0BOutputError,
        RunManifestError,
        StateStorageProjectionError,
        W2CaseScopeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"WORKING_TOOL_V0_B_INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"WORKING_TOOL_V0_B_RUNTIME_ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    manifest = receipt.package.manifest
    completion = {
        "event": "WORKING_TOOL_V0_B_COMPLETED",
        "case_id": receipt.case.case_id,
        "output_dir": str(receipt.output_dir.resolve()),
        "storage_mode": receipt.projection.storage_mode.value,
        "state_sample_interval_accepted_steps": (
            receipt.projection.state_sample_interval_accepted_steps
        ),
        "runtime_state_capture_mode": "FULL",
        "runtime_memory_optimized": False,
        "accepted_steps": manifest["result"]["accepted_steps"],
        "final_time_s": manifest["result"]["final_time_s"],
        "target_reached": manifest["result"]["target_reached"],
        "full_state_samples": receipt.projection.full_state_samples,
        "stored_state_samples": receipt.projection.stored_state_samples,
        "actual_core_total_bytes": receipt.package.core_total_bytes,
        "formal_status": manifest["formal_status"],
        "warning_codes": [
            warning.code for warning in receipt.projection.result.warnings
        ],
    }
    print(json.dumps(completion, indent=2, sort_keys=True, allow_nan=False))
    print(PROVISIONAL_NOTICE, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
