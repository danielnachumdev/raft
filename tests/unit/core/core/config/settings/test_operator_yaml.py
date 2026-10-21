"""YAML encode/decode/replace through OperatorSettingsService."""

from __future__ import annotations

import pytest

from raft.core.core.config.settings import OperatorSettingsService
from raft.core.core.errors.cta import OperatorError

from tests.unit.base import RaftTestCase


class TestOperatorSettingsYaml(RaftTestCase):
    def test_get_yaml_public_includes_document_and_text(self) -> None:
        payload = OperatorSettingsService(self.tmp_path).get_yaml_public()
        assert "logging:" in payload["yaml"]
        assert payload["document"]["edge"]["http"] == 80
        assert any(s["key"] == "dashboard" for s in payload["sections"])

    def test_replace_yaml_round_trip(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        text = svc.get_yaml_public()["yaml"]
        text = text.replace("level: INFO", "level: DEBUG", 1)
        out = svc.replace_yaml({"yaml": text})
        assert out["document"]["logging"]["level"] == "DEBUG"
        assert "yaml" not in out or out.get("document")

    def test_encode_decode_without_persist(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["healing"]["enabled"] = True
        encoded = svc.encode_yaml({"document": doc})
        assert "healing:" in encoded["yaml"]
        decoded = svc.decode_yaml({"yaml": encoded["yaml"]})
        assert decoded["document"]["healing"]["enabled"] is True

    def test_invalid_yaml_raises(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        with pytest.raises(OperatorError, match="invalid settings YAML"):
            svc.replace_yaml({"yaml": "logging: [\n"})

    def test_null_yaml_document_decodes_to_defaults(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        out = svc.decode_yaml({"yaml": "# empty\n"})
        assert "edge" in out["document"]

    def test_yaml_non_mapping_raises(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        with pytest.raises(OperatorError, match="must be a mapping"):
            svc.decode_yaml({"yaml": "- just\n- a\n- list\n"})

    def test_yaml_missing_field_raises(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        with pytest.raises(OperatorError, match="non-empty string field"):
            svc.decode_yaml({"yaml": "   "})

    def test_encode_accepts_bare_document_body(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        encoded = svc.encode_yaml(doc)
        assert "logging:" in encoded["yaml"]

    def test_redact_dashboard_without_auth_mapping(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["dashboard"] = {
            "enabled": True,
            "port": 8787,
            "publicHost": None,
            "tls": "off",
            "auth": "broken",
        }
        # Persist may reject; exercise public redact path via get after raw write.
        from raft.core.core.config.settings.secrets_merge import SettingsSecretsMerge

        redacted = SettingsSecretsMerge().redact_document(
            {"dashboard": {"enabled": True, "auth": "broken"}}
        )
        assert redacted["dashboard"]["auth"] == "broken"

    def test_dashboard_round_trip_and_password_mask(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["dashboard"] = self._dashboard("pbkdf2$demo")
        out = svc.replace({"document": doc})
        assert out["document"]["dashboard"]["enabled"] is True
        assert out["document"]["dashboard"]["auth"]["passwordHash"] == "***"
        again = out["document"]
        again["dashboard"]["auth"]["passwordHash"] = "***"
        again["dashboard"]["port"] = 8790
        svc.replace({"document": again})
        loaded = svc.get_public()["document"]["dashboard"]
        assert loaded["port"] == 8790
        assert loaded["auth"]["passwordHash"] == "***"

    def test_dashboard_plaintext_password_hashed_on_save(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["dashboard"] = self._dashboard("correct-horse")
        out = svc.replace({"document": doc})
        assert out["document"]["dashboard"]["auth"]["passwordHash"] == "***"
        notes = [n["code"] for n in out.get("notes") or []]
        assert "dashboard.enabled" in notes
        raw = (self.tmp_path / "host" / "settings.yaml").read_text(encoding="utf-8")
        assert "pbkdf2_sha256$" in raw
        assert "correct-horse" not in raw

    def test_dashboard_short_password_rejected(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["dashboard"] = self._dashboard("short")
        with pytest.raises(OperatorError, match="8 characters"):
            svc.replace({"document": doc})

    def test_dashboard_disable_note(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["dashboard"] = self._dashboard("pbkdf2$demo")
        svc.replace({"document": doc})
        doc = svc.get_public()["document"]
        doc["dashboard"]["enabled"] = False
        out = svc.replace({"document": doc})
        messages = [n["message"] for n in out.get("notes") or []]
        assert any("enabled is now false" in m for m in messages)

    @staticmethod
    def _dashboard(password_hash: str) -> dict:
        return {
            "enabled": True,
            "port": 8787,
            "publicHost": None,
            "tls": "off",
            "auth": {
                "mode": "none",
                "passwordHash": password_hash,
                "verifyUrl": None,
                "signInUrl": None,
                "identityHeader": "X-Raft-Identity",
                "oauth": {
                    "provider": "google",
                    "redirectPath": "/oauth2/callback",
                    "allowlistFile": "host/secrets/dashboard/oauth-allowlist.txt",
                    "issuerUrl": None,
                },
            },
        }
