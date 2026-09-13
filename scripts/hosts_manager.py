#!/usr/bin/env python3
"""Temporarily manage Linux and Windows hosts files with guaranteed restore."""

from __future__ import annotations

import argparse
import atexit
import os
import re
import signal
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType, TracebackType
from typing import Optional, Sequence, Type

DEFAULT_LINUX_HOSTS = Path("/etc/hosts")
DEFAULT_WINDOWS_HOSTS = Path("/mnt/c/Windows/System32/drivers/etc/hosts")
POWERSHELL = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
IPCONFIG = Path("/mnt/c/Windows/System32/ipconfig.exe")

MARKER_BEGIN = "# >>> raft hosts-manager BEGIN"
MARKER_END = "# <<< raft hosts-manager END"
HANDLED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
_PUBLIC_HOST_RE = re.compile(
    r'^(?:publicHost|public_host)\s*:\s*["\']?([^"\'#\s]+)["\']?\s*(?:#.*)?$'
)

def _data_home() -> Path:
    override = os.environ.get("RAFT_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".raft").resolve()

def _public_hosts_from_registry(registry_dir: Path) -> tuple[str, ...]:
    names: list[str] = []
    for path in sorted(registry_dir.glob("*.yaml")):
        host = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _PUBLIC_HOST_RE.match(line.strip())
            if match:
                host = match.group(1).strip()
                break
        if not host:
            continue
        names.append(host)
        if not host.startswith("www."):
            names.append(f"www.{host}")
    return tuple(names)

@dataclass(frozen=True)
class HostBinding:
    ip: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        ip = self.ip.strip()
        cleaned = tuple(n.strip() for n in self.names if n and n.strip())
        if not ip:
            raise ValueError("HostBinding.ip must be non-empty")
        if not cleaned:
            raise ValueError(f"HostBinding for {ip!r} needs at least one hostname")
        object.__setattr__(self, "ip", ip)
        object.__setattr__(self, "names", cleaned)

    def hosts_line(self) -> str:
        return f"{self.ip}\t{' '.join(self.names)}"

@dataclass(frozen=True)
class HostsPatchPlan:
    bindings: tuple[HostBinding, ...]

    def __post_init__(self) -> None:
        if not self.bindings:
            raise ValueError("HostsPatchPlan requires at least one HostBinding")

    @classmethod
    def default(cls) -> HostsPatchPlan:
        registry = _data_home() / "state" / "apps"
        names: tuple[str, ...] = ()
        if registry.is_dir():
            try:
                names = _public_hosts_from_registry(registry)
            except OSError:
                names = ()
        if not names:
            raise ValueError(
                "no applied apps under ~/.raft/state/apps/*.yaml; "
                "apply an App first or pass --entry IP,hostname[,hostname...]"
            )
        return cls(
            bindings=(
                HostBinding(ip="127.0.0.1", names=names),
            )
        )

    @classmethod
    def from_cli_entries(cls, values: Optional[Sequence[str]]) -> HostsPatchPlan:
        if not values:
            return cls.default()

        order: list[str] = []
        merged: dict[str, list[str]] = {}
        for raw in values:
            binding = _parse_cli_entry(raw)
            if binding.ip not in merged:
                order.append(binding.ip)
                merged[binding.ip] = []
            for name in binding.names:
                if name not in merged[binding.ip]:
                    merged[binding.ip].append(name)

        return cls(
            bindings=tuple(
                HostBinding(ip=ip, names=tuple(merged[ip])) for ip in order
            )
        )

    def describe(self) -> list[str]:
        return [b.hosts_line() for b in self.bindings]

def _parse_cli_entry(raw: str) -> HostBinding:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) < 2:
        raise argparse.ArgumentTypeError(
            f"expected IP,name[,name...] got {raw!r}"
        )
    ip, *names = parts
    try:
        return HostBinding(ip=ip, names=tuple(names))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc

def _wsl_to_windows_path(path: Path) -> str:
    resolved = path.resolve()
    parts = resolved.parts
    if len(parts) >= 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"
    raise ValueError(f"not a /mnt/<drive> path: {path}")

def _windows_temp_dir() -> Path:
    profile = os.environ.get("USERPROFILE")
    candidates = [
        Path("/mnt/c/Users/User/AppData/Local/Temp"),
        Path(f"/mnt/c/Users/{os.environ.get('USER', 'User')}/AppData/Local/Temp"),
        Path("/mnt/c/Windows/Temp"),
    ]
    if profile and profile.startswith("C:"):
        win = profile.replace("\\", "/")
        if win[1:3] == ":/":
            candidates.insert(
                0, Path("/mnt/" + win[0].lower() + win[2:]) / "AppData/Local/Temp"
            )
    for path in candidates:
        if path.is_dir() and os.access(path, os.W_OK):
            return path
    try:
        out = subprocess.check_output(
            ["/mnt/c/Windows/System32/cmd.exe", "/c", "echo %LOCALAPPDATA%"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip().splitlines()[-1].strip().replace("\r", "")
        if out.upper().startswith("C:"):
            local = Path("/mnt/c") / out[3:].replace("\\", "/")
            tmp = local / "Temp"
            if tmp.is_dir():
                return tmp
    except (OSError, subprocess.CalledProcessError, IndexError):
        pass
    raise RuntimeError("could not find a writable Windows Temp directory")

@dataclass
class HostsTarget:
    path: Path
    label: str
    original: Optional[bytes] = None
    backup_path: Optional[Path] = None
    elevated: bool = False
    touched: bool = False

@dataclass
class HostsManager:
    plan: HostsPatchPlan = field(default_factory=HostsPatchPlan.default)
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
        if not isinstance(self.plan, HostsPatchPlan):
            raise TypeError(
                "plan must be a HostsPatchPlan "
                f"(got {type(self.plan).__name__})"
            )

    def __enter__(self) -> "HostsManager":
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
                self._flush_dns()
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
                    self._flush_dns()
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
            self._write_windows_elevated(target.path, data)
            return
        if not os.access(target.path, os.W_OK):
            raise PermissionError(
                f"cannot write {target.path}; re-run with sudo "
                f"(e.g. sudo python3 {Path(__file__).name} ...)"
            )
        self._atomic_write(target.path, data)

    def _write_windows_elevated(self, path: Path, data: bytes) -> None:
        if not POWERSHELL.is_file():
            raise RuntimeError(
                f"cannot write {path}: not writable, and powershell.exe not found. "
                "Re-run from an elevated Windows Terminal (Run as administrator)."
            )
        tmp_dir = _windows_temp_dir()
        tmp = tmp_dir / f"raft-hosts-{uuid.uuid4().hex}.txt"
        ps1 = tmp_dir / f"raft-hosts-{uuid.uuid4().hex}.ps1"
        try:
            tmp.write_bytes(data)
            src_win = _wsl_to_windows_path(tmp)
            dst_win = _wsl_to_windows_path(path)
            src_lit = "'" + src_win.replace("'", "''") + "'"
            dst_lit = "'" + dst_win.replace("'", "''") + "'"
            ps1.write_text(
                "\r\n".join(
                    [
                        "$ErrorActionPreference = 'Stop'",
                        f"Copy-Item -LiteralPath {src_lit} -Destination {dst_lit} -Force",
                    ]
                )
                + "\r\n",
                encoding="utf-8",
            )
            ps1_win = _wsl_to_windows_path(ps1)
            cmd = (
                "Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait "
                f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','{ps1_win}'"
            )
            completed = subprocess.run(
                [str(POWERSHELL), "-NoProfile", "-Command", cmd],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                err = (completed.stderr or completed.stdout or "").strip()
                raise PermissionError(
                    f"elevated write to {path} failed (exit {completed.returncode})"
                    + (f": {err}" if err else "")
                    + ". Approve the UAC prompt, or run Windows Terminal as Administrator."
                )
        finally:
            for victim in (tmp, ps1):
                try:
                    victim.unlink(missing_ok=True)
                except OSError:
                    pass

    def _build_patched(self, original: bytes) -> bytes:
        newline = "\r\n" if b"\r\n" in original else "\n"
        text = original.decode("utf-8", errors="surrogateescape")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = self._strip_managed_block(text)
        if not text.endswith("\n"):
            text += "\n"
        block = [
            MARKER_BEGIN,
            "# managed by raft hosts_manager; do not edit",
            *(binding.hosts_line() for binding in self.plan.bindings),
            MARKER_END,
            "",
        ]
        patched = text + "\n".join(block)
        if newline != "\n":
            patched = patched.replace("\n", newline)
        return patched.encode("utf-8", errors="surrogateescape")

    @staticmethod
    def _strip_managed_block(text: str) -> str:
        begin = text.find(MARKER_BEGIN)
        if begin == -1:
            return text
        end = text.find(MARKER_END, begin)
        if end == -1:
            return text
        end = text.find("\n", end)
        if end == -1:
            return text[:begin].rstrip("\n") + "\n"
        return text[:begin].rstrip("\n") + "\n" + text[end + 1 :].lstrip("\n")

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

    @staticmethod
    def _flush_dns() -> None:
        if not IPCONFIG.is_file():
            return
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

def _cmd_hold(manager: HostsManager) -> int:
    print("Press Ctrl+C to restore both hosts files and exit.", flush=True)
    with manager:
        for line in manager.plan.describe():
            print(f"  {line}", flush=True)
        try:
            signal.pause()
        except KeyboardInterrupt:
            print("\nInterrupted — restoring hosts.", flush=True)
    print("hosts restored.", flush=True)
    return 0

def _cmd_run(manager: HostsManager, command: list[str]) -> int:
    if not command:
        raise SystemExit("run requires a command after --")
    with manager:
        print(f"hosts patched for duration of: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        return completed.returncode

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Safely patch Linux /etc/hosts and the Windows hosts file, "
            "then always restore the prior state."
        )
    )
    parser.add_argument(
        "--linux-hosts",
        default=str(DEFAULT_LINUX_HOSTS),
        help="Linux hosts path (default: /etc/hosts)",
    )
    parser.add_argument(
        "--windows-hosts",
        default=str(DEFAULT_WINDOWS_HOSTS),
        help="Windows hosts path as seen from WSL",
    )
    parser.add_argument(
        "--linux-only",
        action="store_true",
        help="only patch Linux /etc/hosts",
    )
    parser.add_argument(
        "--windows-only",
        action="store_true",
        help="only patch the Windows hosts file",
    )
    parser.add_argument(
        "--no-flush-dns",
        action="store_true",
        help="skip ipconfig /flushdns after Windows changes",
    )
    parser.add_argument(
        "--entry",
        action="append",
        metavar="IP,name[,name...]",
        help="override HostsPatchPlan.default(); repeatable",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hold", help="apply entries until Ctrl+C / signal, then restore")
    run_parser = sub.add_parser(
        "run", help="apply entries, run a command, restore afterward"
    )
    run_parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="command to run (use -- before it)",
    )

    args = parser.parse_args(argv)
    if args.linux_only and args.windows_only:
        parser.error("use only one of --linux-only / --windows-only")

    manager = HostsManager(
        plan=HostsPatchPlan.from_cli_entries(args.entry),
        linux_hosts=args.linux_hosts,
        windows_hosts=args.windows_hosts,
        include_linux=not args.windows_only,
        include_windows=not args.linux_only,
        flush_windows_dns=not args.no_flush_dns,
    )

    if args.command == "hold":
        return _cmd_hold(manager)
    if args.command == "run":
        cmd = list(args.cmd)
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        return _cmd_run(manager, cmd)
    parser.error(f"unknown command {args.command}")
    return 2

if __name__ == "__main__":
    sys.exit(main())
