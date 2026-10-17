"""GitHub OAuth, accounts, providers, and deploy-assist (shared capability).

Adapters: ``raft.services.serve.github`` and ``raft github …`` CLI.
"""

from .accounts import (
    GithubAccount,
    GithubAccountStore,
    GithubActiveResolver,
    GithubPendingOauth,
)
from .assist import GithubAssistService
from .deploy import (
    CiPrResult,
    DeployJob,
    DeployJobStore,
    DeployStep,
    GithubCiPrSetup,
    GithubDeployRunner,
)
from .gateway import GithubApiGateway, GithubHttpError, GithubHttpResponse
from .oauth import GITHUB_OAUTH_SCOPES, GithubOauth, GithubSettingsWriter
from .providers import (
    GithubProvider,
    GithubRepo,
    MockGithubProvider,
    RealGithubProvider,
    filter_repos,
)

__all__ = [
    "CiPrResult",
    "DeployJob",
    "DeployJobStore",
    "DeployStep",
    "GITHUB_OAUTH_SCOPES",
    "GithubAccount",
    "GithubAccountStore",
    "GithubActiveResolver",
    "GithubApiGateway",
    "GithubAssistService",
    "GithubCiPrSetup",
    "GithubDeployRunner",
    "GithubHttpError",
    "GithubHttpResponse",
    "GithubOauth",
    "GithubPendingOauth",
    "GithubProvider",
    "GithubRepo",
    "GithubSettingsWriter",
    "MockGithubProvider",
    "RealGithubProvider",
    "filter_repos",
]
