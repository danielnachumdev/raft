"""GitHub OAuth helpers + settings persistence for ``raft serve``."""

from .oauth import GITHUB_LOGIN_SCOPES, GITHUB_OAUTH_SCOPES, GithubOauth
from .public_base import GithubOauthPublicBase
from .settings_write import GithubSettingsWriter
from .setup import (
    APPLICATION_NAME,
    APPLICATION_NAME_PUBLIC,
    DESCRIPTION,
    DESCRIPTION_PUBLIC,
    GITHUB_APP_CREATE_URL,
    GITHUB_OAUTH_APP_NEW,
    SETUP_DOCS_URL,
    GithubOauthAppSetup,
)

__all__ = [
    "APPLICATION_NAME",
    "APPLICATION_NAME_PUBLIC",
    "DESCRIPTION",
    "DESCRIPTION_PUBLIC",
    "GITHUB_APP_CREATE_URL",
    "GITHUB_LOGIN_SCOPES",
    "GITHUB_OAUTH_APP_NEW",
    "GITHUB_OAUTH_SCOPES",
    "GithubOauth",
    "GithubOauthAppSetup",
    "GithubOauthPublicBase",
    "GithubSettingsWriter",
    "SETUP_DOCS_URL",
]
