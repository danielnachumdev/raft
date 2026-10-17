"""Import order: alerts before controller.jobs and reverse."""

import subprocess
import sys
from tests.unit.base import RaftTestCase


class TestImportOrder(RaftTestCase):
    def test_alerts_then_jobs(self) -> None:
        self._run(
            "import raft.core.observe.alerts; import raft.services.controller.jobs"
        )

    def test_jobs_then_alerts(self) -> None:
        self._run(
            "import raft.services.controller.jobs; import raft.core.observe.alerts"
        )

    def _run(self, code: str) -> None:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
