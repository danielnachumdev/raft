"""Shared doctor fixtures (coverage Doctor + report CheckResult cases)."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

from raft.core.platform.adapters.docker.compose_status import ComposeStatusTable
from raft.core.observe.ops.doctor import INFRA, CheckResult, Doctor

# ``docker ps`` (no ``-a``) lists these states; exited containers stay hidden.
_PS_VISIBLE = frozenset({"created", "restarting", "running", "removing", "paused"})


def coverage_doctor(stack, *, shell=None, docker=None, auth=None) -> Doctor:
    """Doctor with public_host_ok patched for edge-coverage tests."""
    doctor = Doctor(stack)
    doctor.sh = shell if shell is not None else MagicMock()
    doctor.auth = auth if auth is not None else MagicMock()
    doctor.docker = docker if docker is not None else MagicMock()
    _default_runtime(doctor.docker)
    wire_labeled_docker_ps(doctor.sh, doctor.docker)
    original_run = doctor.run

    def run_with_host_ok():
        with patch(
            "raft.core.observe.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=True,
        ):
            return original_run()

    doctor.run = run_with_host_ok  # type: ignore[method-assign]
    return doctor


def wire_labeled_docker_ps(shell, docker) -> None:
    """Feed engine ps/inspect from the compose-status double tests already set."""
    shell.docker.side_effect = _engine_from_compose(docker)


def _engine_from_compose(docker):
    def docker_cmd(*args, **kwargs):
        del kwargs
        if args[:1] == ("ps",):
            return _cmd_ok(_ps_stdout(_status_table(docker)))
        if args[:1] == ("inspect",):
            return _cmd_ok(_inspect_stdout(_status_table(docker)))
        return _cmd_ok("")

    return docker_cmd


def _status_table(docker) -> ComposeStatusTable:
    table = docker.compose_service_status()
    if isinstance(table, ComposeStatusTable):
        return table
    return ComposeStatusTable({})


def _cmd_ok(stdout: str) -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = ""
    return result


def _ps_stdout(table: ComposeStatusTable) -> str:
    lines = [
        f"{_cid(name)}\t{name}"
        for name in table.services()
        if table.runtime(name)[0] in _PS_VISIBLE
    ]
    return "".join(f"{line}\n" for line in lines)


def _inspect_stdout(table: ComposeStatusTable) -> str:
    payload = [
        _inspect_item(name, *table.runtime(name))
        for name in table.services()
        if table.runtime(name)[0] in _PS_VISIBLE
    ]
    return json.dumps(payload)


def _inspect_item(name: str, state: str, health: str) -> dict:
    return {
        "Id": _cid(name),
        "RestartCount": 0,
        "State": _inspect_state(state, health),
        "HostConfig": {},
    }


def _inspect_state(state: str, health: str) -> dict:
    body = {
        "Status": state,
        "StartedAt": "2024-01-01T00:00:00Z",
        "FinishedAt": "",
        "OOMKilled": False,
        "ExitCode": 0,
    }
    if health and health != "none":
        body["Health"] = {"Status": health}
    return body


def _cid(name: str) -> str:
    return f"cid{name}"


def _default_runtime(docker) -> None:
    if docker.compose_service_status.side_effect is not None:
        return
    running = docker.running_services.return_value
    names = list(running) if isinstance(running, list) else []
    docker.compose_service_status.return_value = ComposeStatusTable.from_runtime_map(
        {name: ("running", "none") for name in names}
    )
    if not isinstance(docker.service_runtime.return_value, tuple):
        docker.service_runtime.return_value = ("running", "none")


def ok_infra_and_svc():
    return [
        CheckResult(INFRA, "docker", "ok", "fine"),
        CheckResult("svc", "auth", "ok", "fine"),
        CheckResult("svc", "sync", "ok", "fine"),
    ]


def warn_svc():
    return [
        CheckResult("svc", "auth", "ok", "fine"),
        CheckResult("svc", "sync", "warn", "maybe", fix="do x"),
    ]


def fail_hub_multiline():
    return [
        CheckResult(
            "hub",
            "sync",
            "fail",
            "docker image missing locally: ghcr.io/org/hub:main",
            fix="line one\nline two\nline three",
        ),
    ]


def fail_infra_docker():
    return [CheckResult(INFRA, "docker", "fail", "bad", fix="fix it")]


def raft_group_mix():
    return [
        CheckResult(INFRA, "compose.yaml", "ok", "fine"),
        CheckResult(INFRA, "port 80", "ok", "host probe"),
        CheckResult("raft-gate", "running", "ok", "up"),
        CheckResult("raft-gate", "ports", "ok", "80, 443"),
        CheckResult("raft-router", "ports", "ok", "80"),
        CheckResult("raft-raftling", "contract", "ok", "fine"),
        CheckResult("raft-raftling", "ports", "ok", "80"),
        CheckResult("solo", "contract", "ok", "fine"),
        CheckResult("solo", "ports", "ok", "80"),
        CheckResult("orphan", "x", "ok", "fine"),
    ]


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


class NoTty:
    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        return None
