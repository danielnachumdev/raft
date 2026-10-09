"""GitHub deploy runner + next-steps unit tests."""

from __future__ import annotations

import time
from unittest.mock import patch

import yaml

from raft.models.app import App
from raft.models.manifest import AppSpec, VolumeSpec
from raft.models.ports import PortSpec
from raft.services.serve.github.deploy_job import DeployJob, DeployJobStore, GithubDeployRunner
from raft.services.serve.github.next_steps import DeployNextSteps
from raft.services.serve.github.provider import MockGithubProvider
from raft.services.serve.github.account import GithubAccount
from raft.services.serve.paths import ServePaths

from ....base import RaftTestCase, make_stack


class TestDeployNextSteps(RaftTestCase):
    def test_builds_dns_tls_env_volume_key(self) -> None:
        app = App(name="web", public_host="web.test", source="local", path="apps/web")
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            tls="origin",
            env_file="/tmp/web.env",
            volumes=(VolumeSpec(host_path="/data", container_path="/data"),),
        )
        steps = DeployNextSteps().build(
            app, spec, deploy_pubkey="ssh-ed25519 AAAA", key_fingerprint="SHA256:x"
        )
        titles = {s["title"] for s in steps}
        assert {"DNS", "Origin TLS material", "Env file", "Host volumes", "Deploy key"} <= titles
        acme = DeployNextSteps().build(app, AppSpec(ports=(), tls="acme"))
        assert any(s["title"] == "ACME prerequisites" for s in acme)
        bare = DeployNextSteps().build(
            App(name="w", public_host="", source="local", path="apps/w"),
            AppSpec(ports=()),
        )
        assert bare[0]["title"] == "Verify the site"


class TestGithubDeployRunner(RaftTestCase):
    def _session(self) -> GithubAccount:
        return GithubAccount(
            id="mock",
            access_token="mock",
            login="mock-operator",
            mock=True,
            expires_at=time.time() + 60,
        )

    def _wait(self, job: DeployJob) -> None:
        for _ in range(80):
            time.sleep(0.05)
            if job.status in {"succeeded", "failed"}:
                return

    def test_mock_local_deploy_succeeds(self) -> None:
        stack = make_stack(self.tmp_path)
        runner = GithubDeployRunner(
            stack, MockGithubProvider(ServePaths.mock_github_dir()), DeployJobStore()
        )
        repo = next(
            r
            for r in MockGithubProvider(ServePaths.mock_github_dir()).list_repos("t")
            if r.full_name == "demo/http-only-site"
        )
        with patch("raft.services.serve.github.deploy_job.AppApply") as apply_cls:
            apply_cls.return_value.apply_file.return_value = "http-only-site"
            job = runner.start(self._session(), repo, "main")
            self._wait(job)
        assert job.status == "succeeded"
        assert job.app_name == "http-only-site"
        assert job.ci_pr and job.ci_pr["status"] == "opened"
        assert (self.tmp_path / "apps" / "http-only-site" / ".raft" / "app.yaml").is_file()

    def test_missing_manifest_fails(self) -> None:
        runner = GithubDeployRunner(
            make_stack(self.tmp_path),
            MockGithubProvider(ServePaths.mock_github_dir()),
            DeployJobStore(),
        )
        repo = next(
            r
            for r in MockGithubProvider(ServePaths.mock_github_dir()).list_repos("t")
            if r.full_name == "demo/no-manifest"
        )
        job = runner.start(self._session(), repo, "main")
        self._wait(job)
        assert job.status == "failed"
        assert job.error and ".raft/app.yaml" in job.error

    def test_fill_next_steps_from_registry(self) -> None:
        stack = make_stack(self.tmp_path)
        manifest = self._write_registry_manifest()
        runner = GithubDeployRunner(
            stack, MockGithubProvider(ServePaths.mock_github_dir()), DeployJobStore()
        )
        job = DeployJob(
            id="x", full_name="demo/http-only-site", ref="main", app_name="http-only-site"
        )
        runner._fill_next_steps(job, manifest)
        assert any(s["title"] == "DNS" for s in job.next_steps)

    def test_deploy_key_url_requires_slash(self) -> None:
        job = DeployJob(id="x", full_name="noslash", ref="main")
        assert GithubDeployRunner._deploy_key_url(job) is None
        job.full_name = "o/r"
        assert "settings/keys/new" in GithubDeployRunner._deploy_key_url(job)

    def _write_registry_manifest(self) -> dict:
        apps = self.tmp_path / "state" / "apps"
        apps.mkdir(parents=True, exist_ok=True)
        manifest = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "http-only-site"},
            "spec": {
                "publicHost": "site.example.com",
                "source": "local",
                "path": "apps/http-only-site",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                "readiness": {"type": "http", "port": "http", "path": "/"},
            },
        }
        (apps / "http-only-site.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
        (self.tmp_path / "apps" / "http-only-site").mkdir(parents=True, exist_ok=True)
        return manifest
