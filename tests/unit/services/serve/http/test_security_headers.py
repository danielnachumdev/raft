"""Security headers middleware on ``raft serve`` / dashboard FastAPI."""

import asyncio

from fastapi.testclient import TestClient

from raft.core.lifecycle.dashboard.browser_security import BrowserSecurityHeaders
from raft.services.serve.http.security_middleware import SecurityHeadersMiddleware
from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.services.serve import fixtures as serve_fx


class TestSecurityHeadersMiddleware(RaftTestCase):
    def test_spa_and_api_get_csp_without_hsts_on_http(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        expected = BrowserSecurityHeaders().as_dict(https=False)
        for path in ("/", "/api/status"):
            response = client.get(path)
            assert response.status_code == 200
            for name, value in expected.items():
                assert response.headers.get(name) == value
            assert "Strict-Transport-Security" not in response.headers

    def test_hsts_when_x_forwarded_proto_https(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get(
            "/api/status", headers={"X-Forwarded-Proto": "https"}
        )
        assert response.status_code == 200
        assert response.headers["Strict-Transport-Security"] == "max-age=15552000"
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_hsts_when_forwarded_proto_list_starts_with_https(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get(
            "/", headers={"X-Forwarded-Proto": "https, http"}
        )
        assert response.headers["Strict-Transport-Security"] == "max-age=15552000"

    def test_no_hsts_when_forwarded_proto_http(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get(
            "/api/status", headers={"X-Forwarded-Proto": "http"}
        )
        assert "Strict-Transport-Security" not in response.headers

    def test_https_base_url_sets_hsts(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        app = serve_fx.client_and_status(stack, serve_fx.full_snapshot())[0].app
        client = TestClient(app, base_url="https://testserver")
        response = client.get("/api/status")
        assert response.headers["Strict-Transport-Security"] == "max-age=15552000"

    def test_merge_start_skips_existing_header(self) -> None:
        message = {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-security-policy", b"default-src 'none'")],
        }
        extras = BrowserSecurityHeaders().as_dict(https=False)
        out = SecurityHeadersMiddleware._merge_start(message, extras)
        decoded = {k.decode(): v.decode() for k, v in out["headers"]}
        assert decoded["content-security-policy"] == "default-src 'none'"
        assert decoded["x-frame-options"] == "DENY"

    def test_non_http_scope_passthrough(self) -> None:
        calls: list[str] = []

        async def inner(scope, receive, send):
            calls.append(scope["type"])

        mw = SecurityHeadersMiddleware(inner)

        async def _run() -> None:
            await mw({"type": "lifespan"}, None, None)  # type: ignore[arg-type]

        asyncio.run(_run())
        assert calls == ["lifespan"]
