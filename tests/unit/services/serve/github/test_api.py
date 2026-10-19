"""Serve GitHub API route tests (real OAuth path + MagicMock provider)."""

from __future__ import annotations

import time
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.http.app import ServeAppFactory
from raft.core.platform.github.accounts import GithubAccount
from raft.core.platform.github.accounts import GithubAccountStore
from raft.services.serve.github.api import ServeGithubApi
from raft.core.platform.github.deploy import DeployJob, DeployJobStore
from raft.core.platform.github.providers import GithubRepo

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestServeGithubApi(RaftTestCase):
    def _client(self, *, settings: Optional[str] = None, provider=None) -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        body = settings or (
            "edge: {http: 80, https: null}\n"
            "github: {clientId: cid, clientSecret: csec}\n"
        )
        self.write_home_settings(body)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        if provider is None:
            provider = MagicMock()
            provider.list_repos.return_value = [
                GithubRepo(
                    "demo/http-only-site",
                    "http-only-site",
                    "demo",
                    False,
                    "main",
                    "c",
                    "s",
                    "h",
                )
            ]
        github = ServeGithubApi(stack, provider=provider, port=8787)
        return TestClient(ServeAppFactory(stack, status=status, github=github).create())

    def test_session_login_logout_repos(self) -> None:
        client = self._client()
        bare = client.get("/api/github/session").json()
        assert bare["authenticated"] is False
        assert "mock" not in bare
        assert bare["oauth_configured"] is True
        assert bare["accounts"] == []
        login = client.get("/api/github/login", follow_redirects=False)
        assert login.status_code == 302
        assert "github.com/login/oauth/authorize" in login.headers["location"]
        self._seed_account()
        session = client.get("/api/github/session").json()
        assert session["authenticated"] is True
        assert session["login"] == "demo-operator"
        assert len(session["accounts"]) == 1
        assert "access_token" not in session
        assert "access_token" not in session["accounts"][0]
        assert "workflow" in session["scopes"]
        repos = client.get("/api/github/repos").json()["repos"]
        assert any(r["full_name"] == "demo/http-only-site" for r in repos)
        out = client.post("/api/github/logout").json()
        assert out["authenticated"] is False

    def test_add_account_preserves_first_and_select(self) -> None:
        client = self._client()
        store = GithubAccountStore(self.tmp_path)
        first = store.upsert_account(self._alice())
        store.append_account(self._operator())
        session = client.get("/api/github/session").json()
        assert {a["login"] for a in session["accounts"]} == {"alice", "demo-operator"}
        selected = client.post(
            "/api/github/accounts/select",
            json={"account_id": first.id},
        ).json()
        assert selected["login"] == "alice"
        assert store.active_usable().access_token == "tok-a"
        gone = client.delete(f"/api/github/accounts/{first.id}").json()
        assert gone["login"] == "demo-operator"
        assert len(gone["accounts"]) == 1

    def test_config_save_reloads_oauth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_github_env(monkeypatch)
        client = self._client(settings="edge: {http: 80}\n")
        bare = client.get("/api/github/config").json()
        self._assert_setup_urls(bare)
        login = client.get("/api/github/login", follow_redirects=False)
        assert login.status_code == 302 and "oauth_error=" in login.headers["location"]
        saved = client.post(
            "/api/github/config",
            json={"clientId": "cid", "clientSecret": "csec"},
        ).json()
        assert saved["ok"] and saved["reloaded"] and saved["oauth_configured"]
        again = client.get("/api/github/login", follow_redirects=False)
        assert "github.com/login/oauth/authorize" in again.headers["location"]
        assert client.get("/api/github/session").json()["accounts"] == []

    @staticmethod
    def _assert_setup_urls(bare: dict) -> None:
        assert bare["oauth_configured"] is False
        assert "applications/new" in bare["oauth_app_url"]
        assert bare["homepage_url"] == "http://127.0.0.1:8787/"
        assert bare["callback_url"].endswith("/api/github/callback")
        assert bare["application_name"] == "raft serve"
        assert bare["enable_device_flow"] is False
        assert bare["expire_user_access_tokens"] is False

    @staticmethod
    def _alice() -> GithubAccount:
        return GithubAccount(
            id="first",
            login="alice",
            access_token="tok-a",
            expires_at=time.time() + 60,
            github_user_id="1",
        )

    def _operator(self) -> GithubAccount:
        return GithubAccount(
            id="op",
            login="demo-operator",
            access_token="tok-op",
            expires_at=time.time() + 60,
        )

    def _seed_account(self) -> None:
        GithubAccountStore(self.tmp_path).upsert_account(self._operator())

    def test_config_errors_and_hints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._clear_github_env(monkeypatch)
        client = self._client(settings="edge: {http: 80}\n")
        assert "not configured" in client.get("/api/github/session").json()["hint"]
        assert client.post("/api/github/config", json={}).status_code == 400

    @staticmethod
    def _clear_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "RAFT_GITHUB_CLIENT_ID",
            "RAFT_GITHUB_CLIENT_SECRET",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_deploy_requires_session_and_valid_name(self) -> None:
        client = self._client()
        assert client.post("/api/github/deploy", json={}).status_code == 401
        self._seed_account()
        assert client.post("/api/github/deploy", json={"full_name": "nope"}).status_code == 400
        missing = client.post(
            "/api/github/deploy", json={"full_name": "demo/does-not-exist"}
        )
        assert missing.status_code == 400

    def test_deploy_job_poll(self) -> None:
        jobs = DeployJobStore()
        job = DeployJob(
            id="abc", full_name="demo/http-only-site", ref="main", status="running"
        )
        jobs._jobs[job.id] = job
        c = self._authed_client(jobs)
        assert c.get("/api/github/deploy/abc").json()["status"] == "running"
        assert c.get("/api/github/deploy/missing").status_code == 404

    def test_deploy_status_operator_error_is_400(self) -> None:
        github, status = self._github_and_status()
        with patch.object(
            github._assist,
            "deploy_status",
            side_effect=OperatorError("no session", has_fix=False),
        ):
            client = TestClient(
                ServeAppFactory(
                    github.stack, status=status, github=github
                ).create()
            )
            assert client.get("/api/github/deploy/x").status_code == 400

    def test_callback_requires_code(self) -> None:
        client = self._client()
        bad = client.get("/api/github/callback", follow_redirects=False)
        assert bad.status_code == 302 and "oauth_error=" in bad.headers["location"]

    def _github_and_status(self):
        stack = StackMakers.make_stack(self.tmp_path)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {clientId: cid, clientSecret: csec}\n", encoding="utf-8"
        )
        self._seed_account()
        github = ServeGithubApi(stack, provider=MagicMock(), jobs=DeployJobStore())
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        return github, status

    def _authed_client(self, jobs: DeployJobStore) -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {clientId: cid, clientSecret: csec}\n", encoding="utf-8"
        )
        self._seed_account()
        api = ServeGithubApi(stack, provider=MagicMock(), jobs=jobs)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        return TestClient(ServeAppFactory(stack, status=status, github=api).create())
