from __future__ import annotations

from typing import Protocol

from wireclaim.domain.models import CaseReady


class CaseProcessor(Protocol):
    def __call__(self, case: CaseReady) -> None: ...

