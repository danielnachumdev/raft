"""Persist github OAuth settings from serve."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml

from raft.config.settings import load_config
from raft.errors.cta import OperatorError
from raft.services.serve.github.settings_write import GithubSettingsWriter

from ....base import RaftTestCase


class TestGithubSettingsWriter(RaftTestCase):
    def test_save_oauth_and_reload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._clear_env(monkeypatch)
        path = self.tmp_path / "settings.yaml"
        path.write_text("edge: {http: 80}\n", encoding="utf-8")
        writer = GithubSettingsWriter(self.tmp_path)
        assert writer.public_status(port=8787)["oauth_configured"] is False
        cfg = writer.save(client_id="id1", client_secret="sec1")
        assert cfg.client_id == "id1" and cfg.mock is False
        writer.save(client_id="id2", client_secret="sec2")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["edge"]["http"] == 80
        assert data["github"]["clientId"] == "id2"
        assert load_config(self.tmp_path).github.client_secret == "sec2"
        status = writer.public_status(port=9)
        assert status["callback_url"].endswith(":9/api/github/callback")
        assert status["homepage_url"] == "http://127.0.0.1:9/"
        assert status["application_name"] == "raft serve"
        assert "oauth_application%5Bname%5D=" in status["oauth_app_url"] or (
            "oauth_application[name]=" in status["oauth_app_url"]
        )
        assert status["enable_device_flow"] is False
        assert status["expire_user_access_tokens"] is False

    def test_save_mock_and_reject_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._clear_env(monkeypatch)
        writer = GithubSettingsWriter(self.tmp_path)
        with pytest.raises(OperatorError, match="clientId"):
            writer.save(client_id="", client_secret="")
        cfg = writer.save(mock=True)
        assert cfg.mock is True and writer.oauth_ready(cfg)

    def test_load_root_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._clear_env(monkeypatch)
        path = self.tmp_path / "settings.yaml"
        path.unlink()
        writer = GithubSettingsWriter(self.tmp_path)
        assert writer._load_root() == {}
        path.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="YAML mapping"):
            writer._load_root()
        path.write_text("edge: {}\n", encoding="utf-8")
        with patch(
            "raft.services.serve.github.settings_write.yaml.safe_load",
            side_effect=yaml.YAMLError("bad"),
        ):
            with pytest.raises(OperatorError, match="cannot update"):
                writer._load_root()
        path.write_text("edge: {http: 80}\ngithub: true\n", encoding="utf-8")
        writer.save(client_id="x", client_secret="y")
        assert yaml.safe_load(path.read_text(encoding="utf-8"))["github"]["clientId"] == "x"

    @staticmethod
    def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "RAFT_GITHUB_MOCK",
            "RAFT_GITHUB_CLIENT_ID",
            "RAFT_GITHUB_CLIENT_SECRET",
            "RAFT_GITHUB_SESSION_TTL_SECONDS",
        ):
            monkeypatch.delenv(key, raising=False)
