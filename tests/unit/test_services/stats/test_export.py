"""Stats package export coverage."""

from __future__ import annotations

import raft.services as services
from raft.services.ops.stats import Stats


class TestStatsExport:
    def test_lazy_export(self) -> None:
        assert services.Stats is Stats
