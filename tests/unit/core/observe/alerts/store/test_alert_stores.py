"""Rules and runtime store edges."""

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.store.rules_store import AlertRulesStore
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase


class TestAlertStores(RaftTestCase):
    def test_rules_store_empty_and_bad(self) -> None:
        home = Path(self.tmp_path)
        store = AlertRulesStore(home, registries=AlertCatalogs.default())
        assert store.load().rules == ()
        (home / "state" / "alerts").mkdir(parents=True)
        (home / "state" / "alerts" / "rules.yaml").write_text(
            "version: 2\nrules: []\n", encoding="utf-8"
        )
        with pytest.raises(OperatorError):
            store.load()
        (home / "state" / "alerts" / "rules.yaml").write_text(":::bad\n", encoding="utf-8")
        with pytest.raises(OperatorError):
            store.load()

    def test_runtime_not_writable(self) -> None:
        home = Path(self.tmp_path)
        rt = AlertRuntimeStore(home)
        with patch.object(Path, "mkdir", side_effect=OSError("nope")):
            with pytest.raises(OSError):
                rt.ensure_writable()
