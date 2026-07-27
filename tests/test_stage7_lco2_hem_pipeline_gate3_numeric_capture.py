from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.hem_pipeline_gate3_numeric_capture import (
    HEMGate3NumericCaptureError,
    _array_sha256,
    _normalized_f64,
    compare_metrics_to_authoritative,
)


def test_normalized_f64_is_little_endian_contiguous_and_stable() -> None:
    source = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=">f8").T
    normalized = _normalized_f64(source)

    assert normalized.dtype.str == "<f8"
    assert normalized.flags.c_contiguous
    assert np.array_equal(normalized, source)
    assert _array_sha256(normalized) == _array_sha256(source)


def test_normalized_f64_rejects_nonfinite_capture_values() -> None:
    with pytest.raises(HEMGate3NumericCaptureError, match="finite"):
        _normalized_f64(np.asarray([1.0, np.nan]))


def test_metric_comparison_separates_discrete_numeric_and_hash_fields() -> None:
    expected = {
        "case_id": "case-a",
        "step_count": 12,
        "final_time_s": 1.0,
        "maximum_crossing_quality": 2.0e-8,
        "final_state_sha256": "expected-state",
        "run_signature_sha256": "expected-run",
    }
    actual = {
        **expected,
        "final_time_s": 1.0 + 1.0e-15,
        "final_state_sha256": "local-state",
    }

    result = compare_metrics_to_authoritative(actual, expected)

    assert result["all_discrete_fields_exact"] is True
    assert result["all_numeric_fields_exact"] is False
    assert result["all_hash_fields_exact"] is False
    assert result["numeric"]["final_time_s"]["absolute_difference"] > 0.0
    assert result["hashes"]["final_state_sha256"]["exact"] is False
