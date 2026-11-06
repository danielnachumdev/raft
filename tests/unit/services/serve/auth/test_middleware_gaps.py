"""Middleware / session edge branches."""

import asyncio
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.db.dashboard_sessions import DashboardSessionStore
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.services.serve.auth.middleware import DashboardAuthMiddleware
from raft.services.serve.auth.wire import ServeAuthWire
from tests.unit.base import RaftTestCase, StackMakers


class TestMiddlewareGaps(RaftTestCase):
    def test_assets_require_auth(self) -> None:
        app = self._app_with(
            DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        )
        client = TestClient(app, follow_redirects=False)
        assert client.get("/assets/x.js").status_code == 302
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
            home=Path(self.tmp_path),
            store=DashboardSessionStore(self.tmp_path),
        )
        asyncio.run(mw({"type": "lifespan"}, None, None))  # type: ignore[arg-type]
        assert called["ok"] is True

    def test_wire_loads_settings(self) -> None:
        home = Path(self.tmp_path)
        hashed = DashboardPassword().hash("correct-horse")
        (home / "host" / "settings.yaml").write_text(
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
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        ext = DashboardConfig(
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/v",
                sign_in_url="https://auth.demo.example/s",
            )
        )
        app = self._plain_app()
        ServeAuthWire(StackMakers.make_stack(home), config=ext).apply(app)
        session = TestClient(app).get("/api/dashboard/session")
        assert session.status_code == 200
        assert session.json()["mode"] == "external"

    def test_wire_oauth_session_logout_hint(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="oauth"))
        app = self._plain_app()
        ServeAuthWire(StackMakers.make_stack(home), config=cfg).apply(app)
        body = TestClient(app).get("/api/dashboard/session").json()
        assert body["mode"] == "oauth"
        assert body["logout"]["kind"] == "post"
        assert body["logout"]["next"].startswith("/oauth2/sign_out")

    def test_session_password_and_none_logout_hints(self) -> None:
        assert self._hint("password")["kind"] == "post"
        assert self._hint("none")["kind"] == "none"
        ext = self._hint("external")
        assert ext["path"] == "/api/dashboard/logout"
        assert ext["next"] == "/"

    def _hint(self, mode: str) -> dict:
        from raft.core.core.db.dashboard_sessions import DashboardSessionStore
        from raft.services.serve.auth.session_routes import DashboardSessionRoutes

        auth = DashboardAuthConfig(mode=mode, sign_in_url=None)
        return DashboardSessionRoutes(
            DashboardConfig(auth=auth),
            home=Path(self.tmp_path),
            store=DashboardSessionStore(self.tmp_path),
        )._logout_hint(mode)

    def _app_with(self, cfg: DashboardConfig) -> FastAPI:
        app = self._plain_app()
        app.add_middleware(
            DashboardAuthMiddleware,
            config=cfg,
            home=Path(self.tmp_path),
            store=DashboardSessionStore(self.tmp_path),
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
