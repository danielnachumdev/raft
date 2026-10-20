"""Bootstrap must only scaffold host/ + services/ (+ generated), never old roots."""

from pathlib import Path

from raft.core.core.config.paths.bootstrap import RaftHomeBootstrap
from raft.core.core.config.paths.constants import DATA_DIR_RELS

from tests.unit.base import RaftTestCase

_FORBIDDEN_TOP = frozenset(
    {"apps", "state", "logs", "certs", "deploy", "secrets"}
)


class TestBootstrapLayout(RaftTestCase):
    def test_data_dir_rels_never_use_pre313_top_level(self) -> None:
        tops = {Path(rel).parts[0] for rel in DATA_DIR_RELS}
        assert tops.isdisjoint(_FORBIDDEN_TOP), tops & _FORBIDDEN_TOP
        assert "host" in tops
        assert "services" in tops
        assert "generated" in tops

    def test_ensure_data_dirs_skips_pre313_top_level(self, tmp_path: Path) -> None:
        home = tmp_path / "raft-home"
        home.mkdir()
        RaftHomeBootstrap()._ensure_data_dirs(home)
        for name in _FORBIDDEN_TOP:
            assert not (home / name).exists(), name
        assert (home / "host" / "logs").is_dir()
        assert (home / "host" / "secrets" / "dashboard").is_dir()
        assert (home / "services").is_dir()
        assert (home / "generated" / "nginx" / "upstreams").is_dir()
