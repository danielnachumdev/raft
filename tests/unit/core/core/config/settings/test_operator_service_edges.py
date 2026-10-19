"""Edge cases for OperatorSettingsService persistence and notes."""

from __future__ import annotations

import pytest

from raft.core.core.config.settings import OperatorSettingsService, SettingsDocument
from raft.core.core.config.settings.secrets_merge import SettingsSecretsMerge
from raft.core.core.errors.cta import OperatorError

from tests.unit.base import RaftTestCase


class TestOperatorSettingsServiceEdges(RaftTestCase):
    def test_replace_accepts_bare_document_body(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["healing"]["enabled"] = True
        out = svc.replace(doc)
        assert out["document"]["healing"]["enabled"] is True

    def test_require_mapping_rejects_list(self) -> None:
        with pytest.raises(OperatorError, match="JSON object"):
            SettingsDocument.require_mapping([], path="settings.document")

    def test_streams_round_trip(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["edge"]["streams"] = [
            {"name": "ssh", "port": 2222, "protocol": "tcp"}
        ]
        out = svc.replace({"document": doc})
        assert out["document"]["edge"]["streams"][0]["port"] == 2222

    def test_active_acl_emits_legacy_note_on_get_and_put(self) -> None:
        svc = OperatorSettingsService(self.tmp_path)
        doc = svc.get_public()["document"]
        doc["acl"] = {
            "gate": {
                "mode": "whitelist",
                "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
            }
        }
        put = svc.replace({"document": doc})
        assert any(n["code"] == "acl.gate" for n in put["notes"])
        got = svc.get_public()
        assert any(n["code"] == "acl.gate" for n in got["notes"])

    def test_load_root_missing_invalid_and_non_mapping(self) -> None:
        empty = self.tmp_path / "empty-home"
        empty.mkdir()
        svc = OperatorSettingsService(empty)
        assert svc._load_root() == {}
        path = empty / "settings.yaml"
        path.write_text("- list\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="YAML mapping"):
            svc._load_root()
        path.write_text("logging: [\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="cannot update"):
            svc._load_root()

    def test_redact_skips_non_dict_sections(self) -> None:
        merge = SettingsSecretsMerge()
        out = merge.redact_document(
            {
                "github": "skip",
                "notifications": "skip",
            }
        )
        assert out["github"] == "skip"
        assert out["notifications"] == "skip"

    def test_redact_channel_edge_shapes(self) -> None:
        merge = SettingsSecretsMerge()
        out = merge.redact_document(
            {
                "notifications": {
                    "enabled": True,
                    "channels": ["skip", {"id": "x", "settings": "nope"}],
                }
            }
        )
        assert out["notifications"]["channels"][0] == "skip"
        assert out["notifications"]["channels"][1]["settings"] == "nope"

    def test_redact_when_channels_not_list(self) -> None:
        merge = SettingsSecretsMerge()
        out = merge.redact_document(
            {"notifications": {"enabled": True, "channels": {}}}
        )
        assert out["notifications"]["channels"] == {}
