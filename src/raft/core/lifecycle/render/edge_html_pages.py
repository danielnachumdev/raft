"""Install app-owned edge HTML pages into generated gate-http."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec

logger = logging.getLogger(__name__)

UNAVAILABLE_SUBDIR = Path("unavailable")
FORBIDDEN_SUBDIR = Path("forbidden")
CONTAINER_UNAVAILABLE_DIR = "/etc/nginx/http-generated/unavailable"
CONTAINER_FORBIDDEN_DIR = "/etc/nginx/http-generated/forbidden"
DEFAULT_UNAVAILABLE_ROOT = "/usr/share/nginx/errors"
DEFAULT_FORBIDDEN_ALIAS = "/usr/share/nginx/errors/forbidden.html"


class EdgeHtmlPages:
    """Copy ``unavailablePage`` / ``forbiddenPage`` into the gate-http bind mount."""

    def install(self, root: Path, apps: list[App], specs: dict[str, AppSpec]) -> None:
        self._install_kind(
            root,
            apps,
            specs,
            subdir=UNAVAILABLE_SUBDIR,
            attr="unavailable_page",
            label="unavailablePage",
        )
        self._install_kind(
            root,
            apps,
            specs,
            subdir=FORBIDDEN_SUBDIR,
            attr="forbidden_page",
            label="forbiddenPage",
        )

    @classmethod
    def host_dir(cls, root: Path, *, subdir: Path) -> Path:
        return root / "generated" / "nginx" / "gate-http" / subdir

    @classmethod
    def unavailable_alias(cls, app_name: str) -> str:
        return f"{CONTAINER_UNAVAILABLE_DIR}/{app_name}.html"

    @classmethod
    def forbidden_alias(cls, app_name: str) -> str:
        return f"{CONTAINER_FORBIDDEN_DIR}/{app_name}.html"

    @classmethod
    def aliases_for(cls, app: App, spec: AppSpec) -> tuple[Optional[str], Optional[str]]:
        unavail = cls.unavailable_alias(app.name) if spec.unavailable_page else None
        forbid = cls.forbidden_alias(app.name) if spec.forbidden_page else None
        return unavail, forbid

    def _install_kind(
        self,
        root: Path,
        apps: list[App],
        specs: dict[str, AppSpec],
        *,
        subdir: Path,
        attr: str,
        label: str,
    ) -> None:
        dest_dir = self.host_dir(root, subdir=subdir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        wanted: set[str] = set()
        for app in apps:
            name = self._maybe_install_one(
                root, app, specs[app.name], dest_dir, attr=attr, label=label
            )
            if name is not None:
                wanted.add(name)
        self._prune(dest_dir, wanted, label=label)

    def _maybe_install_one(
        self,
        root: Path,
        app: App,
        spec: AppSpec,
        dest_dir: Path,
        *,
        attr: str,
        label: str,
    ) -> Optional[str]:
        rel = getattr(spec, attr)
        if not rel:
            return None
        src = self._resolve_source(root, app, rel, label=label)
        dest = dest_dir / f"{app.name}.html"
        shutil.copy2(src, dest)
        logger.info("%s %s → %s", label, rel, dest.relative_to(root))
        return dest.name

    def _resolve_source(self, root: Path, app: App, rel: str, *, label: str) -> Path:
        base = app.abs_path(root)
        if not base.is_dir():
            raise OperatorError(
                f"{app.name}: app checkout missing at {app.path} "
                f"(needed for spec.{label}).\n"
                f"Fix: raft sync {app.name}, then: raft render"
            )
        src = (base / rel).resolve()
        self._require_under_app_root(app, base, src, rel, label=label)
        if not src.is_file():
            raise OperatorError(
                f"{app.name}: spec.{label} {rel!r} not found under {app.path}.\n"
                f"Fix: ship the HTML in the app tree (path relative to app root), "
                f"then: raft sync {app.name} && raft render"
            )
        return src

    @staticmethod
    def _require_under_app_root(
        app: App, base: Path, src: Path, rel: str, *, label: str
    ) -> None:
        try:
            src.relative_to(base.resolve())
        except ValueError as exc:
            raise OperatorError(
                f"{app.name}: spec.{label} {rel!r} escapes the app root.\n"
                f"Fix: use a path under {app.path} with no '..' segments"
            ) from exc

    @staticmethod
    def _prune(dest_dir: Path, wanted: set[str], *, label: str) -> None:
        for path in dest_dir.glob("*.html"):
            if path.name in wanted:
                continue
            path.unlink()
            logger.info("removed stale %s %s", label, path.name)
