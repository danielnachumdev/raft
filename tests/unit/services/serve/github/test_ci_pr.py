"""Unit tests for GitHub CI workflow PR setup."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest

from raft.errors.cta import OperatorError
from raft.services.serve.github.ci_pr import GithubCiPrSetup
from raft.services.serve.github.ci_workflow import BRANCH_NAME, WORKFLOW_REL, RaftApplyWorkflow
from raft.services.serve.github.next_steps import DeployNextSteps

from ._helpers import sample_repo
from ....base import RaftTestCase


class TestRaftApplyWorkflow(RaftTestCase):
    def test_render_includes_ssh_apply(self) -> None:
        text = RaftApplyWorkflow().render(sample_repo(), "main")
        assert WORKFLOW_REL.endswith("raft-apply.yml")
        assert "raft apply --git" in text
        assert sample_repo().ssh_url in text
        assert "RAFT_SSH_HOST" in text
        assert RaftApplyWorkflow.pr_body()


class TestGithubCiPrSetup(RaftTestCase):
    def test_mock_opens_pr(self) -> None:
        result = GithubCiPrSetup().ensure("tok", sample_repo(), mock=True)
        assert result.status == "opened" and result.pr_url and "pull/1" in result.pr_url

    def test_exists_on_default_branch(self) -> None:
        ci = GithubCiPrSetup()
        with patch.object(ci, "_request", return_value='{"sha":"abc"}'):
            result = ci.ensure("tok", sample_repo(), mock=False)
        assert result.status == "exists"

    def test_opens_pr_happy_path(self) -> None:
        ci = GithubCiPrSetup()
        with patch.object(ci, "_request", side_effect=_HappyGithub()):
            result = ci.ensure("tok", sample_repo(), mock=False)
        assert result.status == "opened"
        assert result.pr_url == "https://github.com/o/r/pull/9"

    def test_branch_exists_and_pr_422(self) -> None:
        ci = GithubCiPrSetup()
        with patch.object(ci, "_request", side_effect=_RetryGithub()):
            result = ci.ensure("tok", sample_repo(), mock=False)
        assert result.pr_url == "https://github.com/o/r/pull/2"

    def test_http_error_and_missing_sha(self) -> None:
        import urllib.error

        ci = GithubCiPrSetup()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("u", 403, "x", hdrs=None, fp=BytesIO(b"no")),
        ):
            with pytest.raises(OperatorError, match="HTTP 403"):
                ci._request("t", "https://api.github.com/x")
        with patch.object(ci, "_request", return_value="{}"):
            with pytest.raises(OperatorError, match="default branch sha"):
                ci._branch_sha("t", "o/r", "main")
        with pytest.raises(OperatorError, match="pull request URL"):
            GithubCiPrSetup._pr_html({})

    def test_unexpected_wrap(self) -> None:
        ci = GithubCiPrSetup()
        with patch.object(ci, "_ensure_real", side_effect=RuntimeError("boom")):
            with pytest.raises(OperatorError, match="CI PR setup failed"):
                ci.ensure("t", sample_repo(), mock=False)

    def test_next_steps_ci(self) -> None:
        ns = DeployNextSteps()
        assert ns.ci_steps({"status": "opened", "pr_url": "https://x/p/1"})[0]["title"] == "Merge CI PR"
        assert ns.ci_steps({"status": "exists"})[0]["title"] == "CI workflow"
        assert ns.ci_steps({"status": "failed", "detail": "nope"})[0]["body"] == "nope"
        assert ns.ci_steps({"status": "weird"}) == []
        assert ns.ci_steps(None) == []
        assert BRANCH_NAME == "raft/ci-apply"

    def test_result_to_dict_without_pr_url(self) -> None:
        from raft.services.serve.github.ci_pr import CiPrResult

        assert CiPrResult(status="exists", detail="ok").to_dict() == {
            "status": "exists",
            "detail": "ok",
        }

    def test_existing_pr_url_empty(self) -> None:
        ci = GithubCiPrSetup()
        with patch.object(ci, "_request", return_value="[]"):
            assert ci._existing_pr_url("t", sample_repo()) is None
        with patch.object(ci, "_request", return_value='[{"html_url": null}]'):
            assert ci._existing_pr_url("t", sample_repo()) is None

    def test_open_pr_422_falls_back_to_repo_url(self) -> None:
        ci = GithubCiPrSetup()
        with patch.object(ci, "_existing_pr_url", return_value=None):
            with patch.object(
                ci,
                "_request",
                side_effect=OperatorError("GitHub API error HTTP 422: pr", has_fix=False),
            ):
                assert ci._open_pr("t", sample_repo(), "main") == sample_repo().html_url

    def test_branch_and_pr_non_422_reraise(self) -> None:
        ci = GithubCiPrSetup()
        err = OperatorError("GitHub API error HTTP 500: x", has_fix=False)
        with patch.object(ci, "_request", side_effect=err):
            with pytest.raises(OperatorError, match="HTTP 500"):
                ci._ensure_branch("t", "o/r", "sha")
            with pytest.raises(OperatorError, match="HTTP 500"):
                ci._open_pr("t", sample_repo(), "main")

    def test_read_success(self) -> None:
        from unittest.mock import MagicMock

        import urllib.request

        resp = MagicMock()
        resp.read.return_value = b'{"ok":true}'
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        with patch("urllib.request.urlopen", return_value=resp):
            out = GithubCiPrSetup._read(urllib.request.Request("https://example.com"))
        assert out == '{"ok":true}'


class _HappyGithub:
    def __call__(self, token, url, method="GET", payload=None):
        del token, payload
        if method == "GET" and "contents" in url:
            raise OperatorError("GitHub API error HTTP 404: missing", has_fix=False)
        if method == "GET" and "git/ref" in url:
            return json.dumps({"object": {"sha": "deadbeef"}})
        if method in {"POST", "PUT"}:
            if url.endswith("/pulls"):
                return json.dumps({"html_url": "https://github.com/o/r/pull/9"})
            return "{}"
        raise AssertionError(url)


class _RetryGithub:
    def __call__(self, token, url, method="GET", payload=None):
        del token, payload
        if method == "GET" and "contents" in url:
            raise OperatorError("GitHub API error HTTP 404: x", has_fix=False)
        if method == "GET" and "git/ref" in url:
            return json.dumps({"object": {"sha": "abc"}})
        if method == "POST" and url.endswith("/git/refs"):
            raise OperatorError("GitHub API error HTTP 422: exists", has_fix=False)
        if method == "PUT":
            return "{}"
        if method == "POST" and url.endswith("/pulls"):
            raise OperatorError("GitHub API error HTTP 422: pr", has_fix=False)
        if method == "GET" and "pulls?" in url:
            return json.dumps([{"html_url": "https://github.com/o/r/pull/2"}])
        raise AssertionError(f"{method} {url}")
