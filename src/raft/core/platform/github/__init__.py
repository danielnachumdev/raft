"""GitHub OAuth, accounts, providers, and deploy-assist (shared capability).

FastAPI adapters stay under ``raft.services.serve.github``; CLI parity is #263.
"""

from .accounts import (
    GithubAccount,
    GithubAccountStore,
    GithubActiveResolver,
    GithubPendingOauth,
)
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
