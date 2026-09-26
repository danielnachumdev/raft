"""Per-app sync / auth / contract checks."""

from __future__ import annotations

from raft.errors import OperatorError, missing_image_doctor_fix

from .....models.registry import AppRegistry
from ....auth.urls import parse_ssh_git_url, real_git_host
from ..context import DoctorContext
from ..models import CheckResult


def auth_deploy_key_fix(service: str, repo_url: str) -> str:
    try:
        parsed = parse_ssh_git_url(repo_url)
        host = real_git_host(service, parsed.host)
    except ValueError:
        return (
            f"run `raft auth show {service}` and paste Title + Key "
            f"as a read-only deploy key on the git host, "
            f"then `raft auth test {service}`"
        )
    if host == "github.com":
        url = f"https://github.com/{parsed.path}/settings/keys/new"
        return (
            f"run `raft auth show {service}` and paste Title + Key at {url} "
            f"(Allow read-only access), then `raft auth test {service}`"
        )
    return (
        f"run `raft auth show {service}` and paste Title + Key as a "
        f"read-only deploy key for {parsed.path} on {host}, "
        f"then `raft auth test {service}`"
    )


class AppChecks:
    name = "apps"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            results.extend(self._check_app(ctx, app))
        return results

    def _check_app(self, ctx: DoctorContext, app) -> list[CheckResult]:
        dest = app.abs_path(ctx.stack.root)
        if app.source == "local":
            return self._local_app(ctx, app, dest)
        if app.source == "docker":
            return self._docker_app(ctx, app)
        return self._git_app(ctx, app, dest)

    def _local_app(self, ctx: DoctorContext, app, dest) -> list[CheckResult]:
        if dest.is_dir():
            return [
                CheckResult(app.compose_id, "sync", "ok", f"local path {app.path}"),
                *self._contract(ctx, app),
            ]
        return [CheckResult(
            app.compose_id, "sync", "fail", f"local path missing: {dest}",
            fix=f"create {app.path} or fix applied App registry",
        )]

    def _docker_app(self, ctx: DoctorContext, app) -> list[CheckResult]:
        return [
            self._docker_image_result(ctx, app),
            *self._contract(ctx, app),
            self._docker_auth_result(ctx, app),
        ]

    def _docker_image_result(self, ctx: DoctorContext, app) -> CheckResult:
        pin = app.compose_pin_image
        probed = ctx.docker.sh.docker(
            "image", "inspect", "-f", "{{.Id}}", pin, check=False, capture=True
        )
        if probed.returncode == 0 and (probed.stdout or "").strip():
            return CheckResult(app.compose_id, "sync", "ok", f"docker image present: {pin}")
        return CheckResult(
            app.compose_id, "sync", "fail", f"docker image missing locally: {pin}",
            fix=missing_image_doctor_fix(pin, app=app.name, repo=app.repo),
        )

    @staticmethod
    def _docker_auth_result(ctx: DoctorContext, app) -> CheckResult:
        if not app.repo:
            return CheckResult(
                app.compose_id, "auth", "ok",
                "n/a (no git repo on App; registry auth is docker login)",
            )
        if ctx.auth.is_configured(app.name):
            return CheckResult(
                app.compose_id, "auth", "ok",
                "deploy key present (optional checkout + GHCR pull separate)",
            )
        return CheckResult(
            app.compose_id, "auth", "warn",
            "no deploy key (optional git checkout for docker source)",
            fix=f"raft auth setup {app.name}",
        )

    def _git_app(self, ctx: DoctorContext, app, dest) -> list[CheckResult]:
        return [self._git_auth_result(ctx, app), *self._git_sync_results(ctx, app, dest)]

    def _git_auth_result(self, ctx: DoctorContext, app) -> CheckResult:
        if not ctx.auth.is_configured(app.name):
            return CheckResult(
                app.compose_id, "auth", "fail", "no local deploy key",
                fix=f"raft auth setup {app.name}",
            )
        try:
            ctx.auth.test(app.name, quiet=True)
            return CheckResult(app.compose_id, "auth", "ok", "deploy key can git ls-remote")
        except RuntimeError as exc:
            return CheckResult(
                app.compose_id, "auth", "fail", str(exc).splitlines()[0],
                fix=auth_deploy_key_fix(app.name, app.repo or ""),
            )

    def _git_sync_results(self, ctx: DoctorContext, app, dest) -> list[CheckResult]:
        if not dest.exists():
            return [CheckResult(
                app.compose_id, "sync", "fail", f"checkout missing: {dest}",
                fix=f"raft sync {app.name}",
            )]
        if not (dest / ".git").is_dir():
            return [CheckResult(
                app.compose_id, "sync", "fail",
                f"{app.path} exists but is not a git checkout",
                fix=f"move it aside, then `raft sync {app.name}`",
            )]
        return [
            CheckResult(app.compose_id, "sync", "ok", f"git checkout at {app.path}"),
            *self._contract(ctx, app),
        ]

    def _contract(self, ctx: DoctorContext, app) -> list[CheckResult]:
        path = AppRegistry(ctx.stack.root).path_for(app.name)
        if not path.is_file():
            return [CheckResult(
                app.compose_id, "contract", "fail",
                f"missing applied manifest {path.relative_to(ctx.stack.root)}",
                fix="raft apply --file path/to/app.yaml   # or --git <repo>",
            )]
        try:
            ctx.stack.contract_for(app)
        except (ValueError, FileNotFoundError, OperatorError) as exc:
            return [CheckResult(
                app.compose_id, "contract", "fail", str(exc).splitlines()[0],
                fix="fix the applied manifest or re-apply",
            )]
        return [CheckResult(app.compose_id, "contract", "ok", path.as_posix())]
