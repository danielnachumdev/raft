"""Serve deploy failure notifies via Notifier."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from raft.core.platform.github.deploy import GithubDeployRunner
from raft.core.platform.github.deploy import DeployJobStore
from raft.core.observe.notify.control_events import KIND_SERVE_DEPLOY_FAILED

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.platform.github import fixtures as github_fx


class TestDeployNotify(RaftTestCase):
    def test_missing_manifest_notifies(self) -> None:
        tree = self.tmp_path / "empty-tree"
        tree.mkdir()
        provider = github_fx.StubLocalGithubProvider(tree, full_name="demo/no-manifest")
        notifier = MagicMock()
        runner = GithubDeployRunner(
            StackMakers.make_stack(self.tmp_path),
            provider,
            DeployJobStore(),
            notifier=notifier,
        )
        repo = provider.list_repos("t")[0]
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
