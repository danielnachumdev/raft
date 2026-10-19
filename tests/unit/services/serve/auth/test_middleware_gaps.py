"""Middleware / session edge branches."""

import asyncio
import hashlib
import hmac
import time
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.services.serve.auth.middleware import DashboardAuthMiddleware
from raft.services.serve.auth.password_session import PasswordSessionAuth
from raft.services.serve.auth.wire import ServeAuthWire
from tests.unit.base import RaftTestCase, StackMakers


class TestMiddlewareGaps(RaftTestCase):
    def test_assets_require_auth(self) -> None:
        app = self._app_with(
            DashboardConfig(auth=DashboardAuthConfig(mode="password")),
            sessions=None,
        )
        client = TestClient(app, follow_redirects=False)
        assert client.get("/assets/x.js").status_code == 401
        assert client.get("/api/status").status_code == 401

    def test_none_and_unknown_mode(self) -> None:
        none_app = self._app_with(
            DashboardConfig(auth=DashboardAuthConfig(mode="none"))
        )
        assert TestClient(none_app).get("/api/status").status_code == 200
        ldap = self._app_with(
            DashboardConfig(auth=DashboardAuthConfig(mode="ldap"))
        )
        assert TestClient(ldap).get("/api/status").status_code == 200

    def test_non_http_scope_passes(self) -> None:
        called = {"ok": False}

        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            called["ok"] = True

        mw = DashboardAuthMiddleware(
            inner,
            config=DashboardConfig(auth=DashboardAuthConfig(mode="password")),
        )
        asyncio.run(mw({"type": "lifespan"}, None, None))  # type: ignore[arg-type]
        assert called["ok"] is True

    def test_session_bad_payload_and_reload_key(self) -> None:
        home = Path(self.tmp_path)
        hashed = DashboardPassword().hash("correct-horse")
        key_path = home / "state" / "serve" / "dashboard-session.key"
        key_path.parent.mkdir(parents=True)
        key_path.write_bytes(b"01234567890123456789012345678901")
        sessions = PasswordSessionAuth(home, password_hash=hashed)
        secret = key_path.read_bytes()
        self._assert_bad_cookies(sessions, secret)

    def test_wire_loads_settings(self) -> None:
        home = Path(self.tmp_path)
        hashed = DashboardPassword().hash("correct-horse")
        (home / "settings.yaml").write_text(
            yaml.safe_dump(
                {
                    "dashboard": {
                        "auth": {"mode": "password", "passwordHash": hashed}
                    }
                }
            ),
            encoding="utf-8",
        )
        app = self._plain_app()
        ServeAuthWire(StackMakers.make_stack(home)).apply(app)
        assert TestClient(app).get("/api/status").status_code == 401

    def test_wire_external_mode(self) -> None:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text("{}\n", encoding="utf-8")
        ext = DashboardConfig(
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/v",
                sign_in_url="https://auth.demo.example/s",
            )
        )
        ServeAuthWire(StackMakers.make_stack(home), config=ext).apply(
            self._plain_app()
        )

    def _app_with(self, cfg: DashboardConfig, sessions=None) -> FastAPI:
        app = self._plain_app()
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, sessions=sessions
        )
        return app

    @staticmethod
    def _plain_app() -> FastAPI:
        app = FastAPI()

        @app.get("/assets/x.js")
        def asset():
            return {"ok": True}

        @app.get("/api/status")
        def status():
            return {"ok": True}

        return app

    @staticmethod
    def _assert_bad_cookies(sessions, secret: bytes) -> None:
        payload = "1|notint|csrf"
        sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        assert not sessions.session_ok(f"{payload}.{sig}")
        payload2 = "2|9999999999|csrf"
        sig2 = hmac.new(secret, payload2.encode(), hashlib.sha256).hexdigest()
        assert not sessions.session_ok(f"{payload2}.{sig2}")
        payload3 = f"1|{int(time.time()) - 10}|csrf"
        sig3 = hmac.new(secret, payload3.encode(), hashlib.sha256).hexdigest()
        assert not sessions.session_ok(f"{payload3}.{sig3}")
