"""CLI ``raft metrics`` history + export paths."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.observe.export.service import ExportService
from raft.services.cli.commands.metrics import MetricsCLI
from raft.services.controller.jobs.metrics import METRICS_DIR, METRICS_FILENAME
from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestMetricsCLI(RaftTestCase):
    def _cli(self) -> MetricsCLI:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        return MetricsCLI(stack)

    def _quiet(self):
        return patch("raft.services.cli.commands.metrics.OperatorSay.say")

    def _seed_metrics(self) -> None:
        import json

        ts = datetime.now(timezone.utc).isoformat()
        path = Path(self.tmp_path) / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": ts,
            "host": {"cpus": 2, "loadavg": [1.0], "memory": {"used_percent": 10}},
            "containers": [
                {
                    "service": "site",
                    "role": "app",
                    "group": "demo",
                    "cpu_percent": 4.0,
                    "memory": {"used_percent": 20},
                }
            ],
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    def test_history_catalog_export(self) -> None:
        self._seed_metrics()
        cli = self._cli()
        with self._quiet():
            cli.history(window=3600, service="site", json=True)
            cli.history(window=3600, json=False)
            cli.history(http=True, json=False)
            cli.catalog()
            cli.catalog(json=True)
            out = Path(self.tmp_path) / "m.csv"
            cli.export_metrics(service="site", file=str(out))
            assert out.is_file() and out.stat().st_size > 0

    def test_export_logs_file_and_stdout(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        logs = MagicMock()
        logs.snapshot.return_value = "line\n"
        cli = MetricsCLI(stack, exports=ExportService(stack, logs=logs))
        out = Path(self.tmp_path) / "site.log"
        with self._quiet(), patch("sys.stdout") as stdout:
            stdout.buffer = MagicMock()
            cli.export_logs("site", file=str(out))
            cli.export_logs("site")
        assert out.read_text(encoding="utf-8") == "line\n"
        stdout.buffer.write.assert_called()

    def test_catalog_empty_branch(self) -> None:
        with self._quiet() as say:
            MetricsCLI._print_catalog([], label="logs")
        assert "(none)" in say.call_args[0][0]

    def test_stdout_adds_trailing_newline(self) -> None:
        cli = self._cli()
        with self._quiet(), patch("sys.stdout") as stdout:
            stdout.buffer = MagicMock()
            cli._emit(b"no-nl", file=None)
        writes = [c.args[0] for c in stdout.buffer.write.call_args_list]
        assert writes == [b"no-nl", b"\n"]
