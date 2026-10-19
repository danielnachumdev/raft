"""LatestReleaseFetcher JSON parsing and repo slug resolution."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.update import LatestReleaseFetcher
from raft.core.platform.github.gateway import GithubApiGateway, GithubHttpError, GithubHttpResponse


class TestLatestReleaseFetcher:
    def test_fetch_parses_tag(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.get.return_value = GithubHttpResponse(
            body=json.dumps(
                {
                    "tag_name": "v0.11.0",
                    "html_url": "https://github.com/danielnachumdev/raft/releases/tag/v0.11.0",
                    "name": "v0.11.0",
                }
            ),
            headers={},
            status=200,
        )
        release = LatestReleaseFetcher(gateway=gateway, repo="danielnachumdev/raft").fetch()
        assert release.tag == "v0.11.0"
        assert "v0.11.0" in release.html_url

    def test_http_error_becomes_operator_error(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.get.side_effect = GithubHttpError(403, "rate limit")
        with pytest.raises(OperatorError, match="latest raft GitHub Release"):
            LatestReleaseFetcher(gateway=gateway).fetch()

    def test_missing_tag_fails(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.get.return_value = GithubHttpResponse(
            body="{}", headers={}, status=200
        )
        with pytest.raises(OperatorError, match="missing tag_name"):
            LatestReleaseFetcher(gateway=gateway).fetch()

    def test_repo_from_env_ssh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "RAFT_REPO_URL", "git@github.com:acme/raft-fork.git"
        )
        fetcher = LatestReleaseFetcher(gateway=MagicMock())
        assert fetcher._repo == "acme/raft-fork"

    def test_repo_from_env_https(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "RAFT_REPO_URL", "https://github.com/acme/raft-fork.git"
        )
        fetcher = LatestReleaseFetcher(gateway=MagicMock())
        assert fetcher._repo == "acme/raft-fork"

    def test_transport_exception(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.get.side_effect = TimeoutError("slow")
        with pytest.raises(OperatorError, match="outbound HTTPS"):
            LatestReleaseFetcher(gateway=gateway).fetch()

    def test_invalid_json(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.get.return_value = GithubHttpResponse(
            body="not-json", headers={}, status=200
        )
        with pytest.raises(OperatorError, match="invalid JSON"):
            LatestReleaseFetcher(gateway=gateway).fetch()

    def test_unexpected_json_shape(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.get.return_value = GithubHttpResponse(
            body="[]", headers={}, status=200
        )
        with pytest.raises(OperatorError, match="unexpected JSON shape"):
            LatestReleaseFetcher(gateway=gateway).fetch()

    def test_repo_from_env_path_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_REPO_URL", "https://git.example/acme/raft.git")
        fetcher = LatestReleaseFetcher(gateway=MagicMock())
        assert fetcher._repo == "acme/raft"

    def test_repo_from_env_single_segment_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAFT_REPO_URL", "https://git.example/only")
        fetcher = LatestReleaseFetcher(gateway=MagicMock())
        assert fetcher._repo == "danielnachumdev/raft"

    def test_blank_repo_arg_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_REPO_URL", raising=False)
        fetcher = LatestReleaseFetcher(gateway=MagicMock(), repo="   ")
        assert fetcher._repo == "danielnachumdev/raft"
