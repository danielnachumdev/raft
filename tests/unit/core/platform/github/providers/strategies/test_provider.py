"""Mock + real GitHub provider unit tests."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.github.gateway import GithubApiGateway
from raft.core.platform.github.providers import MockGithubProvider
from raft.core.platform.github.providers import RealGithubProvider
from raft.services.serve.http.paths import ServePaths

from tests.unit.base import RaftTestCase

_GATEWAY_URLOPEN = "raft.core.platform.github.gateway.urlopen"


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
        assert p.resolve_local_tree("demo/nope") is None
        assert p.resolve_local_tree("bad") is None


class TestRealGithubProvider(RaftTestCase):
    def test_parse_repo(self) -> None:
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
        assert repo.full_name == "o/r" and repo.private is True
        assert RealGithubProvider().resolve_local_tree("o/r") is None

    def test_list_filters_user_repos_only(self) -> None:
        provider = RealGithubProvider()
        payload = (
            '[{"full_name":"demo-org/demo-api","name":"demo-api","private":false,'
            '"default_branch":"main","clone_url":"c","ssh_url":"s","html_url":"h"},'
            '{"full_name":"demo-org/other","name":"other","private":true,'
            '"default_branch":"main","clone_url":"c","ssh_url":"s","html_url":"h"}]'
        )
        with patch.object(provider, "_request_page", return_value=(payload, None)) as page:
            assert provider.list_repos("tok")[0].full_name == "demo-org/demo-api"
            url = page.call_args.args[1]
            assert "/user/repos" in url
            assert "affiliation=owner%2Ccollaborator%2Corganization_member" in url
            assert "search/repositories" not in url
            filtered = provider.list_repos("tok", query="demo-api")
            assert [r.full_name for r in filtered] == ["demo-org/demo-api"]
            assert provider.list_repos("tok", query="nope") == []

    def test_manifest_ok_and_empty(self) -> None:
        gateway = MagicMock(spec=GithubApiGateway)
        gateway.bearer_headers = GithubApiGateway.bearer_headers
        gateway.get.return_value = MagicMock(body="apiVersion: raft/v1\n")
        provider = RealGithubProvider(gateway=gateway)
        assert "raft/v1" in provider.fetch_manifest("tok", "a/b", "main")
        gateway.get.return_value = MagicMock(body="  \n")
        with pytest.raises(OperatorError, match="empty"):
            provider.fetch_manifest("tok", "a/b", "main")

    def test_next_link_parsing(self) -> None:
        assert RealGithubProvider._next_link(None) is None
        link = '<https://api.github.com/x?page=2>; rel="next", <u>; rel="prev"'
        assert "page=2" in (RealGithubProvider._next_link(link) or "")

    def test_gateway_get_ok(self) -> None:
        provider = RealGithubProvider()
        resp = MagicMock()
        resp.read.return_value = b"ok"
        resp.status = 200
        resp.headers = {"Link": ""}
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        with patch(_GATEWAY_URLOPEN, return_value=resp):
            out = provider._http.get(
                "https://example.com",
                headers=provider._http.bearer_headers("tok"),
            )
            assert out.body == "ok"

    def test_gateway_get_404_and_manifest_missing(self) -> None:
        import urllib.error

        from raft.core.platform.github.gateway import GithubHttpError

        provider = RealGithubProvider()
        err = urllib.error.HTTPError(
            "u", 404, "x", hdrs=None, fp=BytesIO(b'{"message":"no"}')
        )
        with patch(_GATEWAY_URLOPEN, side_effect=err):
            with pytest.raises(GithubHttpError) as raised:
                provider._http.get("https://example.com", headers={})
            assert raised.value.code == 404
        with patch.object(
            provider._http,
            "get",
            side_effect=GithubHttpError(404, '{"message":"no"}'),
        ):
            with pytest.raises(OperatorError, match="no .raft/app.yaml"):
                provider.fetch_manifest("tok", "a/b", "main")

    def test_manifest_non_404_api_error(self) -> None:
        from raft.core.platform.github.gateway import GithubHttpError

        provider = RealGithubProvider()
        with patch.object(
            provider._http,
            "get",
            side_effect=GithubHttpError(500, "boom"),
        ):
            with pytest.raises(OperatorError, match="GitHub API error"):
                provider.fetch_manifest("tok", "a/b", "main")

    def test_gateway_put_json_extra_and_getcode(self) -> None:
        from raft.core.platform.github.gateway import GithubApiGateway

        gw = GithubApiGateway()
        headers = GithubApiGateway.json_headers(extra={"X-Demo": "1"})
        assert headers["X-Demo"] == "1"
        resp = MagicMock()
        resp.read.return_value = b"put-ok"
        resp.status = "not-int"
        resp.getcode.return_value = 201
        resp.headers = {"Content-Type": "text/plain"}
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        with patch(_GATEWAY_URLOPEN, return_value=resp):
            out = gw.put("https://example.com", headers={}, body=b"{}")
        assert out.body == "put-ok" and out.status == 201

    def test_request_500_and_empty_lists(self) -> None:
        from raft.core.platform.github.gateway import GithubHttpError

        provider = RealGithubProvider()
        with patch.object(
            provider._http, "get", side_effect=GithubHttpError(500, "boom")
        ):
            with pytest.raises(OperatorError, match="GitHub API error"):
                provider._request_page("tok", "https://example.com")
        with patch.object(provider, "_request_page", return_value=("{}", None)):
            assert provider.list_repos("tok") == []
        with patch.object(provider, "_request_page", return_value=("[]", None)):
            assert provider.list_repos("tok", query="x") == []
