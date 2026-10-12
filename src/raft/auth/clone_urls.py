"""Map canonical SSH remotes onto per-service Host aliases."""

from ..models.app import App
from .keys import SshDeployKeys
from .urls import SshGitUrls


class CloneUrlMapper:
    """Rewrite clone URLs when a deploy key Host alias is configured."""

    def __init__(self, urls: SshGitUrls, keys: SshDeployKeys) -> None:
        self.urls = urls
        self.keys = keys

    def effective(self, app: App) -> str:
        if not app.repo:
            raise ValueError(f"service {app.name!r} has no repo URL")
        if not self.keys.is_configured(app.name):
            return app.repo
        return self.rewrite(app.name, app.repo)

    def rewrite(self, service: str, repo: str) -> str:
        """Map a canonical SSH URL onto this service's Host alias when configured."""
        if not self.keys.is_configured(service):
            return repo
        return self._aliased(service, repo)

    def candidates(self, repo: str) -> tuple[str, ...]:
        """Candidate clone URLs: configured Host aliases first, then the raw repo.

        Trying aliases before ``git@github.com:…`` avoids noisy ``Permission denied
        (publickey)`` on the default identity when a deploy key is already set up.
        """
        try:
            parsed = self.urls.parse(repo)
        except ValueError:
            return (repo,)
        urls: list[str] = []
        for service in self.keys.list_services():
            base_host = self.urls.real_git_host(service, parsed.host)
            alias = self.urls.host_alias(service, base_host)
            urls.append(parsed.with_host_alias(alias))
        urls.append(repo)
        return tuple(dict.fromkeys(urls))

    def _aliased(self, service: str, repo: str) -> str:
        parsed = self.urls.parse(repo)
        base_host = self.urls.real_git_host(service, parsed.host)
        alias = self.urls.host_alias(service, base_host)
        return parsed.with_host_alias(alias)
