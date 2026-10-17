"""MetricsPaths gate access log."""
from pathlib import Path
from raft.core.core.config.paths.metrics_paths import MetricsPaths
from tests.unit.base import RaftTestCase

class TestMetricsPathsGate(RaftTestCase):
    def test_gate_access_log(self) -> None:
        home = Path(self.tmp_path)
        assert MetricsPaths(home).gate_access_log().name == "access.log"
