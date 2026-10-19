"""ServeSettingsApi GET/PUT wiring."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.models.stack import Stack
from raft.services.serve.settings import ServeSettingsApi

from tests.unit.base import RaftTestCase


class TestServeSettingsApi(RaftTestCase):
    def test_get_and_put(self) -> None:
        client = self._client()
        got = client.get("/api/settings")
        assert got.status_code == 200
        doc = got.json()["document"]
        assert doc["edge"]["http"] == 80
        doc["healing"]["enabled"] = True
        doc["healing"]["intervalSeconds"] = 30
        put = client.put("/api/settings", json={"document": doc})
        assert put.status_code == 200
        assert put.json()["document"]["healing"]["enabled"] is True
        assert put.json()["document"]["healing"]["intervalSeconds"] == 30

    def test_put_validation_error(self) -> None:
        client = self._client()
        doc = client.get("/api/settings").json()["document"]
        doc["alerts"]["intervalSeconds"] = 1
        bad = client.put("/api/settings", json={"document": doc})
        assert bad.status_code == 400
        assert "intervalSeconds" in bad.json()["detail"]

    def _client(self) -> TestClient:
        stack = Stack(root=self.tmp_path, apps=())
        app = FastAPI()
        ServeSettingsApi(stack).register(app)
        return TestClient(app)
