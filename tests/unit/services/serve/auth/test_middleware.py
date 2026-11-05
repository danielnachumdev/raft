"""Dashboard auth middleware returns 401 when unauthenticated."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.db.dashboard_sessions import DashboardSessionStore
from raft.services.serve.auth.middleware import DashboardAuthMiddleware
from tests.unit.base import RaftTestCase


class TestDashboardAuthMiddleware(RaftTestCase):
    def test_password_mode_401(self) -> None:
        store = DashboardSessionStore(self.tmp_path)
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        app = FastAPI()
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, home=self.tmp_path, store=store
        )

        @app.get("/api/status")
        def status():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/api/status").status_code == 401

    def test_password_mode_redirects_spa_to_login(self) -> None:
        client = self._password_client_with_shell()
        redir = client.get("/")
        assert redir.status_code == 302
        assert redir.headers["location"] == "/login"
        assert client.get("/api/status").status_code == 401

    def _password_client_with_shell(self) -> TestClient:
        store = DashboardSessionStore(self.tmp_path)
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        app = FastAPI()
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, home=self.tmp_path, store=store
        )

        @app.get("/")
        def index():
            return {"shell": True}

        @app.get("/api/status")
        def status():
            return {"ok": True}

        return TestClient(app, follow_redirects=False)

    def test_external_mode_requires_header(self) -> None:
        self._assert_identity_mode(
            DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
                identity_header="X-Raft-Identity",
            )
        )

    def test_oauth_mode_requires_identity_header(self) -> None:
        self._assert_identity_mode(
            DashboardAuthConfig(mode="oauth", identity_header="X-Raft-Identity")
        )

    def _assert_identity_mode(self, auth: DashboardAuthConfig) -> None:
        store = DashboardSessionStore(self.tmp_path)
        app = FastAPI()
        app.add_middleware(
            DashboardAuthMiddleware,
            config=DashboardConfig(auth=auth),
            home=self.tmp_path,
            store=store,
        )

        @app.get("/api/status")
        def status():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/api/status").status_code == 401
        ok = client.get("/api/status", headers={"X-Raft-Identity": "ops@example.com"})
        assert ok.status_code == 200
        assert client.cookies.get("raft_dash_session")
