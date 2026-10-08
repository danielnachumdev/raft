"""In-memory deploy job store + runner (AppApply / auth reuse)."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from raft.errors.cta import OperatorError

from ....models.app_document import AppDocument
from ....models.stack import Stack, load_stack
from ...apply.service import AppApply
from ...auth.manager import GitAuthManager
from .next_steps import DeployNextSteps
from .provider import GithubProvider, GithubRepo
from .session import GithubSession

logger = logging.getLogger(__name__)


@dataclass
class DeployStep:
    name: str
    status: str = "pending"
    detail: str = ""


@dataclass
class DeployJob:
    id: str
    full_name: str
    ref: str
    status: str = "pending"
    error: Optional[str] = None
    app_name: Optional[str] = None
    steps: List[DeployStep] = field(default_factory=list)
    next_steps: List[Dict[str, str]] = field(default_factory=list)
    deploy_pubkey: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "ref": self.ref,
            "status": self.status,
            "error": self.error,
            "app_name": self.app_name,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail} for s in self.steps],
            "next_steps": self.next_steps,
            "deploy_pubkey": self.deploy_pubkey,
            "created_at": self.created_at,
        }


class DeployJobStore:
    """Process-local job map (serve is single-process)."""

    def __init__(self) -> None:
        self._jobs: Dict[str, DeployJob] = {}
        self._lock = threading.Lock()

    def create(self, full_name: str, ref: str) -> DeployJob:
        job = DeployJob(id=secrets.token_hex(8), full_name=full_name, ref=ref)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[DeployJob]:
        with self._lock:
            return self._jobs.get(job_id)


class GithubDeployRunner:
    """Drive manifest fetch → optional auth → AppApply (mock local or git)."""

    def __init__(
        self,
        stack: Stack,
        provider: GithubProvider,
        store: DeployJobStore,
    ) -> None:
        self._stack = stack
        self._provider = provider
        self._store = store
        self._next = DeployNextSteps()

    def start(self, session: GithubSession, repo: GithubRepo, ref: str) -> DeployJob:
        job = self._store.create(repo.full_name, ref or repo.default_branch)
        thread = threading.Thread(
            target=self._run,
            args=(job.id, session, repo),
            name=f"github-deploy-{job.id}",
            daemon=True,
        )
        thread.start()
        return job

    def _run(self, job_id: str, session: GithubSession, repo: GithubRepo) -> None:
        job = self._store.get(job_id)
        if job is None:
            return
        job.status = "running"
        try:
            self._execute(job, session, repo)
            job.status = "succeeded"
        except OperatorError as exc:
            job.status = "failed"
            job.error = str(exc)
            logger.warning("github deploy %s failed: %s", job.id, exc)
        except Exception as exc:
            job.status = "failed"
            job.error = f"unexpected deploy error: {exc}"
            logger.exception("github deploy %s crashed", job.id)

    def _execute(self, job: DeployJob, session: GithubSession, repo: GithubRepo) -> None:
        self._step(job, "Fetch App manifest", "running")
        text = self._provider.fetch_manifest(session.access_token, repo.full_name, job.ref)
        self._step(job, "Fetch App manifest", "ok", "found .raft/app.yaml")
        data = self._parse_yaml(text, repo.full_name)
        app_name = self._manifest_name(data)
        job.app_name = app_name
        local = self._provider.resolve_local_tree(repo.full_name)
        if local is not None:
            self._deploy_local(job, local, data, app_name)
        else:
            self._deploy_git(job, session, repo, app_name)
        self._fill_next_steps(job, data)

    def _deploy_local(
        self, job: DeployJob, tree: Path, data: dict, app_name: str
    ) -> None:
        self._step(job, "Stage local tree", "running")
        dest = self._stack.root / "apps" / app_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(tree, dest)
        self._step(job, "Stage local tree", "ok", str(dest))
        self._step(job, "Apply + deploy", "running")
        manifest = dest / ".raft" / "app.yaml"
        self._rewrite_local_manifest(manifest, data, app_name)
        AppApply(load_stack(self._stack.root)).apply_file(manifest, deploy=True)
        self._step(job, "Apply + deploy", "ok", f"applied {app_name}")

    def _deploy_git(
        self, job: DeployJob, session: GithubSession, repo: GithubRepo, app_name: str
    ) -> None:
        del session
        fp = self._prepare_deploy_key(job, repo, app_name)
        self._step(job, "Apply + deploy", "running")
        try:
            AppApply(load_stack(self._stack.root)).apply_git(
                repo.ssh_url, ref=job.ref, deploy=True
            )
        except OperatorError as exc:
            self._auth_failure_steps(job, repo, fp)
            raise OperatorError(
                f"{exc}\n"
                f"If the repo is private, add the deploy public key shown in the UI "
                f"(fingerprint {fp}) then retry.",
                has_fix=False,
            ) from exc
        self._step(job, "Apply + deploy", "ok", f"applied {app_name}")

    def _prepare_deploy_key(self, job: DeployJob, repo: GithubRepo, app_name: str) -> str:
        self._step(job, "Prepare deploy key", "running")
        auth = GitAuthManager(load_stack(self._stack.root))
        auth.setup(app_name, repo=repo.ssh_url)
        pubkey = auth.show_pubkey(app_name)
        job.deploy_pubkey = GitAuthManager._pubkey_for_paste(pubkey)
        fp = self._fingerprint(pubkey)
        self._step(job, "Prepare deploy key", "ok", f"fingerprint {fp}")
        return fp

    @staticmethod
    def _auth_failure_steps(job: DeployJob, repo: GithubRepo, fp: str) -> None:
        job.next_steps = [
            {
                "title": "Deploy key",
                "body": (
                    f"Add this read-only public key on GitHub "
                    f"({repo.html_url}/settings/keys/new), then retry deploy. "
                    f"Fingerprint: {fp}"
                ),
            }
        ]

    def _fill_next_steps(self, job: DeployJob, data: dict) -> None:
        if not job.app_name:
            return
        path = self._stack.root / "state" / "apps" / f"{job.app_name}.yaml"
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or data
        app, spec = AppDocument.parse(data, path=path if path.is_file() else Path("."))
        fp = self._fingerprint(job.deploy_pubkey) if job.deploy_pubkey else None
        url = (
            f"https://github.com/{job.full_name}/settings/keys/new"
            if "/" in job.full_name
            else None
        )
        job.next_steps = self._next.build(
            app,
            spec,
            deploy_pubkey=job.deploy_pubkey,
            deploy_key_url=url,
            key_fingerprint=fp,
        )

    @staticmethod
    def _rewrite_local_manifest(path: Path, data: dict, app_name: str) -> None:
        spec = data.setdefault("spec", {})
        if not isinstance(spec, dict):
            raise OperatorError("manifest spec must be a mapping", has_fix=False)
        spec["source"] = "local"
        spec["path"] = f"apps/{app_name}"
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _parse_yaml(text: str, full_name: str) -> dict:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid App manifest YAML in {full_name}: {exc}\n"
                f"Fix: repair .raft/app.yaml",
                has_fix=False,
            ) from exc
        if not isinstance(data, dict):
            raise OperatorError(
                f"app manifest must be a mapping in {full_name}\n"
                f"Fix: repair .raft/app.yaml",
                has_fix=False,
            )
        return data

    @staticmethod
    def _manifest_name(data: dict) -> str:
        meta = data.get("metadata")
        if not isinstance(meta, dict) or not str(meta.get("name", "")).strip():
            raise OperatorError(
                "manifest metadata.name is required\nFix: set metadata.name in .raft/app.yaml",
                has_fix=False,
            )
        return str(meta["name"]).strip()

    @staticmethod
    def _step(job: DeployJob, name: str, status: str, detail: str = "") -> None:
        for step in job.steps:
            if step.name == name:
                step.status = status
                step.detail = detail
                return
        job.steps.append(DeployStep(name=name, status=status, detail=detail))

    @staticmethod
    def _fingerprint(pubkey: Optional[str]) -> str:
        if not pubkey:
            return ""
        parts = pubkey.split()
        blob = parts[1] if len(parts) >= 2 else pubkey
        try:
            raw = hashlib.sha256(base64.b64decode(blob + "==")).digest()
        except Exception:
            return "SHA256:(unparsed)"
        return "SHA256:" + base64.b64encode(raw).decode("ascii").rstrip("=")
