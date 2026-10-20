"""Operator-initiated #313 layout migrate helper."""

from raft.core.observe.ops.migrate import LayoutMigrate

from tests.unit.base import RaftTestCase


class TestLayoutMigrate(RaftTestCase):
    def test_moves_settings_and_app_yaml(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        (home / "settings.yaml").write_text("edge:\n  http: 80\n", encoding="utf-8")
        apps = home / "state" / "apps"
        apps.mkdir(parents=True, exist_ok=True)
        (apps / "demo-api.yaml").write_text("kind: App\n", encoding="utf-8")
        (home / "secrets" / "demo-api").mkdir(parents=True, exist_ok=True)
        (home / "secrets" / "demo-api" / "env").write_text("X=1\n", encoding="utf-8")
        helper = LayoutMigrate(home)
        actions = helper.run(dry_run=False)
        assert (home / "host" / "settings.yaml").is_file()
        assert not (home / "settings.yaml").exists()
        assert (home / "services" / "demo-api" / "app.yaml").is_file()
        assert (home / "services" / "demo-api" / "secrets" / "env").is_file()
        assert any("settings.yaml" in a for a in actions)

    def test_idempotent_skip_when_dest_exists(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        dest = home / "host" / "settings.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("new\n", encoding="utf-8")
        (home / "settings.yaml").write_text("old\n", encoding="utf-8")
        actions = LayoutMigrate(home).run(dry_run=False)
        assert dest.read_text(encoding="utf-8") == "new\n"
        assert (home / "settings.yaml").is_file()
        assert any("skip" in a for a in actions)
