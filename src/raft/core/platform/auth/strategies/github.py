"""GitHub deploy-key settings URL hints."""

from .host_hint import DeployKeyHostHint


class GithubDeployKeyHint(DeployKeyHostHint):
    def matches(self, host: str) -> bool:
        return host == "github.com"

    def open_lines(self, host: str, repo_path: str) -> list[str]:
        del host
        return [
            f"  Open:   https://github.com/{repo_path}/settings/keys/new",
            "          (paste Title + Key, enable Allow read-only access)",
        ]
