"""CLI IO helpers for notification channel files."""

from pathlib import Path

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.services.cli.commands.notifications_io import NotificationsCliIo
from tests.unit.base import RaftTestCase


class TestNotificationsCliIo(RaftTestCase):
    def test_read_yaml_and_json(self) -> None:
        io = NotificationsCliIo()
        yml = Path(self.tmp_path) / "c.yaml"
        yml.write_text("id: ops\ntype: webhook\n", encoding="utf-8")
        assert io.read_mapping(yml)["id"] == "ops"
        js = Path(self.tmp_path) / "c.json"
        js.write_text('{"id":"ops","type":"webhook"}', encoding="utf-8")
        assert io.read_mapping(js)["type"] == "webhook"

    def test_require_file_missing(self) -> None:
        with pytest.raises(OperatorError, match="not found"):
            NotificationsCliIo().require_file(
                str(Path(self.tmp_path) / "nope.yaml"), command="create"
            )

    def test_optional_settings_and_dump(self) -> None:
        io = NotificationsCliIo()
        assert io.optional_settings(None) is None
        assert io.optional_settings('{"url":"https://x"}')["url"] == "https://x"
        with pytest.raises(OperatorError, match="JSON object"):
            io.optional_settings("[]")
        with pytest.raises(OperatorError, match="JSON object"):
            io.optional_settings("not-json")
        text = io.dump({"id": "ops"}, as_json=True)
        assert '"id"' in text
        assert "id: ops" in io.dump({"id": "ops"}, as_json=False)

    def test_reject_non_mapping_and_bad_parse(self) -> None:
        io = NotificationsCliIo()
        bad = Path(self.tmp_path) / "list.yaml"
        bad.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="must be a YAML/JSON object"):
            io.read_mapping(bad)
        broken = Path(self.tmp_path) / "bad.yaml"
        broken.write_text(":\n  -", encoding="utf-8")
        with pytest.raises(OperatorError, match="cannot parse"):
            io.read_mapping(broken)
