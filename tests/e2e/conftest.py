"""E2E fixtures — Docker required; skip cleanly when unavailable."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.shared.compose import (
    ComposeProject,
    apps_only_compose,
    docker_available,
    new_project_name,
)
from tests.shared.env import IsolatedRaftEnv
from tests.shared.raft_home import RaftHomeFixtures


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if docker_available():
        return
    skip = pytest.mark.skip(reason="Docker not available")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolated_raft_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env = IsolatedRaftEnv.install(tmp_path, monkeypatch)
    yield env.home
    env.reset_logging()


@pytest.fixture
def compose_project(isolated_raft_env: Path, request: pytest.FixtureRequest):
    """Apply fixture apps, render, up apps-only compose; always tear down."""
    vol, env_file = _seed_volume_and_env(isolated_raft_env)
    generated = _apply_fixture(isolated_raft_env, request.param, vol, env_file)
    compose_file = apps_only_compose(generated, generated / "compose.e2e.yaml")
    cp = ComposeProject(new_project_name(), compose_file, isolated_raft_env)
    try:
        cp.up()
        yield cp, isolated_raft_env, vol
    finally:
        cp.down()


def _seed_volume_and_env(home: Path):
    vol = home / "bind-vol"
    vol.mkdir(exist_ok=True)
    vol.chmod(0o777)
    (vol / "raft-e2e-marker.txt").write_text("from-host\n", encoding="utf-8")
    env_file = home / "demo.env"
    env_file.write_text("DEMO=1\n", encoding="utf-8")
    return vol, env_file


def _apply_fixture(home: Path, fixture_name: str, vol: Path, env_file: Path) -> Path:
    yamls = RaftHomeFixtures.fixture_app_yamls(fixture_name)
    if fixture_name == "multi_app_group":
        yamls = sorted(yamls, key=lambda p: 0 if "redis" in str(p) else 1)
    generated = RaftHomeFixtures.apply_and_render(home, yamls)
    apps_yaml = generated / "compose.apps.yaml"
    text = apps_yaml.read_text(encoding="utf-8")
    text = text.replace("/tmp/raft-e2e-vol", str(vol))
    text = text.replace("/tmp/raft-e2e-demo.env", str(env_file))
    apps_yaml.write_text(text, encoding="utf-8")
    return generated
