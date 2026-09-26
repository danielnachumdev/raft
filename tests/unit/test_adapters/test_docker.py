"""DockerStack helpers (shell mocked)."""

from unittest.mock import patch

import pytest

from raft.models.ports import PortSpec
from raft.services.certs import MissingOriginCerts

from ..base import make_app
from .base import AdapterTestCase


class TestDockerStack(AdapterTestCase):
    @pytest.fixture(autouse=True)
    def _docker_setup(self, _adapter_setup) -> None:
        self.docker = self.docker_stack()

    def test_start_stop_and_running(self) -> None:
        def compose(*args, **kwargs):
            if args[:1] == ("ps",) and "raft-gate" in args:
                return self.ok("cid1\n")
            if args[:1] == ("ps",) and "app" in args:
                # Newly applied service not in compose yet.
                return self.ok("", returncode=1)
            if args[:1] == ("ps",):
                return self.ok("")
            return self.ok()

        self.shell.compose.side_effect = compose
        assert self.docker.running_services() == ["raft-gate"]
        self.shell.compose.assert_any_call(
            "ps", "-q", "--status", "running", "raft-gate", capture=True, check=False
        )
        self.docker.start_stack()
        self.docker.stop_stack()
        self.shell.compose.assert_any_call(
            "up", "-d", "--build", "--remove-orphans", capture=False, check=False
        )
        self.shell.compose.assert_any_call(
            "down", "--remove-orphans", capture=False, check=False
        )
        self.shell.docker.assert_called()

    def test_recreate_rebuild(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.recreate_router()
        self.docker.rebuild_service("app")
        self.shell.compose.assert_any_call(
            "up", "-d", "--no-deps", "--force-recreate", "raft-router",
            capture=False, check=False,
        )
        self.shell.compose.assert_any_call(
            "up", "-d", "--build", "--no-deps", "app", capture=False, check=False
        )

    def test_recreate_pulled_service_tags_then_up(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok()
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:abc")
        self.shell.docker.assert_any_call(
            "pull", "ghcr.io/org/hub:abc", capture=True, check=False
        )
        self.shell.docker.assert_any_call(
            "tag", "ghcr.io/org/hub:abc", "ghcr.io/org/hub:main",
            capture=True, check=False,
        )
        self.shell.compose.assert_any_call(
            "up", "-d", "--no-deps", "--no-build", "--force-recreate", "hub",
            capture=False, check=False,
        )

    def test_recreate_pulled_service_skips_tag_when_pin(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok()
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:main")
        self.shell.docker.assert_any_call(
            "pull", "ghcr.io/org/hub:main", capture=True, check=False
        )
        assert not any(c.args[:1] == ("tag",) for c in self.shell.docker.call_args_list)

    def test_recreate_pulled_service_unauthorized(self) -> None:
        self.shell.docker.return_value = self.ok(
            returncode=1, stderr="Error response from daemon: unauthorized\n"
        )
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        with pytest.raises(RuntimeError, match="docker login") as exc:
            self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:main")
        assert "unauthorized" in str(exc.value).lower() or "login" in str(exc.value).lower()

    def test_service_container_id_missing(self) -> None:
        self.shell.compose.return_value = self.ok("  \n")
        with pytest.raises(RuntimeError, match="not running"):
            self.docker.service_container_id("app")

    def test_service_is_ready_running_healthy_or_no_healthcheck(self) -> None:
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok("running healthy\n")
        assert self.docker.service_is_ready("app") is True

        self.shell.docker.return_value = self.ok("running none\n")
        assert self.docker.service_is_ready("app") is True

        self.shell.docker.return_value = self.ok("running starting\n")
        assert self.docker.service_is_ready("app") is False

        self.shell.docker.return_value = self.ok("exited none\n")
        assert self.docker.service_is_ready("app") is False

        self.shell.docker.return_value = self.ok("", returncode=1)
        assert self.docker.service_is_ready("app") is False

        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.service_is_ready("app") is False

    def test_service_runtime_and_heal_actions(self) -> None:
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok("running unhealthy\n")
        assert self.docker.service_runtime("app") == ("running", "unhealthy")
        self.shell.docker.return_value = self.ok("exited none\n")
        assert self.docker.service_runtime("app") == ("exited", "none")
        self.shell.compose.return_value = self.ok("", returncode=1)
        assert self.docker.service_runtime("app") == ("missing", "none")
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok("", returncode=1)
        assert self.docker.service_runtime("app") == ("missing", "none")
        self.shell.docker.return_value = self.ok("\n")
        assert self.docker.service_runtime("app") == ("missing", "none")
        self.shell.compose.return_value = self.ok()
        self.docker.restart_service("app")
        self.shell.compose.assert_any_call(
            "restart", "app", capture=False, check=False
        )
        self.docker.start_service("app")
        self.shell.compose.assert_any_call(
            "up", "-d", "--no-deps", "--no-build", "app", capture=False, check=False
        )

    def test_restart_and_start_service_enrich_failures(self) -> None:
        from raft.errors import OperatorError

        with patch.object(
            self.docker,
            "enrich_compose_failure",
            side_effect=lambda exc, **kw: OperatorError(
                f"{exc}\n\n--- app ---\nbad",
                has_fix=True,
            ),
        ):
            self.shell.compose.return_value = self.ok(returncode=1)
            with pytest.raises(RuntimeError, match="--- app ---"):
                self.docker.restart_service("app")
            with pytest.raises(RuntimeError, match="--- app ---"):
                self.docker.start_service("app")

    def test_container_image_ref_named_ok(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("raft-app:latest\n"),
            self.ok("sha256:abc\n"),
        ]
        assert self.docker.container_image_ref("cid") == "raft-app:latest"

    def test_container_image_ref_commits_when_unnamed(self) -> None:
        self.shell.docker.side_effect = [self.ok(""), self.ok()]
        assert self.docker.container_image_ref("abcdefghijklmn") == "raft-snapshot:abcdefghijkl"

    def test_container_image_ref_commits_when_named_missing(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("gone:tag\n"),
            self.ok("", returncode=1),
            self.ok(),
        ]
        assert self.docker.container_image_ref("cid1234567890") == "raft-snapshot:cid123456789"

    def test_container_image_id_falls_back_to_ref(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("img:tag\n"),
            self.ok("sha256:id\n"),
            self.ok("  \n"),
        ]
        assert self.docker.container_image_id("cid") == "img:tag"

    def test_router_network_first_or_default(self) -> None:
        self.shell.compose.return_value = self.ok("routerid\n")
        self.shell.docker.return_value = self.ok("net_a\nnet_b\n")
        assert self.docker.router_network() == "net_a"
        self.shell.docker.return_value = self.ok("\n")
        assert self.docker.router_network() == "raft_default"

    def test_run_tmp_and_remove(self) -> None:
        self.shell.docker.return_value = self.ok()
        self.docker.run_tmp(name="n", alias="a", image="img", network="net")
        assert self.shell.docker.call_count >= 2

    def test_run_tmp_passes_env_file(self) -> None:
        self.shell.docker.return_value = self.ok()
        self.docker.run_tmp(
            name="n",
            alias="a",
            image="img",
            network="net",
            env_file="/tmp/app.env",
        )
        run_call = next(
            c
            for c in self.shell.docker.call_args_list
            if c.args and c.args[0] == "run"
        )
        assert "--env-file" in run_call.args
        assert "/tmp/app.env" in run_call.args

    def test_router_can_fetch_and_nginx_reload(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=0)
        assert self.docker.router_can_fetch("app") is True
        self.shell.compose.return_value = self.ok(returncode=1)
        assert self.docker.router_can_fetch("app") is False
        self.shell.compose.return_value = self.ok()
        assert self.docker.router_can_fetch("app", path="/ping") is True
        self.shell.compose.assert_any_call(
            "exec",
            "-T",
            "raft-router",
            "wget",
            "-qO-",
            "http://app:80/ping",
            check=False,
            capture=True,
        )
        self.shell.compose.return_value = self.ok()
        self.docker.nginx_test_and_reload()
        self.shell.compose.assert_any_call(
            "exec", "-T", "raft-router", "nginx", "-t", capture=True, check=False
        )
        self.shell.compose.assert_any_call(
            "exec", "-T", "raft-router", "nginx", "-s", "reload",
            capture=True, check=False,
        )

    def test_reload_gate_nginx(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.reload_gate_nginx()
        self.shell.compose.assert_any_call(
            "exec", "-T", "raft-gate", "nginx", "-t", capture=True, check=False
        )
        self.shell.compose.assert_any_call(
            "exec", "-T", "raft-gate", "nginx", "-s", "reload",
            capture=True, check=False,
        )

    def test_reload_gate_nginx_captures_cert_failure(self) -> None:
        self.shell.compose.return_value = self.ok(
            returncode=1,
            stderr='cannot load certificate "/etc/nginx/certs/web/origin.pem"',
        )
        with pytest.raises(RuntimeError, match="could not load Origin TLS certificates"):
            self.docker.reload_gate_nginx()

    def test_reload_gate_nginx_lists_missing_certs(self) -> None:
        self.shell.compose.return_value = self.ok(
            returncode=1,
            stderr='cannot load certificate "/etc/nginx/certs/web/origin.pem"',
        )
        missing = [MissingOriginCerts("web", ("origin.pem",))]
        with patch(
            "raft.adapters.docker_edge.missing_origin_certs",
            return_value=missing,
        ):
            with pytest.raises(RuntimeError, match="Origin certs missing"):
                self.docker.reload_gate_nginx()

    def test_reload_router_nginx_rejects_bad_config(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="syntax error")
        with pytest.raises(RuntimeError, match="router nginx rejected"):
            self.docker.reload_router_nginx()

    def test_reload_gate_nginx_rejects_non_cert_error(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="unknown directive")
        with pytest.raises(RuntimeError, match="gate nginx rejected"):
            self.docker.reload_gate_nginx()

    def test_reload_router_nginx_reload_failure(self) -> None:
        self.shell.compose.side_effect = [
            self.ok(),  # nginx -t
            self.ok(returncode=1, stderr="reload failed"),
        ]
        with pytest.raises(RuntimeError, match="reload failed"):
            self.docker.reload_router_nginx()

    def test_service_container_id_compose_failure(self) -> None:
        self.shell.compose.return_value = self.ok(
            returncode=1, stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(RuntimeError, match="Docker daemon"):
            self.docker.service_container_id("app")

    def test_container_image_ref_commit_failure(self) -> None:
        self.shell.docker.side_effect = [
            self.ok(returncode=1, stderr="Cannot connect to the Docker daemon"),
            self.ok(returncode=1, stderr="commit failed"),
        ]
        with pytest.raises(RuntimeError, match="snapshot running container"):
            self.docker.container_image_ref("cid1234567890")

    def test_router_network_inspect_failure(self) -> None:
        self.shell.compose.return_value = self.ok("routerid\n")
        self.shell.docker.return_value = self.ok(
            returncode=1, stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(RuntimeError, match="Docker daemon"):
            self.docker.router_network()

    def test_reload_nginx_empty_detail_and_gate_reload_fail(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="")
        with pytest.raises(RuntimeError, match="router nginx rejected"):
            self.docker.reload_router_nginx()
        with pytest.raises(RuntimeError, match="gate nginx rejected"):
            self.docker.reload_gate_nginx()

        self.shell.compose.side_effect = [
            self.ok(),  # -t ok
            self.ok(returncode=1, stderr=""),  # reload fail empty
        ]
        with pytest.raises(RuntimeError, match="gate recreate"):
            self.docker.reload_gate_nginx()

    def test_router_sees_upstream_target(self) -> None:
        port = PortSpec(name="http", container_port=80, expose="http")
        self.shell.compose.return_value = self.ok(returncode=0)
        assert self.docker.router_sees_upstream_target(self.app, "app_tmp", port) is True
        self.shell.compose.return_value = self.ok(returncode=1)
        assert self.docker.router_sees_upstream_target(self.app, "app_tmp", port) is False

    def test_recreate_gate_and_published_ports(self) -> None:
        self.shell.compose.return_value = self.ok("gatecid\n")
        self.docker.recreate_gate()
        self.shell.compose.assert_any_call(
            "up", "-d", "--no-deps", "--force-recreate", "raft-gate",
            capture=False, check=False,
        )
        self.shell.docker.return_value = self.ok("80/tcp 443/tcp\n")
        assert self.docker.gate_published_ports() == [80, 443]
        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.gate_published_ports() == []

    def test_try_service_container_id(self) -> None:
        self.shell.compose.return_value = self.ok("abc123\n")
        assert self.docker.try_service_container_id("app") == "abc123"
        self.shell.compose.return_value = self.ok("", returncode=1)
        assert self.docker.try_service_container_id("app") is None
        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.try_service_container_id("app") is None

    def test_containers_stats(self) -> None:
        assert self.docker.containers_stats([]) == {}
        self.shell.docker.return_value = self.ok(returncode=1, stderr="boom")
        assert self.docker.containers_stats(["cid1"]) == {}
        payload = (
            '{"ID":"cid1","CPUPerc":"1.2%","MemUsage":"1MiB / 64MiB",'
            '"MemPerc":"1.5%","NetIO":"1kB / 2kB","BlockIO":"0B / 0B","PIDs":"3"}\n'
            "\n"
            "not-json\n"
            "42\n"
            '{"ID":""}\n'
            '{"ID":"other","CPUPerc":"0%"}\n'
        )
        self.shell.docker.return_value = self.ok(payload)
        by_id = self.docker.containers_stats(["cid1full"])
        assert "cid1" in by_id
        assert by_id["cid1full"]["CPUPerc"] == "1.2%"
        assert "other" in by_id
        assert "cid1full" not in by_id or by_id["cid1full"]["CPUPerc"] == "1.2%"
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
        self.shell.docker.return_value = self.ok(returncode=1)
        assert self.docker.container_inspect_runtime("cid") is None
        self.shell.docker.return_value = self.ok("only-one-field\n")
        assert self.docker.container_inspect_runtime("cid") is None
        self.shell.docker.return_value = self.ok("exited|0001-01-01T00:00:00Z|x|y\n")
        info = self.docker.container_inspect_runtime("cid")
        assert info is not None
        assert info["nano_cpus"] is None
        assert info["memory_bytes"] is None

    def test_compose_and_container_logs(self) -> None:
        self.shell.compose.return_value = self.ok(
            'nginx: [emerg] host not found in upstream "old-backend:8000"\n'
        )
        assert "host not found" in self.docker.compose_logs("app")
        self.shell.compose.assert_any_call(
            "logs",
            "--no-color",
            "--tail",
            "40",
            "app",
            capture=True,
            check=False,
        )
        assert self.docker.compose_logs() == ""
        self.shell.docker.return_value = self.ok(
            "", returncode=0, stderr="oauth missing CLIENT_ID\n"
        )
        assert "CLIENT_ID" in self.docker.container_logs("raft-app_tmp")
        assert self.docker.container_logs("") == ""

    def test_service_health_summary_and_diagnostics(self) -> None:
        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok(
            '{"Status":"running","Health":{"Status":"unhealthy",'
            '"Log":[{"Output":"wget failed\\n"}]}}\n'
        )
        summary = self.docker.service_health_summary("app")
        assert "running/unhealthy" in summary
        assert "healthcheck:" in summary

        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.service_health_summary("app") == "absent"

        self.shell.compose.return_value = self.ok("cid\n")
        self.shell.docker.return_value = self.ok(returncode=1)
        assert self.docker.service_health_summary("app") == "unknown"
        self.shell.docker.return_value = self.ok("not-json\n")
        assert self.docker.service_health_summary("app") == "unknown"
        self.shell.docker.return_value = self.ok("[]\n")
        assert self.docker.service_health_summary("app") == "unknown"

        def compose(*args, **kwargs):
            if args[:1] == ("ps",):
                return self.ok("cid\n")
            if args[:1] == ("logs",):
                return self.ok(
                    'nginx: [emerg] host not found in upstream "old-backend:8000"\n'
                )
            return self.ok()

        self.shell.compose.side_effect = compose
        self.shell.docker.return_value = self.ok(
            '{"Status":"running","Health":{"Status":"unhealthy","Log":[]}}\n'
        )
        diag = self.docker.diagnostics_for("app")
        assert "host not found" in diag
        assert "--- app" in diag

        self.shell.docker.return_value = self.ok(
            "", returncode=0, stderr="oauth crash: missing env\n"
        )
        tmp_diag = self.docker.diagnostics_for(containers=("raft-app_tmp",))
        assert "oauth crash" in tmp_diag

    def test_enrich_compose_failure_relays_logs(self) -> None:
        from raft.errors import OperatorError

        def compose(*args, **kwargs):
            if args[:1] == ("ps",):
                return self.ok("cid\n")
            if args[:1] == ("logs",):
                return self.ok(
                    'nginx: [emerg] host not found in upstream "old-backend:8000"\n'
                )
            return self.ok(returncode=1)

        self.shell.compose.side_effect = compose
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

        # start_stack should enrich on failure (services inferred from not-ready).
        with patch.object(
            self.docker,
            "enrich_compose_failure",
            side_effect=lambda exc, **kw: OperatorError(
                f"{exc}\n\n--- app ---\nnginx: [emerg] host not found",
                has_fix=exc.has_fix,
            ),
        ):
            self.shell.compose.side_effect = None
            self.shell.compose.return_value = self.ok(returncode=1)
            with pytest.raises(RuntimeError, match="host not found"):
                self.docker.start_stack()
            with pytest.raises(RuntimeError, match="host not found"):
                self.docker.rebuild_service("app")

        # recreate_pulled_service enrich path
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        self.shell.docker.return_value = self.ok()
        with patch.object(
            self.docker,
            "enrich_compose_failure",
            side_effect=lambda exc, **kw: OperatorError(
                f"{exc}\n\n--- hub ---\nbad",
                has_fix=True,
            ),
        ):
            self.shell.compose.return_value = self.ok(returncode=1)
            with pytest.raises(RuntimeError, match="--- hub ---"):
                self.docker.recreate_pulled_service(
                    app, pull_ref="ghcr.io/org/hub:main"
                )

        # enrich falls back to not_ready_services / returns original when empty
        self.shell.compose.side_effect = None
        self.shell.compose.return_value = self.ok("")
        self.shell.docker.return_value = self.ok("exited none\n")
        bare = OperatorError("compose failed", has_fix=False)
        # no services, no mention, not_ready empty → original
        with patch.object(self.docker, "not_ready_services", return_value=[]):
            assert self.docker.enrich_compose_failure(bare) is bare
        with patch.object(self.docker, "diagnostics_for", return_value=""):
            assert (
                self.docker.enrich_compose_failure(bare, services=("app",)) is bare
            )
        # empty service names skipped; health log last entry not a dict
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
        self.shell.docker.return_value = self.ok(
            "", returncode=0, stderr=""
        )
        # container with empty logs still emits header via health="container"
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
