"""Batched docker image inspect and concurrent git auth probes."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from raft.core.observe.ops.doctor.checks.apps import AppChecks
from raft.core.observe.ops.doctor.context import DoctorContext
from tests.unit.base import AppMakers, StackMakers
from tests.unit.core.observe.ops.doctor.base import DoctorTestCase

_API = "ghcr.io/example/demo-api:main"
_WORKER = "ghcr.io/example/demo-worker:main"
_WEB = "ghcr.io/example/demo-web:main"


class TestDoctorAppProbes(DoctorTestCase):
    def test_docker_images_share_one_inspect(self) -> None:
        docker = self.mock_docker()
        results = self._run(self._docker_apps(), docker=docker, auth=MagicMock())
        self._assert_one_inspect(docker, _API, _WORKER, _WEB)
        keyed = self.by_key(results)
        assert [item.status for item in results if item.check == "sync"] == ["ok", "ok", "ok"]
        assert keyed[("demo-api", "sync")].detail == f"docker image present: {_API}"
        assert keyed[("demo-worker", "auth")].detail.startswith("n/a")
        assert self._pairs(results) == self._docker_pairs()

    def test_partial_inspect_keeps_per_image_levels(self) -> None:
        docker = self._missing_worker_docker()
        keyed = self.by_key(self._run(self._docker_pair(), docker=docker, auth=MagicMock()))
        self._assert_one_inspect(docker, _API, _WORKER)
        assert keyed[("demo-api", "sync")].status == "ok"
        failed = keyed[("demo-worker", "sync")]
        assert failed.status == "fail"
        assert _WORKER in failed.detail
        assert "raft sync demo-worker" in (failed.fix or "")

    def test_unnamed_inspect_failure_marks_images_missing(self) -> None:
        docker = self.mock_docker(image_rc=1, image_out="sha256:abc\n")
        keyed = self.by_key(self._run(self._docker_pair(), docker=docker, auth=MagicMock()))
        assert keyed[("demo-api", "sync")].status == "fail"
        assert keyed[("demo-worker", "sync")].status == "fail"
        assert "docker login ghcr.io" in (keyed[("demo-api", "sync")].fix or "")

    def test_blank_inspect_stdout_is_missing(self) -> None:
        docker = self.mock_docker(image_rc=0, image_out=" \n")
        keyed = self.by_key(self._run(self._docker_pair(), docker=docker, auth=MagicMock()))
        assert keyed[("demo-api", "sync")].status == "fail"
        assert keyed[("demo-worker", "sync")].status == "fail"

    def test_git_auth_tests_overlap(self) -> None:
        auth, probe, docker = self._git_auth_docker()
        keyed = self.by_key(self._run(self._git_apps(), docker=docker, auth=auth))
        assert probe.peak == 3
        assert keyed[("demo-api", "auth")].detail == "deploy key can git ls-remote"
        assert keyed[("demo-worker", "auth")].status == "fail"
        assert keyed[("demo-worker", "auth")].detail == "auth test failed"
        assert "demo/demo-worker" in (keyed[("demo-worker", "auth")].fix or "")
        assert keyed[("demo-web", "auth")].status == "ok"
        assert set(probe.seen) == {"demo-api", "demo-worker", "demo-web"}
        assert docker.sh.docker.call_count == 0

    def _run(self, apps, *, docker, auth):
        stack = StackMakers.make_stack(self.tmp_path, apps)
        ctx = DoctorContext(stack=stack, shell=MagicMock(), auth=auth, docker=docker)
        return AppChecks().run(ctx)

    def _assert_one_inspect(self, docker, *pins: str) -> None:
        calls = [
            call
            for call in docker.sh.docker.call_args_list
            if call.args[:2] == ("image", "inspect")
        ]
        assert len(calls) == 1
        assert calls[0].args == ("image", "inspect", "-f", "{{.Id}}", *pins)
        assert calls[0].kwargs == {"check": False, "capture": True}

    def _missing_worker_docker(self):
        docker = self.mock_docker(image_rc=1, image_out="sha256:abc\n")
        docker.sh.docker.return_value.stderr = (
            "Error response from daemon: No such image: 'ghcr.io/example/demo-worker:main'\n"
            "Error response from daemon: No such image: ghcr.io/example/not-ours:main\n"
        )
        return docker

    def _git_auth_docker(self):
        auth = MagicMock()
        auth.is_configured.return_value = True
        probe = _OverlappingAuth()
        auth.test.side_effect = probe
        return auth, probe, self.mock_docker()

    @staticmethod
    def _docker_apps():
        return (
            AppMakers.make_app("demo-api", source="docker", image="ghcr.io/example/demo-api"),
            AppMakers.make_app("demo-worker", source="docker", image="ghcr.io/example/demo-worker"),
            AppMakers.make_app("demo-web", source="docker", image="ghcr.io/example/demo-web"),
        )

    @staticmethod
    def _docker_pair():
        return TestDoctorAppProbes._docker_apps()[:2]

    @staticmethod
    def _git_apps():
        return (
            AppMakers.make_git_app("demo-api", repo="git@example.com:demo/demo-api.git"),
            AppMakers.make_git_app("demo-worker", repo="git@example.com:demo/demo-worker.git"),
            AppMakers.make_git_app("demo-web", repo="git@example.com:demo/demo-web.git"),
        )

    @staticmethod
    def _pairs(results):
        return [(item.service, item.check) for item in results]

    @staticmethod
    def _docker_pairs():
        pairs = []
        for name in ("demo-api", "demo-worker", "demo-web"):
            pairs.extend((name, check) for check in ("sync", "contract", "auth"))
        return pairs


class _OverlappingAuth:
    def __init__(self) -> None:
        self.seen: list[str] = []
        self.peak = 0
        self._current = 0
        self._lock = threading.Lock()
        self._barrier = threading.Barrier(3)

    def __call__(self, name, **_kwargs):
        self._enter(name)
        try:
            self._barrier.wait(timeout=2)
        finally:
            self._leave()
        if name == "demo-worker":
            raise RuntimeError("auth test failed")

    def _enter(self, name: str) -> None:
        with self._lock:
            self.seen.append(name)
            self._current += 1
            self.peak = max(self.peak, self._current)

    def _leave(self) -> None:
        with self._lock:
            self._current -= 1
