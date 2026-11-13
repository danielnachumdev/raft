"""Router nginx reload retries Compose upstream DNS races."""

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.docker_msgs import DockerMessages
from raft.core.platform.adapters.docker.router_nginx_reload import RouterNginxReload
from tests.shared.nginx import NginxEmerg
from tests.unit.core.platform.adapters.docker.base import DockerTestCase


class TestRouterNginxReload(DockerTestCase):
    def test_retries_host_not_found_on_nginx_test_then_succeeds(self) -> None:
        emerg = NginxEmerg.host_not_found("demo-api-dev", 80)
        self.shell.compose.side_effect = [
            self.ok(returncode=1, stderr=emerg),  # -t race
            self.ok(),  # -t ok
            self.ok(),  # reload ok
        ]
        clock = {"t": 0.0}
        RouterNginxReload(
            self.shell,
            "raft-router",
            timeout=5.0,
            interval=0.5,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
            clock=lambda: clock["t"],
        ).run()
        assert self.shell.compose.call_count == 3

    def test_retries_host_not_found_on_reload_then_succeeds(self) -> None:
        emerg = NginxEmerg.host_not_found("limudpsanter-frontend-dev", 80)
        self.shell.compose.side_effect = [
            self.ok(),  # -t ok
            self.ok(returncode=1, stderr=emerg),  # reload race
            self.ok(),  # -t ok
            self.ok(),  # reload ok
        ]
        clock = {"t": 0.0}
        RouterNginxReload(
            self.shell,
            "raft-router",
            timeout=5.0,
            interval=0.5,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
            clock=lambda: clock["t"],
        ).run()
        assert self.shell.compose.call_count == 4

    def test_non_dns_reject_fails_immediately(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="syntax error")
        with pytest.raises(OperatorError, match="router nginx rejected"):
            RouterNginxReload(
                self.shell,
                "raft-router",
                timeout=5.0,
                sleep=lambda _s: None,
                clock=lambda: 0.0,
            ).run()
        assert self.shell.compose.call_count == 1

    def test_dns_race_timeout_reraises_last_emerg(self) -> None:
        emerg = NginxEmerg.host_not_found("demo-api-dev", 80)
        self.shell.compose.return_value = self.ok(returncode=1, stderr=emerg)
        clock = {"t": 0.0}
        with pytest.raises(OperatorError, match="host not found in upstream") as caught:
            RouterNginxReload(
                self.shell,
                "raft-router",
                timeout=1.0,
                interval=0.5,
                sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
                clock=lambda: clock["t"],
            ).run()
        assert DockerMessages.looks_like_upstream_host_not_found(caught.value)
        assert self.shell.compose.call_count >= 2

    def test_edge_reload_router_nginx_delegates_retry(self) -> None:
        emerg = NginxEmerg.host_not_found("demo-api-dev", 80)
        self.shell.compose.side_effect = [
            self.ok(returncode=1, stderr=emerg),
            self.ok(),
            self.ok(),
        ]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "raft.core.platform.adapters.docker.edge.RouterNginxReload",
                self._fast_reloader,
            )
            self.docker.reload_router_nginx()
        assert self.shell.compose.call_count == 3

    @staticmethod
    def _fast_reloader(shell, router, **_kwargs):
        clock = {"t": 0.0}
        return RouterNginxReload(
            shell,
            router,
            timeout=5.0,
            interval=0.5,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
            clock=lambda: clock["t"],
        )

    def test_timeout_without_prior_dns_error_uses_fallback(self) -> None:
        reloader = RouterNginxReload(self.shell, "raft-router")
        with pytest.raises(OperatorError, match="timed out waiting for Compose DNS"):
            reloader._raise_timeout()


class TestUpstreamHostNotFoundClassifier:
    def test_detects_nginx_emerg_text_and_errors(self) -> None:
        emerg = NginxEmerg.host_not_found("demo-api-dev", 80)
        assert DockerMessages.looks_like_upstream_host_not_found(emerg)
        assert DockerMessages.looks_like_upstream_host_not_found(
            DockerMessages.nginx_rejected("router", emerg)
        )
        assert DockerMessages.looks_like_upstream_host_not_found(
            DockerMessages.nginx_reload_failed("router", emerg)
        )
        assert not DockerMessages.looks_like_upstream_host_not_found("syntax error")
        assert not DockerMessages.looks_like_upstream_host_not_found("")
        assert not DockerMessages.looks_like_upstream_host_not_found(None)
