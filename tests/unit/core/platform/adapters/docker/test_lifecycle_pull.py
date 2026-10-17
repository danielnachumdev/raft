"""Pull / recreate-pulled lifecycle coverage."""

from unittest.mock import patch

import pytest

from tests.unit.base import AppMakers
from tests.unit.core.platform.adapters.docker.base import DockerTestCase

_DEMO = "ghcr.io/example/demo-api"


class TestDockerLifecyclePull(DockerTestCase):
    def test_recreate_pulled_service_tags_then_up(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.side_effect = self._docker_missing_then_ok()
        app = AppMakers.make_app("demo-api", source="docker", image=_DEMO, ref="main")
        self.docker.recreate_pulled_service(app, pull_ref=f"{_DEMO}:abc")
        self._assert_tag_then_up()

    def _docker_missing_then_ok(self):
        def docker(*args, **_kwargs):
            if args[:2] == ("image", "inspect") and args[3:4] == ("{{.Id}}",):
                return self.ok("", returncode=1)
            return self.ok()

        return docker

    def _assert_tag_then_up(self) -> None:
        self.shell.docker.assert_any_call("pull", f"{_DEMO}:abc", capture=True, check=False)
        self.shell.docker.assert_any_call(
            "tag", f"{_DEMO}:abc", f"{_DEMO}:main", capture=True, check=False
        )
        self.shell.compose.assert_any_call(
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--force-recreate",
            "demo-api",
            capture=False,
            check=False,
        )

    def test_recreate_pulled_service_skips_tag_when_pin(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.side_effect = self._docker_missing_then_ok()
        app = AppMakers.make_app("demo-api", source="docker", image=_DEMO, ref="main")
        self.docker.recreate_pulled_service(app, pull_ref=f"{_DEMO}:main")
        self.shell.docker.assert_any_call("pull", f"{_DEMO}:main", capture=True, check=False)
        assert not any(c.args[:1] == ("tag",) for c in self.shell.docker.call_args_list)

    def test_recreate_pulled_service_skips_pull_when_local(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok("sha256:local\n")
        app = AppMakers.make_app("demo-api", source="docker", image=_DEMO, ref="main")
        self.docker.recreate_pulled_service(app, pull_ref=f"{_DEMO}:abc")
        assert not any(c.args[:1] == ("pull",) for c in self.shell.docker.call_args_list)
        self.shell.docker.assert_any_call(
            "tag", f"{_DEMO}:abc", f"{_DEMO}:main", capture=True, check=False
        )

    def test_recreate_pulled_service_unauthorized(self) -> None:
        def docker(*args, **_kwargs):
            if args[:2] == ("image", "inspect"):
                return self.ok("", returncode=1)
            return self.ok(returncode=1, stderr="Error response from daemon: unauthorized\n")

        self.shell.docker.side_effect = docker
        app = AppMakers.make_app("demo-api", source="docker", image=_DEMO, ref="main")
        with pytest.raises(RuntimeError, match="docker login") as exc:
            self.docker.recreate_pulled_service(app, pull_ref=f"{_DEMO}:main")
        assert "unauthorized" in str(exc.value).lower() or "login" in str(exc.value).lower()

    def test_pull_and_build_services(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.side_effect = self._docker_missing_then_ok()
        self.docker.pull_services(())
        self.docker.build_services(())
        assert self.shell.compose.call_count == 0
        self.docker.pull_services(("app", "api"))
        self.docker.build_services(("app",))
        self.shell.compose.assert_any_call(
            "pull", "--ignore-buildable", "app", "api", capture=False, check=False
        )
        self.shell.compose.assert_any_call("build", "app", capture=False, check=False)

    def test_pull_services_skips_when_pin_present(self) -> None:
        from tests.unit.base import StackMakers

        app = AppMakers.make_app(
            "demo-api", source="docker", image=_DEMO, ref="abc123"
        )
        self.stack = StackMakers.make_stack(self.tmp_path, (app,))
        self.docker = self.docker_stack()
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok("sha256:local\n")
        self.docker.pull_services(("demo-api",))
        assert self.shell.compose.call_count == 0
        assert not any(c.args[:1] == ("pull",) for c in self.shell.docker.call_args_list)

    def test_pull_and_build_enrich_failures(self) -> None:
        from raft.core.core.errors.cta import OperatorError

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
