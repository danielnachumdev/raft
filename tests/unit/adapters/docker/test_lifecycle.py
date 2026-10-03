"""Lifecycle and recreate coverage."""

from unittest.mock import patch

import pytest

from raft.models.ports import PortSpec
from raft.services.ops.certs import MissingOriginCerts

from ...base import make_app
from .base import DockerTestCase


class TestDockerLifecycle(DockerTestCase):
    def test_start_stop_and_running(self) -> None:
        self._test_start_stop_and_running_p1()
        self._test_start_stop_and_running_p2()

    def _test_start_stop_and_running_p1(self) -> None:
        def compose(*args, **kwargs):
            if args[:1] == ("ps",) and "--format" in args:
                return self.ok("raft-gate running\nraft-router exited\n")
            if args[:1] == ("ps",):
                return self.ok("")
            return self.ok()

        self.shell.compose.side_effect = compose
        assert self.docker.running_services() == ["raft-gate"]
        self.shell.compose.assert_called_with(
            "ps",
            "--format",
            "{{.Service}} {{.State}} {{.Health}}",
            capture=True,
            check=False,
        )
        assert self.shell.compose.call_count == 1
        self.docker.start_stack()
        self.docker.stop_stack()

    def _test_start_stop_and_running_p2(self) -> None:
        self.shell.compose.assert_any_call(
            "up", "-d", "--build", "--remove-orphans", capture=False, check=False
        )
        self.shell.compose.assert_any_call("down", "--remove-orphans", capture=False, check=False)
        self.shell.docker.assert_called()

    def test_stop_stack_clears_labeled_leftovers(self) -> None:
        self.shell.compose.return_value = self.ok()
        # stop_stack removes each app tmp container before labeled cleanup.
        self.shell.docker.side_effect = [
            self.ok(""),  # rm -f app tmp
            self.ok("cid1\n"),  # ps -aq labeled
            self.ok("/raft-orphan\n"),  # inspect name
            self.ok(""),  # rm -f leftover
        ]
        self.docker.stop_stack()
        labeled_rms = [
            call
            for call in self.shell.docker.call_args_list
            if call.args[:3] == ("rm", "-f", "cid1")
        ]
        assert labeled_rms

    def test_network_holders_uses_router_network(self) -> None:
        with patch.object(self.docker, "router_network", return_value="raft_default"):
            self.shell.docker.return_value = self.ok("raft-orphan other\n")
            assert self.docker.network_holders() == ["raft-orphan", "other"]

    def test_network_holders_without_router_uses_default(self) -> None:
        """After compose down, router is gone — holders must not raise."""
        self.shell.compose.return_value = self.ok("")
        self.shell.docker.return_value = self.ok("", returncode=1)
        assert self.docker.network_holders() == []

    def test_network_holders_without_router_inspects_default(self) -> None:
        self.shell.compose.return_value = self.ok("")
        self.shell.docker.return_value = self.ok("orphan\n")
        assert self.docker.network_holders() == ["orphan"]
        net = next(c for c in self.shell.docker.call_args_list if c.args[:2] == ("network", "inspect"))
        assert net.args[2] == "raft_default"

    def test_recreate_rebuild(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.recreate_router()
        self.docker.rebuild_service("app")
        self.shell.compose.assert_any_call(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "raft-router",
            capture=False,
            check=False,
        )
        self.shell.compose.assert_any_call(
            "up", "-d", "--build", "--no-deps", "app", capture=False, check=False
        )

    def test_recreate_pulled_service_tags_then_up(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok()
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:abc")
        self._assert_tag_then_up()

    def _assert_tag_then_up(self) -> None:
        self.shell.docker.assert_any_call("pull", "ghcr.io/org/hub:abc", capture=True, check=False)
        self.shell.docker.assert_any_call(
            "tag", "ghcr.io/org/hub:abc", "ghcr.io/org/hub:main", capture=True, check=False
        )
        self.shell.compose.assert_any_call(
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--force-recreate",
            "hub",
            capture=False,
            check=False,
        )

    def test_recreate_pulled_service_skips_tag_when_pin(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok()
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:main")
        self.shell.docker.assert_any_call("pull", "ghcr.io/org/hub:main", capture=True, check=False)
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
        self._test_service_runtime_and_heal_actions_p1()
        self._test_service_runtime_and_heal_actions_p2()

    def _test_service_runtime_and_heal_actions_p1(self) -> None:
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
        self.shell.compose.assert_any_call("restart", "app", capture=False, check=False)
        self.docker.start_service("app")

    def _test_service_runtime_and_heal_actions_p2(self) -> None:
        self.docker.stop_service("app")
        self.shell.compose.assert_any_call("stop", "app", capture=False, check=False)
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
            with pytest.raises(RuntimeError, match="--- app ---"):
                self.docker.stop_service("app")

    def test_start_stack_selective_uses_no_deps(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.start_stack(("raft-gate", "raft-router"))
        self.shell.compose.assert_any_call(
            "up",
            "-d",
            "--build",
            "--remove-orphans",
            "--no-deps",
            "raft-gate",
            "raft-router",
            capture=False,
            check=False,
        )

    def test_pull_and_build_services(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.pull_services(())
        self.docker.build_services(())
        assert self.shell.compose.call_count == 0
        self.docker.pull_services(("app", "api"))
        self.docker.build_services(("app",))
        self.shell.compose.assert_any_call(
            "pull",
            "--ignore-buildable",
            "app",
            "api",
            capture=False,
            check=False,
        )
        self.shell.compose.assert_any_call(
            "build", "app", capture=False, check=False
        )

    def test_pull_and_build_enrich_failures(self) -> None:
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
                self.docker.pull_services(("app",))
            with pytest.raises(RuntimeError, match="--- app ---"):
                self.docker.build_services(("app",))
