"""Generic git-host deploy-key UI hints."""

from .host_hint import DeployKeyHostHint


class GenericDeployKeyHint(DeployKeyHostHint):
    def matches(self, host: str) -> bool:
        del host
        return True

    def open_lines(self, host: str, repo_path: str) -> list[str]:
        return [
            f"  Open:   {host} → {repo_path} → Deploy keys → Add",
            "          (paste Title + Key as read-only)",
        ]
