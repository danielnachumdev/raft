"""Subprocess adapter for docker / compose / git."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class Shell:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def run(
        self,
        args: list[str],
        *,
        check: bool = True,
        capture: bool = False,
        input_text: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> subprocess.CompletedProcess[str]:
        workdir = cwd or self.cwd
        logger.debug("run cwd=%s check=%s capture=%s cmd=%s", workdir, check, capture, args)
        completed = subprocess.run(
            args,
            cwd=workdir,
            check=False,
            text=True,
            input=input_text,
            capture_output=capture,
        )
        if check and completed.returncode != 0:
            detail = ""
            if capture:
                err = (completed.stderr or completed.stdout or "").strip()
                if err:
                    detail = f"\n{err}"
            logger.error(
                "command failed rc=%s cmd=%s%s",
                completed.returncode,
                args,
                detail,
            )
            raise subprocess.CalledProcessError(
                completed.returncode,
                args,
                output=completed.stdout,
                stderr=(completed.stderr or "") + detail,
            )
        if completed.returncode != 0:
            logger.debug("command returned rc=%s cmd=%s", completed.returncode, args)
        return completed

    def compose(
        self, *args: str, check: bool = True, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        return self.run(["docker", "compose", *args], check=check, capture=capture)

    def docker(
        self, *args: str, check: bool = True, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        return self.run(["docker", *args], check=check, capture=capture)

    def git(
        self,
        *args: str,
        cwd: Optional[Path] = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return self.run(["git", *args], cwd=cwd, check=check, capture=capture)
