"""Coverage-edge doctor fixture (host probe patched OK)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.services.ops.doctor import Doctor


class CoverageDoctor:
    """Build a Doctor with public_host_ok patched for edge-coverage tests."""

    @staticmethod
    def for_stack(stack, *, shell=None, docker=None, auth=None) -> Doctor:
        doctor = Doctor(stack)
        doctor.sh = shell if shell is not None else MagicMock()
        doctor.auth = auth if auth is not None else MagicMock()
        doctor.docker = docker if docker is not None else MagicMock()
        original_run = doctor.run

        def run_with_host_ok():
            with patch(
                "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
                return_value=True,
            ):
                return original_run()

        doctor.run = run_with_host_ok  # type: ignore[method-assign]
        return doctor
