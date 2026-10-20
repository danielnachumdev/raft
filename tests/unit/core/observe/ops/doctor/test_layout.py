"""Doctor layout check for unmigrated pre-#313 homes."""

from types import SimpleNamespace

from raft.core.core.config.paths import ensure_raft_home
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.doctor.checks.layout import LayoutChecks

from tests.unit.base import RaftTestCase


class TestLayoutChecks(RaftTestCase):
    def test_ok_on_fresh_home(self) -> None:
        home = ensure_raft_home(self.tmp_path / "fresh")
        ctx = SimpleNamespace(stack=Stack.load_apps(home))
        results = LayoutChecks().run(ctx)  # type: ignore[arg-type]
        assert results[0].status == "ok"

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
