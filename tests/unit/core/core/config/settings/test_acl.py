"""Parse ``acl:`` from settings.yaml."""

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.strategies.acl import AclSettingsParser
from tests.unit.base import RaftTestCase


class TestAclSettingsParser(RaftTestCase):
    def test_default_off(self) -> None:
        cfg = AclSettingsParser().parse(None)
        assert cfg.gate.mode == "off"
        assert cfg.gate.entries == ()

    def test_load_from_settings_yaml(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "acl:\n"
            "  gate:\n"
            "    mode: whitelist\n"
            "    entries:\n"
            "      - id: lab\n"
            "        cidr: 192.0.2.0/24\n",
            encoding="utf-8",
        )
        loaded = SettingsLoader().load(self.tmp_path)
        assert loaded.acl.gate.mode == "whitelist"
        assert loaded.acl.gate.entries[0].cidr == "192.0.2.0/24"
        assert loaded.acl.gate.is_active()
