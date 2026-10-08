"""Coverage: deploy runner + API branches."""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.errors.cta import OperatorError
from raft.services.serve.github.api import ServeGithubApi
from raft.services.serve.github.deploy_job import DeployJob, DeployJobStore, GithubDeployRunner
from raft.services.serve.github.provider import GithubRepo, RealGithubProvider
from raft.services.serve.github.session import GithubSessionStore

from ._helpers import sample_repo, sample_session, stub_auth
from ....base import RaftTestCase, make_stack


class TestCoverageDeploy(RaftTestCase):
    def test_deploy_git_path_mocked(self) -> None:
        runner = GithubDeployRunner(make_stack(self.tmp_path), MagicMock(), DeployJobStore())
        runner._provider.fetch_manifest.return_value = (
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\n"
            "spec:\n  publicHost: w.test\n  source: git\n  repo: git@github.com:o/r.git\n"
            "  ref: main\n  ports:\n  - {name: http, containerPort: 80, expose: http}\n"
            "  readiness: {type: http, port: http, path: /}\n"
        )
        runner._provider.resolve_local_tree.return_value = None
        self._run_git_job(runner)

    def test_deploy_git_auth_failure(self) -> None:
        runner = GithubDeployRunner(make_stack(self.tmp_path), MagicMock(), DeployJobStore())
        job = DeployJob(id="z", full_name="o/r", ref="main", app_name="web")
        with patch("raft.services.serve.github.deploy_job.GitAuthManager") as auth_cls, patch(
            "raft.services.serve.github.deploy_job.AppApply"
        ) as apply_cls:
            stub_auth(auth_cls)
            apply_cls.return_value.apply_git.side_effect = OperatorError("no", has_fix=False)
            with pytest.raises(OperatorError, match="deploy public key"):
                runner._deploy_git(job, sample_session(), sample_repo(), "web")
        assert job.next_steps

    def test_api_callback_oauth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_GITHUB_MOCK", raising=False)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {mock: false, clientId: id, clientSecret: sec}\n", encoding="utf-8"
        )
        api = ServeGithubApi(make_stack(self.tmp_path), provider=MagicMock(), port=9999)
        assert api._default_provider().__class__.__name__ == "RealGithubProvider"
        GithubSessionStore(self.tmp_path).save(
            sample_session(access_token="", login="", state="good", mock=False)
        )
        with patch.object(api._oauth, "complete_oauth", return_value=sample_session(mock=False)):
            assert api.api_callback(MagicMock(), code="c", state="good").status_code == 302
        bad = api.api_callback(MagicMock(), code=None, state=None, mock=None)
        assert bad.status_code == 302 and "oauth_error=" in bad.headers["location"]
        denied = api.api_callback(
            MagicMock(), error="access_denied", error_description="user said no"
        )
        assert "oauth_error=" in denied.headers["location"]

    def test_api_port_and_repos_deploy(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("github: {mock: true}\n", encoding="utf-8")
        provider = MagicMock()
        api = ServeGithubApi(make_stack(self.tmp_path), provider=provider, jobs=DeployJobStore())
        GithubSessionStore(self.tmp_path).save(sample_session())
        req = MagicMock()
        req.headers = {"host": "127.0.0.1:8888"}
        assert api._request_port(req) == 8888
        provider.list_repos.side_effect = OperatorError("boom", has_fix=False)
        with pytest.raises(Exception):
            api.api_repos()
        provider.list_repos.side_effect = None
        provider.list_repos.return_value = [
            GithubRepo("demo/http-only-site", "http-only-site", "demo", False, "main", "c", "s", "h")
        ]
        with patch.object(api._runner, "start") as start:
            start.return_value = DeployJob(id="j", full_name="demo/http-only-site", ref="main")
            assert api.api_deploy({"full_name": "demo/http-only-site", "ref": "main"})["id"] == "j"

    def test_provider_paginate_and_page(self) -> None:
        provider = RealGithubProvider()
        page1 = (
            '[{"full_name":"a/b","name":"b","private":false,"default_branch":"main",'
            '"clone_url":"c","ssh_url":"s","html_url":"h"}]'
        )
        with patch.object(
            provider, "_request_page", side_effect=[(page1, "https://next"), ("[]", None)]
        ):
            assert len(provider.list_repos("tok")) == 1
        resp = MagicMock()
        resp.read.return_value = b"[]"
        resp.headers = {"Link": ""}
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=resp):
            body, nxt = provider._request_page("tok", "https://api.github.com/x")
            assert body == "[]" and nxt is None

    def test_provider_page_http_error(self) -> None:
        import urllib.error

        provider = RealGithubProvider()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("u", 403, "x", hdrs=None, fp=BytesIO(b"no")),
        ):
            with pytest.raises(OperatorError):
                provider._request_page("tok", "https://api.github.com/x")
        assert RealGithubProvider._next_link('<https://x>; rel="prev"') is None
        assert RealGithubProvider._next_link("garbage") is None

    def test_run_crash_and_missing_job(self) -> None:
        store = DeployJobStore()
        runner = GithubDeployRunner(make_stack(self.tmp_path), MagicMock(), store)
        job = store.create("o/r", "main")
        with patch.object(runner, "_execute", side_effect=RuntimeError("boom")):
            runner._run(job.id, sample_session(), sample_repo())
        assert store.get(job.id).status == "failed"
        runner._run("missing", sample_session(), sample_repo())

    def test_remaining_api_hints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_GITHUB_MOCK", raising=False)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {mock: false, clientId: id, clientSecret: sec}\n", encoding="utf-8"
        )
        api = ServeGithubApi(make_stack(self.tmp_path), port=8787)
        assert api._oauth.mock_enabled is False
        assert "Temporary GitHub" in api._login_hint()
        with patch.object(
            api._oauth, "login_url", side_effect=OperatorError("x", has_fix=False)
        ):
            login = api.api_login(MagicMock())
            assert login.status_code == 302 and "oauth_error=" in login.headers["location"]
        req = MagicMock()
        req.headers = {"host": "127.0.0.1:notaport"}
        assert api._request_port(req) == 8787

    def test_mock_default_provider(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("github: {mock: true}\n", encoding="utf-8")
        mock_api = ServeGithubApi(make_stack(self.tmp_path), port=8787)
        assert mock_api._default_provider().__class__.__name__ == "MockGithubProvider"

    def test_remaining_deploy_local(self) -> None:
        stack = make_stack(self.tmp_path)
        runner = GithubDeployRunner(stack, MagicMock(), DeployJobStore())
        runner._fill_next_steps(DeployJob(id="1", full_name="o/r", ref="m"), {})
        tree = self._stage_local_tree(stack)
        with pytest.raises(OperatorError):
            runner._rewrite_local_manifest(
                tree / ".raft" / "app.yaml",
                {"metadata": {"name": "web"}, "spec": []},
                "web",
            )
        job = DeployJob(id="2", full_name="o/r", ref="m", app_name="web")
        with patch("raft.services.serve.github.deploy_job.AppApply") as apply_cls:
            apply_cls.return_value.apply_file.return_value = "web"
            runner._deploy_local(job, tree, {"metadata": {"name": "web"}, "spec": {}}, "web")

    def _stage_local_tree(self, stack) -> Path:
        dest = stack.root / "apps" / "web"
        dest.mkdir(parents=True)
        (dest / "keep").write_text("x", encoding="utf-8")
        tree = self.tmp_path / "fixture-tree"
        tree.mkdir()
        (tree / ".raft").mkdir()
        (tree / ".raft" / "app.yaml").write_text("x: 1\n", encoding="utf-8")
        return tree

    def _run_git_job(self, runner: GithubDeployRunner) -> None:
        with patch("raft.services.serve.github.deploy_job.GitAuthManager") as auth_cls, patch(
            "raft.services.serve.github.deploy_job.AppApply"
        ) as apply_cls:
            stub_auth(auth_cls)
            apply_cls.return_value.apply_git.return_value = "web"
            job = runner.start(sample_session(mock=False), sample_repo(), "main")
            for _ in range(80):
                time.sleep(0.05)
                if job.status in {"succeeded", "failed"}:
                    break
        assert job.status == "succeeded"
        assert job.deploy_pubkey
