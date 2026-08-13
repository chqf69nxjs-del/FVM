from __future__ import annotations

from typing import Any

import u3_b2_a1_finite_compression_guard_front_8_step as runner


_original_diagnostic_run = runner.inc8a._run
_active_b1_contract: dict[str, Any] | None = None


class CorrectedDynamicGuardFrontHugoniotHook(
    runner.DynamicGuardFrontHugoniotHook
):
    def __init__(self, *, b1_contract: dict[str, Any], **kwargs: Any) -> None:
        global _active_b1_contract
        _active_b1_contract = b1_contract
        super().__init__(b1_contract=b1_contract, **kwargs)


def _diagnostic_run_with_authoritative_b1(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U,
    parent_root,
):
    del b1_contract
    if _active_b1_contract is None:
        raise RuntimeError("authoritative B1 contract was not bound")
    return _original_diagnostic_run(
        contract=contract,
        b1_contract=_active_b1_contract,
        U=U,
        parent_root=parent_root,
    )


runner.DynamicGuardFrontHugoniotHook = (
    CorrectedDynamicGuardFrontHugoniotHook
)
runner.inc8a._run = _diagnostic_run_with_authoritative_b1


if __name__ == "__main__":
    runner.main()
