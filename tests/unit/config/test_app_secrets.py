"""AppSecretsLayout paths and directory modes."""

from __future__ import annotations

import stat

from raft.config.app_secrets import AppSecretsLayout
from raft.config.paths import ensure_raft_home

from ..base import RaftTestCase


class TestAppSecretsLayout(RaftTestCase):
    def test_ensure_raft_home_creates_secrets_root(self) -> None:
        home = ensure_raft_home(self.tmp_path / "home")
        root = home / "secrets"
        assert root.is_dir()
        assert root.stat().st_mode & 0o777 == 0o700

    def test_ensure_app_dir_mode(self) -> None:
        layout = AppSecretsLayout(self.tmp_path)
        path = layout.ensure_app_dir("demo-api")
        assert path == self.tmp_path / "secrets" / "demo-api"
        assert path.is_dir()
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        assert layout.env_file("demo-api") == path / "env"
