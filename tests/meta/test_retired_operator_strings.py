"""Meta guard: retired operator-facing strings must stay gone (#312)."""

from pathlib import Path
from typing import Iterable, List, Tuple

import pytest

from tests.meta.scan import REPO_ROOT

pytestmark = pytest.mark.meta

# Operator-facing retired labels / aliases (not every historical substring).
# Outside scan: AGENTS.md / README upgrade notes (name removals on purpose),
# AclPolicy unit fixtures that still pass path="acl.gate" for error context.
_FORBIDDEN = (
    "RAFT_BRANCH",
    "serve-acl",
    "acl.gate",
    "AclV1Migrator",
    "NotificationsLock",
    "NOTIFICATIONS_LOCK_NAME",
    "HealForever",
    "migrateLegacyViews",
    "github-session.json",
)

_SCAN_RELATIVE = (
    "install.sh",
    "examples",
    "src/raft",
    "src/spa/src",
)

Hit = Tuple[str, str, int]


class TestRetiredOperatorStrings:
    def test_forbidden_strings_absent_from_operator_surfaces(self) -> None:
        hits = RetiredStringScanner().hits()
        assert not hits, self._fmt(hits)

    @staticmethod
    def _fmt(hits: List[Hit]) -> str:
        lines = ["retired operator-facing strings must stay gone (#312):"]
        lines += [f"  {path}:{lineno}: {needle}" for path, needle, lineno in hits]
        return "\n".join(lines)


class RetiredStringScanner:
    """Walk operator-facing trees for forbidden retirement leftovers."""

    def hits(self) -> List[Hit]:
        out: List[Hit] = []
        for root in self._roots():
            out.extend(self._scan_path(root))
        return out

    def _roots(self) -> List[Path]:
        return [REPO_ROOT / rel for rel in _SCAN_RELATIVE]

    def _scan_path(self, path: Path) -> List[Hit]:
        if path.is_file():
            return self._scan_file(path)
        if not path.is_dir():
            return []
        hits: List[Hit] = []
        for child in sorted(path.rglob("*")):
            if child.is_file() and self._textish(child):
                hits.extend(self._scan_file(child))
        return hits

    def _scan_file(self, path: Path) -> List[Hit]:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        rel = str(path.relative_to(REPO_ROOT))
        return list(self._line_hits(rel, text.splitlines()))

    def _line_hits(self, rel: str, lines: Iterable[str]) -> Iterable[Hit]:
        for lineno, line in enumerate(lines, start=1):
            for needle in _FORBIDDEN:
                if needle in line:
                    yield rel, needle, lineno

    @staticmethod
    def _textish(path: Path) -> bool:
        return path.suffix.lower() in {
            "",
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".css",
            ".md",
            ".yaml",
            ".yml",
            ".sh",
            ".toml",
            ".json",
            ".txt",
        } or path.name in {"install.sh", "Dockerfile"}
