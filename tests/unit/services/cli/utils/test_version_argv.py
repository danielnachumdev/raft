"""VersionArgv detects --version / -V / version before Fire."""

from raft.services.cli.utils.version_argv import VersionArgv


class TestVersionArgv:
    def test_accepts_version_flags(self) -> None:
        assert VersionArgv.is_request(["--version"])
        assert VersionArgv.is_request(["-V"])
        assert VersionArgv.is_request(["version"])
        assert VersionArgv.is_request(["--", "--version"])

    def test_rejects_other_commands(self) -> None:
        assert not VersionArgv.is_request([])
        assert not VersionArgv.is_request(["status"])
        assert not VersionArgv.is_request(["--version", "extra"])
        assert not VersionArgv.is_request(["update", "--ref", "main"])
