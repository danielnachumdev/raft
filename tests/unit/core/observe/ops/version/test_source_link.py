"""SourceLink GitHub commit URL helpers."""

import os
from unittest.mock import patch

from raft.core.observe.ops.version.source_link import SourceLink


class TestSourceLink:
    def test_commit_url_default_repo(self) -> None:
        sha = "abc1234def5678901234567890abcdef12345678"
        assert SourceLink().commit_url(sha) == (
            f"https://github.com/danielnachumdev/raft/commit/{sha}"
        )

    def test_commit_url_none_without_sha(self) -> None:
        assert SourceLink().commit_url(None) is None
        assert SourceLink().commit_url("") is None
        assert SourceLink().commit_url("not a sha!") is None

    def test_repo_slug_from_explicit_url(self) -> None:
        assert (
            SourceLink().repo_slug("https://github.com/acme/demo.git") == "acme/demo"
        )

    def test_repo_slug_from_env(self) -> None:
        with patch.dict(
            os.environ, {"RAFT_REPO_URL": "git@github.com:acme/demo.git"}, clear=False
        ):
            assert SourceLink().repo_slug(None) == "acme/demo"
