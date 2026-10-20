"""Operator-initiated #313 layout migrate helper."""

from unittest.mock import patch

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

    def test_dry_run_does_not_move(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        (home / "settings.yaml").write_text("edge: {}\n", encoding="utf-8")
        actions = LayoutMigrate(home).run(dry_run=True)
        assert (home / "settings.yaml").is_file()
        assert not (home / "host" / "settings.yaml").exists()
        assert any(a.startswith("move:") for a in actions)

    def test_moves_scaling_markers_and_service_logs(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        apps = home / "state" / "apps"
        apps.mkdir(parents=True)
        (apps / "demo-api.yaml").write_text("kind: App\n", encoding="utf-8")
        markers = home / "state" / "scaling" / "markers"
        markers.mkdir(parents=True)
        (markers / "demo-api.wake").write_text("1\n", encoding="utf-8")
        logs = home / "state" / "service-logs" / "demo-api"
        logs.mkdir(parents=True)
        (logs / "current.log").write_text("hi\n", encoding="utf-8")
        edge = home / "state" / "service-logs" / "raft-gate"
        edge.mkdir(parents=True)
        (edge / "current.log").write_text("g\n", encoding="utf-8")
        LayoutMigrate(home).run(dry_run=False)
        assert (
            home / "services" / "demo-api" / "scaling" / "markers" / "demo-api.wake"
        ).is_file()
        assert (home / "services" / "demo-api" / "logs" / "current.log").is_file()
        assert (home / "host" / "logs" / "services" / "raft-gate" / "current.log").is_file()

    def test_discovers_names_from_legacy_trees(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        (home / "certs" / "shop").mkdir(parents=True)
        (home / "certs" / "shop" / "origin.pem").write_text("p\n", encoding="utf-8")
        (home / "apps" / "shop").mkdir(parents=True)
        (home / "deploy" / "shop").mkdir(parents=True)
        (home / "secrets" / "dashboard").mkdir(parents=True)
        (home / "secrets" / "readme.txt").write_text("skip\n", encoding="utf-8")
        svc = home / "services" / "other"
        svc.mkdir(parents=True)
        (svc / "keep").write_text("x\n", encoding="utf-8")
        (home / "services" / "not-a-dir").write_text("x\n", encoding="utf-8")
        actions = LayoutMigrate(home).run(dry_run=False)
        assert (home / "services" / "shop" / "certs" / "origin.pem").is_file()
        assert any("shop" in a for a in actions)
        assert (home / "host" / "secrets" / "dashboard").is_dir()

    def test_dry_run_skips_known_service_logs_in_edge_pass(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        apps = home / "state" / "apps"
        apps.mkdir(parents=True)
        (apps / "demo-api.yaml").write_text("kind: App\n", encoding="utf-8")
        logs = home / "state" / "service-logs" / "demo-api"
        logs.mkdir(parents=True)
        (logs / "current.log").write_text("hi\n", encoding="utf-8")
        actions = LayoutMigrate(home).run(dry_run=True)
        assert logs.is_dir()
        assert any("demo-api" in a and a.startswith("move:") for a in actions)

    def test_report_nothing_and_actions(self) -> None:
        home = self.tmp_path / "home"
        home.mkdir()
        helper = LayoutMigrate(home)
        with patch("raft.core.observe.ops.migrate.layout.OperatorSay.say") as say:
            helper.report([], dry_run=False)
            helper.report(["move: a → b"], dry_run=True)
        texts = [c.args[0] for c in say.call_args_list]
        assert any("nothing to move" in t for t in texts)
        assert any("dry-run" in t for t in texts)
        assert any("move: a → b" in t for t in texts)
