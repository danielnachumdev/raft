"""Atomic text file writes with restrictive mode."""

import os
import tempfile
from pathlib import Path


class AtomicText:
    """Write text via tempfile + os.replace."""

    @staticmethod
    def write(path: Path, text: str, *, mode: int = 0o600) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, path)
            os.chmod(path, mode)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
