"""Runtime store quarantine + atomic cleanup."""

import json
from pathlib import Path
from unittest.mock import patch

from raft.core.observe.alerts.store.atomic import AtomicText
from raft.core.observe.alerts.store.runtime_state import AlertRuntime, _parse
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase


class TestRuntimeQuarantine(RaftTestCase):
    def test_corrupt_json_and_non_mapping(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        store = AlertRuntimeStore(home)
        store.path.write_text("not-json", encoding="utf-8")
        assert store.load().instances == {}
        store.path.write_text("[]", encoding="utf-8")
        assert store.load().instances == {}

    def test_quarantine_rename_fails(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        store = AlertRuntimeStore(home)
        store.path.write_text("{", encoding="utf-8")
        with patch.object(Path, "rename", side_effect=OSError("x")):
            assert store.load().instances == {}

    def test_atomic_unlink_oserror(self) -> None:
        home = Path(self.tmp_path)
        with patch("os.path.exists", return_value=True), patch(
            "os.unlink", side_effect=OSError("x")
        ):
            AtomicText.write(home / "y.txt", "z")

    def test_runtime_parse_edges(self) -> None:
        assert _parse(None) is None
        assert _parse("bad") is None
        rt = AlertRuntime.from_mapping(
            {"instances": {"a": "bad", "b": {"ruleId": "x", "state": "ok"}}}
        )
        assert "a" not in rt.instances and "b" in rt.instances
