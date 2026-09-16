"""Registry unauthorized messaging."""

from raft.services.registry import (
    looks_like_registry_unauthorized,
    missing_image_doctor_fix,
    registry_unauthorized_message,
)


def test_looks_like_registry_unauthorized() -> None:
    assert looks_like_registry_unauthorized("unauthorized")
    assert looks_like_registry_unauthorized("Error: authentication required")
    assert looks_like_registry_unauthorized("denied: denied\npull access denied")
    assert not looks_like_registry_unauthorized("connection refused")


def test_registry_unauthorized_message() -> None:
    msg = registry_unauthorized_message(
        "ghcr.io/org/hub:main",
        detail="Error response from daemon: unauthorized\nunauthorized",
    )
    assert "cannot pull ghcr.io/org/hub:main" in msg
    assert "docker login ghcr.io" in msg
    assert "read:packages" in msg
    assert "raft auth" in msg
    assert "(docker: Error response from daemon: unauthorized)" in msg


def test_registry_unauthorized_message_without_detail() -> None:
    msg = registry_unauthorized_message("ghcr.io/org/hub:main")
    assert "cannot pull ghcr.io/org/hub:main" in msg
    assert "(docker:" not in msg


def test_registry_unauthorized_message_blank_detail_line() -> None:
    msg = registry_unauthorized_message("ghcr.io/org/hub:main", detail="\n\n")
    assert "(docker:" not in msg


def test_missing_image_doctor_fix() -> None:
    fix = missing_image_doctor_fix("ghcr.io/org/hub:main")
    assert "image not on this VPS yet" in fix
    assert "docker login ghcr.io" in fix
    assert "raft sync" in fix
    assert "raft auth" in fix.lower()


def test_missing_image_doctor_fix_non_ghcr() -> None:
    fix = missing_image_doctor_fix("docker.io/library/nginx:latest")
    assert "docker login <registry>" in fix
    assert "docker pull docker.io/library/nginx:latest" in fix
