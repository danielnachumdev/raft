"""Resolve a service repo URL from ``--repo`` or an applied App."""

from typing import Optional

from ..errors.cta import OperatorError
from ..models.stack import Stack


class RepoUrlResolver:
    """Repo URL from CLI ``--repo`` or registry (no chicken-and-egg)."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def resolve(self, service: str, repo: Optional[str] = None) -> str:
        if repo is not None and str(repo).strip():
            return str(repo).strip()
        return self._from_applied_app(service)

    def _from_applied_app(self, service: str) -> str:
        try:
            app = self.stack.app(service)
        except RuntimeError as exc:
            known = ", ".join(a.name for a in self.stack.apps) or "(none applied)"
            raise OperatorError(
                f"unknown app {service!r} (known: {known}). "
                f"Pass --repo git@host:owner/repo.git to set up auth before apply, "
                f"or register a manifest first: raft apply --file PATH --no-deploy",
                has_fix=False,
            ) from exc
        if not app.repo:
            raise OperatorError(
                f"{service!r} needs a repo URL: pass --repo, or set spec.repo on the "
                f"applied App (git source, or docker with repo for checkout)",
                has_fix=False,
            )
        return app.repo
