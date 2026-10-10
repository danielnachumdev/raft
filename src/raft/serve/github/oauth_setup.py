"""Suggested GitHub OAuth App field values for ``raft serve`` setup."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlencode

GITHUB_OAUTH_APP_NEW = "https://github.com/settings/applications/new"
SETUP_DOCS_URL = (
    "https://github.com/danielnachumdev/raft/blob/main/docs/serve-github-deploy.md"
)
APPLICATION_NAME = "raft serve"
DESCRIPTION = (
    "Localhost raft serve ops UI — temporary GitHub login to pick a repo and deploy."
)


class GithubOauthAppSetup:
    """Concrete checklist values + create-app URL for serve OAuth setup."""

    def public_fields(self, *, port: int) -> Dict[str, Any]:
        homepage = f"http://127.0.0.1:{port}/"
        callback = f"http://127.0.0.1:{port}/api/github/callback"
        return {
            "application_name": APPLICATION_NAME,
            "homepage_url": homepage,
            "description": DESCRIPTION,
            "callback_url": callback,
            "enable_device_flow": False,
            "expire_user_access_tokens": False,
            "oauth_app_url": self.create_app_url(
                name=APPLICATION_NAME,
                homepage=homepage,
                description=DESCRIPTION,
                callback=callback,
            ),
            "docs_url": SETUP_DOCS_URL,
        }

    def create_app_url(
        self,
        *,
        name: str,
        homepage: str,
        description: str,
        callback: str,
    ) -> str:
        # Best-effort Rails-style form keys. GitHub documents URL prefills for
        # GitHub Apps only; classic OAuth Apps may ignore these query params.
        params = urlencode(
            {
                "oauth_application[name]": name,
                "oauth_application[url]": homepage,
                "oauth_application[description]": description,
                "oauth_application[callback_url]": callback,
            }
        )
        return f"{GITHUB_OAUTH_APP_NEW}?{params}"
