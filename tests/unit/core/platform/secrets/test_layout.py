"""AppSecretsLayout paths and directory modes."""

import stat

from raft.core.platform.secrets import ENV_FILE_MODE, SECRETS_DIRNAME, AppSecretsLayout

from tests.unit.base import RaftTestCase


class TestAppSecretsLayout(RaftTestCase):
    def test_ensure_root_mode(self) -> None:
        layout = AppSecretsLayout(self.tmp_path)
        root = layout.ensure_root()
        assert root == self.tmp_path / SECRETS_DIRNAME
        assert root.is_dir()
        assert stat.S_IMODE(root.stat().st_mode) == 0o700

    def test_ensure_app_dir_mode(self) -> None:
        layout = AppSecretsLayout(self.tmp_path)
        path = layout.ensure_app_dir("demo-api")
        assert path == self.tmp_path / SECRETS_DIRNAME / "demo-api"
        assert path.is_dir()
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        assert layout.env_file("demo-api") == path / "env"
        assert ENV_FILE_MODE == 0o600
