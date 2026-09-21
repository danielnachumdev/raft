"""Per-app sync / auth / contract checks."""

from __future__ import annotations

from raft.errors import OperatorError, missing_image_doctor_fix

from ....models.manifest import registry_path
from ...auth import parse_ssh_git_url, real_git_host
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
            dest = app.abs_path(ctx.stack.root)
            if app.source == "local":
                if dest.is_dir():
                    results.append(CheckResult(app.compose_id, "sync", "ok", f"local path {app.path}"))
                    results.extend(self._contract(ctx, app))
                else:
                    results.append(
                        CheckResult(app.compose_id,
                            "sync",
                            "fail",
                            f"local path missing: {dest}",
                            fix=f"create {app.path} or fix applied App registry",
                        )
                    )
                continue

            if app.source == "docker":
                results.extend(self._docker_app(ctx, app))
                continue

            results.extend(self._git_app(ctx, app, dest))
        return results

    def _docker_app(self, ctx: DoctorContext, app) -> list[CheckResult]:
        results: list[CheckResult] = []
        pin = app.compose_pin_image
        probed = ctx.docker.sh.docker(
            "image",
            "inspect",
            "-f",
            "{{.Id}}",
            pin,
            check=False,
            capture=True,
        )
        if probed.returncode == 0 and (probed.stdout or "").strip():
            results.append(
                CheckResult(
                    app.compose_id,
                    "sync",
                    "ok",
                    f"docker image present: {pin}",
                )
            )
        else:
            results.append(
                CheckResult(
                    app.compose_id,
                    "sync",
                    "fail",
                    f"docker image missing locally: {pin}",
                    fix=missing_image_doctor_fix(pin, app=app.name, repo=app.repo),
                )
            )
        results.extend(self._contract(ctx, app))
        if app.repo:
            if not ctx.auth.is_configured(app.name):
                results.append(
                    CheckResult(
                        app.compose_id,
                        "auth",
                        "warn",
                        "no deploy key (optional git checkout for docker source)",
                        fix=f"raft auth setup {app.name}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        app.compose_id,
                        "auth",
                        "ok",
                        "deploy key present (optional checkout + GHCR pull separate)",
                    )
                )
        else:
            results.append(
                CheckResult(
                    app.compose_id,
                    "auth",
                    "ok",
                    "n/a (no git repo on App; registry auth is docker login)",
                )
            )
        return results

    def _git_app(self, ctx: DoctorContext, app, dest) -> list[CheckResult]:
        results: list[CheckResult] = []
        if not ctx.auth.is_configured(app.name):
            results.append(
                CheckResult(
                    app.compose_id,
                    "auth",
                    "fail",
                    "no local deploy key",
                    fix=f"raft auth setup {app.name}",
                )
            )
        else:
            try:
                ctx.auth.test(app.name, quiet=True)
                results.append(
                    CheckResult(
                        app.compose_id,
                        "auth",
                        "ok",
                        "deploy key can git ls-remote",
                    )
                )
            except RuntimeError as exc:
                results.append(
                    CheckResult(
                        app.compose_id,
                        "auth",
                        "fail",
                        str(exc).splitlines()[0],
                        fix=auth_deploy_key_fix(app.name, app.repo or ""),
                    )
                )

        if not dest.exists():
            results.append(
                CheckResult(
                    app.compose_id,
                    "sync",
                    "fail",
                    f"checkout missing: {dest}",
                    fix=f"raft sync {app.name}",
                )
            )
        elif not (dest / ".git").is_dir():
            results.append(
                CheckResult(
                    app.compose_id,
                    "sync",
                    "fail",
                    f"{app.path} exists but is not a git checkout",
                    fix=f"move it aside, then `raft sync {app.name}`",
                )
            )
        else:
            results.append(CheckResult(app.compose_id, "sync", "ok", f"git checkout at {app.path}"))
            results.extend(self._contract(ctx, app))
        return results

    def _contract(self, ctx: DoctorContext, app) -> list[CheckResult]:
        path = registry_path(ctx.stack.root, app.name)
        if not path.is_file():
            return [
                CheckResult(
                    app.compose_id,
                    "contract",
                    "fail",
                    f"missing applied manifest {path.relative_to(ctx.stack.root)}",
                    fix="raft apply --file path/to/app.yaml   # or --git <repo>",
                )
            ]
        try:
            ctx.stack.contract_for(app)
        except (ValueError, FileNotFoundError, OperatorError) as exc:
            return [
                CheckResult(
                    app.compose_id,
                    "contract",
                    "fail",
                    str(exc).splitlines()[0],
                    fix="fix the applied manifest or re-apply",
                )
            ]
        return [CheckResult(app.compose_id, "contract", "ok", path.as_posix())]
