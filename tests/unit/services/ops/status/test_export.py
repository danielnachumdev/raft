"""Status package export coverage."""

from __future__ import annotations

from raft.services.ops import status as status_pkg
from raft.services.ops.status import Status


class TestStatusExport:
    def test_package_exports_status(self) -> None:
        assert status_pkg.Status is Status
