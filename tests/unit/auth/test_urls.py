"""SshGitUrls: parse remotes, Host aliases, SSH dir."""

import pytest

from raft.auth.urls import SshGitUrls

from tests.unit.domain_case import DomainTestCase


class TestParseSshGitUrl:
    def setup_method(self) -> None:
        self.urls = SshGitUrls()

    def test_variants(self) -> None:
        assert self.urls.parse("git@github.com:org/repo.git").path == "org/repo"
        assert self.urls.parse("ssh://git@gitlab.com/org/repo.git").host == "gitlab.com"
        assert self.urls.parse("git@github.com:org/repo").canonical.endswith(".git")

    def test_rejects_https_and_bad(self) -> None:
        with pytest.raises(ValueError, match="HTTPS"):
            self.urls.parse("https://github.com/org/repo.git")
        with pytest.raises(ValueError, match="cannot parse"):
            self.urls.parse("not-a-url")
        with pytest.raises(ValueError, match="owner/repo"):
            self.urls.parse("git@github.com:noreply")


class TestHostAliasHelpers:
    def setup_method(self) -> None:
        self.urls = SshGitUrls()

    def test_alias_and_real_host(self) -> None:
        assert self.urls.host_alias("svc", "github.com") == "github.com-raft-svc"
        assert self.urls.host_alias("svc", "github.com-raft-svc") == "github.com-raft-svc"
        assert self.urls.real_git_host("svc", "github.com-raft-svc") == "github.com"
        assert self.urls.real_git_host("svc", "github.com") == "github.com"


class TestDefaultSshDir(DomainTestCase):
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        target = self.tmp_path / "custom-ssh"
        target.mkdir()
        monkeypatch.setenv("RAFT_SSH_DIR", str(target))
        assert SshGitUrls().default_ssh_dir() == target.resolve()

    def test_home_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_SSH_DIR", raising=False)
        monkeypatch.setattr("raft.auth.urls.Path.home", lambda: self.tmp_path)
        assert SshGitUrls().default_ssh_dir() == (self.tmp_path / ".ssh").resolve()
