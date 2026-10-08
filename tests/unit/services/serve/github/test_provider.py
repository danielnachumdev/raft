"""Mock + real GitHub provider unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.errors.cta import OperatorError
from raft.services.serve.github.provider import MockGithubProvider, RealGithubProvider
from raft.services.serve.paths import ServePaths

from ....base import RaftTestCase


class TestMockGithubProvider(RaftTestCase):
    def test_list_filter_and_manifest(self) -> None:
        p = MockGithubProvider(ServePaths.mock_github_dir())
        all_repos = p.list_repos("tok")
        assert {r.full_name for r in all_repos} == {
            "demo/http-only-site",
            "demo/no-manifest",
        }
        filtered = p.list_repos("tok", query="http-only")
        assert [r.full_name for r in filtered] == ["demo/http-only-site"]
        text = p.fetch_manifest("tok", "demo/http-only-site", "main")
        assert "http-only-site" in text
        with pytest.raises(OperatorError, match="no .raft/app.yaml"):
            p.fetch_manifest("tok", "demo/no-manifest", "main")
        with pytest.raises(OperatorError, match="unknown mock"):
            p.fetch_manifest("tok", "other/x", "main")


class TestRealGithubProvider(RaftTestCase):
    def test_parse_and_404(self) -> None:
        item = {
            "full_name": "o/r",
            "name": "r",
            "owner": {"login": "o"},
            "private": True,
            "default_branch": "main",
            "clone_url": "https://github.com/o/r.git",
            "ssh_url": "git@github.com:o/r.git",
            "html_url": "https://github.com/o/r",
        }
        repo = RealGithubProvider._parse_repo(item)
        assert repo.full_name == "o/r"
        assert repo.private is True
        assert RealGithubProvider().resolve_local_tree("o/r") is None

    def test_list_repos_uses_api(self) -> None:
        provider = RealGithubProvider()
        payload = (
            '[{"full_name":"a/b","name":"b","private":false,'
            '"default_branch":"main","clone_url":"c","ssh_url":"s","html_url":"h"}]'
        )
        with patch.object(provider, "_request_page", return_value=(payload, None)):
            repos = provider.list_repos("tok")
        assert len(repos) == 1
        assert repos[0].full_name == "a/b"

    def test_search_and_manifest_404(self) -> None:
        provider = RealGithubProvider()
        search = '{"items":[{"full_name":"a/b","name":"b","private":false,'
        search += '"default_branch":"main","clone_url":"c","ssh_url":"s","html_url":"h"}]}'
        with patch.object(provider, "_request", return_value=search):
            repos = provider.list_repos("tok", query="b")
        assert repos[0].name == "b"
        err = MagicMock()
        err.code = 404
        err.read.return_value = b"missing"
        with patch.object(provider, "_request", side_effect=self._http_404()):
            with pytest.raises(OperatorError, match="no .raft/app.yaml"):
                provider.fetch_manifest("tok", "a/b", "main")

    @staticmethod
    def _http_404():
        import urllib.error

        def _raise(*_a, **_k):
            raise urllib.error.HTTPError("u", 404, "x", hdrs=None, fp=MagicMock(read=lambda: b""))

        return _raise
