"""Serve deploy failure notifies via Notifier."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from raft.services.serve.github.deploy_job import GithubDeployRunner
from raft.services.serve.github.deploy_models import DeployJobStore
from raft.services.serve.github.strategies.mock import MockGithubProvider
from raft.services.serve.paths import ServePaths
from raft.core.observe.notify.control_events import KIND_SERVE_DEPLOY_FAILED

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.services.serve.github import fixtures as github_fx


class TestDeployNotify(RaftTestCase):
    def test_missing_manifest_notifies(self) -> None:
        notifier = MagicMock()
        runner = GithubDeployRunner(
            StackMakers.make_stack(self.tmp_path),
            MockGithubProvider(ServePaths.mock_github_dir()),
            DeployJobStore(),
            notifier=notifier,
        )
        repo = next(
            r
            for r in MockGithubProvider(ServePaths.mock_github_dir()).list_repos("t")
            if r.full_name == "demo/no-manifest"
        )
        job = runner.start(github_fx.sample_account(), repo, "main")
        self._wait(job)
        event = notifier.notify.call_args[0][0]
        assert event.kind == KIND_SERVE_DEPLOY_FAILED
        assert event.context["full_name"] == "demo/no-manifest"

    @staticmethod
    def _wait(job) -> None:
        for _ in range(100):
            if job.status in {"succeeded", "failed"}:
                return
            time.sleep(0.05)
