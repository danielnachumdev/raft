"""Environment diagnostics for operators (`raft doctor`)."""

from __future__ import annotations

import shutil
import socket
import sys
from dataclasses import dataclass
from typing import Literal, Optional, TextIO

from ..adapters import DockerStack, Shell
from ..config.settings import load_config
from ..models import Stack
from ..models.manifest import registry_path
from ..ui import BOLD, CYAN, DIM, GREEN, RED, YELLOW, paint, want_color
from .auth import GitAuthManager, parse_ssh_git_url, real_git_host
from .certs import missing_origin_certs
from .registry import missing_image_doctor_fix

Status = Literal["ok", "warn", "fail"]

INFRA = "infra"

_STATUS_LABEL = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}

_STATUS_COLOR = {"ok": GREEN, "warn": YELLOW, "fail": RED}


@dataclass(frozen=True)
class CheckResult:
    service: str
    check: str
    status: Status
    detail: str
    fix: str = ""


class Doctor:
    def __init__(
        self,
        stack: Stack,
        *,
        shell: Optional[Shell] = None,
        auth: Optional[GitAuthManager] = None,
        docker: Optional[DockerStack] = None,
    ) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)
        self.auth = auth or GitAuthManager(stack, self.sh)
        self.docker = docker or DockerStack(stack, self.sh)

    def run(self) -> list[CheckResult]:
        checks: list[CheckResult] = []
        checks.append(self._check_compose_file())
        checks.append(self._check_generated())
        checks.extend(self._check_docker())
        checks.extend(self._check_apps())
        checks.extend(self._check_upstreams())
        checks.extend(self._check_certs())
        checks.extend(self._check_stack_running())
        checks.extend(self._check_edge_listeners())
        checks.extend(self._check_gate_drift())
        return checks

    def report(
        self,
        results: Optional[list[CheckResult]] = None,
        *,
        out: Optional[TextIO] = None,
        color: Optional[bool] = None,
    ) -> int:
        stream = out if out is not None else sys.stdout
        use_color = want_color(stream, color)
        results = results if results is not None else self.run()

        by_service: dict[str, list[CheckResult]] = {}
        for r in results:
            by_service.setdefault(r.service, []).append(r)

        preferred = [INFRA, *[a.name for a in self.stack.apps]]
        ordered = [s for s in preferred if s in by_service]
        ordered.extend(s for s in by_service if s not in preferred)

        def tint(text: str, *codes: str) -> str:
            return paint(text, *codes, color=use_color)

        issues = [r for r in results if r.status != "ok"]
        check_width = max((len(r.check) for r in issues), default=0)

        fails = sum(1 for r in results if r.status == "fail")
        warns = sum(1 for r in results if r.status == "warn")
        first_block = True

        for service in ordered:
            items = by_service[service]
            bad = [r for r in items if r.status != "ok"]

            if not first_block:
                print(file=stream)
            first_block = False

            # Service name is always the top-level heading (column 0).
            print(tint(service, BOLD, CYAN), file=stream)

            if not bad:
                label = tint(_STATUS_LABEL["ok"], _STATUS_COLOR["ok"], BOLD)
                print(f"  {label}", file=stream)
                continue

            for r in bad:
                status = tint(
                    _STATUS_LABEL[r.status],
                    _STATUS_COLOR[r.status],
                    BOLD,
                )
                print(f"  {status}  {r.check:<{check_width}}", file=stream)
                # Detail + fix are nested notes (deeper indent, not status-column).
                print(f"    {r.detail}", file=stream)
                if r.fix:
                    fix_lines = r.fix.splitlines() or [""]
                    print(f"    {tint('fix → ' + fix_lines[0], DIM, CYAN)}", file=stream)
                    for line in fix_lines[1:]:
                        print(f"           {tint(line, DIM, CYAN)}", file=stream)

        print(file=stream)
        if fails:
            print(tint(f"{fails} check(s) failed", RED, BOLD), file=stream)
            return 1
        if warns:
            print(tint(f"ok ({warns} warning(s))", YELLOW), file=stream)
        else:
            print(tint("all checks passed", GREEN, BOLD), file=stream)
        return 0

    @staticmethod
    def _auth_deploy_key_fix(service: str, repo_url: str) -> str:
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

    def _check_compose_file(self) -> CheckResult:
        path = self.stack.root / "compose.yaml"
        if path.is_file():
            return CheckResult(INFRA, "compose.yaml", "ok", str(path))
        return CheckResult(
            INFRA,
            "compose.yaml",
            "fail",
            f"missing at {path}",
            fix="run `raft render` (syncs Compose templates into ~/.raft)",
        )

    def _check_generated(self) -> CheckResult:
        path = self.stack.root / "generated" / "compose.apps.yaml"
        if path.is_file():
            return CheckResult(INFRA, "generated", "ok", str(path))
        return CheckResult(
            INFRA,
            "generated",
            "fail",
            "missing generated/compose.apps.yaml",
            fix="raft sync   # or: raft render",
        )

    def _check_docker(self) -> list[CheckResult]:
        out: list[CheckResult] = []
        if not shutil.which("docker"):
            out.append(
                CheckResult(
                    INFRA,
                    "docker",
                    "fail",
                    "docker CLI not found on PATH",
                    fix="install Docker Engine and ensure `docker` is on PATH",
                )
            )
            return out
        probe = self.sh.run(["docker", "info"], check=False, capture=True)
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout or "docker info failed").strip().splitlines()
            brief = detail[-1] if detail else "docker info failed"
            out.append(
                CheckResult(
                    INFRA,
                    "docker",
                    "fail",
                    brief,
                    fix="start the Docker daemon (and join the `docker` group if permission denied)",
                )
            )
            return out
        out.append(CheckResult(INFRA, "docker", "ok", "CLI and daemon reachable"))
        return out

    def _check_apps(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        for app in self.stack.apps:
            dest = app.abs_path(self.stack.root)
            if app.source == "local":
                if dest.is_dir():
                    results.append(CheckResult(app.name, "sync", "ok", f"local path {app.path}"))
                    results.extend(self._check_contract(app))
                else:
                    results.append(
                        CheckResult(
                            app.name,
                            "sync",
                            "fail",
                            f"local path missing: {dest}",
                            fix=f"create {app.path} or fix applied App registry",
                        )
                    )
                continue

            if app.source == "docker":
                pin = app.compose_pin_image
                probed = self.docker.sh.docker(
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
                            app.name,
                            "sync",
                            "ok",
                            f"docker image present: {pin}",
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            app.name,
                            "sync",
                            "fail",
                            f"docker image missing locally: {pin}",
                            fix=missing_image_doctor_fix(
                                pin, app=app.name, repo=app.repo
                            ),
                        )
                    )
                results.extend(self._check_contract(app))
                if app.repo:
                    if not self.auth.is_configured(app.name):
                        results.append(
                            CheckResult(
                                app.name,
                                "auth",
                                "warn",
                                "no deploy key (optional git checkout for docker source)",
                                fix=f"raft auth setup {app.name}",
                            )
                        )
                    else:
                        results.append(
                            CheckResult(
                                app.name,
                                "auth",
                                "ok",
                                "deploy key present (optional checkout + GHCR pull separate)",
                            )
                        )
                else:
                    results.append(
                        CheckResult(
                            app.name,
                            "auth",
                            "ok",
                            "n/a (no git repo on App; registry auth is docker login)",
                        )
                    )
                continue

            if not self.auth.is_configured(app.name):
                results.append(
                    CheckResult(
                        app.name,
                        "auth",
                        "fail",
                        "no local deploy key",
                        fix=f"raft auth setup {app.name}",
                    )
                )
            else:
                try:
                    self.auth.test(app.name, quiet=True)
                    results.append(
                        CheckResult(
                            app.name,
                            "auth",
                            "ok",
                            "deploy key can git ls-remote",
                        )
                    )
                except RuntimeError as exc:
                    results.append(
                        CheckResult(
                            app.name,
                            "auth",
                            "fail",
                            str(exc).splitlines()[0],
                            fix=self._auth_deploy_key_fix(app.name, app.repo or ""),
                        )
                    )

            if not dest.exists():
                results.append(
                    CheckResult(
                        app.name,
                        "sync",
                        "fail",
                        f"checkout missing: {dest}",
                        fix=f"raft sync {app.name}",
                    )
                )
            elif not (dest / ".git").is_dir():
                results.append(
                    CheckResult(
                        app.name,
                        "sync",
                        "fail",
                        f"{app.path} exists but is not a git checkout",
                        fix=f"move it aside, then `raft sync {app.name}`",
                    )
                )
            else:
                results.append(CheckResult(app.name, "sync", "ok", f"git checkout at {app.path}"))
                results.extend(self._check_contract(app))
        return results

    def _check_contract(self, app) -> list[CheckResult]:
        path = registry_path(self.stack.root, app.name)
        if not path.is_file():
            return [
                CheckResult(
                    app.name,
                    "contract",
                    "fail",
                    f"missing applied manifest {path.relative_to(self.stack.root)}",
                    fix=f"raft apply --file path/to/app.yaml   # or --git <repo>",
                )
            ]
        try:
            self.stack.contract_for(app)
        except (ValueError, FileNotFoundError) as exc:
            return [
                CheckResult(
                    app.name,
                    "contract",
                    "fail",
                    str(exc).splitlines()[0],
                    fix="fix the applied manifest or re-apply",
                )
            ]
        return [CheckResult(app.name, "contract", "ok", path.as_posix())]

    def _check_upstreams(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        for app in self.stack.apps:
            try:
                app_spec = self.stack.spec_for(app)
            except (ValueError, FileNotFoundError):
                continue
            http_ports = app_spec.http_ports()
            if not http_ports:
                results.append(
                    CheckResult(
                        app.name,
                        "upstream",
                        "ok",
                        "n/a (no expose=http ports)",
                    )
                )
                continue
            for port in http_ports:
                path = self.stack.upstream_file(app, port)
                if path.is_file():
                    results.append(CheckResult(app.name, "upstream", "ok", str(path.name)))
                else:
                    results.append(
                        CheckResult(
                            app.name,
                            "upstream",
                            "warn",
                            f"missing {path.name}",
                            fix="created automatically on `raft sync` / `raft up`",
                        )
                    )
        return results

    def _check_certs(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        missing_by_name = {m.app_name: m for m in missing_origin_certs(self.stack)}
        for app in self.stack.apps:
            try:
                app_spec = self.stack.spec_for(app)
            except (ValueError, FileNotFoundError):
                continue
            if app_spec.tls != "origin":
                results.append(
                    CheckResult(
                        app.name,
                        "certs",
                        "ok",
                        "n/a (tls: off)",
                    )
                )
                continue
            item = missing_by_name.get(app.name)
            if item is None:
                results.append(
                    CheckResult(
                        app.name,
                        "certs",
                        "ok",
                        f"certs/{app.name}/origin.pem+key",
                    )
                )
                continue
            results.append(
                CheckResult(
                    app.name,
                    "certs",
                    "fail",
                    item.detail,
                    fix=item.fix,
                )
            )
        return results

    def _check_stack_running(self) -> list[CheckResult]:
        if not shutil.which("docker"):
            return [
                CheckResult(
                    INFRA,
                    "stack",
                    "warn",
                    "skipped (docker unavailable)",
                )
            ]
        try:
            running = set(self.docker.running_services())
        except Exception as exc:  # noqa: BLE001
            return [
                CheckResult(
                    INFRA,
                    "stack",
                    "warn",
                    f"could not query compose: {exc}",
                    fix="ensure compose.yaml is valid and docker works",
                )
            ]
        expected = list(self.stack.core_services)
        missing = [s for s in expected if s not in running]
        if not missing:
            return [
                CheckResult(
                    INFRA,
                    "stack",
                    "ok",
                    f"running: {', '.join(expected)}",
                )
            ]
        if not running:
            return [
                CheckResult(
                    INFRA,
                    "stack",
                    "warn",
                    "no core services running",
                    fix="raft up",
                )
            ]
        return [
            CheckResult(
                INFRA,
                "stack",
                "warn",
                f"running {sorted(running)}; missing {missing}",
                fix="raft up   # or redeploy the missing service",
            )
        ]

    def _check_edge_listeners(self) -> list[CheckResult]:
        edge = load_config(self.stack.root).edge
        published = edge.published_ports()
        if not published:
            return [
                CheckResult(
                    INFRA,
                    "edge",
                    "warn",
                    "no edge listeners declared in settings.yaml",
                    fix="set edge.http / edge.https / edge.streams in ~/.raft/settings.yaml",
                )
            ]
        try:
            running = set(self.docker.running_services()) if shutil.which("docker") else set()
        except Exception:  # noqa: BLE001
            running = set()
        gate_up = self.stack.gate in running
        results: list[CheckResult] = []
        for port, protocol in published:
            if protocol != "tcp":
                results.append(
                    CheckResult(
                        INFRA,
                        f"port {port}/{protocol}",
                        "ok",
                        "declared (udp listen not probed)",
                    )
                )
                continue
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                    in_use = True
            except OSError:
                in_use = False
            label = f"port {port}"
            if in_use and gate_up:
                results.append(CheckResult(INFRA, label, "ok", "accepting (gate running)"))
            elif in_use and not gate_up:
                results.append(
                    CheckResult(
                        INFRA,
                        label,
                        "warn",
                        f"something is listening on 127.0.0.1:{port} (gate may fail to bind)",
                        fix="stop the other process, or change edge ports in settings.yaml",
                    )
                )
            elif gate_up:
                results.append(
                    CheckResult(
                        INFRA,
                        label,
                        "warn",
                        f"gate running but nothing accepting on 127.0.0.1:{port}",
                        fix="raft gate recreate   # pick up edge: ports",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        INFRA,
                        label,
                        "ok",
                        f"nothing accepting on 127.0.0.1:{port}",
                    )
                )
        return results

    def _check_gate_drift(self) -> list[CheckResult]:
        if not shutil.which("docker"):
            return []
        try:
            running = set(self.docker.running_services())
        except Exception:  # noqa: BLE001
            return []
        if self.stack.gate not in running:
            return []
        edge = load_config(self.stack.root).edge
        declared = sorted({p for p, _ in edge.published_ports()})
        actual = self.docker.gate_published_ports()
        if not actual:
            return [
                CheckResult(
                    INFRA,
                    "gate ports",
                    "warn",
                    "could not inspect gate published ports",
                    fix="raft gate recreate",
                )
            ]
        if declared == actual:
            return [
                CheckResult(
                    INFRA,
                    "gate ports",
                    "ok",
                    f"match edge: {declared}",
                )
            ]
        return [
            CheckResult(
                INFRA,
                "gate ports",
                "fail",
                f"declared {declared} but gate publishes {actual}",
                fix="raft gate recreate   # Docker binds ports at create time",
            )
        ]
