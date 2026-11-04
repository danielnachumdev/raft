"""In-process YAML cache for GitOps reads."""

import time
from pathlib import Path

from raft.core.core.gitops import CachedYamlLoad
from tests.unit.base import RaftTestCase


class TestCachedYamlLoad(RaftTestCase):
    def test_cache_hit_and_mtime_refresh(self) -> None:
        path = Path(self.tmp_path) / "host" / "demo.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("version: 1\nname: first\n", encoding="utf-8")
        cache = CachedYamlLoad()
        first = cache.mapping(path, label="demo.yaml")
        assert first["name"] == "first"
        info = cache.cache_info()
        again = cache.mapping(path, label="demo.yaml")
        assert again["name"] == "first"
        assert cache.cache_info().hits >= info.hits
        time.sleep(0.01)
        path.write_text("version: 1\nname: second\n", encoding="utf-8")
        third = cache.mapping(path, label="demo.yaml")
        assert third["name"] == "second"

    def test_missing_returns_none(self) -> None:
        path = Path(self.tmp_path) / "missing.yaml"
        assert CachedYamlLoad().mapping(path, label="missing.yaml") is None
