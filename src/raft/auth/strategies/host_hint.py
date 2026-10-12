"""Strategy ABC: where to open the git host's deploy-key UI."""

from abc import ABC, abstractmethod


class DeployKeyHostHint(ABC):
    """Host-specific CTA lines after a deploy key is minted."""

    @abstractmethod
    def matches(self, host: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def open_lines(self, host: str, repo_path: str) -> list[str]:
        raise NotImplementedError
