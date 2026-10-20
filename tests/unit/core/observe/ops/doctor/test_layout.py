"""Doctor layout check for unmigrated pre-#313 homes."""

from types import SimpleNamespace

from raft.core.core.config.paths import ensure_raft_home
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.doctor.checks.layout import LayoutChecks

from tests.unit.base import RaftTestCase

_MANY_OLD = (
    "settings.yaml",
    "logs",
    "apps",
    "certs",
    "deploy",
    "secrets",
    "state/apps",
    "state/locks",
    "state/firewall",
    "state/alerts",
    "state/events",
)


class TestLayoutChecks(RaftTestCase):
    def test_ok_on_fresh_home(self) -> None:
        home = ensure_raft_home(self.tmp_path / "fresh")
        ctx = SimpleNamespace(stack=Stack.load_apps(home))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "ok"
        assert "host/" in results[0].detail

    def test_ok_on_empty_home(self) -> None:
        home = self.tmp_path / "empty"
        home.mkdir()
        ctx = SimpleNamespace(stack=Stack(root=home, apps=()))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "ok"
        assert "empty or fresh" in results[0].detail

    def test_fail_on_old_settings(self) -> None:
        home = self.tmp_path / "old"
        home.mkdir()
        (home / "settings.yaml").write_text("edge: {}\n", encoding="utf-8")
        (home / "state" / "apps").mkdir(parents=True, exist_ok=True)
        ctx = SimpleNamespace(stack=Stack(root=home, apps=()))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "fail"
        assert "settings.yaml" in results[0].detail
        assert "313" in (results[0].fix or "")

    def test_fail_truncates_many_leftovers(self) -> None:
        home = self._seed_many_old_markers()
        ctx = SimpleNamespace(stack=Stack(root=home, apps=()))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "fail"
        assert "more" in results[0].detail

    def _seed_many_old_markers(self):
        home = self.tmp_path / "many"
        home.mkdir()
        for name in _MANY_OLD:
            path = home / name
            if name.endswith(".yaml"):
                path.write_text("x: 1\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
        (home / "secrets" / "demo-api").mkdir(parents=True)
        return home

    def test_dashboard_only_secrets_not_leftover(self) -> None:
        home = self.tmp_path / "dash"
        home.mkdir()
        (home / "secrets" / "dashboard").mkdir(parents=True)
        ctx = SimpleNamespace(stack=Stack(root=home, apps=()))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "ok"

    def test_top_level_secrets_file_ignored(self) -> None:
        home = self.tmp_path / "secfile"
        home.mkdir()
        (home / "secrets").write_text("not-a-dir\n", encoding="utf-8")
        ctx = SimpleNamespace(stack=Stack(root=home, apps=()))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "ok"

    def test_secrets_dir_with_only_files_ok(self) -> None:
        home = self.tmp_path / "secfiles"
        home.mkdir()
        secrets = home / "secrets"
        secrets.mkdir()
        (secrets / "readme.txt").write_text("skip\n", encoding="utf-8")
        ctx = SimpleNamespace(stack=Stack(root=home, apps=()))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "ok"
