"""Install app-owned scale-to-zero holding pages into generated gate-http."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from raft.errors.cta import OperatorError
from raft.models.app import App
from raft.models.manifest import AppSpec

logger = logging.getLogger(__name__)

HOLDING_SUBDIR = Path("holding")
CONTAINER_HOLDING_DIR = "/etc/nginx/http-generated/holding"


class ScalingHoldingPages:
    """Copy ``spec.scaling.holdingPage`` into the gate-http bind mount (reload, no recreate)."""

    def install(self, root: Path, apps: list[App], specs: dict[str, AppSpec]) -> None:
        dest_dir = self.host_dir(root)
        dest_dir.mkdir(parents=True, exist_ok=True)
        wanted: set[str] = set()
        for app in apps:
            name = self._maybe_install_one(root, app, specs[app.name], dest_dir)
            if name is not None:
                wanted.add(name)
        self._prune(dest_dir, wanted)

    @classmethod
    def host_dir(cls, root: Path) -> Path:
        return root / "generated" / "nginx" / "gate-http" / HOLDING_SUBDIR

    @classmethod
    def container_alias(cls, app_name: str) -> str:
        return f"{CONTAINER_HOLDING_DIR}/{app_name}.html"

    def _maybe_install_one(
        self, root: Path, app: App, spec: AppSpec, dest_dir: Path
    ) -> Optional[str]:
        scaling = spec.scaling
        if scaling is None or not scaling.holding_page:
            return None
        src = self._resolve_source(root, app, scaling.holding_page)
        dest = dest_dir / f"{app.name}.html"
        shutil.copy2(src, dest)
        logger.info(
            "holding page %s → %s",
            scaling.holding_page,
            dest.relative_to(root),
        )
        return dest.name

    def _resolve_source(self, root: Path, app: App, rel: str) -> Path:
        base = app.abs_path(root)
        if not base.is_dir():
            raise OperatorError(
                f"{app.name}: app checkout missing at {app.path} "
                f"(needed for spec.scaling.holdingPage).\n"
                f"Fix: raft sync {app.name}, then: raft render"
            )
        src = (base / rel).resolve()
        self._require_under_app_root(app, base, src, rel)
        if not src.is_file():
            raise OperatorError(
                f"{app.name}: spec.scaling.holdingPage {rel!r} not found under {app.path}.\n"
                f"Fix: ship the HTML in the app tree (path relative to app root), "
                f"then: raft sync {app.name} && raft render"
            )
        return src

    @staticmethod
    def _require_under_app_root(app: App, base: Path, src: Path, rel: str) -> None:
        try:
            src.relative_to(base.resolve())
        except ValueError as exc:
            raise OperatorError(
                f"{app.name}: spec.scaling.holdingPage {rel!r} escapes the app root.\n"
                f"Fix: use a path under {app.path} with no '..' segments"
            ) from exc

    @staticmethod
    def _prune(dest_dir: Path, wanted: set[str]) -> None:
        for path in dest_dir.glob("*.html"):
            if path.name in wanted:
                continue
            path.unlink()
            logger.info("removed stale holding page %s", path.name)
