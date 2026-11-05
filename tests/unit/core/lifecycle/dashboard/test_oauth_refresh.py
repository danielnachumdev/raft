"""OAuthAllowlistRefresh after RBAC-derived allowlist sync."""

from unittest.mock import MagicMock, patch

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.dashboard.oauth_refresh import OAuthAllowlistRefresh
from tests.unit.base import RaftTestCase


class TestOAuthAllowlistRefresh(RaftTestCase):
    def test_skips_when_not_synced(self) -> None:
        stack = load_stack(self.tmp_path)
        out = OAuthAllowlistRefresh(stack).after_sync({"synced": False})
        assert out["refreshed"] is False

    def test_redeploy_success_and_operator_error(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        stack = load_stack(self.tmp_path)
        with patch(
            "raft.core.lifecycle.dashboard.oauth_refresh.ServiceActions"
        ) as actions_cls:
            actions_cls.return_value.redeploy.return_value = {"ok": True}
            ok = OAuthAllowlistRefresh(stack).after_sync({"synced": True})
            assert ok["refreshed"] is True
            actions_cls.return_value.redeploy.side_effect = OperatorError(
                "dashboard disabled.\nFix: enable", has_fix=False
            )
            fail = OAuthAllowlistRefresh(stack).after_sync({"synced": True})
            assert fail["refreshed"] is False
            assert "redeploy dashboard" in fail["note"]
