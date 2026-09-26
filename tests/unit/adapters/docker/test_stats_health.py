"""Docker stats, logs, health, and compose enrich."""

from unittest.mock import patch

import pytest

from raft.errors import OperatorError

from ...base import make_app
from .base import DockerTestCase


class TestDockerStatsHealth(DockerTestCase):
    def test_try_service_container_id(self) -> None:
        self.shell.compose.return_value = self.ok("abc123\n")
        assert self.docker.try_service_container_id("app") == "abc123"
        self.shell.compose.return_value = self.ok("", returncode=1)
        assert self.docker.try_service_container_id("app") is None
        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.try_service_container_id("app") is None

    def test_containers_stats_empty_and_error(self) -> None:
        assert self.docker.containers_stats([]) == {}
        self.shell.docker.return_value = self.ok(returncode=1, stderr="boom")
        assert self.docker.containers_stats(["cid1"]) == {}

    def test_containers_stats_parses_rows(self) -> None:
        payload = (
            '{"ID":"cid1","CPUPerc":"1.2%","MemUsage":"1MiB / 64MiB",'
            '"MemPerc":"1.5%","NetIO":"1kB / 2kB","BlockIO":"0B / 0B","PIDs":"3"}\n'
            "\nnot-json\n42\n{\"ID\":\"\"}\n{\"ID\":\"other\",\"CPUPerc\":\"0%\"}\n"
        )
        self.shell.docker.return_value = self.ok(payload)
        by_id = self.docker.containers_stats(["cid1full"])
        assert "cid1" in by_id and by_id["cid1full"]["CPUPerc"] == "1.2%"
        assert "other" in by_id
        assert "cid1full" not in by_id or by_id["cid1full"]["CPUPerc"] == "1.2%"

    def test_containers_stats_container_key(self) -> None:
        self.shell.docker.return_value = self.ok(
            '{"Container":"short","CPUPerc":"0%","MemUsage":"0B / 0B",'
            '"MemPerc":"0%","NetIO":"0B / 0B","BlockIO":"0B / 0B","PIDs":"1"}\n'
        )
        by_container = self.docker.containers_stats(["short"])
        assert by_container["short"]["CPUPerc"] == "0%"

    def test_container_inspect_runtime(self) -> None:
        self.shell.docker.return_value = self.ok(
            "running|2024-01-01T00:00:00Z|250000000|67108864\n"
        )
        info = self.docker.container_inspect_runtime("cid")
        assert info == {
            "status": "running",
            "started_at": "2024-01-01T00:00:00Z",
            "nano_cpus": 250000000,
            "memory_bytes": 67108864,
        }
        self._assert_inspect_edge_cases()

    def _assert_inspect_edge_cases(self) -> None:
        self.shell.docker.return_value = self.ok(returncode=1)
        assert self.docker.container_inspect_runtime("cid") is None
        self.shell.docker.return_value = self.ok("only-one-field\n")
        assert self.docker.container_inspect_runtime("cid") is None
        self.shell.docker.return_value = self.ok("exited|0001-01-01T00:00:00Z|x|y\n")
        info = self.docker.container_inspect_runtime("cid")
        assert info is not None
        assert info["nano_cpus"] is None and info["memory_bytes"] is None

    def test_compose_and_container_logs(self) -> None:
        self.shell.compose.return_value = self.ok(
            'nginx: [emerg] host not found in upstream "old-backend:8000"\n'
        )
        assert "host not found" in self.docker.compose_logs("app")
        self.shell.compose.assert_any_call(
            "logs", "--no-color", "--tail", "40", "app", capture=True, check=False
        )
        assert self.docker.compose_logs() == ""
        self.shell.docker.return_value = self.ok(
            "", returncode=0, stderr="oauth missing CLIENT_ID\n"
        )
        assert "CLIENT_ID" in self.docker.container_logs("raft-app_tmp")
        assert self.docker.container_logs("") == ""

    def test_service_health_summary_and_diagnostics(self) -> None:
        self._assert_health_unhealthy_with_log()
        self._assert_health_absent_and_unknown()
        self._assert_diagnostics_compose_and_tmp()

    def _assert_health_unhealthy_with_log(self) -> None:
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok(
            '{"Status":"running","Health":{"Status":"unhealthy",'
            '"Log":[{"Output":"wget failed\\n"}]}}\n'
        )
        summary = self.docker.service_health_summary("app")
        assert "running/unhealthy" in summary and "healthcheck:" in summary

    def _assert_health_absent_and_unknown(self) -> None:
        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.service_health_summary("app") == "absent"
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok(returncode=1)
        assert self.docker.service_health_summary("app") == "unknown"
        self.shell.docker.return_value = self.ok("not-json\n")
        assert self.docker.service_health_summary("app") == "unknown"
        self.shell.docker.return_value = self.ok("[]\n")
        assert self.docker.service_health_summary("app") == "unknown"

    def _ps_then_logs(self):
        def compose(*args, **kwargs):
            if args[:1] == ("ps",):
                return self.ok("cid\n")
            if args[:1] == ("logs",):
                return self.ok(
                    'nginx: [emerg] host not found in upstream "old-backend:8000"\n'
                )
            return self.ok()

        return compose

    def _assert_diagnostics_compose_and_tmp(self) -> None:
        self.shell.compose.side_effect = self._ps_then_logs()
        self.shell.docker.return_value = self.ok(
            '{"Status":"running","Health":{"Status":"unhealthy","Log":[]}}\n'
        )
        diag = self.docker.diagnostics_for("app")
        assert "host not found" in diag and "--- app" in diag
        self.shell.docker.return_value = self.ok(
            "", returncode=0, stderr="oauth crash: missing env\n"
        )
        assert "oauth crash" in self.docker.diagnostics_for(containers=("raft-app_tmp",))

    def test_enrich_compose_failure_relays_logs(self) -> None:
        self._assert_enrich_appends_diagnostics()
        self._assert_start_and_rebuild_enrich()
        self._assert_recreate_pulled_enrich()
        self._assert_enrich_returns_original()
        self._assert_health_summary_edges()

    def _assert_enrich_appends_diagnostics(self) -> None:
        self.shell.compose.side_effect = self._ps_then_logs()
        self.shell.docker.return_value = self.ok(
            '{"Status":"running","Health":{"Status":"unhealthy","Log":[]}}\n'
        )
        base = OperatorError(
            "docker compose failed while trying to bring the stack up.\n"
            "dependency failed to start: container raft-app-1 is unhealthy",
            has_fix=True,
        )
        enriched = self.docker.enrich_compose_failure(base, services=("app",))
        assert "host not found" in str(enriched)
        assert enriched.has_fix is True

    def _enrich_patch(self, body: str):
        return patch.object(
            self.docker,
            "enrich_compose_failure",
            side_effect=lambda exc, **kw: OperatorError(
                f"{exc}\n\n{body}", has_fix=exc.has_fix
            ),
        )

    def _assert_start_and_rebuild_enrich(self) -> None:
        with self._enrich_patch("--- app ---\nnginx: [emerg] host not found"):
            self.shell.compose.side_effect = None
            self.shell.compose.return_value = self.ok(returncode=1)
            with pytest.raises(RuntimeError, match="host not found"):
                self.docker.start_stack()
            with pytest.raises(RuntimeError, match="host not found"):
                self.docker.rebuild_service("app")

    def _assert_recreate_pulled_enrich(self) -> None:
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        self.shell.docker.return_value = self.ok()
        with self._enrich_patch("--- hub ---\nbad"):
            self.shell.compose.return_value = self.ok(returncode=1)
            with pytest.raises(RuntimeError, match="--- hub ---"):
                self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:main")

    def _assert_enrich_returns_original(self) -> None:
        self.shell.compose.side_effect = None
        self.shell.compose.return_value = self.ok("")
        self.shell.docker.return_value = self.ok("exited none\n")
        bare = OperatorError("compose failed", has_fix=False)
        with patch.object(self.docker, "not_ready_services", return_value=[]):
            assert self.docker.enrich_compose_failure(bare) is bare
        with patch.object(self.docker, "diagnostics_for", return_value=""):
            assert self.docker.enrich_compose_failure(bare, services=("app",)) is bare

    def _assert_health_summary_edges(self) -> None:
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok(
            '{"Status":"running","Health":{"Status":"unhealthy","Log":["x"]}}\n'
        )
        assert "running/unhealthy" in self.docker.service_health_summary("app")
        self.shell.docker.return_value = self.ok('{"Status":"","Health":{"Log":[]}}\n')
        assert self.docker.service_health_summary("app") == "unknown"
        self.shell.docker.return_value = self.ok('{"Status":"exited"}\n')
        assert self.docker.service_health_summary("app") == "exited"
        assert self.docker.diagnostics_for("", containers=("",)) == ""
        self.shell.docker.return_value = self.ok("", returncode=0, stderr="")
        assert "raft-app_tmp" in self.docker.diagnostics_for(containers=("raft-app_tmp",))

    def test_not_ready_services(self) -> None:
        def compose(*args, **kwargs):
            if "app" in args:
                return self.ok("cid\n")
            return self.ok("")

        self.shell.compose.side_effect = compose
        self.shell.docker.return_value = self.ok("running unhealthy\n")
        assert "app" in self.docker.not_ready_services(["app", "missing"])
