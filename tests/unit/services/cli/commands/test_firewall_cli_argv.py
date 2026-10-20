"""CLI argv dispatch for ``raft firewall …``."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from tests.unit.core.lifecycle.firewall.helpers import rule_dict
from tests.unit.services.cli.base import CliTestCase


class TestFirewallCliArgv(CliTestCase):
    def _seed_settings(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        (self.tmp_path / "host" / "firewall").mkdir(parents=True, exist_ok=True)

    def _rules_path(self) -> Path:
        path = self.tmp_path / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [rule_dict("lab")]}),
            encoding="utf-8",
        )
        return path

    def _quiet(self):
        return patch("raft.services.cli.commands.firewall_output.OperatorSay.say")

    def test_replace_and_show_argv(self) -> None:
        self._seed_settings()
        path = self._rules_path()
        with self._quiet():
            assert self.run_main(["firewall", "replace", "--file", str(path)]) == 0
            assert self.run_main(["firewall", "show"]) == 0

    def test_export_and_import_argv(self) -> None:
        self._seed_settings()
        path = self._rules_path()
        with self._quiet():
            assert self.run_main(["firewall", "export", "--json"]) == 0
            assert (
                self.run_main(["firewall", "import_document", "--file", str(path)])
                == 0
            )

    def test_services_and_recommendations_argv(self) -> None:
        self._seed_settings()
        with self._quiet():
            assert self.run_main(["firewall", "services", "--json"]) == 0
            assert self.run_main(["firewall", "recommendations"]) == 0
            assert self.run_main(["firewall", "dismiss", "permit-port-80"]) == 0

    def test_inspection_argv(self) -> None:
        self._seed_settings()
        with self._quiet():
            assert self.run_main(self._draft_argv()) == 0
            assert self.run_main(self._apply_argv()) == 0
            assert self.run_main(self._remove_argv()) == 0

    def test_run_cli_firewall_show(self) -> None:
        self._seed_settings()
        with self._quiet():
            with pytest.raises(SystemExit) as exc:
                self.run_cli(["firewall", "show"])
            assert exc.value.code == 0

    @staticmethod
    def _draft_argv() -> list[str]:
        return ["firewall", "draft", "--client-ip=192.0.2.1", "--action=deny"]

    @staticmethod
    def _apply_argv() -> list[str]:
        return ["firewall", "apply_inspection", "--client-ip=192.0.2.1"]

    @staticmethod
    def _remove_argv() -> list[str]:
        return ["firewall", "remove_inspection", "--client-ip=192.0.2.1"]
