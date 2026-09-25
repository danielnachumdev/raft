"""Fire root component (`raft` top-level commands)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence, Union

from raft.errors import OperatorError, apply_requires_source, redeploy_requires_app, unknown_app
from raft.services.manifest_env import ApplyEnvSources

from . import delete as delete_cmd
from . import deps
from . import get as get_cmd
from .argv import ApplyEnvOverrides
from .auth import AuthCLI
from .gate import GateCLI
logger = logging.getLogger(__name__)


class RaftCLI:
    """raft — low-budget single-VPS orchestrator (apply App manifests, sync, redeploy)."""

    def __init__(self) -> None:
        self._stack = deps.load_stack()
        config = deps.load_config(self._stack.root)
        log_file = deps.setup_logging(self._stack.root, config)
        logger.debug("config loaded; log_file=%s", log_file)
        self.auth = AuthCLI(self._stack)
        self.gate = GateCLI(self._stack)

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
        """Register an App manifest on this VPS (from file or git URL).

        ``--env-file`` / repeatable ``--env KEY=VALUE`` expand ``${VAR}``
        placeholders in the App manifest text (before YAML parse). They do not
        inject Compose env by themselves — bridge CI values into the container
        by templating ``spec.env`` / ``spec.envFile``::

            env:
              DATABASE_URL: ${CI_DATABASE_URL}   # Docker name ← CI template name

        Precedence: process env → ``--env-file`` → ``--env`` (later wins).
        Merging happens here once; ``AppApply`` receives only the finalized map.
        """
        applier = deps.AppApply(self._stack)
        deploy = not no_deploy
        apply_env = self._build_apply_env(env_file=env_file, env=env)
        if file is not None:
            applier.apply_file(
                Path(file),
                ref_override=ref,
                deploy=deploy,
                force_sync=force_sync,
                env=apply_env,
            )
            return
        if git:
            applier.apply_git(
                git,
                ref=ref or "main",
                deploy=deploy,
                force_sync=force_sync,
                env=apply_env,
            )
            return
        raise apply_requires_source()

    def get(
        self,
        resource: str,
        name: Optional[str] = None,
        group: Optional[str] = None,
    ) -> None:
        """Show applied resources (e.g. get apps, get app NAME, get apps --group=demo)."""
        if resource == "apps":
            get_cmd.get_apps(self._stack, group=group)
            return
        if resource == "app":
            if not name:
                raise SystemExit("get app requires a name")
            get_cmd.get_app(self._stack, name)
            return
        raise SystemExit(f"unknown resource {resource!r} (try: apps, app)")

    def delete(self, resource: str, name: Optional[str] = None) -> None:
        """Remove applied resources (e.g. delete app NAME)."""
        if resource == "app":
            if not name:
                raise SystemExit("delete app requires a name")
            delete_cmd.delete_app(self._stack, name)
            return
        raise SystemExit(f"unknown resource {resource!r} (try: app)")

    def up(self) -> None:
        """Sync applied apps, then bring the stack up."""
        deps.Orchestrator(self._stack).start()

    def down(self) -> None:
        """Stop and remove the stack."""
        deps.Orchestrator(self._stack).stop()

    def render(self) -> None:
        """Generate Compose/nginx from ~/.raft/state/apps/*.yaml."""
        deps.Orchestrator(self._stack).render()

    def doctor(self) -> None:
        """Check docker, auth, sync, upstreams, and stack status; print fixes."""
        code = deps.Doctor(self._stack).report()
        if code:
            raise SystemExit(code)

    def status(self, json: bool = False, live: bool = False) -> None:
        """Show host and container resource usage (point-in-time snapshot).

        Pass ``--json`` for a machine-readable snapshot (basis for future scaling).
        Pass ``--live`` to clear and refresh the human table until Ctrl+C
        (not combinable with ``--json``).
        """
        deps.Stats(self._stack).report(as_json=json, live=live)

    def update(self) -> None:
        """Re-install raft from GitHub (re-run install.sh / uv tool install)."""
        deps.SelfUpdate(self._stack).run()

    def uninstall(self, yes: bool = False, uv: bool = False) -> None:
        """Remove raft from this machine (stack, ~/.raft, deploy keys, uv tool).

        Requires ``--yes``. Pass ``--uv`` to also remove the ``uv`` installer
        (left installed by default — other tools may need it). Does not revoke
        git-host deploy keys or CDN certs.
        """
        deps.Uninstall(self._stack).run(yes=yes, uv=uv)

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
        deps.Orchestrator(self._stack).sync(names, ref_override=ref, force=force)

    def redeploy(
        self,
        app: Optional[str] = None,
        ref: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
        """Redeploy one running app, or recreate inner router."""
        name = (app or "").strip()
        if not name:
            raise redeploy_requires_app()
        orch = deps.Orchestrator(self._stack)
        if name == "router":
            orch.redeploy_router()
            return
        if name not in self._app_names:
            raise unknown_app(name, self._known)
        orch.redeploy_app(name, ref_override=ref, force_sync=force_sync)

    @staticmethod
    def _build_apply_env(
        *,
        env_file: Optional[str],
        env: Optional[Union[str, Sequence[str]]],
    ) -> dict[str, str]:
        """Merge process → ``--env-file`` → peeled/Fire ``--env`` once for apply."""
        peeled = ApplyEnvOverrides.get()
        overrides: Union[None, str, Sequence[str]] = list(peeled) if peeled else env
        return ApplyEnvSources.from_apply(
            env_file=Path(env_file) if env_file else None,
            env_overrides=overrides,
        ).build()
