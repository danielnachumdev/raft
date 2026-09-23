"""Docker Compose helpers for the compose stack."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Optional, Sequence

from raft.errors import (
    OperatorError,
    append_diagnostics,
    compose_services_from_failure_text,
    format_missing_origin_certs,
    format_service_log_block,
    join_diagnostic_blocks,
    looks_like_missing_origin_cert,
    missing_origin_certs_fallback,
    nginx_rejected,
    nginx_reload_failed,
    prefer_errorish_lines,
    raise_for_compose_failure,
    raise_for_docker_pull_failure,
    run_compose_checked,
    run_docker_checked,
    service_not_running,
    summarize_health_inspect,
)

from ..models.app import COMPOSE_PROJECT, App
from ..models.ports import PortSpec
from ..models.stack import Stack
from ..services.certs import missing_origin_certs
from .shell import Shell

logger = logging.getLogger(__name__)

# Keep OperatorError / doctor messages short but include the fatal line.
_DIAG_LOG_TAIL = 40
_DIAG_MAX_LINES = 16


class DockerStack:
    def __init__(self, stack: Stack, shell: Shell) -> None:
        self.stack = stack
        self.sh = shell

    def start_stack(self) -> None:
        logger.info("compose up -d --build --remove-orphans")
        try:
            run_compose_checked(
                self.sh,
                ("up", "-d", "--build", "--remove-orphans"),
                action="bring the stack up",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc) from exc

    def stop_stack(self) -> None:
        logger.info("compose down --remove-orphans")
        run_compose_checked(
            self.sh,
            ("down", "--remove-orphans"),
            action="bring the stack down",
            stream=True,
        )
        for app in self.stack.apps:
            self.remove_container(app.tmp_container)

    def running_services(self) -> list[str]:
        """Return compose services that are currently running.

        Unknown services (not yet in the rendered compose file) must not raise —
        ``docker compose ps <name>`` exits non-zero when the service is absent.
        """
        running: list[str] = []
        for service in self.stack.core_services:
            result = self.sh.compose(
                "ps",
                "-q",
                "--status",
                "running",
                service,
                capture=True,
                check=False,
            )
            if result.returncode == 0 and (result.stdout or "").strip():
                running.append(service)
        logger.debug("running services: %s", running)
        return running

    def recreate_router(self) -> None:
        logger.info("force-recreate router")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--force-recreate", self.stack.router),
            action="recreate router",
            stream=True,
        )

    def recreate_gate(self) -> None:
        logger.info("force-recreate gate (published edge ports)")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--force-recreate", self.stack.gate),
            action="recreate gate",
            hint="after edge port changes in ~/.raft/settings.yaml",
            stream=True,
        )

    def gate_published_ports(self) -> list[int]:
        try:
            cid = self.service_container_id(self.stack.gate)
        except RuntimeError:
            return []
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{range $p, $conf := .NetworkSettings.Ports}}" "{{if $conf}}{{$p}} {{end}}{{end}}",
            cid,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        ports: list[int] = []
        for token in (result.stdout or "").split():
            # e.g. 80/tcp
            num = token.split("/", 1)[0]
            if num.isdigit():
                ports.append(int(num))
        return sorted(set(ports))

    def rebuild_service(self, service: str) -> None:
        logger.info("rebuild service %s", service)
        try:
            run_compose_checked(
                self.sh,
                ("up", "-d", "--build", "--no-deps", service),
                action=f"rebuild service {service}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=(service,)) from exc

    def recreate_pulled_service(self, app: App, *, pull_ref: str) -> None:
        pin = app.compose_pin_image
        logger.info(
            "pull %s then recreate compose service %s (pin %s)",
            pull_ref,
            app.compose_id,
            pin,
        )
        result = self.sh.docker("pull", pull_ref, capture=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise_for_docker_pull_failure(
                pull_ref, detail=detail, app=app.name, repo=app.repo
            )
        if pull_ref != pin:
            run_docker_checked(
                self.sh,
                ("tag", pull_ref, pin),
                action=f"tag {pull_ref} as {pin}",
            )
        try:
            run_compose_checked(
                self.sh,
                (
                    "up",
                    "-d",
                    "--no-deps",
                    "--no-build",
                    "--force-recreate",
                    app.compose_id,
                ),
                action=f"recreate service {app.compose_id}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(
                exc, services=(app.compose_id,)
            ) from exc

    def service_container_id(self, service: str) -> str:
        result = self.sh.compose("ps", "-q", service, capture=True, check=False)
        if result.returncode != 0:
            exc = subprocess.CalledProcessError(
                result.returncode,
                ["docker", "compose", "ps", "-q", service],
                output=result.stdout,
                stderr=(result.stderr or "").strip(),
            )
            raise_for_compose_failure(exc, action=f"inspect service {service}")
        cid = (result.stdout or "").strip()
        if not cid:
            raise service_not_running(service)
        return cid

    def try_service_container_id(self, service: str) -> Optional[str]:
        """Return the running container id for ``service``, or ``None`` if absent."""
        result = self.sh.compose("ps", "-q", service, capture=True, check=False)
        if result.returncode != 0:
            return None
        cid = (result.stdout or "").strip()
        return cid or None

    def containers_stats(self, container_ids: list[str]) -> dict[str, dict[str, Any]]:
        """One-shot ``docker stats --no-stream`` keyed by container id prefix/full id.

        Returns an empty dict when no ids are given or docker fails.
        """
        if not container_ids:
            return {}
        result = self.sh.docker(
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            *container_ids,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "docker stats failed rc=%s: %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return {}
        by_id: dict[str, dict[str, Any]] = {}
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("skip unparseable docker stats line: %r", line)
                continue
            if not isinstance(row, dict):
                continue
            raw_id = str(row.get("ID") or row.get("Container") or "").strip()
            if not raw_id:
                continue
            by_id[raw_id] = row
            # Compose ps -q may return a full id while stats shortens it.
            for cid in container_ids:
                if cid.startswith(raw_id) or raw_id.startswith(cid):
                    by_id[cid] = row
        return by_id

    def container_inspect_runtime(self, container_id: str) -> Optional[dict[str, Any]]:
        """Status, start time, and HostConfig resource limits for one container."""
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{.State.Status}}|{{.State.StartedAt}}|"
            "{{.HostConfig.NanoCpus}}|{{.HostConfig.Memory}}",
            container_id,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        parts = (result.stdout or "").strip().split("|")
        if len(parts) < 4:
            return None
        status, started_at, nano_raw, mem_raw = parts[0], parts[1], parts[2], parts[3]
        nano_cpus: Optional[int] = None
        memory_bytes: Optional[int] = None
        if nano_raw.isdigit():
            nano_cpus = int(nano_raw)
        if mem_raw.isdigit():
            memory_bytes = int(mem_raw)
        return {
            "status": status or "unknown",
            "started_at": started_at or "",
            "nano_cpus": nano_cpus,
            "memory_bytes": memory_bytes,
        }

    def service_is_ready(self, service: str) -> bool:
        """True when the Compose service is running and healthy (or has no healthcheck).

        Used for ``expose: none`` TCP readiness — those ports are not on the host.
        """
        try:
            cid = self.service_container_id(service)
        except OperatorError:
            return False
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            cid,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return False
        parts = (result.stdout or "").strip().split()
        if not parts or parts[0] != "running":
            return False
        health = parts[1] if len(parts) > 1 else "none"
        ready = health in ("none", "healthy")
        logger.debug("service_is_ready %s -> %s (%s)", service, ready, " ".join(parts))
        return ready

    def container_image_ref(self, container_id: str) -> str:
        try:
            named = run_docker_checked(
                self.sh,
                ("inspect", "-f", "{{.Config.Image}}", container_id),
                action="inspect container image",
            ).stdout.strip()
        except OperatorError:
            named = ""
        if named:
            probed = self.sh.docker(
                "image", "inspect", "-f", "{{.Id}}", named, check=False, capture=True
            )
            if probed.returncode == 0 and probed.stdout.strip():
                return named
        tag = f"{COMPOSE_PROJECT}-snapshot:{container_id[:12]}"
        logger.info("committing container %s as %s", container_id[:12], tag)
        run_docker_checked(
            self.sh,
            ("commit", container_id, tag),
            action="snapshot running container for cutover",
            hint="ensure the service is healthy, then: raft redeploy <app>",
        )
        return tag

    def container_image_id(self, container_id: str) -> str:
        ref = self.container_image_ref(container_id)
        result = run_docker_checked(
            self.sh,
            ("image", "inspect", "-f", "{{.Id}}", ref),
            action="inspect image id",
        )
        return (result.stdout or "").strip() or ref

    def router_network(self) -> str:
        router_id = self.service_container_id(self.stack.router)
        result = run_docker_checked(
            self.sh,
            (
                "inspect",
                "-f",
                "{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}",
                router_id,
            ),
            action="detect compose network",
            hint="raft up / raft doctor",
        )
        networks = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        return networks[0] if networks else f"{COMPOSE_PROJECT}_default"

    def remove_container(self, name: str) -> None:
        logger.debug("remove container %s", name)
        self.sh.docker("rm", "-f", name, check=False, capture=True)

    def run_tmp(
        self,
        *,
        name: str,
        alias: str,
        image: str,
        network: str,
        env_file: Optional[str] = None,
    ) -> None:
        logger.info("run tmp container name=%s alias=%s image=%s", name, alias, image)
        self.remove_container(name)
        args: list[str] = [
            "run",
            "-d",
            "--name",
            name,
            "--network",
            network,
            "--network-alias",
            alias,
            "--restart",
            "no",
        ]
        if env_file:
            args.extend(["--env-file", env_file])
        args.append(image)
        run_docker_checked(
            self.sh,
            tuple(args),
            action=f"start cutover tmp container {name}",
            hint="raft doctor; docker compose ps",
        )

    def router_can_fetch(
        self, hostname: str, *, port: int = 80, path: str = "/"
    ) -> bool:
        fetch_path = path if path.startswith("/") else f"/{path}"
        result = self.sh.compose(
            "exec",
            "-T",
            self.stack.router,
            "wget",
            "-qO-",
            f"http://{hostname}:{port}{fetch_path}",
            check=False,
            capture=True,
        )
        ok = result.returncode == 0
        logger.debug("router_can_fetch %s:%s%s -> %s", hostname, port, fetch_path, ok)
        return ok

    def reload_router_nginx(self) -> None:
        logger.info("nginx -t && reload on router")
        result = self.sh.compose(
            "exec", "-T", self.stack.router, "nginx", "-t", capture=True, check=False
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise nginx_rejected("router", detail)
        reload = self.sh.compose(
            "exec", "-T", self.stack.router, "nginx", "-s", "reload",
            capture=True, check=False,
        )
        if reload.returncode != 0:
            detail = (reload.stderr or reload.stdout or "").strip()
            raise nginx_reload_failed("router", detail)

    def nginx_test_and_reload(self) -> None:
        """Reload router nginx (alias kept for call sites / tests)."""
        self.reload_router_nginx()

    def reload_gate_nginx(self) -> None:
        logger.info("nginx -t && reload on gate")
        result = self.sh.compose(
            "exec", "-T", self.stack.gate, "nginx", "-t", capture=True, check=False
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            blob = f"nginx -t\n{detail}"
            if looks_like_missing_origin_cert(blob):
                missing = missing_origin_certs(self.stack)
                if missing:
                    raise OperatorError(
                        format_missing_origin_certs(
                            missing, include_doctor_footer=False
                        )
                    )
                raise OperatorError(missing_origin_certs_fallback(detail=detail))
            raise nginx_rejected("gate", detail)
        reload = self.sh.compose(
            "exec", "-T", self.stack.gate, "nginx", "-s", "reload",
            capture=True, check=False,
        )
        if reload.returncode != 0:
            detail = (reload.stderr or reload.stdout or "").strip()
            raise nginx_reload_failed("gate", detail)

    def router_sees_upstream_target(
        self,
        app: App,
        target: str,
        port: PortSpec,
    ) -> bool:
        filename = f"{app.name}-{port.name}.conf"
        result = self.sh.compose(
            "exec",
            "-T",
            self.stack.router,
            "grep",
            "-q",
            target,
            f"/etc/nginx/upstreams/{filename}",
            check=False,
            capture=True,
        )
        return result.returncode == 0

    def compose_logs(self, *services: str, tail: int = _DIAG_LOG_TAIL) -> str:
        """Tail recent Compose logs for ``services`` (declarative log relay)."""
        names = [s for s in services if s]
        if not names:
            return ""
        result = self.sh.compose(
            "logs",
            "--no-color",
            "--tail",
            str(tail),
            *names,
            capture=True,
            check=False,
        )
        return (result.stdout or result.stderr or "").strip()

    def container_logs(self, name: str, *, tail: int = _DIAG_LOG_TAIL) -> str:
        """Tail logs for a named container (e.g. cutover ``_tmp``)."""
        if not name:
            return ""
        result = self.sh.docker(
            "logs",
            "--tail",
            str(tail),
            name,
            capture=True,
            check=False,
        )
        # docker logs writes the container stream to stderr by default.
        return (result.stderr or result.stdout or "").strip()

    def service_health_summary(self, service: str) -> str:
        """Short status/health (+ last healthcheck output when present)."""
        cid = self.try_service_container_id(service)
        if not cid:
            return "absent"
        result = self.sh.docker(
            "inspect",
            "--format",
            "{{json .State}}",
            cid,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return "unknown"
        raw = (result.stdout or "").strip()
        try:
            state = json.loads(raw)
        except json.JSONDecodeError:
            return "unknown"
        if not isinstance(state, dict):
            return "unknown"
        status = str(state.get("Status") or "unknown")
        health_obj = state.get("Health")
        health = "none"
        last_out = ""
        if isinstance(health_obj, dict):
            health = str(health_obj.get("Status") or "none")
            log = health_obj.get("Log")
            if isinstance(log, list) and log:
                last = log[-1]
                if isinstance(last, dict):
                    last_out = str(last.get("Output") or "")
        return summarize_health_inspect(status, health, last_output=last_out)

    def not_ready_services(self, services: Optional[list[str]] = None) -> list[str]:
        """Compose services that are missing, exited, or unhealthy."""
        names = services if services is not None else list(self.stack.core_services)
        return [name for name in names if not self.service_is_ready(name)]

    def diagnostics_for(
        self,
        *services: str,
        containers: Sequence[str] = (),
        tail: int = _DIAG_LOG_TAIL,
        max_lines: int = _DIAG_MAX_LINES,
    ) -> str:
        """Readable log/health blocks for Compose services and/or containers."""
        blocks: list[str] = []
        for service in services:
            if not service:
                continue
            health = self.service_health_summary(service)
            logs = prefer_errorish_lines(
                self.compose_logs(service, tail=tail),
                max_lines=max_lines,
            )
            blocks.append(
                format_service_log_block(
                    service, logs, health=health, max_lines=max_lines
                )
            )
        for name in containers:
            if not name:
                continue
            logs = prefer_errorish_lines(
                self.container_logs(name, tail=tail),
                max_lines=max_lines,
            )
            blocks.append(
                format_service_log_block(
                    name, logs, health="container", max_lines=max_lines
                )
            )
        return join_diagnostic_blocks(*blocks)

    def enrich_compose_failure(
        self,
        exc: OperatorError,
        *,
        services: Optional[Sequence[str]] = None,
        detail: str = "",
    ) -> OperatorError:
        """Append recent logs for unhealthy/exited services to a compose CTA."""
        blob = str(exc)
        known = list(self.stack.core_services)
        mentioned = compose_services_from_failure_text(
            f"{blob}\n{detail}",
            known_services=known,
        )
        targets: list[str] = []
        if services:
            targets.extend(services)
        targets.extend(mentioned)
        if not targets:
            targets = self.not_ready_services()
        # De-dupe while preserving order.
        seen: set[str] = set()
        ordered: list[str] = []
        for name in targets:
            if name and name not in seen:
                seen.add(name)
                ordered.append(name)
        if not ordered:
            return exc
        diagnostics = self.diagnostics_for(*ordered)
        if not diagnostics:
            return exc
        return OperatorError(
            append_diagnostics(blob, diagnostics),
            has_fix=exc.has_fix,
        )
