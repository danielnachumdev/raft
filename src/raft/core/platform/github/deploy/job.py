"""Deploy job runner (AppApply / auth reuse + CI PR setup)."""

import logging
import shutil
import threading
from pathlib import Path
from typing import Optional

from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.lifecycle.apply.service import AppApply
from raft.core.platform.auth.manager import GitAuthManager
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.contract_path import ContractRelPath
from raft.core.core.models.stack import Stack, load_stack
from raft.core.observe.notify.control_events import ControlPlaneEvents
from raft.core.observe.notify.notifier import Notifier
from ..accounts import GithubAccount
from ..providers import GithubProvider, GithubRepo
from .ci_pr import GithubCiPrSetup
from .host_git import GithubDeployHostGit
from .job_failures import GithubDeployFailures
from .job_manifest import GithubDeployManifest
from .models import DeployJob, DeployJobStore, DeployStep
from .next_steps import DeployNextSteps

logger = logging.getLogger(__name__)


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
        self._paths = ContractRelPath()
        self._host_git = GithubDeployHostGit(stack)
        self._failures = GithubDeployFailures()
        self._manifest = GithubDeployManifest()

    def start(
        self,
        account: GithubAccount,
        repo: GithubRepo,
        ref: str,
        *,
        manifest_path: str = "",
    ) -> DeployJob:
        rel = self._paths.normalize(manifest_path)
        job, coalesced = self._store.claim_or_create(
            repo.full_name,
            ref or repo.default_branch,
            manifest_path=rel,
        )
        if coalesced:
            return self._log_coalesce(job, repo.full_name, rel)
        self._spawn(job.id, account, repo)
        return job

    def _log_coalesce(self, job: DeployJob, full_name: str, rel: str) -> DeployJob:
        logger.info(
            "github deploy coalesce full_name=%s path=%s job_id=%s",
            full_name,
            rel,
            job.id,
        )
        return job

    def _spawn(self, job_id: str, account: GithubAccount, repo: GithubRepo) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(job_id, account, repo),
            name=f"github-deploy-{job_id}",
            daemon=True,
        )
        thread.start()

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
        rel = job.manifest_path or ContractRelPath.DEFAULT
        self._step(job, "Fetch App manifest", "running")
        text = self._provider.fetch_manifest(
            account.access_token, repo.full_name, job.ref, path=rel
        )
        self._step(job, "Fetch App manifest", "ok", f"found {rel}")
        data = self._manifest.parse_yaml(text, repo.full_name)
        app_name = self._manifest.manifest_name(data)
        job.app_name = app_name
        local = self._provider.resolve_local_tree(repo.full_name)
        if local is not None:
            self._deploy_local(job, local, data, app_name, rel=rel)
        else:
            self._deploy_git(job, account, repo, app_name, rel=rel)
        self._setup_ci_pr(job, account, repo)
        self._fill_next_steps(job, data)

    def _setup_ci_pr(
        self, job: DeployJob, account: GithubAccount, repo: GithubRepo
    ) -> None:
        self._step(job, "CI workflow PR", "running")
        try:
            result = self._ci.ensure(account.access_token, repo)
            job.ci_pr = result.to_dict()
            self._step(job, "CI workflow PR", "ok", result.detail)
        except OperatorError as exc:
            job.ci_pr = {"status": "failed", "detail": str(exc)}
            self._step(job, "CI workflow PR", "failed", str(exc)[:200])

    def _deploy_local(
        self,
        job: DeployJob,
        tree: Path,
        data: dict,
        app_name: str,
        *,
        rel: str,
    ) -> None:
        self._step(job, "Stage local tree", "running")
        dest = ServicePaths(self._stack.root, app_name).checkout()
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(tree, dest)
        self._step(job, "Stage local tree", "ok", str(dest))
        self._apply_local_manifest(job, dest, data, app_name, rel=rel)

    def _apply_local_manifest(
        self,
        job: DeployJob,
        dest: Path,
        data: dict,
        app_name: str,
        *,
        rel: str,
    ) -> None:
        self._step(job, "Apply + deploy", "running")
        manifest = self._paths.under(dest, rel)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        self._manifest.rewrite_local(manifest, data, app_name)
        try:
            AppApply(load_stack(self._stack.root)).apply_file(manifest, deploy=True)
        except OperatorError as exc:
            self._failures.apply_steps(job, str(exc))
            raise
        self._step(job, "Apply + deploy", "ok", f"applied {app_name}")

    def _deploy_git(
        self,
        job: DeployJob,
        account: GithubAccount,
        repo: GithubRepo,
        app_name: str,
        *,
        rel: str,
    ) -> None:
        del account
        fp = self._prepare_deploy_key(job, repo, app_name)
        self._step(job, "Apply + deploy", "running")
        try:
            self._apply_git(repo.ssh_url, ref=job.ref, rel=rel)
        except OperatorError as exc:
            self._handle_git_apply_error(job, exc, fp)
        self._step(job, "Apply + deploy", "ok", f"applied {app_name}")

    def _handle_git_apply_error(
        self, job: DeployJob, exc: OperatorError, fp: str
    ) -> None:
        detail = str(exc)
        if self._failures.is_deploy_key_failure(detail):
            self._failures.auth_steps(job, fp)
            raise OperatorError(
                self._failures.auth_message(detail, fp),
                has_fix=False,
            ) from exc
        self._failures.apply_steps(job, detail)
        raise

    def _apply_git(self, ssh_url: str, *, ref: str, rel: str) -> None:
        if self._host_git.in_dashboard():
            self._host_git.apply_git(ssh_url, ref=ref, manifest_path=rel)
            return
        AppApply(load_stack(self._stack.root)).apply_git(
            ssh_url, ref=ref, deploy=True, manifest_path=rel
        )

    def _prepare_deploy_key(self, job: DeployJob, repo: GithubRepo, app_name: str) -> str:
        self._step(job, "Prepare deploy key", "running")
        if self._host_git.in_dashboard():
            pubkey = self._host_git.prepare_key(app_name, repo.ssh_url)
        else:
            auth = GitAuthManager(load_stack(self._stack.root))
            auth.setup(app_name, repo=repo.ssh_url)
            pubkey = auth.show_pubkey(app_name)
        job.deploy_pubkey = GitAuthManager._pubkey_for_paste(pubkey)
        job.deploy_key_title = self._manifest.title_from_pubkey(pubkey) or f"raft:{app_name}"
        job.deploy_key_url = self._failures.deploy_key_url(job)
        fp = self._manifest.fingerprint(pubkey)
        self._step(job, "Prepare deploy key", "ok", f"fingerprint {fp}")
        return fp

    def _fill_next_steps(self, job: DeployJob, data: dict) -> None:
        if not job.app_name:
            return
        path = ServicePaths(self._stack.root, job.app_name).app_yaml()
        data = self._manifest.registry_or(data, path)
        app, spec = AppDocument.parse(data, path=path if path.is_file() else Path("."))
        steps = self._next.build(
            app,
            spec,
            deploy_pubkey=job.deploy_pubkey,
            deploy_key_url=self._failures.deploy_key_url(job),
            key_fingerprint=(
                self._manifest.fingerprint(job.deploy_pubkey)
                if job.deploy_pubkey
                else None
            ),
        )
        steps.extend(self._next.ci_steps(job.ci_pr))
        job.next_steps = steps

    # Compat wrappers used by unit tests / callers that touch class methods.
    _parse_yaml = staticmethod(GithubDeployManifest.parse_yaml)
    _manifest_name = staticmethod(GithubDeployManifest.manifest_name)
    _rewrite_local_manifest = staticmethod(GithubDeployManifest.rewrite_local)
    _registry_or = staticmethod(GithubDeployManifest.registry_or)
    _title_from_pubkey = staticmethod(GithubDeployManifest.title_from_pubkey)
    _fingerprint = staticmethod(GithubDeployManifest.fingerprint)
    _deploy_key_url = staticmethod(GithubDeployFailures.deploy_key_url)
    _is_deploy_key_failure = staticmethod(GithubDeployFailures.is_deploy_key_failure)
    _auth_failure_message = staticmethod(GithubDeployFailures.auth_message)

    @staticmethod
    def _step(job: DeployJob, name: str, status: str, detail: str = "") -> None:
        for step in job.steps:
            if step.name == name:
                step.status = status
                step.detail = detail
                return
        job.steps.append(DeployStep(name=name, status=status, detail=detail))
