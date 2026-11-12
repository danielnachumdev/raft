"""Suggested OAuth App create-form values for serve."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from raft.core.platform.github.oauth import (
    APPLICATION_NAME,
    APPLICATION_NAME_PUBLIC,
    GithubOauthAppSetup,
)


class TestGithubOauthAppSetup:
    def test_public_fields_include_checklist_values(self) -> None:
        fields = GithubOauthAppSetup().public_fields(port=8787)
        assert fields["application_name"] == APPLICATION_NAME
        assert fields["homepage_url"] == "http://127.0.0.1:8787/"
        assert fields["callback_url"] == "http://127.0.0.1:8787/api/github/callback"
        assert fields["enable_device_flow"] is False
        assert fields["expire_user_access_tokens"] is False
        assert "localhost raft serve" in fields["description"].lower()

    def test_public_fields_use_dashboard_public_host(self) -> None:
        fields = GithubOauthAppSetup().public_fields(
            port=8787,
            public_host="ops.example.com",
            tls="origin",
        )
        assert fields["application_name"] == APPLICATION_NAME_PUBLIC
        assert fields["homepage_url"] == "https://ops.example.com/"
        assert (
            fields["callback_url"]
            == "https://ops.example.com/api/github/callback"
        )
        assert "public raft dashboard" in fields["description"].lower()

    def test_create_app_url_prefills_query_params(self) -> None:
        url = GithubOauthAppSetup().create_app_url(
            name="raft serve",
            homepage="http://127.0.0.1:9/",
            description="desc",
            callback="http://127.0.0.1:9/api/github/callback",
        )
        parsed = urlparse(url)
        assert parsed.path.endswith("/settings/applications/new")
        query = parse_qs(parsed.query)
        assert query["oauth_application[name]"] == ["raft serve"]
        assert query["oauth_application[url]"] == ["http://127.0.0.1:9/"]
        assert query["oauth_application[description]"] == ["desc"]
        assert query["oauth_application[callback_url]"] == [
            "http://127.0.0.1:9/api/github/callback"
        ]
