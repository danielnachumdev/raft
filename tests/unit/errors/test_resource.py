"""Host OOM / disk-full Docker failure classifiers and CTAs."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from raft.adapters.docker.compose_diagnostics import ComposeDiagnostics
from raft.errors.checked import (
    raise_for_compose_failure,
    raise_for_docker_pull_failure,
    run_docker_checked,
)
from raft.errors.classify import SubprocessCtx, _build_resource, classify_subprocess
from raft.errors.cta import OperatorError
from raft.errors.resource_msgs import (
    disk_full_message,
    host_oom_message,
    looks_like_disk_full,
    looks_like_host_oom,
    looks_like_host_oom_exc,
    resource_error_from_exc,
    resource_error_from_text,
)

from ..cta_asserts import assert_cta, assert_operator


class TestResourceDetection:
    def test_oom_and_disk_markers(self) -> None:
        assert looks_like_host_oom("runtime: out of memory")
        assert looks_like_host_oom("Cannot allocate memory")
        assert looks_like_host_oom("Container demo was OOMKilled")
        assert not looks_like_host_oom("unauthorized: authentication required")
        assert looks_like_disk_full("write /var/lib/docker: no space left on device")
        assert looks_like_disk_full("ENOSPC: no space left")
        assert not looks_like_disk_full("manifest unknown")

    def test_exit_137_docker_sigkill(self) -> None:
        exc = subprocess.CalledProcessError(137, ["docker", "pull", "img"], stderr="")
        assert looks_like_host_oom_exc(exc)
        other = subprocess.CalledProcessError(137, ["sleep", "1"], stderr="")
        assert not looks_like_host_oom_exc(other)


class TestResourceMessages:
    def test_oom_cta_names_app_and_image(self) -> None:
        msg = host_oom_message(
            detail="Cannot allocate memory\nmore",
            app="demo-api",
            image="ghcr.io/demo/api:abc",
            action="pull image",
        )
        assert_cta(
            msg,
            contains=(
                "demo-api",
                "ghcr.io/demo/api:abc",
                "insufficient host memory (OOM)",
                "not registry auth",
                "free memory",
                "raft sync demo-api",
                "raft doctor",
            ),
            tag="docker",
        )
        assert "docker login" not in msg

    def test_disk_cta(self) -> None:
        msg = disk_full_message(
            detail="no space left on device",
            app="demo-api",
            image="ghcr.io/demo/api:abc",
        )
        assert_cta(
            msg,
            contains=(
                "demo-api",
                "insufficient host disk space",
                "not registry auth",
                "docker system df",
            ),
            tag="docker",
        )


class TestResourceRaisePaths:
    def test_pull_oom_before_registry(self) -> None:
        with pytest.raises(OperatorError) as caught:
            raise_for_docker_pull_failure(
                "ghcr.io/demo/api:abc",
                detail="failed to register layer: Cannot allocate memory",
                app="demo-api",
            )
        assert_operator(
            caught.value,
            contains=("insufficient host memory (OOM)", "demo-api", "not registry auth"),
        )
        assert "docker login" not in str(caught.value)

    def test_pull_disk_full(self) -> None:
        with pytest.raises(OperatorError) as caught:
            raise_for_docker_pull_failure(
                "ghcr.io/demo/api:abc",
                detail="failed to extract layer: no space left on device",
                app="demo-api",
            )
        assert_operator(
            caught.value,
            contains=("insufficient host disk space", "demo-api", "not registry auth"),
        )

    def test_compose_oom(self) -> None:
        with pytest.raises(OperatorError) as caught:
            raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1,
                    ["docker", "compose", "up"],
                    stderr="Error: Cannot allocate memory",
                ),
                action="start service demo-api",
                app="demo-api",
            )
        assert_operator(caught.value, contains=("insufficient host memory (OOM)", "demo-api"))

    def test_run_docker_checked_oom(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="docker: Error response from daemon: OCI runtime create failed: out of memory",
        )
        with pytest.raises(OperatorError) as caught:
            run_docker_checked(
                shell,
                ("run", "-d", "ghcr.io/demo/api:abc"),
                action="start cutover tmp",
            )
        assert_operator(
            caught.value,
            contains=("insufficient host memory (OOM)", "ghcr.io/demo/api:abc"),
        )

    def test_classify_subprocess_oom_and_disk(self) -> None:
        oom = subprocess.CalledProcessError(
            1,
            ["docker", "pull", "ghcr.io/demo/api:abc"],
            stderr="runtime/cgo: out of memory",
        )
        err = classify_subprocess(oom, SubprocessCtx(app="demo-api"))
        assert err is not None
        assert_operator(err, contains=("insufficient host memory (OOM)", "demo-api"))
        disk = subprocess.CalledProcessError(
            1,
            ["docker", "pull", "ghcr.io/demo/api:abc"],
            stderr="no space left on device",
        )
        err = classify_subprocess(disk, SubprocessCtx(app="demo-api"))
        assert err is not None
        assert_operator(err, contains=("insufficient host disk space",))

    def test_resource_error_from_text_none(self) -> None:
        assert resource_error_from_text("manifest unknown") is None

    def test_enrich_reclassifies_oom_from_diagnostics(self) -> None:
        docker = MagicMock()
        docker.diagnostics_for.return_value = "--- demo-api ---\nOOMKilled: out of memory"
        diag = ComposeDiagnostics(stack=MagicMock(), shell=MagicMock(), docker=docker)
        base = OperatorError("docker compose failed while trying to start service")
        err = diag.enrich_compose_failure(base, services=("demo-api",))
        assert_operator(err, contains=("insufficient host memory (OOM)", "not registry auth"))

    def test_exit_137_classify_and_disk_from_exc(self) -> None:
        oom = subprocess.CalledProcessError(137, ["docker", "pull", "img"], stderr="")
        err = classify_subprocess(oom, SubprocessCtx(app="demo-api"))
        assert err is not None
        assert_operator(err, contains=("insufficient host memory (OOM)",))
        disk_exc = subprocess.CalledProcessError(
            1, ["docker", "compose", "up"], stderr="no space left on device"
        )
        disk_err = resource_error_from_exc(disk_exc, app="demo-api")
        assert disk_err is not None
        assert_operator(disk_err, contains=("insufficient host disk space",))
        classified = classify_subprocess(disk_exc, SubprocessCtx(app="demo-api"))
        assert classified is not None
        assert_operator(classified, contains=("insufficient host disk space",))

    def test_headline_without_app_or_action(self) -> None:
        msg = host_oom_message(detail="Cannot allocate memory")
        assert "docker operation failed: insufficient host memory (OOM)" in msg

    def test_build_resource_fallback(self) -> None:
        exc = subprocess.CalledProcessError(1, ["docker", "ps"], stderr="")
        err = _build_resource(exc, SubprocessCtx(), "")
        assert_operator(err, contains=("insufficient host memory (OOM)",))
