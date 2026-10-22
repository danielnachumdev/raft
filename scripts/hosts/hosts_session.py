"""Apply / restore HostsPlan against Linux and Windows hosts files."""

from __future__ import annotations

import atexit
import os
import signal
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType, TracebackType
from typing import Optional, Sequence, Type

from hosts_plan import (
    DEFAULT_LINUX_HOSTS,
    DEFAULT_WINDOWS_HOSTS,
    MARKER_BEGIN,
    MARKER_END,
    _LEGACY_MARKER_PAIRS,
    HostsPlan,
)
from hosts_windows import flush_dns, write_windows_elevated

HANDLED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)

@dataclass
class HostsTarget:
    path: Path
    label: str
    original: Optional[bytes] = None
    backup_path: Optional[Path] = None
    elevated: bool = False
    touched: bool = False


@dataclass
class Hosts:
    """Apply a HostsPlan to Linux/Windows hosts files; always restore on exit."""

    plan: HostsPlan = field(default_factory=HostsPlan.from_applied_apps)
    linux_hosts: Path = DEFAULT_LINUX_HOSTS
    windows_hosts: Optional[Path] = DEFAULT_WINDOWS_HOSTS
    include_windows: bool = True
    include_linux: bool = True
    backup_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()))
    flush_windows_dns: bool = True

    _targets: list[HostsTarget] = field(default_factory=list, init=False, repr=False)
    _active: bool = field(default=False, init=False, repr=False)
    _restored: bool = field(default=False, init=False, repr=False)
    _previous_handlers: dict[int, object] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.linux_hosts = Path(self.linux_hosts)
        if self.windows_hosts is not None:
            self.windows_hosts = Path(self.windows_hosts)
        self.backup_dir = Path(self.backup_dir)
        if not isinstance(self.plan, HostsPlan):
            raise TypeError(f"plan must be a HostsPlan (got {type(self.plan).__name__})")

    def __enter__(self) -> "Hosts":
        self.apply()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.restore()

    @property
    def targets(self) -> Sequence[HostsTarget]:
        return tuple(self._targets)

    def apply(self) -> None:
        if self._active:
            return
        self._targets = self._resolve_targets()
        if not self._targets:
            raise RuntimeError("no hosts targets selected/available")

        for target in self._targets:
            if not target.path.is_file():
                raise FileNotFoundError(f"hosts file not found: {target.path}")
            target.original = target.path.read_bytes()
            target.backup_path = self.backup_dir / f"raft-hosts-{target.label}.backup"
            target.backup_path.write_bytes(target.original)
            target.elevated = self._needs_elevation(target)

        self._restored = False
        self._install_protection()

        applied: list[HostsTarget] = []
        try:
            for target in self._targets:
                patched = self._build_patched(target.original or b"")
                self._write_hosts(target, patched)
                target.touched = True
                applied.append(target)
                print(
                    f"patched {target.path}"
                    + (" (via Windows UAC elevation)" if target.elevated else ""),
                    flush=True,
                )
            if self.flush_windows_dns and any(t.label == "windows" for t in applied):
                flush_dns()
        except Exception:
            for target in reversed(applied):
                try:
                    if target.original is not None:
                        self._write_hosts(target, target.original)
                except Exception as restore_err:
                    print(
                        f"WARNING: failed to roll back {target.path}: {restore_err}",
                        file=sys.stderr,
                        flush=True,
                    )
            self._uninstall_protection()
            raise

        self._active = True

    def restore(self) -> None:
        if self._restored:
            return
        errors: list[str] = []
        try:
            for target in reversed(self._targets):
                payload = target.original
                if payload is None and target.backup_path and target.backup_path.is_file():
                    payload = target.backup_path.read_bytes()
                if payload is None:
                    continue
                try:
                    self._write_hosts(target, payload)
                    print(f"restored {target.path}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{target.path}: {exc}")
            if self.flush_windows_dns and any(t.label == "windows" for t in self._targets):
                try:
                    flush_dns()
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"flushdns: {exc}")
        finally:
            self._restored = True
            self._active = False
            self._uninstall_protection()
            for target in self._targets:
                if target.backup_path:
                    try:
                        target.backup_path.unlink(missing_ok=True)
                    except OSError:
                        pass
        if errors:
            raise RuntimeError("restore incomplete:\n  " + "\n  ".join(errors))

    def _resolve_targets(self) -> list[HostsTarget]:
        targets: list[HostsTarget] = []
        if self.include_linux:
            targets.append(HostsTarget(path=self.linux_hosts, label="linux"))
        if self.include_windows and self.windows_hosts is not None:
            if self.windows_hosts.is_file():
                targets.append(HostsTarget(path=self.windows_hosts, label="windows"))
            else:
                print(
                    f"note: Windows hosts not found at {self.windows_hosts}; skipping",
                    flush=True,
                )
        return targets

    @staticmethod
    def _needs_elevation(target: HostsTarget) -> bool:
        if target.label == "windows":
            return True
        return not os.access(target.path, os.W_OK)

    def _write_hosts(self, target: HostsTarget, data: bytes) -> None:
        if target.label == "windows":
            write_windows_elevated(target.path, data)
            return
        if not os.access(target.path, os.W_OK):
            raise PermissionError(
                f"cannot write {target.path}; re-run with sudo "
                f"(e.g. sudo python3 {Path(__file__).name} ...)"
            )
        self._atomic_write(target.path, data)

    def _build_patched(self, original: bytes) -> bytes:
        newline = "\r\n" if b"\r\n" in original else "\n"
        text = original.decode("utf-8", errors="surrogateescape")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _strip_managed_blocks(text)
        if not text.endswith("\n"):
            text += "\n"
        patched = text + "\n".join(self.plan.managed_block_lines())
        if newline != "\n":
            patched = patched.replace("\n", newline)
        return patched.encode("utf-8", errors="surrogateescape")

    def _atomic_write(self, path: Path, data: bytes) -> None:
        directory = path.parent
        fd, tmp_name = tempfile.mkstemp(prefix=".hosts-", dir=directory)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(tmp_path, 0o644)
            except OSError:
                pass
            os.replace(tmp_path, path)
            try:
                dir_fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        subprocess.run(
            [str(IPCONFIG), "/flushdns"],
            check=False,
            capture_output=True,
            text=True,
        )
        print("flushed Windows DNS cache", flush=True)

    def _install_protection(self) -> None:
        atexit.register(self.restore)
        for sig in HANDLED_SIGNALS:
            self._previous_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._on_signal)

    def _uninstall_protection(self) -> None:
        try:
            atexit.unregister(self.restore)
        except Exception:
            pass
        for sig, previous in self._previous_handlers.items():
            try:
                signal.signal(sig, previous)  # type: ignore[arg-type]
            except Exception:
                pass
        self._previous_handlers.clear()

    def _on_signal(self, signum: int, frame: Optional[FrameType]) -> None:
        try:
            self.restore()
        finally:
            if signum == signal.SIGINT:
                raise KeyboardInterrupt
            raise SystemExit(128 + signum)


def _strip_one_block(text: str, begin: str, end: str) -> str:
    start = text.find(begin)
    if start == -1:
        return text
    stop = text.find(end, start)
    if stop == -1:
        return text
    stop = text.find("\n", stop)
    if stop == -1:
        return text[:start].rstrip("\n") + "\n"
    return text[:start].rstrip("\n") + "\n" + text[stop + 1 :].lstrip("\n")


def _strip_managed_blocks(text: str) -> str:
    for begin, end in ((MARKER_BEGIN, MARKER_END), *_LEGACY_MARKER_PAIRS):
        text = _strip_one_block(text, begin, end)
    return text


