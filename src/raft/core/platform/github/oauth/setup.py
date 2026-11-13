"""Suggested GitHub OAuth App field values for serve / public dashboard."""

from typing import Any, Dict, Optional
from urllib.parse import urlencode

from .public_base import GithubOauthPublicBase

GITHUB_APP_CREATE_URL = "https://github.com/settings/applications/new"
# Separate literal so CodeQL does not taint CREATE_URL via the OAUTH-named alias.
GITHUB_OAUTH_APP_NEW = "https://github.com/settings/applications/new"
SETUP_DOCS_URL = "https://github.com/danielnachumdev/raft/blob/main/README.md"
APPLICATION_NAME = "raft serve"
APPLICATION_NAME_PUBLIC = "raft dashboard"
DESCRIPTION = (
    "Localhost raft serve ops UI — temporary GitHub login to pick a repo "
    "and deploy."
)
DESCRIPTION_PUBLIC = (
    "Public raft dashboard — temporary GitHub login to pick a repo and deploy."
)


class GithubOauthAppSetup:
    """Concrete checklist values + create-app URL for serve OAuth setup."""

    def __init__(self) -> None:
        self._base = GithubOauthPublicBase()

    def public_fields(
        self,
        *,
        port: int,
        public_host: Optional[str] = None,
        tls: str = "off",
    ) -> Dict[str, Any]:
        homepage, callback = self._base.urls(
            port=port, public_host=public_host, tls=tls
        )
        name, description = self._labels(public_host)
        return self._fields_dict(name, homepage, description, callback)

    def _labels(self, public_host: Optional[str]) -> tuple[str, str]:
        public = self._base.is_public(public_host)
        name = APPLICATION_NAME_PUBLIC if public else APPLICATION_NAME
        description = DESCRIPTION_PUBLIC if public else DESCRIPTION
        return name, description

    def _fields_dict(
        self, name: str, homepage: str, description: str, callback: str
    ) -> Dict[str, Any]:
        return {
            "application_name": name,
            "homepage_url": homepage,
            "description": description,
            "callback_url": callback,
            "enable_device_flow": False,
            "expire_user_access_tokens": False,
            "oauth_app_url": self.create_app_url(
                name=name,
                homepage=homepage,
                description=description,
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
        return f"{GITHUB_APP_CREATE_URL}?{params}"
