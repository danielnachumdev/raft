"""HTTP-01 challenge token files under ``state/acme/http-01/``."""

from __future__ import annotations

from pathlib import Path

from .paths import AcmePaths


class AcmeHttp01Webroot:
    """Write and delete flat challenge tokens for the gate alias mount."""

    def __init__(self, data_home: Path) -> None:
        self._root = AcmePaths(data_home).http01_webroot

    def path_for(self, token: str) -> Path:
        # Tokens are URL path segments; reject traversal.
        name = Path(token).name
        if not name or name != token:
            raise ValueError(f"invalid HTTP-01 token {token!r}")
        return self._root / name

    def write(self, token: str, content: str) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(token)
        path.write_text(content, encoding="utf-8")
        return path

    def delete(self, token: str) -> None:
        path = self.path_for(token)
        if path.is_file():
            path.unlink()
