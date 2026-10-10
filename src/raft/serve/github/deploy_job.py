"""Deploy job runner (AppApply / auth reuse + CI PR setup)."""

from __future__ import annotations

import base64
import hashlib
import logging
import shutil
import threading
from pathlib import Path
from typing import Optional

import yaml

from raft.errors.cta import OperatorError
from raft.notify.control_events import ControlPlaneEvents
from raft.notify.notifier import Notifier

from raft.models.app_document import AppDocument
from raft.models.stack import Stack, load_stack
from raft.apply.service import AppApply
from raft.auth.manager import GitAuthManager
from .ci_pr import GithubCiPrSetup
from .deploy_models import DeployJob, DeployJobStore, DeployStep
from .next_steps import DeployNextSteps
from .provider import GithubProvider, GithubRepo
from .account import GithubAccount

logger = logging.getLogger(__name__)

__all__ = ["DeployJob", "DeployJobStore", "DeployStep", "GithubDeployRunner"]


class GithubDeployRunner:
    """Drive manifest fetch → optional auth → AppApply → CI workflow PR."""

    def __init__(
        self,
        stack: Stack,
        provider: GithubProvider,
        store: DeployJobStore,
        *,
        ci: Optional[GithubCiPrSetup] = None,
        notifier: Optional[Notifier] = None,
    ) -> None:
        self._stack = stack
        self._provider = provider
        self._store = store
        self._next = DeployNextSteps()
        self._ci = ci or GithubCiPrSetup()
        self._notifier = notifier if notifier is not None else Notifier(stack.root)

    def start(self, account: GithubAccount, repo: GithubRepo, ref: str) -> DeployJob:
        job = self._store.create(repo.full_name, ref or repo.default_branch)
        thread = threading.Thread(
            target=self._run,
            args=(job.id, account, repo),
            name=f"github-deploy-{job.id}",
            daemon=True,
        )
        thread.start()
        return job

    def _run(self, job_id: str, account: GithubAccount, repo: GithubRepo) -> None:
        job = self._store.get(job_id)
        if job is None:
            return
        job.status = "running"
        try:
            self._execute(job, account, repo)
            job.status = "succeeded"
        except OperatorError as exc:
            self._fail(job, str(exc))
            logger.warning("github deploy %s failed: %s", job.id, exc)
        except Exception as exc:
            self._fail(job, f"unexpected deploy error: {exc}")
            logger.exception("github deploy %s crashed", job.id)

    def _fail(self, job: DeployJob, error: str) -> None:
        job.status = "failed"
        job.error = error
        self._notifier.notify(
            ControlPlaneEvents.serve_deploy_failed(
                job_id=job.id, full_name=job.full_name, error=error
            )
        )

    def _execute(self, job: DeployJob, account: GithubAccount, repo: GithubRepo) -> None:
        self._step(job, "Fetch App manifest", "running")
        text = self._provider.fetch_manifest(account.access_token, repo.full_name, job.ref)
        self._step(job, "Fetch App manifest", "ok", "found .raft/app.yaml")
        data = self._parse_yaml(text, repo.full_name)
        app_name = self._manifest_name(data)
        job.app_name = app_name
        local = self._provider.resolve_local_tree(repo.full_name)
        if local is not None:
            self._deploy_local(job, local, data, app_name)
        else:
            self._deploy_git(job, account, repo, app_name)
        self._setup_ci_pr(job, account, repo)
        self._fill_next_steps(job, data)

    def _setup_ci_pr(
        self, job: DeployJob, account: GithubAccount, repo: GithubRepo
    ) -> None:
        self._step(job, "CI workflow PR", "running")
        try:
            result = self._ci.ensure(account.access_token, repo, mock=account.mock)
            job.ci_pr = result.to_dict()
            self._step(job, "CI workflow PR", "ok", result.detail)
        except OperatorError as exc:
            job.ci_pr = {"status": "failed", "detail": str(exc)}
            self._step(job, "CI workflow PR", "failed", str(exc)[:200])

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
        self, job: DeployJob, account: GithubAccount, repo: GithubRepo, app_name: str
    ) -> None:
        del account
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
        data = self._registry_or(data, path)
        app, spec = AppDocument.parse(data, path=path if path.is_file() else Path("."))
        steps = self._next.build(
            app,
            spec,
            deploy_pubkey=job.deploy_pubkey,
            deploy_key_url=self._deploy_key_url(job),
            key_fingerprint=self._fingerprint(job.deploy_pubkey) if job.deploy_pubkey else None,
        )
        steps.extend(self._next.ci_steps(job.ci_pr))
        job.next_steps = steps

    @staticmethod
    def _registry_or(data: dict, path: Path) -> dict:
        if path.is_file():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or data
        return data

    @staticmethod
    def _deploy_key_url(job: DeployJob) -> Optional[str]:
        if "/" not in job.full_name:
            return None
        return f"https://github.com/{job.full_name}/settings/keys/new"

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
