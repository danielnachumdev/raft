"""GitHub commit URLs for non-release raft installs."""

import os
import re
from typing import Optional
from urllib.parse import urlparse


_DEFAULT_REPO = "danielnachumdev/raft"
_SLUG_RE = re.compile(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", re.I)


class SourceLink:
    """Build a browser URL for an installed git commit when the host is GitHub."""

    def commit_url(
        self, commit: Optional[str], *, repo_url: Optional[str] = None
    ) -> Optional[str]:
        """``https://github.com/<owner>/<repo>/commit/<sha>`` when inputs are usable."""
        sha = (commit or "").strip()
        if not sha or not all(c.isalnum() for c in sha):
            return None
        slug = self.repo_slug(repo_url)
        if not slug:
            return None
        return f"https://github.com/{slug}/commit/{sha}"

    def repo_slug(self, repo_url: Optional[str] = None) -> str:
        """Owner/name from an explicit URL, ``RAFT_REPO_URL``, or the default raft repo."""
        for candidate in (repo_url, os.environ.get("RAFT_REPO_URL")):
            parsed = self._slug_from_text((candidate or "").strip())
            if parsed:
                return parsed
        return _DEFAULT_REPO

    @staticmethod
    def _slug_from_text(text: str) -> Optional[str]:
        if not text:
            return None
        match = _SLUG_RE.search(text.rstrip("/"))
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        path = urlparse(text).path.strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1].removesuffix('.git')}"
        return None
