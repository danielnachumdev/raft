"""Operator-initiated one-shot move of pre-#313 paths (idempotent)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from raft.core.core.config.paths.constants import SETTINGS_REL
from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.ui import OperatorSay

MoveFn = Callable[[Path, Path], None]


class LayoutMigrate:
    """Perform the #313 path moves only — never dual-read at runtime."""

    def __init__(self, home: Path, *, mover: Optional[MoveFn] = None) -> None:
        self.home = home
        self._move = mover or self._rename

    def run(self, *, dry_run: bool = False) -> list[str]:
        actions: list[str] = []
        self._host_moves(actions, dry_run=dry_run)
        self._service_moves(actions, dry_run=dry_run)
        self._edge_service_logs(actions, dry_run=dry_run)
        return actions

    def _host_moves(self, actions: list[str], *, dry_run: bool) -> None:
        pairs = [
            (Path("settings.yaml"), SETTINGS_REL),
            (Path("state") / "firewall", Path("host") / "firewall"),
            (Path("state") / "alerts", Path("host") / "alerts"),
            (Path("state") / "events", Path("host") / "events"),
            (Path("state") / "metrics", Path("host") / "metrics"),
            (Path("state") / "locks", Path("host") / "locks"),
            (Path("state") / "serve", Path("host") / "serve"),
            (Path("state") / "acme" / "account.key", Path("host") / "acme" / "account.key"),
            (Path("state") / "acme" / "account.json", Path("host") / "acme" / "account.json"),
            (Path("state") / "acme" / "http-01", Path("host") / "acme" / "http-01"),
            (Path("state") / "gate-nginx.fingerprint", Path("host") / "gate-nginx.fingerprint"),
            (Path("state") / "router-nginx.fingerprint", Path("host") / "router-nginx.fingerprint"),
            (Path("logs"), Path("host") / "logs"),
            (Path("secrets") / "dashboard", Path("host") / "secrets" / "dashboard"),
        ]
        for src_rel, dst_rel in pairs:
            self._maybe_move(src_rel, dst_rel, actions, dry_run=dry_run)

    def _service_moves(self, actions: list[str], *, dry_run: bool) -> None:
        apps_dir = self.home / "state" / "apps"
        if apps_dir.is_dir():
            for yaml_path in sorted(apps_dir.glob("*.yaml")):
                name = yaml_path.stem
                dest = ServicePaths(self.home, name).app_yaml()
                self._maybe_move_abs(yaml_path, dest, actions, dry_run=dry_run)
                self._move_service_tree(name, actions, dry_run=dry_run)
        for name in self._discover_service_names():
            self._move_service_tree(name, actions, dry_run=dry_run)

    def _move_service_tree(
        self, name: str, actions: list[str], *, dry_run: bool
    ) -> None:
        svc = ServicePaths(self.home, name)
        for src_rel, dst_rel in self._service_pairs(name, svc):
            self._maybe_move(src_rel, dst_rel, actions, dry_run=dry_run)
        self._move_scaling_markers(name, svc, actions, dry_run=dry_run)
        self._move_app_service_logs(name, svc, actions, dry_run=dry_run)

    def _service_pairs(
        self, name: str, svc: ServicePaths
    ) -> list[tuple[Path, Path]]:
        return [
            (Path("secrets") / name, svc.secrets().relative_to(self.home)),
            (Path("certs") / name, svc.certs().relative_to(self.home)),
            (Path("apps") / name, svc.checkout().relative_to(self.home)),
            (Path("deploy") / name, svc.deploy().relative_to(self.home)),
            (Path("deploy") / f"{name}.ref", svc.deploy_ref().relative_to(self.home)),
            (
                Path("deploy") / f"{name}.image",
                svc.deploy_image().relative_to(self.home),
            ),
            (
                Path("state") / "scaling" / f"{name}.json",
                svc.scaling_state().relative_to(self.home),
            ),
            (
                Path("state") / "acme" / "apps" / f"{name}.json",
                svc.acme_state().relative_to(self.home),
            ),
        ]

    def _move_scaling_markers(
        self, name: str, svc: ServicePaths, actions: list[str], *, dry_run: bool
    ) -> None:
        markers = self.home / "state" / "scaling" / "markers"
        if not markers.is_dir():
            return
        dest_dir = svc.scaling_markers()
        for path in sorted(markers.glob(f"{name}.*")):
            self._maybe_move_abs(
                path, dest_dir / path.name, actions, dry_run=dry_run
            )

    def _move_app_service_logs(
        self, name: str, svc: ServicePaths, actions: list[str], *, dry_run: bool
    ) -> None:
        root = self.home / "state" / "service-logs"
        if not root.is_dir():
            return
        for key in (name,):
            src = root / key
            if src.exists():
                self._maybe_move_abs(src, svc.logs(), actions, dry_run=dry_run)
        # compose_id may equal name for ungrouped Apps; grouped keys stay for edge pass

    def _edge_service_logs(self, actions: list[str], *, dry_run: bool) -> None:
        root = self.home / "state" / "service-logs"
        if not root.is_dir():
            return
        known = set(self._discover_service_names())
        dest_root = self.home / "host" / "logs" / "services"
        for child in sorted(root.iterdir()):
            if child.name in known:
                continue
            self._maybe_move_abs(
                child, dest_root / child.name, actions, dry_run=dry_run
            )

    def _discover_service_names(self) -> set[str]:
        names: set[str] = set()
        apps = self.home / "state" / "apps"
        if apps.is_dir():
            names.update(p.stem for p in apps.glob("*.yaml"))
        services = self.home / "services"
        if services.is_dir():
            for child in services.iterdir():
                if child.is_dir():
                    names.add(child.name)
        for top in ("secrets", "certs", "apps", "deploy"):
            base = self.home / top
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if child.is_dir() and child.name != "dashboard":
                    names.add(child.name)
        return names

    def _maybe_move(
        self, src_rel: Path, dst_rel: Path, actions: list[str], *, dry_run: bool
    ) -> None:
        self._maybe_move_abs(
            self.home / src_rel, self.home / dst_rel, actions, dry_run=dry_run
        )

    def _maybe_move_abs(
        self, src: Path, dst: Path, actions: list[str], *, dry_run: bool
    ) -> None:
        if not src.exists():
            return
        if dst.exists():
            actions.append(f"skip (exists): {src.relative_to(self.home)} → {dst.relative_to(self.home)}")
            return
        actions.append(f"move: {src.relative_to(self.home)} → {dst.relative_to(self.home)}")
        if dry_run:
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._move(src, dst)

    @staticmethod
    def _rename(src: Path, dst: Path) -> None:
        shutil.move(str(src), str(dst))

    def report(self, actions: list[str], *, dry_run: bool) -> None:
        if not actions:
            OperatorSay.say("layout migrate: nothing to move (already cut over?)")
            return
        label = "dry-run" if dry_run else "done"
        OperatorSay.say(f"layout migrate ({label}): {len(actions)} action(s)")
        for line in actions:
            OperatorSay.say(f"  {line}")
