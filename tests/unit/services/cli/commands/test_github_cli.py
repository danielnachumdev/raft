"""CLI ``raft github`` over GithubAssistService."""

from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.github import DeployJobStore, GithubAssistService
from raft.core.platform.github.providers.strategies.mock import MockGithubProvider
from raft.services.cli.commands.github import GithubCLI
from tests.unit.base import RaftTestCase, StackMakers


class TestGithubCLI(RaftTestCase):
    def _cli(self) -> GithubCLI:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\ngithub:\n  mock: true\n",
            encoding="utf-8",
        )
        stack = StackMakers.make_stack(self.tmp_path)
        assist = GithubAssistService(
            stack, provider=MockGithubProvider(), jobs=DeployJobStore()
        )
        return GithubCLI(stack, assist=assist)

    def _quiet(self):
        return patch("raft.services.cli.commands.github.OperatorSay.say")

    def test_login_accounts_repos_deploy(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.login(mock=True)
            cli.session(json=True)
            cli.config_show()
            cli.accounts()
            cli.accounts(json=True)
            cli.repos()
            cli.repos(json=True)
            with patch.object(
                cli._assist,
                "start_deploy",
                return_value={"id": "j1", "status": "queued", "app_name": "site"},
            ):
                cli.deploy("demo/http-only-site", json=True)
            with pytest.raises(OperatorError):
                cli.deploy("missing/repo")

    def test_select_logout(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.login(mock=True)
            account_id = cli._assist.session()["accounts"][0]["id"]
            cli.select(account_id)
            cli.logout(account_id)
            cli.login(mock=True)
            cli.logout()

    def test_authorize_url_when_not_mock(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n"
            "github:\n  mock: false\n  clientId: cid\n  clientSecret: sec\n",
            encoding="utf-8",
        )
        stack = StackMakers.make_stack(self.tmp_path)
        cli = GithubCLI(stack, assist=GithubAssistService(stack, provider=MagicMock()))
        with self._quiet() as say:
            cli.login(port=8787)
        assert "Open this URL" in str(say.call_args_list)

    def test_deploy_status_missing(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.login(mock=True)
            with pytest.raises(OperatorError, match="not found"):
                cli.deploy_status("missing")

    def test_config_save(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.config_save(client_id="cid", client_secret="sec")

    def test_empty_accounts_and_complete(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.accounts()
            with patch.object(
                cli._assist,
                "complete_oauth",
                return_value={"ok": True, "account": {"login": "u"}},
            ):
                cli.complete(code="c", state="s")

    def test_human_deploy_and_status(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.login(mock=True)
            with patch.object(
                cli._assist,
                "start_deploy",
                return_value={"id": "j1", "status": "queued", "app_name": "site"},
            ):
                cli.deploy("demo/http-only-site")
            with patch.object(
                cli._assist,
                "deploy_status",
                return_value={"id": "j1", "status": "succeeded"},
            ):
                cli.deploy_status("j1")

    def test_empty_repos_and_missing_ids(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.login(mock=True)
            with patch.object(cli._assist, "repos", return_value={"repos": []}):
                cli.repos()
            with pytest.raises(OperatorError, match="not found"):
                cli.select("missing")
            with pytest.raises(OperatorError, match="not found"):
                cli.logout("missing")
