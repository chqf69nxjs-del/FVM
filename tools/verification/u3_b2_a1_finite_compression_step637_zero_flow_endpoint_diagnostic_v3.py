from __future__ import annotations

import u3_b2_a1_finite_compression_step637_zero_flow_endpoint_diagnostic_v2 as diagnostic


STALE_PARENT_SOURCE_SHA = "8d0568abd827684562783393650d6f63f3aa390f"
STALE_EXPECTED_TIME_S = 0.0042695827462251995
AUTHORITATIVE_PARENT_SOURCE_SHA = "c89a992d69c2985fc081fe3750c5b27136d3941e"
AUTHORITATIVE_EXPECTED_TIME_S = 0.004269583083221582


def _assert_frozen_increment_9j_scope() -> None:
    """Fail closed unless this wrapper is correcting only the known binding defect."""

    assert diagnostic.PARENT_SOURCE_SHA == STALE_PARENT_SOURCE_SHA
    assert diagnostic.EXPECTED_TIME_S == STALE_EXPECTED_TIME_S
    assert diagnostic.PARENT_RUN == 31670285271
    assert diagnostic.PARENT_JOB == 94353300958
    assert diagnostic.PARENT_ARTIFACT == 9169437776
    assert diagnostic.PARENT_ARTIFACT_NAME == (
        "u3-b2-a1-finite-compression-increment-9i-root-schema-31670285271"
    )
    assert diagnostic.EXPECTED_STEP == 637
    assert diagnostic.NEXT_STEP == 638
    assert diagnostic.ULTRAFINE_LOWER_FACTOR == 0.98
    assert diagnostic.ULTRAFINE_UPPER_FACTOR == 1.02
    assert diagnostic.ULTRAFINE_NODE_COUNT == 4097
    assert diagnostic.BROAD_LOWER_FACTOR == 0.50
    assert diagnostic.BROAD_UPPER_FACTOR == 2.00
    assert diagnostic.BROAD_NODE_COUNT == 513
    assert diagnostic.SCALAR_BISECTION_ITERATIONS == 80
    assert diagnostic.base.WEAK_COMPRESSION_CHI_LIMIT == 1.0e-6
    assert diagnostic.base.DIAGNOSTIC_CHI_CAP == 1.0e-4
    assert diagnostic.ROOT_TOLERANCE == 1.0e-8


def main() -> None:
    _assert_frozen_increment_9j_scope()

    # Correct only the immutable parent authority binding. All diagnostic
    # equations, scope limits, scan sizes, tolerances, gates, and output
    # schemas remain those fixed in the imported Increment 9J implementation.
    diagnostic.PARENT_SOURCE_SHA = AUTHORITATIVE_PARENT_SOURCE_SHA
    diagnostic.EXPECTED_TIME_S = AUTHORITATIVE_EXPECTED_TIME_S
    diagnostic.main()


if __name__ == "__main__":
    main()
