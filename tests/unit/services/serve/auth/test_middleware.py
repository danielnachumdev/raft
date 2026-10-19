"""Dashboard auth middleware returns 401 when unauthenticated."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.services.serve.auth.middleware import DashboardAuthMiddleware
from raft.services.serve.auth.password_session import PasswordSessionAuth
from tests.unit.base import RaftTestCase


class TestDashboardAuthMiddleware(RaftTestCase):
    def test_password_mode_401(self) -> None:
        hashed = DashboardPassword().hash("correct-horse")
        sessions = PasswordSessionAuth(self.tmp_path, password_hash=hashed)
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(mode="password", password_hash=hashed)
        )
        app = FastAPI()
        app.add_middleware(DashboardAuthMiddleware, config=cfg, sessions=sessions)

        @app.get("/api/status")
        def status():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/api/status").status_code == 401

    def test_password_mode_allows_spa_shell_get(self) -> None:
        hashed = DashboardPassword().hash("correct-horse")
        sessions = PasswordSessionAuth(self.tmp_path, password_hash=hashed)
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(mode="password", password_hash=hashed)
        )
        app = FastAPI()
        app.add_middleware(DashboardAuthMiddleware, config=cfg, sessions=sessions)

        @app.get("/")
        def index():
            return {"shell": True}

        @app.get("/api/status")
        def status():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/api/status").status_code == 401

    def test_external_mode_requires_header(self) -> None:
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
                identity_header="X-Raft-Identity",
            )
        )
        app = FastAPI()
        app.add_middleware(DashboardAuthMiddleware, config=cfg)

        @app.get("/api/status")
        def status():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/api/status").status_code == 401
        ok = client.get("/api/status", headers={"X-Raft-Identity": "ops"})
        assert ok.status_code == 200
