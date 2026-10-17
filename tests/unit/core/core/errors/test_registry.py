"""Registry unauthorized messaging (``RegistryMessages``)."""

import json
from pathlib import Path

import pytest

from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.errors.operator_error import OperatorError
from raft.core.core.errors.registry_msgs import RegistryMessages
from tests.unit.cta_asserts import CtaAsserts


class TestRegistryMessages:
    def test_looks_like_registry_unauthorized(self) -> None:
        assert RegistryMessages.looks_like_registry_unauthorized("unauthorized")
        assert RegistryMessages.looks_like_registry_unauthorized(
            "Error: authentication required"
        )
        assert RegistryMessages.looks_like_registry_unauthorized(
            "denied: denied\npull access denied"
        )
        assert RegistryMessages.looks_like_registry_unauthorized(
            "error from registry: denied"
        )
        assert RegistryMessages.looks_like_registry_unauthorized(
            "failed to authorize: failed to fetch oauth token"
        )
        assert not RegistryMessages.looks_like_registry_unauthorized(
            "connection refused"
        )

    def test_registry_host(self) -> None:
        assert (
            RegistryMessages.registry_host("ghcr.io/example/demo-api:abc123")
            == "ghcr.io"
        )
        assert RegistryMessages.registry_host("nginx:latest") == "docker.io"
        assert RegistryMessages.registry_host("library/nginx") == "docker.io"

    def test_ghcr_pat_create_url(self) -> None:
        url = RegistryMessages.ghcr_pat_create_url(description="raft-ghcr-app")
        assert url.startswith("https://github.com/settings/tokens/new?")
        assert "scopes=read:packages" in url
        assert "description=raft-ghcr-app" in url

    def test_docker_config_has_registry_auth(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"auths": {"ghcr.io": {"auth": "e30="}}}),
            encoding="utf-8",
        )
        assert RegistryMessages.docker_config_has_registry_auth(
            "ghcr.io", config_path=cfg
        ) is True
        assert RegistryMessages.docker_config_has_registry_auth(
            "quay.io", config_path=cfg
        ) is False
        assert RegistryMessages.docker_config_has_registry_auth(
            "ghcr.io", config_path=tmp_path / "missing.json"
        ) is None

    def test_docker_config_cred_helpers(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"credHelpers": {"ghcr.io": "gh"}}),
            encoding="utf-8",
        )
        assert RegistryMessages.docker_config_has_registry_auth(
            "ghcr.io", config_path=cfg
        ) is True

    def test_registry_unauthorized_message(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/example/demo-api:abc123",
            detail="Error response from daemon: unauthorized\nunauthorized",
            app="demo-api",
            repo="git@github.com:example/demo-api.git",
            config_path=Path("/nonexistent/docker-config.json"),
        )
        self._assert_unauthorized_message(msg)

    def _assert_unauthorized_message(self, msg: str) -> None:
        assert "cannot pull ghcr.io/example/demo-api:abc123" in msg
        assert "not `raft auth`" in msg
        assert "Possible causes:" in msg
        assert "read:packages" in msg
        assert "How to check" in msg
        assert "~/.docker/config.json" in msg
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in msg
        assert "description=raft-ghcr-demo-api" in msg
        assert "docker login ghcr.io" in msg
        assert "raft apply --git git@github.com:example/demo-api.git" in msg
        assert "(docker: Error response from daemon: unauthorized)" in msg
        assert "Fix (as the raft user):" in msg

    def test_registry_unauthorized_tailors_stale_login(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"auths": {"ghcr.io": {}}}), encoding="utf-8")
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/example/demo-api:abc123",
            config_path=cfg,
        )
        assert "credentials may be stale" in msg

    def test_registry_unauthorized_tailors_missing_login(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"auths": {}}), encoding="utf-8")
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/example/demo-api:abc123",
            config_path=cfg,
        )
        assert "registry login is missing" in msg

    def test_registry_unauthorized_message_without_detail(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/example/demo-api:abc123",
            config_path=Path("/nonexistent/docker-config.json"),
        )
        assert "cannot pull ghcr.io/example/demo-api:abc123" in msg
        assert "(docker:" not in msg
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in msg

    def test_registry_unauthorized_message_blank_detail_line(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/example/demo-api:abc123",
            detail="\n\n",
            config_path=Path("/nonexistent/docker-config.json"),
        )
        assert "(docker:" not in msg

    def test_registry_unauthorized_non_ghcr(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message(
            "quay.io/example/demo-api:abc123",
            config_path=Path("/nonexistent/docker-config.json"),
        )
        assert "docker login <registry>" in msg
        assert "github.com/settings/tokens" not in msg
        assert "SAML SSO" not in msg

    def test_denied_ghcr_pull_raises_registry_cta(self) -> None:
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_docker_pull_failure(
                "ghcr.io/example/demo-api:abc123",
                detail="error from registry: denied",
                app="demo-api",
            )
        CtaAsserts.operator(
            caught.value,
            contains=(
                "registry unauthorized",
                "Possible causes:",
                "docker login ghcr.io",
                "read:packages",
            ),
            fix_label="Fix (as the raft user):",
        )

    def test_missing_image_doctor_fix(self) -> None:
        fix = RegistryMessages.missing_image_doctor_fix(
            "ghcr.io/example/demo-api:abc123",
            app="demo-api",
            repo="git@github.com:example/demo-api.git",
        )
        assert "image not on this VPS yet" in fix
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in fix
        assert "docker login ghcr.io" in fix
        assert "raft sync demo-api" in fix
        assert "raft apply --git git@github.com:example/demo-api.git" in fix
        assert "raft auth" in fix.lower()

    def test_missing_image_doctor_fix_non_ghcr(self) -> None:
        fix = RegistryMessages.missing_image_doctor_fix(
            "docker.io/library/nginx:latest"
        )
        assert "docker login <registry>" in fix
        assert "docker pull docker.io/library/nginx:latest" in fix
        assert "github.com/settings/tokens" not in fix
