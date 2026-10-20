"""Coverage: settings, oauth, session, fingerprint."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.config.settings.strategies.github import GithubSettingsParser
from raft.core.core.config.settings.types import GithubServeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.github.deploy import GithubDeployRunner
from raft.core.platform.github.deploy import DeployJob, DeployJobStore
from raft.core.platform.github.deploy import DeployNextSteps
from raft.core.platform.github.oauth import GithubOauth
from raft.core.platform.github.providers import RealGithubProvider
from raft.core.platform.github.accounts import GithubAccountStore

from tests.unit.base import RaftTestCase, StackMakers


class TestCoverageOauth(RaftTestCase):
    def test_settings_env_ttl_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        p = GithubSettingsParser()
        with pytest.raises(OperatorError):
            p.parse({"sessionTtlSeconds": "nope"})
        monkeypatch.setenv("RAFT_GITHUB_SESSION_TTL_SECONDS", "nope")
        with pytest.raises(OperatorError):
            p.parse(None)
        monkeypatch.setenv("RAFT_GITHUB_SESSION_TTL_SECONDS", "30")
        with pytest.raises(OperatorError):
            p.parse(None)
        monkeypatch.delenv("RAFT_GITHUB_SESSION_TTL_SECONDS")
        assert p.parse({"clientId": "  "}).client_id is None

    def test_oauth_token_request_http_error(self) -> None:
        oauth = GithubOauth(
            GithubServeConfig(client_id="id", client_secret="sec"),
            GithubAccountStore(self.tmp_path),
        )
        import urllib.error

        with patch(
            "raft.core.platform.github.gateway.urlopen",
            side_effect=urllib.error.HTTPError("u", 400, "x", hdrs=None, fp=BytesIO(b"bad")),
        ):
            with pytest.raises(OperatorError, match="token exchange"):
                oauth._exchange_code("c")

    def test_oauth_exchange_ok_and_fetch(self) -> None:
        oauth = GithubOauth(
            GithubServeConfig(client_id="id", client_secret="sec"),
            GithubAccountStore(self.tmp_path),
        )
        ok = MagicMock()
        ok.read.return_value = b'{"access_token":"tok"}'
        ok.status = 200
        ok.headers = {}
        ok.__enter__.return_value = ok
        ok.__exit__.return_value = False
        with patch("raft.core.platform.github.gateway.urlopen", return_value=ok):
            assert oauth._exchange_code("c") == "tok"
        user = MagicMock()
        user.read.return_value = b'{"login":"bob"}'
        user.status = 200
        user.headers = {}
        user.__enter__.return_value = user
        user.__exit__.return_value = False
        with patch("raft.core.platform.github.gateway.urlopen", return_value=user):
            assert oauth._fetch_user("tok") == ("bob", None)

    def test_oauth_fetch_user_missing(self) -> None:
        oauth = GithubOauth(
            GithubServeConfig(client_id="id", client_secret="sec"),
            GithubAccountStore(self.tmp_path),
        )
        user = MagicMock()
        user.read.return_value = b"{}"
        user.status = 200
        user.headers = {}
        user.__enter__.return_value = user
        user.__exit__.return_value = False
        with patch("raft.core.platform.github.gateway.urlopen", return_value=user):
            with pytest.raises(OperatorError, match="login"):
                oauth._fetch_user("tok")
    def test_session_bad_raw_and_next_steps_key(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        path = self.tmp_path / "host" / "serve" / "github-accounts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        assert store.public_snapshot()["accounts"] == []
        path.write_text(json.dumps({"version": 1, "accounts": [{"access_token": 1}]}), encoding="utf-8")
        assert store.public_snapshot()["accounts"] == []
        steps = DeployNextSteps()._deploy_key(None, "https://x", "SHA256:abc")
        assert steps and "Fingerprint" in steps[0]["body"]
        assert DeployNextSteps()._deploy_key("ssh-ed25519 AAAA", None, None)
        assert GithubOauth._user_from_payload({"login": "x", "id": 7}) == ("x", "7")

    def test_deploy_parse_errors(self) -> None:
        runner = GithubDeployRunner(StackMakers.make_stack(self.tmp_path), MagicMock(), DeployJobStore())
        with pytest.raises(OperatorError):
            runner._parse_yaml(":", "o/r")
        with pytest.raises(OperatorError):
            runner._parse_yaml("[]", "o/r")
        with pytest.raises(OperatorError):
            runner._manifest_name({})
        job = DeployJob(id="1", full_name="o/r", ref="main")
        runner._step(job, "A", "running")
        runner._step(job, "A", "ok", "done")
        assert job.steps[0].status == "ok"

    def test_deploy_fingerprint(self) -> None:
        runner = GithubDeployRunner(StackMakers.make_stack(self.tmp_path), MagicMock(), DeployJobStore())
        fp = runner._fingerprint("ssh-ed25519 " + "A" * 44)
        assert fp.startswith("SHA256:") and "unparsed" not in fp
        assert runner._fingerprint("nospaceblob")
        assert runner._fingerprint(None) == ""
        with patch(
            "raft.core.platform.github.deploy.job.base64.b64decode",
            side_effect=ValueError("bad"),
        ):
            assert "unparsed" in runner._fingerprint("ssh-ed25519 AAAA")

    def test_provider_partial_branches(self) -> None:
        provider = RealGithubProvider()
        with patch.object(
            provider,
            "_request_page",
            return_value=(
                '[1, {"full_name":"a/b","name":"b","private":false,'
                '"default_branch":"main","clone_url":"c","ssh_url":"s","html_url":"h"}]',
                None,
            ),
        ):
            assert len(provider.list_repos("tok")) == 1
        assert RealGithubProvider._next_link('rel="next"') is None
