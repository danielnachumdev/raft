"""GithubAssistService: oauth session, repos, deploy status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.github import (
    DeployJobStore,
    GithubAccountStore,
    GithubAssistService,
)
from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.platform.github import fixtures as github_fx


class TestGithubAssistService(RaftTestCase):
    def _svc(self) -> GithubAssistService:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n"
            "github: {clientId: id, clientSecret: sec}\n",
            encoding="utf-8",
        )
        stack = StackMakers.make_stack(self.tmp_path)
        provider = MagicMock()
        provider.list_repos.return_value = [github_fx.sample_repo()]
        return GithubAssistService(stack, provider=provider, jobs=DeployJobStore())

    def _seed_account(self) -> None:
        GithubAccountStore(self.tmp_path).upsert_account(github_fx.sample_account())

    def test_session_repos_and_hint(self) -> None:
        svc = self._svc()
        self._seed_account()
        session = svc.session()
        assert session["authenticated"] is True
        assert "mock" not in session
        assert "Temporary GitHub" in session["hint"]
        repos = svc.repos()
        assert repos["repos"][0]["full_name"] == "o/r"

    def test_deploy_requires_full_name(self) -> None:
        svc = self._svc()
        self._seed_account()
        with pytest.raises(OperatorError, match="full_name"):
            svc.start_deploy(full_name="nope")

    def test_deploy_status_missing(self) -> None:
        svc = self._svc()
        self._seed_account()
        with pytest.raises(KeyError):
            svc.deploy_status("missing")

    def test_select_delete_and_save_config(self) -> None:
        svc = self._svc()
        store = GithubAccountStore(self.tmp_path)
        first = store.upsert_account(github_fx.sample_account(id="a1", login="one"))
        second = store.append_account(
            github_fx.sample_account(id="a2", login="two", access_token="t2")
        )
        svc.select_account(second.id)
        assert svc.session()["active_account_id"] == second.id
        svc.delete_account(first.id)
        ids = {a["id"] for a in svc.session()["accounts"]}
        assert first.id not in ids
        saved = svc.save_config(client_id="cid", client_secret="sec")
        assert saved["ok"] is True

    def test_complete_callback_requires_code(self) -> None:
        svc = self._svc()
        with pytest.raises(OperatorError, match="code/state"):
            svc.complete_callback()

    def test_complete_oauth_delegates(self) -> None:
        svc = self._svc()
        account = MagicMock()
        account.to_public.return_value = {"login": "u"}
        with patch.object(svc._oauth, "complete_oauth", return_value=account):
            out = svc.complete_oauth(code="c", state="s")
        assert out == {"ok": True, "account": {"login": "u"}}

    def test_login_url_requires_oauth(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        svc = GithubAssistService(
            StackMakers.make_stack(self.tmp_path),
            provider=MagicMock(),
            jobs=DeployJobStore(),
        )
        with pytest.raises(OperatorError, match="not configured"):
            svc.login_url()
        assert "not configured" in svc._login_hint()
