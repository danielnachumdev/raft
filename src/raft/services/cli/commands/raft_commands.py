"""Fire root component (`raft` top-level commands)."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Union

from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.ui import OperatorSay

from ..utils.deps import (
    AppApply,
    Doctor,
    HostLogging,
    Logs,
    Orchestrator,
    Purge,
    SelfUpdate,
    Serve,
    ServiceActions,
    SettingsLoader,
    Status,
    Uninstall,
    load_stack,
)
from .alerts import AlertsCLI
from .apply_env_cli import CONTROL_PLANE_REDEPLOY, ApplyEnvCli
from .auth import AuthCLI
from .db import DbCLI
from .events import EventsCLI
from .firewall import FirewallCLI
from .get import GetCLI
from .github import GithubCLI
from .http_requests import HttpRequestsCLI
from .metrics import MetricsCLI
from .notifications import NotificationsCLI

logger = logging.getLogger(__name__)


class RaftCLICommands:
    """raft — low-budget single-VPS orchestrator (apply App manifests, sync, redeploy).

    ``apply``: deploy on by default; preprocess is ``${{ if }}`` then ``${VAR}``
    (``--env`` / ``--env-file``, not durable secrets). Durable secrets via
    ``spec.envFile`` → ``~/.raft/services/<name>/secrets/env`` (0700/0600);
    never bake into git / ``spec.env`` / ``--env``. Workers: ``ports: []``,
    ``readiness: none``, ``tls: off``, no ``spec.scaling``.
    """

    def __init__(self) -> None:
        self._stack = load_stack()
        config = SettingsLoader().load(self._stack.root)
        log_file = HostLogging().configure(self._stack.root, config)
        logger.debug("config loaded; log_file=%s", log_file)
        self.auth = AuthCLI(self._stack)
        self.alerts = AlertsCLI(self._stack)
        self.firewall = FirewallCLI(self._stack)
        self.notifications = NotificationsCLI(self._stack)
        self.http_requests = HttpRequestsCLI(self._stack)
        self.metrics = MetricsCLI(self._stack)
        self.github = GithubCLI(self._stack)
        self.events = EventsCLI(self._stack)
        self.db = DbCLI(self._stack)

    @property
    def _app_names(self) -> list[str]:
        return [a.name for a in self._stack.apps]

    @property
    def _known(self) -> str:
        names = self._app_names
        return ", ".join(names) if names else "(none applied — use raft apply)"

    def apply(
        self,
        file: Optional[str] = None,
        git: Optional[str] = None,
        ref: Optional[str] = None,
        no_deploy: bool = False,
        force_sync: bool = False,
        env_file: Optional[str] = None,
        env: Optional[Union[str, Sequence[str]]] = None,
    ) -> None:
        """Register an App from ``--file`` or ``--git``; preprocess, then deploy."""
        apply_env = ApplyEnvCli.build(env_file=env_file, env=env)
        self._apply_source(
            file=file,
            git=git,
            ref=ref,
            deploy=not no_deploy,
            force_sync=force_sync,
            env=apply_env,
        )

    def _apply_source(
        self,
        *,
        file: Optional[str],
        git: Optional[str],
        ref: Optional[str],
        deploy: bool,
        force_sync: bool,
        env: dict[str, str],
    ) -> None:
        applier = AppApply(self._stack)
        if file is not None:
            applier.apply_file(
                Path(file), ref_override=ref, deploy=deploy, force_sync=force_sync, env=env
            )
            return
        if git:
            applier.apply_git(
                git, ref=ref or "main", deploy=deploy, force_sync=force_sync, env=env
            )
            return
        raise DomainErrors.apply_requires_source()

    def get(
        self,
        resource: str,
        name: Optional[str] = None,
        group: Optional[str] = None,
    ) -> None:
        """Show applied resources (e.g. get apps, get app NAME, get apps --group=demo)."""
        getter = GetCLI(self._stack)
        if resource == "apps":
            getter.apps(group=group)
            return
        if resource == "app":
            if not name:
                raise SystemExit("get app requires a name")
            getter.app(name)
            return
        raise SystemExit(f"unknown resource {resource!r} (try: apps, app)")

    def delete(self, resource: str, name: Optional[str] = None) -> None:
        """Remove applied resources (e.g. delete app NAME)."""
        if resource == "app":
            if not name:
                raise SystemExit("delete app requires a name")
            AppApply(self._stack).delete(name)
            return
        raise SystemExit(f"unknown resource {resource!r} (try: app)")

    def up(self, name: Optional[str] = None, no_deps: bool = False) -> None:
        """Bring the stack up, or one Compose service when ``NAME`` is given."""
        if name is None:
            if no_deps:
                raise OperatorError(
                    "`--no-deps` requires a service name.\n"
                    "Fix: raft up NAME --no-deps",
                    has_fix=False,
                )
            Orchestrator(self._stack).up()
            return
        result = ServiceActions(self._stack).up(name, no_deps=no_deps)
        self._say_up_result(result)

    def down(self, name: Optional[str] = None) -> None:
        """Tear the stack down, or bring one Compose service down when ``NAME`` is given."""
        if name is None:
            Orchestrator(self._stack).down()
            return
        result = ServiceActions(self._stack).down(name)
        OperatorSay.say(f"Brought down {result['service']}.")

    def _say_up_result(self, result: Dict[str, Any]) -> None:
        if result.get("no_deps"):
            OperatorSay.say("Skipping dependsOn (--no-deps).")
        for dep in result.get("started_deps") or ():
            OperatorSay.say(f"Bringing up dependency {dep}…")
            OperatorSay.say(f"Brought up {dep}.")
        OperatorSay.say(f"Brought up {result['service']}.")

    def render(self) -> None:
        """Generate Compose/nginx from ~/.raft/services/*/app.yaml."""
        Orchestrator(self._stack).render()

    def doctor(self, name: Optional[str] = None) -> None:
        """Check docker, auth, sync, upstreams, and stack status; print fixes."""
        code = Doctor(self._stack).report(app_name=name)
        if code:
            raise SystemExit(code)

    def status(self, json: bool = False, live: bool = False) -> None:
        """Show host and container resource usage (point-in-time snapshot)."""
        Status(self._stack).report(as_json=json, live=live)

    def serve(self, port: int = 8787, stop: bool = False) -> None:
        """Start a localhost-only SSR UI (``127.0.0.1``; ``--stop`` to terminate)."""
        serve = Serve(self._stack)
        if stop:
            serve.stop(port=port)
            return
        serve.run(port=port)

    def logs(
        self,
        *services: str,
        tail: int = 100,
        follow: bool = False,
    ) -> None:
        """Show container stdout/stderr for apps or edge services."""
        Logs(self._stack).show(*services, tail=tail, follow=follow)

    def purge(self) -> None:
        """Remove unused Docker images plus build cache."""
        Purge(self._stack).run()

    def update(self, ref: Optional[str] = None) -> None:
        """Re-install raft from GitHub (latest Release, or ``--ref``)."""
        SelfUpdate(self._stack).run(ref=ref)

    def uninstall(self, yes: bool = False, uv: bool = False) -> None:
        """Remove raft from this machine (requires ``--yes``)."""
        Uninstall(self._stack).run(yes=yes, uv=uv)

    def sync(
        self,
        *services: str,
        ref: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """Clone/update sources for applied apps."""
        names = list(services) if services else None
        if names:
            unknown = [n for n in names if n not in self._app_names]
            if unknown:
                raise OperatorError(
                    f"unknown service(s): {', '.join(unknown)} (known: {self._known}).\n"
                    f"Fix: raft get apps"
                )
        Orchestrator(self._stack).sync(names, ref_override=ref, force=force)

    def redeploy(
        self,
        app: Optional[str] = None,
        ref: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
        """Redeploy one running app, router, gate, controller, or dashboard."""
        name = (app or "").strip()
        if not name:
            raise DomainErrors.redeploy_requires_app()
        if name in CONTROL_PLANE_REDEPLOY:
            result = ServiceActions(self._stack).redeploy(name)
            if not result.get("started"):
                OperatorSay.say(f"Redeployed {result['service']}.")
            return
        if name not in self._app_names:
            raise DomainErrors.unknown_app(name, self._known)
        Orchestrator(self._stack).redeploy_app(
            name, ref_override=ref, force_sync=force_sync
        )
