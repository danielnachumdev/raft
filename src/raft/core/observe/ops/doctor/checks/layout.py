"""Detect unmigrated pre-#313 data-home layout (hard fail, no dual-read)."""

from __future__ import annotations

from pathlib import Path

from raft.core.core.config.paths.constants import OLD_LAYOUT_MARKERS, SETTINGS_REL

from ..context import DoctorContext
from ..models import INFRA, CheckResult

_MIGRATE_CTA = (
    "migrate the data home per GitHub issue #313 "
    "(host/ + services/<name>/), then: raft migrate   "
    "# or move paths manually; see docs/data-home-migrate.md"
)


class LayoutChecks:
    """Fail when leftover old roots mean the home was not cut over."""

    name = "layout"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        leftovers = self._leftovers(ctx.stack.root)
        if leftovers:
            return [self._fail(leftovers)]
        return [self._ok(ctx.stack.root)]

    def _ok(self, home: Path) -> CheckResult:
        if (home / SETTINGS_REL).is_file() or (home / "services").is_dir():
            return CheckResult(INFRA, "layout", "ok", "host/ + services/ layout")
        return CheckResult(
            INFRA,
            "layout",
            "ok",
            "empty or fresh data home (new layout dirs on ensure)",
        )

    @staticmethod
    def _fail(leftovers: list[str]) -> CheckResult:
        detail = "unmigrated old paths: " + ", ".join(leftovers[:8])
        if len(leftovers) > 8:
            detail += f" (+{len(leftovers) - 8} more)"
        return CheckResult(INFRA, "layout", "fail", detail, fix=_MIGRATE_CTA)

    def _leftovers(self, home: Path) -> list[str]:
        found: list[str] = []
        for rel in OLD_LAYOUT_MARKERS:
            found.extend(self._marker_hits(home, rel))
        return found

    def _marker_hits(self, home: Path, rel: Path) -> list[str]:
        path = home / rel
        if rel == Path("secrets"):
            return [str(rel) + "/"] if self._top_level_app_secrets(path) else []
        if rel == Path("settings.yaml"):
            return [str(rel)] if path.is_file() else []
        if path.exists():
            return [str(rel) + ("/" if path.is_dir() else "")]
        return []

    @staticmethod
    def _top_level_app_secrets(path: Path) -> bool:
        """True when top-level secrets/<app>/ exists (dashboard alone is OK under host/)."""
        if not path.is_dir():
            return False
        for child in path.iterdir():
            if child.name == "dashboard":
                continue
            if child.is_dir():
                return True
        return False
