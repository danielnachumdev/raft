"""Fully remove raft from this machine (`raft uninstall --yes`)."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from raft.errors import OperatorError

from ...adapters.shell import Shell
from ...models import Stack
from ...ui import say
from ..auth.urls import default_ssh_dir

_RAFT_SSH_BLOCKS = re.compile(
    r"# BEGIN raft:[^\n]*\n.*?# END raft:[^\n]*\n?",
    re.DOTALL,
)


class Uninstall:
    """Tear down Compose project, data home, deploy keys, and the uv tool."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)

    def run(self, *, yes: bool = False, uv: bool = False) -> None:
        home = self.stack.root
        ssh_dir = default_ssh_dir()
        keys_dir = ssh_dir / "raft"
        config_path = ssh_dir / "config"
        keep_checkout = Path(
            os.environ.get("RAFT_HOME", str(Path.home() / "raft"))
        ).expanduser()
        if not yes:
            self._refuse_without_yes(home, keys_dir, config_path, keep_checkout, uv=uv)
        self._compose_down()
        self._remove_raft_images()
        self._scrub_ssh(keys_dir, config_path)
        self._remove_tree(home, label="data home")
        if self._looks_like_raft_checkout(keep_checkout):
            self._remove_tree(keep_checkout, label="checkout")
        self._uv_tool_uninstall()
        if uv:
            self._remove_uv()
        say("OK: raft uninstalled", style="ok")

    def _refuse_without_yes(
        self,
        home: Path,
        keys_dir: Path,
        config_path: Path,
        keep_checkout: Path,
        *,
        uv: bool,
    ) -> None:
        self._print_uninstall_plan(home, keys_dir, config_path, keep_checkout, uv=uv)
        raise OperatorError(
            "refusing to uninstall without confirmation.\n"
            "Fix: raft uninstall --yes\n"
            "     raft uninstall --yes --uv   # also remove the uv installer"
        )

    def _print_uninstall_plan(
        self, home, keys_dir, config_path, keep_checkout, *, uv: bool
    ) -> None:
        say("This permanently removes raft from this machine:", style="warn")
        say(f"  • Docker Compose project in {home} (containers, orphans, volumes)")
        say(f"  • Data home {home} (settings, applied apps, certs, generated, …)")
        say(f"  • Deploy keys {keys_dir}/ and raft Host blocks in {config_path}")
        if self._looks_like_raft_checkout(keep_checkout):
            say(f"  • Optional checkout {keep_checkout}")
        say("  • `uv tool uninstall raft` (removes the CLI from PATH)")
        if uv:
            say("  • `uv` itself (~/.local/bin/uv, uv data dirs) — requested via --uv")
        else:
            say(
                "  • leaves `uv` installed (add --uv only if nothing else needs it)",
                style="info",
            )
        say(
            "Git-host deploy keys and Cloudflare Origin certs on the CDN "
            "are not revoked — remove those manually if needed.",
            style="info",
        )

    def _remove_uv_binaries(self) -> None:
        home = Path.home()
        binaries = self._uv_binary_candidates(home)
        seen: set[Path] = set()
        for path in binaries:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in seen:
                continue
            seen.add(resolved)
            if path.is_file() or path.is_symlink():
                say(f"Removing {path}", style="info")
                path.unlink(missing_ok=True)

    @staticmethod
    def _uv_binary_candidates(home: Path) -> list[Path]:
        binaries: list[Path] = []
        which = shutil.which("uv")
        if which:
            binaries.append(Path(which))
        binaries.extend([
            home / ".local" / "bin" / "uv",
            home / ".local" / "bin" / "uvx",
            home / ".cargo" / "bin" / "uv",
        ])
        return binaries

    def _compose_down(self) -> None:
        compose = self.stack.root / "compose.yaml"
        if not compose.is_file():
            say("no compose.yaml — skipping stack tear-down", style="info")
            return
        say("Stopping Compose project…", style="info")
        try:
            self.sh.compose(
                "down",
                "--remove-orphans",
                "--volumes",
                check=False,
                capture=False,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup
            say(f"compose down skipped: {exc}", style="warn")

    def _remove_raft_images(self) -> None:
        """Remove locally built ``raft-*`` images (not shared base images)."""
        for ref in self._list_raft_image_refs():
            say(f"Removing image {ref}", style="info")
            self.sh.docker("rmi", "-f", ref, check=False, capture=True)

    def _list_raft_image_refs(self) -> list[str]:
        listed = self._docker_image_list_stdout()
        if listed is None:
            return []
        return [
            line.strip()
            for line in listed.splitlines()
            if line.strip().startswith("raft-")
            and not line.strip().endswith(":<none>")
        ]

    def _docker_image_list_stdout(self) -> Optional[str]:
        try:
            listed = self.sh.docker(
                "images",
                "--format",
                "{{.Repository}}:{{.Tag}}",
                check=False,
                capture=True,
            )
        except Exception:  # noqa: BLE001
            return None
        if listed.returncode != 0:
            return None
        return listed.stdout or ""

    def _scrub_ssh(self, keys_dir: Path, config_path: Path) -> None:
        if keys_dir.is_dir():
            say(f"Removing {keys_dir}", style="info")
            shutil.rmtree(keys_dir, ignore_errors=True)
        if not config_path.is_file():
            return
        text = config_path.read_text(encoding="utf-8")
        cleaned = _RAFT_SSH_BLOCKS.sub("", text)
        if cleaned != text:
            say(f"Scrubbing raft Host blocks from {config_path}", style="info")
            config_path.write_text(cleaned, encoding="utf-8")
            os.chmod(config_path, 0o600)

    @staticmethod
    def _remove_tree(path: Path, *, label: str) -> None:
        if not path.exists():
            say(f"no {label} at {path}", style="info")
            return
        say(f"Removing {label} {path}", style="info")
        shutil.rmtree(path, ignore_errors=True)

    @staticmethod
    def _looks_like_raft_checkout(path: Path) -> bool:
        pyproject = path / "pyproject.toml"
        if not pyproject.is_file():
            return False
        try:
            return 'name = "raft"' in pyproject.read_text(encoding="utf-8")
        except OSError:
            return False

    def _uv_tool_uninstall(self) -> None:
        say("Uninstalling uv tool `raft`…", style="info")
        try:
            self.sh.run(
                ["uv", "tool", "uninstall", "raft"],
                check=False,
                capture=True,
            )
        except Exception as exc:  # noqa: BLE001
            say(
                f"uv tool uninstall skipped ({exc}). "
                "If `raft` remains on PATH: uv tool uninstall raft",
                style="warn",
            )

    def _remove_uv(self) -> None:
        """Best-effort removal of the uv binary and its data dirs (opt-in)."""
        say("Removing uv (requested via --uv)…", style="info")
        self._remove_uv_binaries()
        self._remove_uv_data_dirs()

    @staticmethod
    def _remove_uv_data_dirs() -> None:
        home = Path.home()
        data_dirs = [
            Path(os.environ["UV_TOOL_DIR"]) if os.environ.get("UV_TOOL_DIR") else None,
            home / ".local" / "share" / "uv",
            home / ".config" / "uv",
            home / ".cache" / "uv",
        ]
        for path in data_dirs:
            if path is not None and path.is_dir():
                say(f"Removing {path}", style="info")
                shutil.rmtree(path, ignore_errors=True)
