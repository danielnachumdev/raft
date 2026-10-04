"""Windows hosts-file helpers (WSL path mapping + elevated write)."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from hosts_plan import IPCONFIG, POWERSHELL

def wsl_to_windows_path(path: Path) -> str:
    resolved = path.resolve()
    parts = resolved.parts
    if len(parts) >= 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"
    raise ValueError(f"not a /mnt/<drive> path: {path}")


def windows_temp_dir() -> Path:
    profile = os.environ.get("USERPROFILE")
    candidates = [
        Path("/mnt/c/Users/User/AppData/Local/Temp"),
        Path(f"/mnt/c/Users/{os.environ.get('USER', 'User')}/AppData/Local/Temp"),
        Path("/mnt/c/Windows/Temp"),
    ]
    if profile and profile.startswith("C:"):
        win = profile.replace("\\", "/")
        if win[1:3] == ":/":
            candidates.insert(0, Path("/mnt/" + win[0].lower() + win[2:]) / "AppData/Local/Temp")
    for path in candidates:
        if path.is_dir() and os.access(path, os.W_OK):
            return path
    try:
        out = (
            subprocess.check_output(
                ["/mnt/c/Windows/System32/cmd.exe", "/c", "echo %LOCALAPPDATA%"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
            .splitlines()[-1]
            .strip()
            .replace("\r", "")
        )
        if out.upper().startswith("C:"):
            local = Path("/mnt/c") / out[3:].replace("\\", "/")
            tmp = local / "Temp"
            if tmp.is_dir():
                return tmp
    except (OSError, subprocess.CalledProcessError, IndexError):
        pass
    raise RuntimeError("could not find a writable Windows Temp directory")



def write_windows_elevated(path: Path, data: bytes) -> None:
    if not POWERSHELL.is_file():
        raise RuntimeError(
            f"cannot write {path}: not writable, and powershell.exe not found. "
            "Re-run from an elevated Windows Terminal (Run as administrator)."
        )
    tmp_dir = windows_temp_dir()
    tmp = tmp_dir / f"raft-hosts-{uuid.uuid4().hex}.txt"
    ps1 = tmp_dir / f"raft-hosts-{uuid.uuid4().hex}.ps1"
    try:
        tmp.write_bytes(data)
        src_win = wsl_to_windows_path(tmp)
        dst_win = wsl_to_windows_path(path)
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
        ps1_win = wsl_to_windows_path(ps1)
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


def flush_dns() -> None:
    if not IPCONFIG.is_file():
        return
    subprocess.run(
        [str(IPCONFIG), "/flushdns"],
        check=False,
        capture_output=True,
        text=True,
    )
    print("flushed Windows DNS cache", flush=True)


