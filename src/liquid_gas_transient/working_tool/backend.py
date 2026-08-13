"""Working Tool W0 runtime backend contract."""

from __future__ import annotations

from typing import Protocol

from .case_schema import WorkingToolCase
from .results import BackendRunData


class WorkingToolBackend(Protocol):
    """Runtime interface that the W1 A2 live adapter must implement."""

    def run(self, case: WorkingToolCase) -> BackendRunData:
        ...
