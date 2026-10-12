"""Docker health summary, diagnostics, and compose-failure enrich."""

from unittest.mock import patch

import pytest

from raft.errors.cta import OperatorError
from tests.shared.nginx import NginxEmerg

from ...base import make_app
from .base import DockerTestCase


class TestDockerHealthEnrich(DockerTestCase):
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
                return self.ok(NginxEmerg.host_not_found() + "\n")
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
        assert "oauth crash" in self.docker.diagnostics_for(
            containers=("raft-app_tmp",)
        )

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
                self.docker.recreate_pulled_service(
                    app, pull_ref="ghcr.io/org/hub:main"
                )

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
        self.shell.docker.return_value = self.ok(
            '{"Status":"","Health":{"Log":[]}}\n'
        )
        assert self.docker.service_health_summary("app") == "unknown"
        self.shell.docker.return_value = self.ok('{"Status":"exited"}\n')
        assert self.docker.service_health_summary("app") == "exited"
        assert self.docker.diagnostics_for("", containers=("",)) == ""
        self.shell.docker.return_value = self.ok("", returncode=0, stderr="")
        assert "raft-app_tmp" in self.docker.diagnostics_for(
            containers=("raft-app_tmp",)
        )

    def test_not_ready_services(self) -> None:
        def compose(*args, **kwargs):
            if "app" in args:
                return self.ok("cid\n")
            return self.ok("")

        self.shell.compose.side_effect = compose
        self.shell.docker.return_value = self.ok("running unhealthy\n")
        assert "app" in self.docker.not_ready_services(["app", "missing"])
