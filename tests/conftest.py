from __future__ import annotations

import os
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class OptionalArtifactSuite:
    marker: str
    directory_environment: str
    required_environment: str


OPTIONAL_ARTIFACT_SUITES = (
    OptionalArtifactSuite(
        marker="u3_b0_reference_artifact",
        directory_environment="U3_B0_REFERENCE_ARTIFACT_DIR",
        required_environment="U3_B0_REQUIRE_REFERENCE_ARTIFACT",
    ),
    OptionalArtifactSuite(
        marker="u3_b1_reference_artifact",
        directory_environment="U3_B1_REFERENCE_ARTIFACT_DIR",
        required_environment="U3_B1_REQUIRE_REFERENCE_ARTIFACT",
    ),
)


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Deselect artifact-backed tests outside their authoritative workflow."""

    unavailable_markers = {
        suite.marker
        for suite in OPTIONAL_ARTIFACT_SUITES
        if not os.environ.get(suite.directory_environment)
        and os.environ.get(suite.required_environment) != "1"
    }
    if not unavailable_markers:
        return

    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if any(
            item.get_closest_marker(marker) is not None
            for marker in unavailable_markers
        ):
            deselected.append(item)
        else:
            selected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
