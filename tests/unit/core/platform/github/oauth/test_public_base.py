"""GithubOauthPublicBase URL resolution (dummy hosts only)."""

from raft.core.platform.github.oauth import GithubOauthPublicBase


class TestGithubOauthPublicBase:
    def test_localhost_fallback(self) -> None:
        base = GithubOauthPublicBase()
        assert base.base(port=8787) == "http://127.0.0.1:8787"
        homepage, callback = base.urls(port=9)
        assert homepage == "http://127.0.0.1:9/"
        assert callback == "http://127.0.0.1:9/api/github/callback"

    def test_public_host_https_for_origin_tls(self) -> None:
        base = GithubOauthPublicBase()
        assert (
            base.base(port=8787, public_host="ops.example.com", tls="origin")
            == "https://ops.example.com"
        )
        assert (
            base.base(port=8787, public_host="ops.example.com", tls="acme")
            == "https://ops.example.com"
        )

    def test_public_host_http_when_tls_off(self) -> None:
        base = GithubOauthPublicBase()
        assert (
            base.base(port=8787, public_host="ops.example.com", tls="off")
            == "http://ops.example.com"
        )

    def test_strips_scheme_and_ignores_loopback(self) -> None:
        base = GithubOauthPublicBase()
        assert base.normalize_host("https://ops.example.com/") == "ops.example.com"
        assert base.normalize_host("http://127.0.0.1:8787") is None
        assert base.normalize_host("localhost") is None
        assert base.is_public("ops.example.com") is True
        assert base.is_public(None) is False
