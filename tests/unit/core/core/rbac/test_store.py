"""RbacStore load/save coverage (#307)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.core.core.rbac.document import RbacDocument
from raft.core.core.rbac.store import RbacStore
from tests.unit.base import RaftTestCase


class TestRbacStore(RaftTestCase):
    def test_exists_load_save(self) -> None:
        home = Path(self.tmp_path)
        store = RbacStore(home)
        assert store.exists() is False
        assert store.load() is None
        doc = RbacDocument.from_mapping(
            {
                "version": 1,
                "roles": [{"id": "admin", "permissions": ["*:read"]}],
                "bindings": [],
            },
            path="host/rbac.yaml",
        )
        store.save(doc)
        assert store.exists() is True
        loaded = store.load()
        assert loaded is not None
        assert loaded.roles[0].id == "admin"

    def test_atomic_write_cleans_tmp_on_replace_error(self) -> None:
        home = Path(self.tmp_path)
        store = RbacStore(home)
        store.path.parent.mkdir(parents=True, exist_ok=True)
        doc = RbacDocument.from_mapping({"version": 1}, path="host/rbac.yaml")
        with patch("os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                store.save(doc)
        leftovers = list(store.path.parent.glob("*.tmp"))
        assert leftovers == []
