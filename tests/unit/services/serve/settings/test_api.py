"""ServeSettingsApi GET/PUT wiring (JSON + YAML)."""

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
        body = got.json()
        doc = body["document"]
        assert doc["edge"]["http"] == 80
        assert "dashboard" in doc
        assert any(s["key"] == "healing" for s in body["sections"])
        doc["healing"]["enabled"] = True
        doc["healing"]["intervalSeconds"] = 30
        put = client.put("/api/settings", json={"document": doc})
        assert put.status_code == 200
        assert put.json()["document"]["healing"]["enabled"] is True

    def test_put_validation_error(self) -> None:
        client = self._client()
        doc = client.get("/api/settings").json()["document"]
        doc["alerts"]["intervalSeconds"] = 1
        bad = client.put("/api/settings", json={"document": doc})
        assert bad.status_code == 400
        assert "intervalSeconds" in bad.json()["detail"]

    def test_yaml_get_put_and_encode_decode(self) -> None:
        client = self._client()
        got = client.get("/api/settings/yaml")
        assert got.status_code == 200
        yaml_text = got.json()["yaml"]
        assert "logging:" in yaml_text
        put = client.put("/api/settings/yaml", json={"yaml": yaml_text})
        assert put.status_code == 200
        doc = client.get("/api/settings").json()["document"]
        enc = client.post("/api/settings/yaml/encode", json={"document": doc})
        assert enc.status_code == 200
        assert "yaml" in enc.json()
        dec = client.post(
            "/api/settings/yaml/decode", json={"yaml": enc.json()["yaml"]}
        )
        assert dec.status_code == 200
        assert dec.json()["document"]["edge"]["http"] == 80

    def test_yaml_put_rejects_invalid(self) -> None:
        client = self._client()
        bad = client.put("/api/settings/yaml", json={"yaml": "logging: ["})
        assert bad.status_code == 400

    def _client(self) -> TestClient:
        stack = Stack(root=self.tmp_path, apps=())
        app = FastAPI()
        ServeSettingsApi(stack).register(app)
        return TestClient(app)
