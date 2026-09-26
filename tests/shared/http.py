"""  """"""Stdlib HTTP client for tests (e2e, integration, unit probes)."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Mapping, Optional, Tuple
from urllib.request import Request


class HttpClient:
    """GET/POST against a base URL; optional Host header for gate routing."""

    def __init__(
        self,
        base: str = "",
        *,
        timeout: float = 5.0,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.headers = dict(headers or {})

    def get(
        self,
        path: str = "/",
        *,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Tuple[int, str]:
        return self.request("GET", path, host=host, timeout=timeout, headers=headers)

    def post(
        self,
        path: str = "/",
        *,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        data: Optional[bytes] = None,
    ) -> Tuple[int, str]:
        return self.request(
            "POST", path, host=host, timeout=timeout, headers=headers, data=data
        )

    def request(
        self,
        method: str,
        path: str = "/",
        *,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        data: Optional[bytes] = None,
    ) -> Tuple[int, str]:
        req = Request(self._url(path), data=data, method=method.upper())
        for key, value in self._merge_headers(host, headers).items():
            req.add_header(key, value)
        return self._open(req, timeout if timeout is not None else self.timeout)

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{self.base}{suffix}" if self.base else suffix

    def _merge_headers(
        self, host: Optional[str], headers: Optional[Mapping[str, str]]
    ) -> dict:
        merged = dict(self.headers)
        if headers:
            merged.update(headers)
        if host is not None:
            merged["Host"] = host
        return merged

    @staticmethod
    def _open(req: Request, timeout: float) -> Tuple[int, str]:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return int(resp.status), body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return int(exc.code), body


def tcp_connect(host: str, port: int, *, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
