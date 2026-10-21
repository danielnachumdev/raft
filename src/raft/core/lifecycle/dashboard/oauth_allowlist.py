"""Read/write dashboard OAuth allowlist file (0600)."""

import os
from pathlib import Path
from typing import Dict, List

from raft.core.core.config.settings.dashboard_config import DEFAULT_OAUTH_ALLOWLIST
from raft.core.core.errors.cta import OperatorError

from .oauth_paths import DashboardOAuthPaths


class DashboardOAuthAllowlist:
    """One identity per line; comments and blanks ignored."""

    def __init__(self, data_home: Path) -> None:
        self._paths = DashboardOAuthPaths(data_home)

    def path(self, relative: str = DEFAULT_OAUTH_ALLOWLIST) -> Path:
        return self._paths.allowlist_file(relative)

    def ensure(self, relative: str = DEFAULT_OAUTH_ALLOWLIST) -> Path:
        path = self.path(relative)
        if path.is_file():
            return path
        self._paths.ensure_dir()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# One identity per line (docs example: ops@example.com)\n",
            encoding="utf-8",
        )
        os.chmod(path, 0o600)
        return path

    def read(self, relative: str = DEFAULT_OAUTH_ALLOWLIST) -> List[str]:
        path = self.path(relative)
        if not path.is_file():
            return []
        return self.parse(path.read_text(encoding="utf-8"))

    def write(
        self, lines: List[str], *, relative: str = DEFAULT_OAUTH_ALLOWLIST
    ) -> Dict[str, object]:
        path = self.path(relative)
        self._paths.ensure_dir()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "# One identity per line\n"
        if lines:
            body += "\n".join(lines) + "\n"
        path.write_text(body, encoding="utf-8")
        os.chmod(path, 0o600)
        return {"allowlistFile": str(path), "count": len(lines)}

    def set_from_file(
        self, source: Path, *, relative: str = DEFAULT_OAUTH_ALLOWLIST
    ) -> Dict[str, object]:
        if not source.is_file():
            raise OperatorError(
                f"allowlist source not found: {source}\n"
                "Fix: pass an existing file path",
                has_fix=False,
            )
        return self.write(self.parse(source.read_text(encoding="utf-8")), relative=relative)

    def add(
        self, identity: str, *, relative: str = DEFAULT_OAUTH_ALLOWLIST
    ) -> Dict[str, object]:
        text = (identity or "").strip()
        if not text or text.startswith("#"):
            raise OperatorError(
                "allowlist identity must be a non-empty line.\n"
                "Fix: append ops@example.com to "
                "host/secrets/dashboard/oauth-allowlist.txt",
                has_fix=False,
            )
        existing = self.read(relative)
        if text.lower() not in {x.lower() for x in existing}:
            existing.append(text)
        return self.write(existing, relative=relative)

    def exists(self, relative: str = DEFAULT_OAUTH_ALLOWLIST) -> bool:
        return self.path(relative).is_file()

    @staticmethod
    def parse(text: str) -> List[str]:
        out: List[str] = []
        for line in text.splitlines():
            item = line.strip()
            if not item or item.startswith("#"):
                continue
            out.append(item)
        return out
