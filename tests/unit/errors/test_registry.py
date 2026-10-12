"""Registry unauthorized messaging (``RegistryMessages``)."""

from raft.errors.registry_msgs import RegistryMessages


class TestRegistryMessages:
    def test_looks_like_registry_unauthorized(self) -> None:
        assert RegistryMessages.looks_like_registry_unauthorized("unauthorized")
        assert RegistryMessages.looks_like_registry_unauthorized(
            "Error: authentication required"
        )
        assert RegistryMessages.looks_like_registry_unauthorized(
            "denied: denied\npull access denied"
        )
        assert not RegistryMessages.looks_like_registry_unauthorized(
            "connection refused"
        )

    def test_ghcr_pat_create_url(self) -> None:
        url = RegistryMessages.ghcr_pat_create_url(description="raft-ghcr-app")
        assert url.startswith("https://github.com/settings/tokens/new?")
        assert "scopes=read:packages" in url
        assert "description=raft-ghcr-app" in url

    def test_registry_unauthorized_message(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/org/hub:main",
            detail="Error response from daemon: unauthorized\nunauthorized",
            app="hub",
            repo="git@github.com:org/hub.git",
        )
        self._assert_unauthorized_message(msg)

    def _assert_unauthorized_message(self, msg: str) -> None:
        assert "cannot pull ghcr.io/org/hub:main" in msg
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in msg
        assert "description=raft-ghcr-hub" in msg
        assert "docker login ghcr.io" in msg
        assert "raft apply --git git@github.com:org/hub.git" in msg
        assert "raft auth" in msg
        assert "(docker: Error response from daemon: unauthorized)" in msg

    def test_registry_unauthorized_message_without_detail(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message("ghcr.io/org/hub:main")
        assert "cannot pull ghcr.io/org/hub:main" in msg
        assert "(docker:" not in msg
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in msg

    def test_registry_unauthorized_message_blank_detail_line(self) -> None:
        msg = RegistryMessages.registry_unauthorized_message(
            "ghcr.io/org/hub:main", detail="\n\n"
        )
        assert "(docker:" not in msg

    def test_missing_image_doctor_fix(self) -> None:
        fix = RegistryMessages.missing_image_doctor_fix(
            "ghcr.io/org/hub:main",
            app="hub",
            repo="git@github.com:org/hub.git",
        )
        assert "image not on this VPS yet" in fix
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in fix
        assert "docker login ghcr.io" in fix
        assert "raft sync hub" in fix
        assert "raft apply --git git@github.com:org/hub.git" in fix
        assert "raft auth" in fix.lower()

    def test_missing_image_doctor_fix_non_ghcr(self) -> None:
        fix = RegistryMessages.missing_image_doctor_fix(
            "docker.io/library/nginx:latest"
        )
        assert "docker login <registry>" in fix
        assert "docker pull docker.io/library/nginx:latest" in fix
        assert "github.com/settings/tokens" not in fix
