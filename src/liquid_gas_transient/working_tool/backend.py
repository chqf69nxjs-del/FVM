"""Working Tool W0 runtime backend contract."""

from __future__ import annotations

from typing import Protocol

from .case_schema import WorkingToolCase
from .results import BackendRunData


class WorkingToolBackend(Protocol):
    """Backend-independent run API that the W1 A2 adapter must implement."""

    def run_case(self, case: WorkingToolCase) -> BackendRunData:
        ...
