"""Nginx reload and router reachability helpers for the Compose stack."""

from __future__ import annotations

import logging

from raft.errors import (
    OperatorError,
    format_missing_origin_certs,
    looks_like_missing_origin_cert,
    missing_origin_certs_fallback,
    nginx_rejected,
    nginx_reload_failed,
)

from ..models.app import App
from ..models.ports import PortSpec
from ..models.stack import Stack
from ..services.certs import missing_origin_certs
from .shell import Shell

logger = logging.getLogger(__name__)


class DockerEdge:
    """Mixin: router/gate nginx reload and upstream/fetch probes."""

    stack: Stack
    sh: Shell

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
            self._raise_gate_nginx_test_failure(result.stderr or result.stdout or "")
        reload = self.sh.compose(
            "exec", "-T", self.stack.gate, "nginx", "-s", "reload",
            capture=True, check=False,
        )
        if reload.returncode != 0:
            detail = (reload.stderr or reload.stdout or "").strip()
            raise nginx_reload_failed("gate", detail)

    def _raise_gate_nginx_test_failure(self, detail: str) -> None:
        detail = detail.strip()
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

