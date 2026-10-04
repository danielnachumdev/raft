"""ComposeEnvFilePath: host-absolute env files under data home."""

from __future__ import annotations

from pathlib import Path

from raft.services.render.env_file_path import ComposeEnvFilePath


class TestComposeEnvFilePath:
    def test_for_compose_relativizes_under_root(self, tmp_path: Path) -> None:
        env = tmp_path / "app.env"
        env.write_text("A=1\n", encoding="utf-8")
        assert ComposeEnvFilePath(tmp_path).for_compose(str(env)) == "app.env"

    def test_for_compose_keeps_relative_and_external(self, tmp_path: Path) -> None:
        helper = ComposeEnvFilePath(tmp_path)
        assert helper.for_compose("nested/app.env") == "nested/app.env"
        assert helper.for_compose("/tmp/outside.env") == "/tmp/outside.env"

    def test_for_compose_remaps_host_absolute_when_present(self, tmp_path: Path) -> None:
        env = tmp_path / "api-dev.env"
        env.write_text("A=1\n", encoding="utf-8")
        host_path = "/home/raft/.raft/api-dev.env"
        assert ComposeEnvFilePath(tmp_path).for_compose(host_path) == "api-dev.env"

    def test_for_runtime_joins_relative_and_keeps_external(self, tmp_path: Path) -> None:
        helper = ComposeEnvFilePath(tmp_path)
        assert helper.for_runtime("app.env") == str(tmp_path / "app.env")
        assert helper.for_runtime("/tmp/outside.env") == "/tmp/outside.env"

    def test_for_runtime_remaps_host_absolute_when_present(self, tmp_path: Path) -> None:
        env = tmp_path / "api-dev.env"
        env.write_text("A=1\n", encoding="utf-8")
        host_path = "/home/raft/.raft/api-dev.env"
        assert ComposeEnvFilePath(tmp_path).for_runtime(host_path) == str(env)

    def test_for_runtime_under_root_absolute(self, tmp_path: Path) -> None:
        env = tmp_path / "sub" / "app.env"
        env.parent.mkdir()
        env.write_text("A=1\n", encoding="utf-8")
        assert ComposeEnvFilePath(tmp_path).for_runtime(str(env)) == str(env.resolve())
