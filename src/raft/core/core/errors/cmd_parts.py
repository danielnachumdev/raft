"""Command-line helpers for subprocess classification."""

import subprocess
from typing import List, Optional


class CmdParts:
    """Extract readable command parts from ``CalledProcessError``."""

    @staticmethod
    def parts(exc: subprocess.CalledProcessError) -> List[str]:
        return [str(p) for p in (exc.cmd or [])]

    @classmethod
    def text(cls, exc: subprocess.CalledProcessError) -> str:
        return " ".join(cls.parts(exc))

    @classmethod
    def blob(cls, exc: subprocess.CalledProcessError, detail: str) -> str:
        return f"{cls.text(exc)}\n{detail}"

    @classmethod
    def pull_image(cls, exc: subprocess.CalledProcessError) -> Optional[str]:
        parts = cls.parts(exc)
        if parts and "docker" in parts and "pull" in parts:
            return parts[-1]
        return None
