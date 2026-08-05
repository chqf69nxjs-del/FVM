from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Deselect optional artifact-backed tests outside their authoritative CI.

    The U3 B0 adapter workflow supplies both the authoritative reference
    artifact directory and a required flag. Other workflows should not report
    these tests as skipped merely because they do not download that artifact.
    """

    artifact_dir = os.environ.get("U3_B0_REFERENCE_ARTIFACT_DIR")
    artifact_required = os.environ.get("U3_B0_REQUIRE_REFERENCE_ARTIFACT") == "1"
    if artifact_dir or artifact_required:
        return

    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("u3_b0_reference_artifact") is not None:
            deselected.append(item)
        else:
            selected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
