"""Shared assertions for controller/compose template layout after ensure."""


class TemplateAsserts:
    def assert_controller_templates(self, home) -> None:
        assert (home / "compose.yaml").is_file()
        assert (home / "nginx" / "gate" / "nginx.conf").is_file()
        assert (home / "controller" / "Dockerfile").is_file()
        dockerfile = (home / "controller" / "Dockerfile").read_text(encoding="utf-8")
        assert "uv pip compile pyproject.toml" in dockerfile
        assert "uv pip install --system" in dockerfile
        self._assert_controller_pyproject(home)

    def _assert_controller_pyproject(self, home) -> None:
        assert (home / "controller" / "pyproject.toml").is_file()
        pyproject = (home / "controller" / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "raft"' in pyproject
        assert "fire" in pyproject and "PyYAML" in pyproject
        assert not (home / "controller" / "requirements.txt").exists()
        assert (home / "controller" / "raft" / "__init__.py").is_file()
        assert (
            home / "controller" / "raft" / "services" / "controller" / "__init__.py"
        ).is_file()

    def assert_compose_and_generated(self, home) -> None:
        compose = (home / "compose.yaml").read_text(encoding="utf-8")
        self.assert_compose_controller_mounts(compose)
        self.assert_compose_acme_mounts(compose)
        assert (home / "generated" / "compose.apps.yaml").is_file()
        assert (home / "generated" / "compose.edge.yaml").is_file()
        self._assert_layout_dirs(home)

    def _assert_layout_dirs(self, home) -> None:
        assert (home / "services").is_dir()
        assert (home / "host" / "metrics").is_dir()
        assert (home / "host" / "serve").is_dir()
        assert (home / "host" / "acme" / "http-01").is_dir()
        assert (home / "host" / "locks").is_dir()
        assert (home / "nginx" / "gate" / "acme_challenge.inc").is_file()

    def assert_compose_controller_mounts(self, compose: str) -> None:
        assert "raft-controller:" in compose and "context: ./controller" in compose
        assert "RAFT_DATA_HOME: /raft" in compose
        assert "/var/run/docker.sock:/var/run/docker.sock" in compose
        assert ".:/raft:ro" in compose and "./host/locks:/raft/host/locks" in compose
        assert "./host/metrics:/raft/host/metrics" in compose
        assert "./host/logs:/raft/host/logs" in compose
        assert "./host/events:/raft/host/events" in compose
        assert "./host/alerts:/raft/host/alerts" in compose
        assert "./services:/raft/services" in compose
        assert "./host/acme:/raft/host/acme" in compose
        assert "./generated/nginx/upstreams:/raft/generated/nginx/upstreams" in compose
        assert "RAFT_HOST_UID" in compose and "working_dir: /raft" in compose
        assert "RAFT_DOCKER_GID" in compose and "group_add:" in compose
        assert "memory: 192M" in compose

    def assert_compose_acme_mounts(self, compose: str) -> None:
        assert "./host/acme/http-01:/etc/nginx/acme-www:ro" in compose
        assert "./services:/etc/nginx/services:ro" in compose
        assert "acme_challenge.inc" in compose
