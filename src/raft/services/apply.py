"""Apply / delete App manifests into the on-VPS registry (low-budget k8s)."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from ..adapters.shell import Shell
from ..models.manifest import (
    CONTRACT_REL_PATH,
    contract_path,
    delete_registry_app,
    parse_app_document,
    write_registry_app,
)
from ..models.stack import Stack, load_stack
from ..ui import say
from .orchestrator import Orchestrator
from .render import StackRenderer

logger = logging.getLogger(__name__)


class AppApply:
    def __init__(self, stack: Stack, shell: Optional[Shell] = None) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)

    def apply_file(
        self,
        path: Path,
        *,
        ref_override: Optional[str] = None,
        deploy: bool = True,
        force_sync: bool = False,
    ) -> str:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: document must be a mapping")
        if ref_override:
            spec = data.setdefault("spec", {})
            if not isinstance(spec, dict):
                raise ValueError(f"{path}: spec must be an object")
            spec["ref"] = ref_override
        app, _ = parse_app_document(data, path=path)
        dest = write_registry_app(self.stack.root, data)
        say(f"applied {app.name} → {dest.relative_to(self.stack.root)}")
        if deploy:
            self._deploy(app.name, ref_override=ref_override, force_sync=force_sync)
        return app.name

    def apply_git(
        self,
        repo: str,
        *,
        ref: str = "main",
        deploy: bool = True,
        force_sync: bool = False,
    ) -> str:
        tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
        try:
            try:
                self.sh.git(
                    "clone",
                    "--quiet",
                    "--depth",
                    "1",
                    "--branch",
                    ref,
                    repo,
                    str(tmp),
                )
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
                self.sh.git("clone", "--quiet", repo, str(tmp))
                self.sh.git("checkout", "-f", "--detach", ref, cwd=tmp)

            manifest = contract_path(tmp)
            if not manifest.is_file():
                raise FileNotFoundError(f"no {CONTRACT_REL_PATH.as_posix()} in {repo}@{ref}")
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("app manifest must be a mapping")
            spec = data.setdefault("spec", {})
            if not isinstance(spec, dict):
                raise ValueError("spec must be an object")
            spec.setdefault("repo", repo)
            spec["ref"] = ref
            if not spec.get("source"):
                spec["source"] = "docker" if spec.get("image") else "git"
            app, _ = parse_app_document(data, path=manifest)
            dest = write_registry_app(self.stack.root, data)
            say(f"applied {app.name} from {repo}@{ref} → " f"{dest.relative_to(self.stack.root)}")
            if deploy:
                self._deploy(app.name, ref_override=ref, force_sync=force_sync)
            return app.name
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def delete(self, name: str) -> None:
        if not delete_registry_app(self.stack.root, name):
            raise KeyError(f"app {name!r} is not applied")
        say(f"deleted {name} from registry")
        fresh = load_stack(self.stack.root)
        if fresh.apps:
            StackRenderer(fresh).render()
            say("re-rendered generated/; remove the Compose service if it is still running")
        else:
            StackRenderer(fresh).render()
            say("re-rendered generated/ (no apps applied)")

    def _deploy(
        self,
        name: str,
        *,
        ref_override: Optional[str],
        force_sync: bool,
    ) -> None:
        orch = Orchestrator(load_stack(self.stack.root))
        running = orch.docker.running_services()
        if name in running:
            orch.redeploy_app(name, ref_override=ref_override, force_sync=force_sync)
        else:
            orch.sync([name], ref_override=ref_override, force=force_sync)
            say(f"synced {name}; bring the stack up with: raft up")
