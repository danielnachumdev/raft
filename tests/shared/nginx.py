"""Nginx log / upstream fixtures shared across adapter, doctor, and cutover tests."""

from __future__ import annotations

from pathlib import Path


class NginxEmerg:
    """Canonical nginx diagnostic log lines used in mock docker logs."""

    @staticmethod
    def host_not_found(host: str = "old-backend", port: int = 8000) -> str:
        return f'nginx: [emerg] host not found in upstream "{host}:{port}"'


class UpstreamFile:
    """Write or assert upstream conf snippets under ``upstreams/``."""

    @staticmethod
    def body(name: str, target: str, port: int = 80) -> str:
        return f"upstream {name} {{ server {target}:{port}; }}\n"

    @classmethod
    def write(
        cls,
        dir_path: Path,
        filename: str,
        *,
        upstream: str,
        target: str,
        port: int = 80,
    ) -> Path:
        dir_path.mkdir(parents=True, exist_ok=True)
        path = dir_path / filename
        path.write_text(cls.body(upstream, target, port), encoding="utf-8")
        return path

    @staticmethod
    def assert_contains(path: Path, *needles: str) -> str:
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, f"missing {needle!r} in {path}: {text!r}"
        return text
