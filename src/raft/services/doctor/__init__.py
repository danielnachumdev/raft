"""Environment diagnostics for operators (`raft doctor`).

Public surface matches the former ``services.doctor`` module.
"""

from __future__ import annotations

import shutil  # noqa: F401 — re-export for unit-test patch targets
import socket  # noqa: F401 — re-export for unit-test patch targets

from .models import INFRA, RAFT_GROUP, UNGROUPED, CheckResult, Status
from .service import Doctor

__all__ = [
    "INFRA",
    "RAFT_GROUP",
    "UNGROUPED",
    "CheckResult",
    "Doctor",
    "Status",
]
