"""Cover residual package-move branches that unit suites still miss."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import urllib.error

from raft.core.core.config import settings_types
from raft.core.core.config.paths import settings_path
from raft.core.core.errors.certs_msgs import CertMessages
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.acme.account.gateway import AcmeClientGateway
from raft.core.lifecycle.acme.order.order import AcmeOrderRunner
from raft.core.lifecycle.apply.expr.error import DirectiveExpressionError
from raft.core.lifecycle.render.stack_renderer import StackRenderer
from raft.core.lifecycle.sync.registry import SourceSyncRegistry
from raft.core.lifecycle.sync.context import SyncContext
from raft.core.lifecycle.sync.strategy import SyncStrategy
from raft.core.platform.adapters.http.gateway import HttpGateway
from raft.core.platform.auth.instructions import DeployKeyInstructions
from raft.core.platform.auth.strategies.generic import GenericDeployKeyHint
from raft.core.platform.auth.strategies.host_hint import DeployKeyHostHint
from raft.core.platform.locking.apps_and_stack_locks import AppsAndStackLocks
from raft.core.platform.locking.exclusive import ExclusiveLock
from raft.services.cli.exit_mapper import CliExitMapper

from tests.unit.base import RaftTestCase, StackMakers


class _StubSync(SyncStrategy):
    @property
    def type_id(self) -> str:
        return "stub"

    def sync(self, app, ctx: SyncContext) -> None:  # noqa: ANN001
        del app, ctx


class TestCoverageGaps(RaftTestCase):
    def test_settings_types_reexport_and_settings_path(self) -> None:
        assert settings_types.CONFIG_FILENAME
        assert settings_types.RaftConfig is not None
        home = self.tmp_path / ".raft"
        home.mkdir(parents=True, exist_ok=True)
        assert settings_path(home) == home / "host" / settings_types.CONFIG_FILENAME

    def test_certs_msgs_doctor_footer_branch(self) -> None:
        missing = [
            MagicMock(app_name="demo", detail="gone", fix="add pems"),
        ]
        text = CertMessages.format_missing_acme_certs(missing, include_doctor_footer=False)
        assert "raft doctor" not in text
        assert "demo" in text

    def test_acme_gateway_delegates(self) -> None:
        client = MagicMock()
        net = MagicMock()
        gw = AcmeClientGateway(client, net=net)
        gw.new_order(b"csr")
        client.new_order.assert_called_once_with(b"csr")
        gw.answer_challenge(MagicMock(), MagicMock())
        assert client.answer_challenge.called
        gw.poll_and_finalize(MagicMock())
        assert client.poll_and_finalize.called
        assert gw.key is net.key

    def test_fullchain_bytes_accepts_bytes(self) -> None:
        finalized = MagicMock(fullchain_pem=b"PEM")
        assert AcmeOrderRunner._fullchain_bytes(finalized) == b"PEM"

    def test_directive_expression_empty_path_label(self) -> None:
        err = DirectiveExpressionError(path="").near("x == y")
        assert isinstance(err, OperatorError)
        assert err.args[0].startswith("manifest:")
        labeled = DirectiveExpressionError(path="/tmp/demo.yaml").near("x == y")
        assert "manifest at /tmp/demo.yaml" in labeled.args[0]

    def test_stack_renderer_path_helpers(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        renderer = StackRenderer(stack)
        assert renderer.compose_apps_path().name == "compose.apps.yaml"
        assert renderer.compose_edge_path().name == "compose.edge.yaml"
        assert renderer.router_hosts_path().name == "hosts.conf"

    def test_source_sync_registry_paths(self) -> None:
        reg = SourceSyncRegistry()
        first = _StubSync()
        reg.register(first)
        with pytest.raises(ValueError, match="duplicate"):
            reg.register(_StubSync())
        assert reg.get("stub") is first
        assert reg.catalog() == [{"type_id": "stub"}]
        with pytest.raises(OperatorError, match="unknown app source"):
            reg.get("missing")
        empty = SourceSyncRegistry()
        with pytest.raises(OperatorError, match="\\(none\\)"):
            empty.get("x")

    def test_http_gateway_get_branches(self) -> None:
        gw = HttpGateway()
        resp = MagicMock()
        resp.status = 200
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        with patch.object(gw._opener, "open", return_value=resp):
            assert gw.get("http://example/") == 200
        err = urllib.error.HTTPError("u", 302, "x", hdrs=None, fp=BytesIO(b""))
        with patch.object(gw._opener, "open", side_effect=err):
            assert gw.get("http://example/") == 302
        with patch.object(
            gw._opener, "open", side_effect=urllib.error.URLError("down")
        ):
            assert gw.get("http://example/") is None

    def test_deploy_key_hint_fallback_and_abc(self) -> None:
        instructions = DeployKeyInstructions(hints=())
        assert isinstance(instructions._hint_for("example.com"), GenericDeployKeyHint)
        DeployKeyHostHint.__abstractmethods__ = frozenset()
        bare = DeployKeyHostHint()
        with pytest.raises(NotImplementedError):
            bare.matches("h")
        with pytest.raises(NotImplementedError):
            bare.open_lines("h", "o/r")

    def test_apps_and_stack_locks_error_and_noop_exit(self) -> None:
        locks = AppsAndStackLocks(self.tmp_path, ("web",), timeout=0.01)
        locks.__exit__(None, None, None)
        with patch(
            "raft.core.platform.locking.apps_and_stack_locks.AppDeployLock",
            side_effect=RuntimeError("busy"),
        ):
            with pytest.raises(RuntimeError, match="busy"):
                with AppsAndStackLocks(self.tmp_path, ("web",), timeout=0.01):
                    pass

    def test_exclusive_close_failed_fd_when_already_none(self) -> None:
        lock = ExclusiveLock(self.tmp_path / "x.lock", kind="stack", timeout=1)
        lock.fd = None
        lock._close_failed_fd()

    def test_exit_mapper_fallback_and_unmapped(self) -> None:
        mapper = CliExitMapper()
        with pytest.raises(KeyboardInterrupt):
            mapper._fallback_handle([], KeyboardInterrupt())
        assert mapper._map_operator_exc(KeyboardInterrupt()) is None
