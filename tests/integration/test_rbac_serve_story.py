"""Integration story: host rbac.yaml gates the wired serve API (#415)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.http.app import ServeAppFactory
from raft.services.serve.http.paths import ServePaths
from tests.shared.raft_home import RaftHomeFixtures
from tests.unit.core.observe.ops.status import fixtures as status_fx

pytestmark = pytest.mark.integration

_ADMIN_DOC = {
    "version": 1,
    "roles": [{"id": "admin", "permissions": ["*:read", "*:write"]}],
    "bindings": [{"subject": "ops@example.com", "role": "admin"}],
}
_IDENTITY = {"X-Raft-Identity": "ops@example.com"}
_STRANGER = {"X-Raft-Identity": "other@example.com"}


class TestRbacServeGateStory:
    """Operator enables RBAC; unbound callers are denied; admin wildcards pass.

    Scenario:
      1) Dashboard auth is external; rbac.yaml is absent → bootstrap allow.
      2) PUT /api/rbac saves host/rbac.yaml and returns temporary_override.
      3) Unbound identity is 403 on firewall reads; admin *:read is allowed.
    """

    def test_bootstrap_save_then_gate(
        self, isolated_raft_env: Path
    ) -> None:
        client = self._client(isolated_raft_env)
        assert client.get("/api/status", headers=_IDENTITY).status_code == 200
        saved = client.put("/api/rbac", json=_ADMIN_DOC, headers=_IDENTITY)
        assert saved.status_code == 200
        body = saved.json()
        assert body["document"]["bindings"][0]["subject"] == "ops@example.com"
        assert "temporary_override" in body["gitops"]
        assert "host/rbac.yaml" in body["gitops"]["temporary_override"]
        assert client.get("/api/firewall", headers=_STRANGER).status_code == 403
        assert client.get("/api/firewall", headers=_IDENTITY).status_code == 200

    def _client(self, home: Path) -> TestClient:
        RaftHomeFixtures.prepare(home, settings=self._external_settings())
        ServePaths.spa_assets_dir().mkdir(parents=True, exist_ok=True)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        return TestClient(
            ServeAppFactory(load_stack(home), status=status).create()
        )

    @staticmethod
    def _external_settings() -> dict:
        return {
            "edge": {"http": 80, "https": None},
            "dashboard": {
                "auth": {
                    "mode": "external",
                    "verifyUrl": "http://127.0.0.1:9/verify",
                    "signInUrl": "http://127.0.0.1:9/sign-in",
                }
            },
        }
