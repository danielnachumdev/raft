"""Stats package export coverage."""

from __future__ import annotations

from raft.services.ops import stats as stats_pkg
from raft.services.ops.stats import Stats


class TestStatsExport:
    def test_package_exports_stats(self) -> None:
        assert stats_pkg.Stats is Stats
