"""Status package export coverage."""

from __future__ import annotations

from raft.ops import status as status_pkg
from raft.ops.status import Status


class TestStatusExport:
    def test_package_exports_status(self) -> None:
        assert status_pkg.Status is Status
