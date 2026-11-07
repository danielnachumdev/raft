"""Per-app sync / auth / contract checks."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.registry_msgs import RegistryMessages
from raft.core.core.models.registry import AppRegistry
from raft.core.platform.auth.urls import SshGitUrls

from ..context import DoctorContext
from ..models import CheckResult

_NO_SUCH_IMAGE = re.compile(r"(?i)no such image:\s*(\S+)")


class AppChecks:
    name = "apps"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        images = self._image_presence(ctx)
        git_auth = self._git_auth_results(ctx)
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            results.extend(self._check_app(ctx, app, images, git_auth))
        return results

    def _image_presence(self, ctx: DoctorContext) -> dict[str, bool]:
        pins = _docker_pins(ctx)
        if not pins:
            return {}
        present = _present_pins(pins, _inspect_images(ctx, pins))
        return {pin: pin in present for pin in pins}

    def _git_auth_results(self, ctx: DoctorContext) -> dict[str, CheckResult]:
        ready, pending = self._git_auth_plan(ctx)
        if not pending:
            return ready
        self._fill_git_auth_probes(ctx, pending, ready)
        return ready

    def _git_auth_plan(self, ctx: DoctorContext):
        ready: dict[str, CheckResult] = {}
        pending: list = []
        for app in ctx.stack.apps:
            self._classify_git_auth(ctx, app, ready, pending)
        return ready, pending

    def _classify_git_auth(self, ctx: DoctorContext, app, ready: dict, pending: list) -> None:
        if app.source != "git":
            return
        if not ctx.auth.is_configured(app.name):
            ready[app.compose_id] = self._git_auth_unconfigured(app)
            return
        pending.append(app)

    def _fill_git_auth_probes(self, ctx: DoctorContext, pending: list, ready: dict) -> None:
        futures = _submit_git_auth(self._git_auth_probe, ctx, pending)
        for app, fut in zip(pending, futures):
            ready[app.compose_id] = fut.result()

    def _git_auth_probe(self, ctx: DoctorContext, app) -> CheckResult:
        try:
            ctx.auth.test(app.name, quiet=True)
        except RuntimeError as exc:
            return self._git_auth_failed(app, exc)
        return CheckResult(app.compose_id, "auth", "ok", "deploy key can git ls-remote")

    @staticmethod
    def auth_deploy_key_fix(service: str, repo_url: str) -> str:
        """Operator Fix CTA when a deploy key cannot ``git ls-remote``."""
        urls = SshGitUrls()
        try:
            parsed = urls.parse(repo_url)
            host = urls.real_git_host(service, parsed.host)
        except ValueError:
            return AppChecks._auth_fix_generic(service)
        return AppChecks._auth_fix_for_host(service, host, parsed.path)

    @staticmethod
    def _auth_fix_generic(service: str) -> str:
        return (
            f"run `raft auth show {service}` and paste Title + Key "
            f"as a read-only deploy key on the git host, "
            f"then `raft auth test {service}`"
        )

    @staticmethod
    def _auth_fix_for_host(service: str, host: str, repo_path: str) -> str:
        if host == "github.com":
            url = f"https://github.com/{repo_path}/settings/keys/new"
            return (
                f"run `raft auth show {service}` and paste Title + Key at {url} "
                f"(Allow read-only access), then `raft auth test {service}`"
            )
        return (
            f"run `raft auth show {service}` and paste Title + Key as a "
            f"read-only deploy key for {repo_path} on {host}, "
            f"then `raft auth test {service}`"
        )

    def _check_app(
        self, ctx: DoctorContext, app, images: dict, git_auth: dict
    ) -> list[CheckResult]:
        dest = app.abs_path(ctx.stack.root)
        if app.source == "local":
            return self._local_app(ctx, app, dest)
        if app.source == "docker":
            return self._docker_app(ctx, app, images)
        return self._git_app(ctx, app, dest, git_auth)

    def _local_app(self, ctx: DoctorContext, app, dest) -> list[CheckResult]:
        if dest.is_dir():
            return [
                CheckResult(app.compose_id, "sync", "ok", f"local path {app.path}"),
                *self._contract(ctx, app),
            ]
        return [
            CheckResult(
                app.compose_id,
                "sync",
                "fail",
                f"local path missing: {dest}",
                fix=f"create {app.path} or fix applied App registry",
            )
        ]

    def _docker_app(self, ctx: DoctorContext, app, images: dict) -> list[CheckResult]:
        return [
            self._docker_image_result(app, images),
            *self._contract(ctx, app),
            self._docker_auth_result(ctx, app),
        ]

    def _docker_image_result(self, app, images: dict[str, bool]) -> CheckResult:
        pin = app.compose_pin_image
        if images.get(pin):
            return CheckResult(app.compose_id, "sync", "ok", f"docker image present: {pin}")
        return self._docker_image_missing(app, pin)

    @staticmethod
    def _docker_image_missing(app, pin: str) -> CheckResult:
        return CheckResult(
            app.compose_id,
            "sync",
            "fail",
            f"docker image missing locally: {pin}",
            fix=RegistryMessages.missing_image_doctor_fix(pin, app=app.name, repo=app.repo),
        )

    @staticmethod
    def _docker_auth_result(ctx: DoctorContext, app) -> CheckResult:
        cid = app.compose_id
        if not app.repo:
            return CheckResult(
                cid, "auth", "ok", "n/a (no git repo on App; registry auth is docker login)"
            )
        if ctx.auth.is_configured(app.name):
            return CheckResult(
                cid, "auth", "ok", "deploy key present (optional checkout + GHCR pull separate)"
            )
        return CheckResult(
            cid,
            "auth",
            "warn",
            "no deploy key (optional git checkout for docker source)",
            fix=f"raft auth setup {app.name}",
        )

    def _git_app(self, ctx: DoctorContext, app, dest, git_auth: dict) -> list[CheckResult]:
        return [git_auth[app.compose_id], *self._git_sync_results(ctx, app, dest)]

    @staticmethod
    def _git_auth_unconfigured(app) -> CheckResult:
        return CheckResult(
            app.compose_id,
            "auth",
            "fail",
            "no local deploy key",
            fix=f"raft auth setup {app.name}",
        )

    @staticmethod
    def _git_auth_failed(app, exc: RuntimeError) -> CheckResult:
        return CheckResult(
            app.compose_id,
            "auth",
            "fail",
            str(exc).splitlines()[0],
            fix=AppChecks.auth_deploy_key_fix(app.name, app.repo or ""),
        )

    def _git_sync_results(self, ctx: DoctorContext, app, dest) -> list[CheckResult]:
        missing = self._git_checkout_missing(app, dest)
        if missing is not None:
            return missing
        return [
            CheckResult(app.compose_id, "sync", "ok", f"git checkout at {app.path}"),
            *self._contract(ctx, app),
        ]

    @staticmethod
    def _git_checkout_missing(app, dest) -> Optional[list[CheckResult]]:
        if not dest.exists():
            detail, fix = f"checkout missing: {dest}", f"raft sync {app.name}"
            return [CheckResult(app.compose_id, "sync", "fail", detail, fix=fix)]
        if not (dest / ".git").is_dir():
            detail = f"{app.path} exists but is not a git checkout"
            fix = f"move it aside, then `raft sync {app.name}`"
            return [CheckResult(app.compose_id, "sync", "fail", detail, fix=fix)]
        return None

    def _contract(self, ctx: DoctorContext, app) -> list[CheckResult]:
        path = AppRegistry(ctx.stack.root).path_for(app.name)
        if not path.is_file():
            return [
                self._contract_fail(
                    app,
                    f"missing applied manifest {path.relative_to(ctx.stack.root)}",
                    "raft apply --file path/to/app.yaml   # or --git <repo>",
                )
            ]
        try:
            ctx.stack.contract_for(app)
        except (ValueError, FileNotFoundError, OperatorError) as exc:
            return [
                self._contract_fail(
                    app,
                    str(exc).splitlines()[0],
                    "fix the applied manifest or re-apply",
                )
            ]
        return [CheckResult(app.compose_id, "contract", "ok", path.as_posix())]

    @staticmethod
    def _contract_fail(app, detail: str, fix: str) -> CheckResult:
        return CheckResult(app.compose_id, "contract", "fail", detail, fix=fix)


def _docker_pins(ctx: DoctorContext) -> list[str]:
    pins = [app.compose_pin_image for app in ctx.stack.apps if app.source == "docker"]
    return list(dict.fromkeys(pins))


def _inspect_images(ctx: DoctorContext, pins: list[str]):
    return ctx.docker.sh.docker(
        "image",
        "inspect",
        "-f",
        "{{.Id}}",
        *pins,
        check=False,
        capture=True,
    )


def _present_pins(pins: list[str], probed) -> set[str]:
    if _inspect_succeeded(probed):
        return set(pins)
    return _present_after_partial(pins, probed)


def _inspect_succeeded(probed) -> bool:
    return probed.returncode == 0 and bool((probed.stdout or "").strip())


def _present_after_partial(pins: list[str], probed) -> set[str]:
    if not (probed.stdout or "").strip():
        return set()
    missing = _missing_image_names(probed.stderr or "", pins)
    if not missing:
        return set()
    return {pin for pin in pins if pin not in missing}


def _missing_image_names(stderr: str, pins: list[str]) -> set[str]:
    known = set(pins)
    return {name for name in _image_names(stderr) if name in known}


def _image_names(stderr: str) -> list[str]:
    return [match.group(1).strip("'\"") for match in _NO_SUCH_IMAGE.finditer(stderr)]


def _submit_git_auth(probe, ctx: DoctorContext, pending: list) -> list:
    with ThreadPoolExecutor(max_workers=len(pending)) as pool:
        return [pool.submit(probe, ctx, app) for app in pending]
