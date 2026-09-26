"""Stdlib HTTP client for tests (e2e, integration, unit probes)."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Optional
from urllib.request import Request

_BODY_SNIPPET = 200


@dataclass(frozen=True)
class HttpResponse:
    """Response after an optional expected-status assert."""

    status: int
    body: str
    headers: Mapping[str, str]
    method: str
    url: str


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
        expect_status: Optional[int] = 200,
    ) -> HttpResponse:
        return self.request(
            "GET",
            path,
            host=host,
            timeout=timeout,
            headers=headers,
            expect_status=expect_status,
        )

    def post(
        self,
        path: str = "/",
        *,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        data: Optional[bytes] = None,
        expect_status: Optional[int] = 200,
    ) -> HttpResponse:
        return self.request(
            "POST",
            path,
            host=host,
            timeout=timeout,
            headers=headers,
            data=data,
            expect_status=expect_status,
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
        expect_status: Optional[int] = 200,
    ) -> HttpResponse:
        url = self._url(path)
        verb = method.upper()
        req = Request(url, data=data, method=verb)
        for key, value in self._merge_headers(host, headers).items():
            req.add_header(key, value)
        resp = self._open(req, timeout if timeout is not None else self.timeout, verb, url)
        self._assert_status(resp, expect_status)
        return resp

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
    def _assert_status(resp: HttpResponse, expect_status: Optional[int]) -> None:
        if expect_status is None or resp.status == expect_status:
            return
        snippet = resp.body[:_BODY_SNIPPET].replace("\n", " ")
        raise AssertionError(
            f"{resp.method} {resp.url}: expected status {expect_status}, "
            f"got {resp.status}; body={snippet!r}"
        )

    @staticmethod
    def _open(req: Request, timeout: float, method: str, url: str) -> HttpResponse:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return HttpClient._response(method, url, int(resp.status), resp.read(), resp.headers)
        except urllib.error.HTTPError as exc:
            return HttpClient._response(method, url, int(exc.code), exc.read(), exc.headers)

    @staticmethod
    def _response(
        method: str,
        url: str,
        status: int,
        raw: bytes,
        headers: Mapping[str, str],
    ) -> HttpResponse:
        return HttpResponse(
            status=status,
            body=raw.decode("utf-8", errors="replace"),
            headers=dict(headers or {}),
            method=method,
            url=url,
        )


def tcp_connect(host: str, port: int, *, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
