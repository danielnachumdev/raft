"""Serve GitHub API route tests (mock provider)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory
from raft.services.serve.github.api import ServeGithubApi
from raft.services.serve.github.deploy_job import DeployJob, DeployJobStore
from raft.services.serve.github.provider import MockGithubProvider
from raft.services.serve.github.session import GithubSession, GithubSessionStore
from raft.services.serve.paths import ServePaths

from ....base import RaftTestCase, make_stack
from ....services.ops.status.fixtures import StatusFixtures


class TestServeGithubApi(RaftTestCase):
    def _client(self) -> TestClient:
        stack = make_stack(self.tmp_path)
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\ngithub: {mock: true}\n",
            encoding="utf-8",
        )
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
        assert client.get("/api/github/login", follow_redirects=False).status_code == 302
        cb = client.get("/api/github/callback?mock=1", follow_redirects=False)
        assert cb.status_code == 302 and cb.headers["location"] == "/deploy"
        session = client.get("/api/github/session").json()
        assert session["authenticated"] is True
        assert session["login"] == "mock-operator"
        assert "workflow" in session["scopes"]
        repos = client.get("/api/github/repos").json()["repos"]
        assert any(r["full_name"] == "demo/http-only-site" for r in repos)
        assert client.post("/api/github/logout").json()["authenticated"] is False

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
        self._save_mock_session()
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

    def _save_mock_session(self) -> None:
        GithubSessionStore(self.tmp_path).save(
            GithubSession(
                access_token="mock",
                login="mock-operator",
                mock=True,
                expires_at=time.time() + 60,
            )
        )
