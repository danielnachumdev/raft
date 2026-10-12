"""Shared AppApply test helpers."""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
from unittest.mock import MagicMock, patch

import yaml

from raft.core.lifecycle.apply import AppApply

from tests.unit.domain_case import DomainTestCase


class ApplyTestCase(DomainTestCase):
    def applier(self, stack=None, shell=None) -> AppApply:
        applier = AppApply(stack or self.stack)
        applier.sh = shell if shell is not None else self.shell
        return applier

    @staticmethod
    def manifest(
        name: str = "web",
        *,
        source: str = "local",
        public_host: str = "web.test",
        **spec_extra: Any,
    ) -> dict:
        spec = {
            "publicHost": public_host,
            "source": source,
            "path": f"apps/{name}",
            "ref": "main",
            "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            "build": {"context": "."},
            **spec_extra,
        }
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": spec,
        }

    def write_clone_manifest(self, target: Path, doc: dict) -> None:
        target.mkdir(parents=True, exist_ok=True)
        raft = target / ".raft"
        raft.mkdir(parents=True, exist_ok=True)
        (raft / "app.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")

    def clone_side_effect(self, doc: dict, *, strip_build: bool = False):
        def clone(*args, **kwargs):
            if "clone" not in args:
                return MagicMock(returncode=0)
            target = Path(args[-1])
            payload = dict(doc)
            if strip_build:
                payload = yaml.safe_load(yaml.safe_dump(doc))
                payload["spec"].pop("build", None)
            self.write_clone_manifest(target, payload)
            return MagicMock(returncode=0)

        return clone

    @contextmanager
    def patched_deploy(
        self,
        stack=None,
        orch: Optional[MagicMock] = None,
    ) -> Iterator[MagicMock]:
        stack = self.stack if stack is None else stack
        orch = MagicMock() if orch is None else orch
        with patch("raft.core.lifecycle.apply.service.Orchestrator", return_value=orch):
            with patch("raft.core.lifecycle.apply.service.load_stack", return_value=stack):
                yield orch
