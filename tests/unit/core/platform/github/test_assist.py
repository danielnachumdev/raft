"""GithubAssistService: mock login, repos, deploy status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.github import (
    DeployJobStore,
    GithubAssistService,
    MockGithubProvider,
)
from tests.unit.base import RaftTestCase, StackMakers


class TestGithubAssistService(RaftTestCase):
    def _svc(self, *, mock: bool = True) -> GithubAssistService:
        (self.tmp_path / "settings.yaml").write_text(
            f"edge: {{http: 80, https: null}}\ngithub:\n  mock: {str(mock).lower()}\n",
            encoding="utf-8",
        )
        stack = StackMakers.make_stack(self.tmp_path)
        return GithubAssistService(
            stack, provider=MockGithubProvider(), jobs=DeployJobStore()
        )

    def test_mock_login_repos_and_session(self) -> None:
        svc = self._svc()
        out = svc.complete_mock()
        assert out["account"]["login"] == "mock-operator"
        session = svc.session()
        assert session["mock"] is True
        assert session["accounts"]
        repos = svc.repos()
        assert isinstance(repos["repos"], list)

    def test_deploy_requires_full_name(self) -> None:
        svc = self._svc()
        svc.complete_mock()
        with pytest.raises(OperatorError, match="full_name"):
            svc.start_deploy(full_name="nope")

    def test_deploy_status_missing(self) -> None:
        svc = self._svc()
        svc.complete_mock()
        with pytest.raises(KeyError):
            svc.deploy_status("missing")

    def test_select_delete_and_save_config(self) -> None:
        svc = self._svc()
        first = svc.complete_mock()["account"]["id"]
        second = svc.complete_mock(add=True)["account"]["id"]
        svc.select_account(second)
        assert svc.session()["active_account_id"] == second
        svc.delete_account(first)
        ids = {a["id"] for a in svc.session()["accounts"]}
        assert first not in ids
        saved = svc.save_config(client_id="cid", client_secret="sec")
        assert saved["ok"] is True

    def test_complete_callback_mock(self) -> None:
        svc = self._svc()
        svc.complete_callback(mock="1")
        assert svc.session()["accounts"]

    def test_complete_callback_requires_code(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "github: {mock: false, clientId: id, clientSecret: sec}\n",
            encoding="utf-8",
        )
        svc = GithubAssistService(
            StackMakers.make_stack(self.tmp_path),
            provider=MockGithubProvider(),
            jobs=DeployJobStore(),
        )
        with pytest.raises(OperatorError, match="code/state"):
            svc.complete_callback()

    def test_complete_oauth_delegates(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "github: {mock: false, clientId: id, clientSecret: sec}\n",
            encoding="utf-8",
        )
        svc = GithubAssistService(
            StackMakers.make_stack(self.tmp_path),
            provider=MockGithubProvider(),
            jobs=DeployJobStore(),
        )
        account = MagicMock()
        account.to_public.return_value = {"login": "u"}
        with patch.object(svc._oauth, "complete_oauth", return_value=account):
            out = svc.complete_oauth(code="c", state="s")
        assert out == {"ok": True, "account": {"login": "u"}}
