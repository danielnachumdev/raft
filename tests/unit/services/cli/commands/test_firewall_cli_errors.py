"""Error and edge paths for firewall CLI helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.services.cli.commands.firewall import FirewallCLI
from raft.services.cli.commands.firewall_io import FirewallCliIo
from raft.services.cli.commands.firewall_output import FirewallCliOutput
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import rule_dict


class TestFirewallCliErrors(RaftTestCase):
    def test_io_require_and_parse_errors(self) -> None:
        io = FirewallCliIo()
        with pytest.raises(OperatorError):
            io.require_file(None, command="replace")
        with pytest.raises(OperatorError):
            io.require_file("  ", command="replace")
        missing = Path(self.tmp_path) / "missing.yaml"
        with pytest.raises(OperatorError):
            io.read_mapping(str(missing))
        bad = Path(self.tmp_path) / "bad.yaml"
        bad.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(OperatorError):
            io.read_mapping(str(bad))
        broken = Path(self.tmp_path) / "broken.json"
        broken.write_text("{not-json", encoding="utf-8")
        with pytest.raises(OperatorError):
            io.read_mapping(str(broken))

    def test_io_json_and_dump(self) -> None:
        io = FirewallCliIo()
        path = Path(self.tmp_path) / "rules.json"
        path.write_text('{"version": 1, "rules": []}\n', encoding="utf-8")
        assert io.read_mapping(str(path))["version"] == 1
        assert '"version"' in io.dump({"version": 1}, as_json=True)
        assert "version:" in io.dump({"version": 1}, as_json=False)

    def test_output_tables_and_json(self) -> None:
        out = FirewallCliOutput()
        with patch("raft.services.cli.commands.firewall_output.OperatorSay.say") as say:
            out.recommendations_table([])
            out.recommendations_table(
                [{"id": "default-deny", "kind": "default-deny", "title": "Deny"}]
            )
            out.services_table([{"name": "any", "label": "Any (edge-wide)"}])
            out.services_table([{"name": "demo-api", "publicHost": "demo.example"}])
            out.emit({"ok": True}, as_json=True)
            out.emit({"ok": True}, as_json=False)
            out.applied({"rules": [rule_dict()]})
            assert say.called

    def test_replace_requires_file(self) -> None:
        cli = FirewallCLI(
            Stack(root=Path(self.tmp_path), apps=()), orchestrator=MagicMock()
        )
        with pytest.raises(OperatorError):
            cli.replace("")

    def test_rule_from_file_flat(self) -> None:
        cli = FirewallCLI(
            Stack(root=Path(self.tmp_path), apps=()), orchestrator=MagicMock()
        )
        path = Path(self.tmp_path) / "flat.yaml"
        path.write_text(
            "id: x\ncidr: 192.0.2.0/24\nport: 80\nprotocol: tcp\n"
            "service: any\naction: deny\n",
            encoding="utf-8",
        )
        rule = cli._rule_from_file(str(path))
        assert rule["id"] == "x"
