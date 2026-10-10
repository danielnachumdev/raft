"""Serve GitHub API route tests (mock provider)."""

from __future__ import annotations

import time
from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from raft.ops.status.models import StatusSnapshot
from raft.serve.app import ServeAppFactory
from raft.serve.github.account import GithubAccount
from raft.serve.github.accounts import GithubAccountStore
from raft.serve.github.api import ServeGithubApi
from raft.serve.github.deploy_job import DeployJob, DeployJobStore
from raft.serve.github.strategies.mock import MockGithubProvider
from raft.serve.paths import ServePaths

from tests.unit.base import RaftTestCase, make_stack
from tests.unit.ops.status.fixtures import StatusFixtures


class TestServeGithubApi(RaftTestCase):
    def _client(self, *, settings: Optional[str] = None) -> TestClient:
        stack = make_stack(self.tmp_path)
        body = settings or (
            "edge: {http: 80, https: null}\ngithub: {mock: true}\n"
        )
        (self.tmp_path / "settings.yaml").write_text(body, encoding="utf-8")
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(), containers=()
        )
        github = ServeGithubApi(
            stack,
            provider=MockGithubProvider(ServePaths.mock_github_dir()),
            port=8787,
        )
        return TestClient(ServeAppFactory(stack, status=status, github=github).create())

    def test_session_login_logout_repos(self) -> None:
        client = self._client()
        bare = client.get("/api/github/session").json()
        assert bare["authenticated"] is False and bare["mock"] is True
        assert bare["oauth_configured"] is True
        assert bare["accounts"] == []
        assert client.get("/api/github/login", follow_redirects=False).status_code == 302
        cb = client.get("/api/github/callback?mock=1", follow_redirects=False)
        assert cb.status_code == 302 and cb.headers["location"] == "/deploy"
        session = client.get("/api/github/session").json()
        assert session["authenticated"] is True
        assert session["login"] == "mock-operator"
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
        client.get("/api/github/callback?mock=1")
        session = client.get("/api/github/session").json()
        assert {a["login"] for a in session["accounts"]} == {
            "alice",
            "mock-operator",
        }
        selected = client.post(
            "/api/github/accounts/select",
            json={"account_id": first.id},
        ).json()
        assert selected["login"] == "alice"
        assert store.active_usable().access_token == "tok-a"
        gone = client.post(f"/api/github/accounts/{first.id}/logout").json()
        assert gone["login"] == "mock-operator"
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
            mock=False,
            expires_at=time.time() + 60,
            github_user_id="1",
        )

    def test_config_errors_and_hints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._clear_github_env(monkeypatch)
        client = self._client(settings="edge: {http: 80}\n")
        assert "not configured" in client.get("/api/github/session").json()["hint"]
        assert client.post("/api/github/config", json={}).status_code == 400

    @staticmethod
    def _clear_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "RAFT_GITHUB_MOCK",
            "RAFT_GITHUB_CLIENT_ID",
            "RAFT_GITHUB_CLIENT_SECRET",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_deploy_requires_session_and_valid_name(self) -> None:
        client = self._client()
        assert client.post("/api/github/deploy", json={}).status_code == 401
        client.get("/api/github/callback?mock=1")
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

    def _authed_client(self, jobs: DeployJobStore) -> TestClient:
        stack = make_stack(self.tmp_path)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {mock: true}\n", encoding="utf-8"
        )
        self._save_mock_account()
        api = ServeGithubApi(
            stack,
            provider=MockGithubProvider(ServePaths.mock_github_dir()),
            jobs=jobs,
        )
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(), containers=()
        )
        return TestClient(ServeAppFactory(stack, status=status, github=api).create())

    def _save_mock_account(self) -> None:
        GithubAccountStore(self.tmp_path).upsert_account(
            GithubAccount(
                id="mock",
                access_token="mock",
                login="mock-operator",
                mock=True,
                expires_at=time.time() + 60,
            )
        )
