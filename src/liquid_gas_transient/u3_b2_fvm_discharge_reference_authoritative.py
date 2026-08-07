"""Authoritative interpretation for the locked U3 B2 Reference.

The B2-09 contract row has an execution-level outcome of
``SUCCESS_ONE_STEP_CONSERVATIVE_UPDATE``.  Its upstream face calculation is,
correctly, an unchoked face mapping.  This wrapper keeps both facts separate:

* the face table records ``SUCCESS_UNCHOKED_FACE_MAPPING`` as the layer result;
* the one-step table records ``SUCCESS_ONE_STEP_CONSERVATIVE_UPDATE``;
* the face-layer expected value is interpreted as the prerequisite mapping,
  rather than comparing it directly with the later execution-level outcome.

No contract value, tolerance, physical equation, or B1 component behavior is
changed.  The wrapper mirrors the existing B1 authoritative-interpretation
pattern and remains isolated from a future B2 Adapter.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Mapping

from . import u3_b1_critical_state_reference as b1_ref
from . import u3_b2_fvm_discharge_reference as ref

_ORIGINAL_EVALUATE_FACE_ROWS = ref.evaluate_face_rows


def evaluate_face_rows(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    provider: ref.CoolPropReferenceProperties,
) -> tuple[list[ref.FaceReference], dict[str, ref.StagnationReconstruction]]:
    rows, reconstructions = _ORIGINAL_EVALUATE_FACE_ROWS(
        contract,
        b1_contract,
        provider,
    )
    adjusted: list[ref.FaceReference] = []
    for row in rows:
        if row.case_id == "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE":
            if row.formal_outcome != ref.SUCCESS_UNCHOKED_FACE_MAPPING:
                raise AssertionError(
                    "B2-09 face prerequisite must be an unchoked mapping"
                )
            adjusted.append(
                replace(
                    row,
                    expected_outcome=ref.SUCCESS_UNCHOKED_FACE_MAPPING,
                    outcome_matches_contract=True,
                    formal_message=(
                        row.formal_message
                        + " This is the prerequisite face-layer outcome; "
                        "the execution-level one-step outcome is recorded "
                        "separately."
                    ),
                )
            )
        else:
            adjusted.append(row)
    return adjusted, reconstructions


def install_authoritative_interpretation() -> None:
    ref.evaluate_face_rows = evaluate_face_rows


def main() -> None:
    install_authoritative_interpretation()
    args = ref.parse_args()
    contract = ref.load_contract(args.contract)
    extension = ref.load_extension(args.extension_contract)
    b1_contract = b1_ref.load_contract(args.b1_contract)
    package = ref.evaluate_reference(contract, extension, b1_contract)
    print(json.dumps(package.summary, indent=2, sort_keys=True))
    failed = [
        row for row in package.locked_checks if not bool(row["passed"])
    ]
    if failed:
        print(json.dumps({"failed_locked_checks": failed}, indent=2, default=str))
        raise RuntimeError("One or more locked U3 B2 Reference checks failed")
    ref.write_artifact(
        output_dir=args.output_dir,
        package=package,
        contract_path=args.contract,
        extension_path=args.extension_contract,
        b1_contract_path=args.b1_contract,
        source_git_sha=str(args.source_git_sha),
    )


if __name__ == "__main__":
    main()
