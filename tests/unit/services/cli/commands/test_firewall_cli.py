"""CLI ``raft firewall`` commands (service + table paths)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from raft.core.core.models.stack import Stack
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.services.cli.commands.firewall import FirewallCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import document, rule_dict


class TestFirewallCLI(RaftTestCase):
    def _cli(self) -> FirewallCLI:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        (home / "host" / "firewall").mkdir(parents=True, exist_ok=True)
        return FirewallCLI(Stack(root=home, apps=()), orchestrator=MagicMock())

    def _rules_file(self, name: str = "rules.yaml") -> Path:
        path = Path(self.tmp_path) / name
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [rule_dict("lab")]}),
            encoding="utf-8",
        )
        return path

    def test_replace_show_export_import(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.firewall_output.OperatorSay.say"):
            cli.replace(str(self._rules_file()))
            cli.show()
            cli.show(json=True)
            cli.export()
            out = Path(self.tmp_path) / "out.yaml"
            cli.export(file=str(out))
            assert out.is_file()
            cli.import_document(str(self._rules_file("imp.yaml")))

    def test_services_recommendations_dismiss(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.firewall_output.OperatorSay.say"):
            cli.services()
            cli.services(json=True)
            cli.recommendations()
            cli.recommendations(json=True)
            cli.dismiss("permit-port-80")

    def test_draft_apply_remove_inspection(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.firewall_output.OperatorSay.say"):
            cli.draft(client_ip="192.0.2.1", service="any", action="deny")
            cli.apply_inspection(client_ip="192.0.2.1", action="deny")
            cli.remove_inspection(client_ip="192.0.2.1")

    def test_apply_inspection_from_file(self) -> None:
        cli = self._cli()
        path = Path(self.tmp_path) / "rule.yaml"
        path.write_text(
            yaml.safe_dump({"rule": rule_dict("inspect-any-192-0-2-1")}),
            encoding="utf-8",
        )
        with patch("raft.services.cli.commands.firewall_output.OperatorSay.say"):
            cli.apply_inspection(client_ip="192.0.2.1", file=str(path))
        loaded = FirewallStore(Path(self.tmp_path)).load()
        assert loaded is not None
        assert loaded.rules[0].id == "inspect-any-192-0-2-1"

    def test_empty_show(self) -> None:
        cli = self._cli()
        FirewallStore(Path(self.tmp_path)).save(document())
        with patch("raft.services.cli.commands.firewall_output.OperatorSay.say") as say:
            cli.show()
            assert "No firewall rules" in say.call_args[0][0]
