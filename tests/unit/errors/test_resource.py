"""Host OOM / disk-full Docker failure classifiers and CTAs."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from raft.adapters.docker.compose_diagnostics import ComposeDiagnostics
from raft.errors.checked import CheckedCommands
from raft.errors.classify import SubprocessClassifier, SubprocessCtx
from raft.errors.cta import CtaFormatter, OperatorError
from raft.errors.resource_msgs import ResourceMessages

from ..cta_asserts import CtaAsserts


class TestResourceDetection:
    def test_oom_and_disk_markers(self) -> None:
        assert ResourceMessages.looks_like_host_oom("runtime: out of memory")
        assert ResourceMessages.looks_like_host_oom("Cannot allocate memory")
        assert ResourceMessages.looks_like_host_oom("Container demo was OOMKilled")
        assert not ResourceMessages.looks_like_host_oom("unauthorized: authentication required")
        assert ResourceMessages.looks_like_disk_full("write /var/lib/docker: no space left on device")
        assert ResourceMessages.looks_like_disk_full("ENOSPC: no space left")
        assert not ResourceMessages.looks_like_disk_full("manifest unknown")

    def test_exit_137_docker_sigkill(self) -> None:
        exc = subprocess.CalledProcessError(137, ["docker", "pull", "img"], stderr="")
        assert ResourceMessages.looks_like_host_oom_exc(exc)
        other = subprocess.CalledProcessError(137, ["sleep", "1"], stderr="")
        assert not ResourceMessages.looks_like_host_oom_exc(other)


class TestResourceMessages:
    def test_oom_cta_names_app_and_image(self) -> None:
        msg = ResourceMessages.host_oom_message(
            detail="Cannot allocate memory\nmore",
            app="demo-api",
            image="ghcr.io/demo/api:abc",
            action="pull image",
        )
        CtaAsserts.cta(
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
        msg = ResourceMessages.disk_full_message(
            detail="no space left on device",
            app="demo-api",
            image="ghcr.io/demo/api:abc",
        )
        CtaAsserts.cta(
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
            CheckedCommands.raise_for_docker_pull_failure(
                "ghcr.io/demo/api:abc",
                detail="failed to register layer: Cannot allocate memory",
                app="demo-api",
            )
        CtaAsserts.operator(
            caught.value,
            contains=("insufficient host memory (OOM)", "demo-api", "not registry auth"),
        )
        assert "docker login" not in str(caught.value)

    def test_pull_disk_full(self) -> None:
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_docker_pull_failure(
                "ghcr.io/demo/api:abc",
                detail="failed to extract layer: no space left on device",
                app="demo-api",
            )
        CtaAsserts.operator(
            caught.value,
            contains=("insufficient host disk space", "demo-api", "not registry auth"),
        )

    def test_compose_oom(self) -> None:
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1,
                    ["docker", "compose", "up"],
                    stderr="Error: Cannot allocate memory",
                ),
                action="start service demo-api",
                app="demo-api",
            )
        CtaAsserts.operator(caught.value, contains=("insufficient host memory (OOM)", "demo-api"))

    def test_run_docker_checked_oom(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="docker: Error response from daemon: OCI runtime create failed: out of memory",
        )
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.run_docker(
                shell,
                ("run", "-d", "ghcr.io/demo/api:abc"),
                action="start cutover tmp",
            )
        CtaAsserts.operator(
            caught.value,
            contains=("insufficient host memory (OOM)", "ghcr.io/demo/api:abc"),
        )

    def test_classify_subprocess_oom_and_disk(self) -> None:
        oom = subprocess.CalledProcessError(
            1,
            ["docker", "pull", "ghcr.io/demo/api:abc"],
            stderr="runtime/cgo: out of memory",
        )
        err = SubprocessClassifier().classify(oom, SubprocessCtx(app="demo-api"))
        assert err is not None
        CtaAsserts.operator(err, contains=("insufficient host memory (OOM)", "demo-api"))
        disk = subprocess.CalledProcessError(
            1,
            ["docker", "pull", "ghcr.io/demo/api:abc"],
            stderr="no space left on device",
        )
        err = SubprocessClassifier().classify(disk, SubprocessCtx(app="demo-api"))
        assert err is not None
        CtaAsserts.operator(err, contains=("insufficient host disk space",))

    def test_resource_error_from_text_none(self) -> None:
        assert ResourceMessages.resource_error_from_text("manifest unknown") is None

    def test_enrich_reclassifies_oom_from_diagnostics(self) -> None:
        docker = MagicMock()
        docker.diagnostics_for.return_value = "--- demo-api ---\nOOMKilled: out of memory"
        diag = ComposeDiagnostics(stack=MagicMock(), shell=MagicMock(), docker=docker)
        base = OperatorError("docker compose failed while trying to start service")
        err = diag.enrich_compose_failure(base, services=("demo-api",))
        CtaAsserts.operator(err, contains=("insufficient host memory (OOM)", "not registry auth"))

    def test_exit_137_classify_and_disk_from_exc(self) -> None:
        oom = subprocess.CalledProcessError(137, ["docker", "pull", "img"], stderr="")
        err = SubprocessClassifier().classify(oom, SubprocessCtx(app="demo-api"))
        assert err is not None
        CtaAsserts.operator(err, contains=("insufficient host memory (OOM)",))
        disk_exc = subprocess.CalledProcessError(
            1, ["docker", "compose", "up"], stderr="no space left on device"
        )
        disk_err = ResourceMessages.resource_error_from_exc(disk_exc, app="demo-api")
        assert disk_err is not None
        CtaAsserts.operator(disk_err, contains=("insufficient host disk space",))
        classified = SubprocessClassifier().classify(disk_exc, SubprocessCtx(app="demo-api"))
        assert classified is not None
        CtaAsserts.operator(classified, contains=("insufficient host disk space",))

    def test_headline_without_app_or_action(self) -> None:
        msg = ResourceMessages.host_oom_message(detail="Cannot allocate memory")
        assert "docker operation failed: insufficient host memory (OOM)" in msg

    def test_build_resource_fallback(self) -> None:
        exc = subprocess.CalledProcessError(1, ["docker", "ps"], stderr="")
        err = ResourceMessages.from_subprocess(exc, detail="")
        CtaAsserts.operator(err, contains=("insufficient host memory (OOM)",))
