"""Normalize relative App manifest paths (default ``.raft/app.yaml``)."""

from pathlib import Path, PurePosixPath
from typing import Optional

from raft.core.core.errors.cta import OperatorError

from .manifest import CONTRACT_REL_PATH


class ContractRelPath:
    """Repo-relative manifest path for apply / GitHub deploy assist."""

    DEFAULT = CONTRACT_REL_PATH.as_posix()

    def normalize(self, raw: Optional[str] = None) -> str:
        text = str(raw or "").strip().replace("\\", "/")
        if not text:
            return self.DEFAULT
        if text.endswith("/"):
            raise OperatorError(
                f"manifest path must point at a file (got {text!r}).\n"
                f"Fix: include the filename, e.g. {self.DEFAULT}",
                has_fix=False,
            )
        path = PurePosixPath(text)
        if path.is_absolute() or ".." in path.parts or not path.name:
            raise OperatorError(
                f"manifest path must be a relative file path (got {text!r}).\n"
                f"Fix: use something like {self.DEFAULT} or apps/demo/.raft/app.yaml",
                has_fix=False,
            )
        return path.as_posix()

    def under(self, root: Path, raw: Optional[str] = None) -> Path:
        rel = self.normalize(raw)
        base = root.resolve()
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise OperatorError(
                f"manifest path escapes checkout: {rel!r}\n"
                f"Fix: use a path under the repo root",
                has_fix=False,
            ) from exc
        return candidate
