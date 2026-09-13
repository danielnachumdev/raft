"""GitAuthManager: deploy keys, SSH config, clone URL rewrite."""

from unittest.mock import MagicMock

import pytest

from .base import ServicesTestCase
from raft.services.auth import (
    GitAuthManager,
    default_ssh_dir,
    host_alias,
    parse_ssh_git_url,
    real_git_host,
)

class TestParseSshGitUrl:
    def test_variants(self) -> None:
        assert parse_ssh_git_url("git@github.com:org/repo.git").path == "org/repo"
        assert parse_ssh_git_url("ssh://git@gitlab.com/org/repo.git").host == "gitlab.com"
        assert parse_ssh_git_url("git@github.com:org/repo").canonical.endswith(".git")

    def test_rejects_https_and_bad(self) -> None:
        with pytest.raises(ValueError, match="HTTPS"):
            parse_ssh_git_url("https://github.com/org/repo.git")
        with pytest.raises(ValueError, match="cannot parse"):
            parse_ssh_git_url("not-a-url")
        with pytest.raises(ValueError, match="owner/repo"):
            parse_ssh_git_url("git@github.com:noreply")

class TestHostAliasHelpers:
    def test_alias_and_real_host(self) -> None:
        assert host_alias("svc", "github.com") == "github.com-raft-svc"
        assert host_alias("svc", "github.com-raft-svc") == "github.com-raft-svc"
        assert real_git_host("svc", "github.com-raft-svc") == "github.com"
        assert real_git_host("svc", "github.com") == "github.com"

class TestDefaultSshDir(ServicesTestCase):
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        target = self.tmp_path / "custom-ssh"
        target.mkdir()
        monkeypatch.setenv("RAFT_SSH_DIR", str(target))
        assert default_ssh_dir() == target.resolve()

    def test_home_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_SSH_DIR", raising=False)
        monkeypatch.setattr("raft.services.auth.Path.home", lambda: self.tmp_path)
        assert default_ssh_dir() == (self.tmp_path / ".ssh").resolve()

class TestGitAuthManager(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _auth_setup(self, _services_setup) -> None:
        self.mgr = self.auth_manager()
        self.shell.run.side_effect = self.fake_ssh_keygen()

    def test_effective_clone_url_with_and_without_key(self) -> None:
        app = self.mgr.stack.app("svc")
        assert self.mgr.effective_clone_url(app) == app.repo
        self.write_keypair(self.mgr, "svc")
        assert (
            self.mgr.effective_clone_url(app)
            == "git@github.com-raft-svc:org/svc.git"
        )
        with pytest.raises(ValueError, match="no repo URL"):
            self.mgr.effective_clone_url(self.mgr.stack.app("localapp"))

    def test_setup_creates_key_config_and_manual_instructions(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self.mgr.setup("svc")

        assert self.mgr.is_configured("svc")
        cfg = self.mgr.config_path.read_text(encoding="utf-8")
        assert "BEGIN raft:svc" in cfg
        assert "Host github.com-raft-svc" in cfg
        assert "IdentityFile" in cfg
        out = capsys.readouterr().out
        assert "Title:" in out
        assert "Key:" in out
        assert "ssh-ed25519 AAAA" in out
        assert "AAAA setup" not in out
        assert "settings/keys/new" in out
        assert "gh " not in out

    def test_setup_rejects_local_and_idempotent_and_force(self) -> None:
        with pytest.raises(RuntimeError, match="repo URL"):
            self.mgr.setup("localapp")

        self.mgr.setup("svc")
        self.mgr.setup("svc")
        self.mgr.setup("svc", force=True)

    def test_setup_non_github_manual(self, capsys: pytest.CaptureFixture[str]) -> None:
        mgr = self.auth_manager(repo="git@gitlab.com:org/svc.git")
        self.shell.run.side_effect = self.fake_ssh_keygen()
        mgr.setup("svc")
        out = capsys.readouterr().out
        assert "Title:" in out
        assert "Key:" in out
        assert "ssh-ed25519 AAAA" in out
        assert "AAAA setup" not in out
        assert "Deploy keys" in out

    def test_pubkey_for_paste_strips_comment(self) -> None:
        assert (
            GitAuthManager._pubkey_for_paste("ssh-ed25519 AAAA comment-here")
            == "ssh-ed25519 AAAA"
        )
        assert GitAuthManager._pubkey_for_paste("weird") == "weird"

    def test_show_prints_title_key_and_url(self, capsys: pytest.CaptureFixture[str]) -> None:
        self.write_keypair(self.mgr, "svc")
        self.mgr.show("svc")
        out = capsys.readouterr().out
        assert "Title:" in out
        assert "Key:" in out
        assert "AAAA" in out
        assert "settings/keys/new" in out
        with pytest.raises(RuntimeError, match="repo URL"):
            self.mgr.show("localapp")

    def test_list_show_test_remove(self) -> None:
        assert self.mgr.list_services() == []
        with pytest.raises(RuntimeError, match="no deploy key"):
            self.mgr.show_pubkey("svc")
        with pytest.raises(RuntimeError, match="no key"):
            self.mgr.test("svc")
        with pytest.raises(RuntimeError, match="no repo URL"):
            self.mgr.test("localapp")

        self.write_keypair(self.mgr, "svc")
        assert self.mgr.list_services() == ["svc"]
        self.mgr.pub_path("orphan").write_text("ssh-ed25519 ORPHAN\n", encoding="utf-8")
        assert self.mgr.list_services() == ["svc"]
        assert "AAAA" in self.mgr.show_pubkey("svc")

        self.mgr._ensure_ssh_layout()
        self.mgr.config_path.write_text("Host keep\n  HostName z", encoding="utf-8")
        self.mgr._upsert_ssh_config(
            "svc", alias="github.com-raft-svc", hostname="github.com"
        )
        assert self.mgr.config_path.read_text(encoding="utf-8").endswith("\n")

        self.shell.git.return_value = MagicMock(
            returncode=0, stdout="abc\tHEAD\n", stderr=""
        )
        self.mgr.test("svc")
        self.mgr.test("svc", quiet=True)
        self.shell.git.return_value = MagicMock(
            returncode=1, stdout="", stderr="denied"
        )
        with pytest.raises(RuntimeError, match="auth test failed"):
            self.mgr.test("svc")
        self.shell.git.return_value = MagicMock(returncode=1, stdout="", stderr="")
        with pytest.raises(RuntimeError, match="auth test failed"):
            self.mgr.test("svc")

        self.mgr.remove("svc", remove_files=False)
        assert self.mgr.key_path("svc").is_file()
        self.mgr.remove("svc", remove_files=True)
        assert not self.mgr.key_path("svc").is_file()
        self.mgr.config_path.unlink(missing_ok=True)
        self.mgr.remove("ghost")
