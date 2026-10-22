"""OperatorSettingsService: full-document GET/PUT + secret merge + edge notes."""

from __future__ import annotations

import yaml
import pytest

from raft.core.core.config.settings import OperatorSettingsService, SettingsLoader
from raft.core.core.errors.cta import OperatorError

from tests.unit.base import RaftTestCase


class TestOperatorSettingsService(RaftTestCase):
    def test_get_defaults_when_missing(self) -> None:
        payload = OperatorSettingsService(self.tmp_path).get_public()
        doc = payload["document"]
        assert doc["edge"]["http"] == 80
        assert doc["edge"]["https"] == 443
        assert doc["healing"]["enabled"] is False
        assert doc["notifications"]["channels"] == []
        assert doc["dashboard"]["enabled"] is False
        assert any(s["key"] == "dashboard" for s in payload["sections"])
        assert payload["path"].endswith("settings.yaml")

    def test_replace_round_trip_and_redact_github_secret(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = self._with_github_secret(svc.get_public()["document"], "super-secret")
        out = svc.replace({"document": doc})
        assert out["document"]["github"]["clientSecret"] == "***"
        assert out["document"]["acme"]["email"] == "ops@example.com"
        disk = yaml.safe_load(
            (self.tmp_path / "host" / "settings.yaml").read_text(encoding="utf-8")
        )
        assert disk["github"]["clientSecret"] == "super-secret"

    def test_replace_preserves_masked_secret(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = self._with_github_secret(svc.get_public()["document"], "keep-me")
        svc.replace({"document": doc})
        again = svc.get_public()["document"]
        again["github"]["clientSecret"] = "***"
        again["github"]["sessionTtlSeconds"] = 7200
        svc.replace({"document": again})
        loaded = SettingsLoader().load(self.tmp_path).github
        assert loaded.client_secret == "keep-me"
        assert loaded.session_ttl_seconds == 7200

    def test_edge_port_change_emits_gate_redeploy_note(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["edge"]["http"] = 8080
        out = svc.replace({"document": doc})
        warn = next(n for n in out["notes"] if n["code"] == "edge.ports")
        assert warn["severity"] == "warn"
        assert "redeploy gate" in warn["message"]

    def test_invalid_section_raises(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["logging"]["level"] = "NOPE"
        with pytest.raises(OperatorError):
            svc.replace({"document": doc})

    def test_notifications_channel_secret_merge(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["notifications"] = self._webhook_channel("live-token")
        svc.replace({"document": doc})
        again = svc.get_public()["document"]
        again["notifications"]["channels"][0]["settings"]["token"] = "***"
        again["notifications"]["channels"][0]["settings"]["url"] = (
            "https://hooks.example.invalid/raft-v2"
        )
        svc.replace({"document": again})
        ch = SettingsLoader().load(self.tmp_path).notifications.channels[0]
        assert ch.settings["token"] == "live-token"
        assert "raft-v2" in ch.settings["url"]

    @staticmethod
    def _with_github_secret(doc: dict, secret: str) -> dict:
        doc["github"] = {
            "clientId": "Iv1.demo",
            "clientSecret": secret,
            "sessionTtlSeconds": 3600,
        }
        doc["acme"]["email"] = "ops@example.com"
        return doc

    @staticmethod
    def _webhook_channel(token: str) -> dict:
        return {
            "enabled": True,
            "channels": [
                {
                    "id": "ops-primary",
                    "type": "webhook",
                    "enabled": True,
                    "settings": {
                        "url": "https://hooks.example.invalid/raft",
                        "token": token,
                    },
                }
            ],
        }
