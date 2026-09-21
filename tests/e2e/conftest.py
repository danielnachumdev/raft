"""E2E fixtures — Docker required; skip cleanly when unavailable."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.config import reset_logging_for_tests

from tests.e2e.shared.compose import ComposeProject, apps_only_compose, docker_available, new_project_name
from tests.shared.raft_home import apply_and_render, fixture_app_yamls


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if docker_available():
        return
    skip = pytest.mark.skip(reason="Docker not available")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolated_raft_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "raft-data-home"
    home.mkdir()
    ssh = tmp_path / ".ssh-raft-test"
    ssh.mkdir()
    log_dir = tmp_path / "test-logs"
    log_dir.mkdir()
    monkeypatch.setenv("RAFT_DATA_HOME", str(home))
    monkeypatch.setenv("RAFT_SSH_DIR", str(ssh))
    monkeypatch.setenv("RAFT_LOG_DIR", str(log_dir))
    reset_logging_for_tests()
    yield home
    reset_logging_for_tests()


@pytest.fixture
def compose_project(isolated_raft_env: Path, request: pytest.FixtureRequest):
    """Apply fixture apps, render, up apps-only compose; always tear down."""
    fixture_name = request.param
    yamls = fixture_app_yamls(fixture_name)
    if fixture_name == "multi_app_group":
        yamls = sorted(yamls, key=lambda p: 0 if "redis" in str(p) else 1)

    # Volume bind path for expose_none_volume / volume tests
    vol = isolated_raft_env / "bind-vol"
    vol.mkdir(exist_ok=True)
    vol.chmod(0o777)
    (vol / "raft-e2e-marker.txt").write_text("from-host\n", encoding="utf-8")
    env_file = isolated_raft_env / "demo.env"
    env_file.write_text("DEMO=1\n", encoding="utf-8")

    # Rewrite fixture env/volume paths into the temp home when needed
    generated = apply_and_render(isolated_raft_env, yamls)
    # Patch generated compose for temp paths (expose_none_volume uses /tmp/…)
    apps_yaml = generated / "compose.apps.yaml"
    text = apps_yaml.read_text(encoding="utf-8")
    text = text.replace("/tmp/raft-e2e-vol", str(vol))
    text = text.replace("/tmp/raft-e2e-demo.env", str(env_file))
    apps_yaml.write_text(text, encoding="utf-8")

    compose_file = apps_only_compose(generated, generated / "compose.e2e.yaml")
    project = new_project_name()
    cp = ComposeProject(project, compose_file, isolated_raft_env)
    try:
        cp.up()
        yield cp, isolated_raft_env, vol
    finally:
        cp.down()
