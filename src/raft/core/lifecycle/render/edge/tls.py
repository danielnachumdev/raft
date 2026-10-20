"""Gate TLS snippets for ``spec.tls: origin`` and ``spec.tls: acme``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from raft.core.lifecycle.acme.paths import AcmePaths
from raft.core.lifecycle.render.acl.proxy_location import AclProxyLocation
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from .fragments import EdgeFragments

_DEFAULT_READ = "60s"


@dataclass(frozen=True)
class TlsEdge:
    def contribute_app(
        self,
        app: App,
        spec: AppSpec,
        *,
        edge: EdgeConfig,
        data_home: Path,
        acl_include: str = "",
        proxy_read_timeout: str = _DEFAULT_READ,
        proxy_send_timeout: Optional[str] = None,
    ) -> EdgeFragments:
        if spec.tls == "origin":
            return self._origin_fragments(
                app,
                spec,
                edge,
                acl_include=acl_include,
                proxy_read_timeout=proxy_read_timeout,
                proxy_send_timeout=proxy_send_timeout,
            )
        if spec.tls == "acme":
            return self._acme_fragments(
                app,
                spec,
                edge,
                data_home,
                acl_include=acl_include,
                proxy_read_timeout=proxy_read_timeout,
                proxy_send_timeout=proxy_send_timeout,
            )
        return EdgeFragments()

    def _origin_fragments(
        self,
        app: App,
        spec: AppSpec,
        edge: EdgeConfig,
        *,
        acl_include: str,
        proxy_read_timeout: str,
        proxy_send_timeout: Optional[str],
    ) -> EdgeFragments:
        if edge.https is None:
            raise OperatorError(
                f"{app.name}: tls=origin requires edge.https in settings.yaml.\n"
                f"Fix: set edge.https (e.g. 443) in ~/.raft/host/settings.yaml, then: raft render"
            )
        body = self._tls_server_body(
            app,
            spec,
            stem="origin",
            acl_include=acl_include,
            proxy_read_timeout=proxy_read_timeout,
            proxy_send_timeout=proxy_send_timeout,
        )
        return EdgeFragments(gate_tls={f"{app.name}.conf": body})

    def _acme_fragments(
        self,
        app: App,
        spec: AppSpec,
        edge: EdgeConfig,
        data_home: Path,
        *,
        acl_include: str,
        proxy_read_timeout: str,
        proxy_send_timeout: Optional[str],
    ) -> EdgeFragments:
        self.require_acme_edge(app, edge)
        if not AcmePaths(data_home).live_material_present(app.name):
            return EdgeFragments()
        body = self._tls_server_body(
            app,
            spec,
            stem="acme",
            acl_include=acl_include,
            proxy_read_timeout=proxy_read_timeout,
            proxy_send_timeout=proxy_send_timeout,
        )
        return EdgeFragments(gate_tls={f"{app.name}.conf": body})

    @staticmethod
    def require_acme_edge(app: App, edge: EdgeConfig) -> None:
        if edge.http is None:
            raise OperatorError(
                f"{app.name}: tls=acme requires edge.http in settings.yaml "
                f"(HTTP-01 challenge on port 80).\n"
                f"Fix: set edge.http (e.g. 80) in ~/.raft/host/settings.yaml, then: raft render"
            )
        if edge.https is None:
            raise OperatorError(
                f"{app.name}: tls=acme requires edge.https in settings.yaml.\n"
                f"Fix: set edge.https (e.g. 443) in ~/.raft/host/settings.yaml, then: raft render"
            )

    @staticmethod
    def _tls_server_body(
        app: App,
        spec: AppSpec,
        *,
        stem: str,
        acl_include: str = "",
        proxy_read_timeout: str = _DEFAULT_READ,
        proxy_send_timeout: Optional[str] = None,
    ) -> str:
        names = " ".join(spec.server_names(app.public_host))
        head = TlsEdge._tls_server_head(app, names=names, stem=stem)
        if TlsEdge._use_shared_proxy_include(
            acl_include, proxy_read_timeout, proxy_send_timeout
        ):
            return head + "    include /etc/nginx/gate/proxy_router.inc;\n}\n"
        return TlsEdge._expanded_tls_proxy(
            head, acl_include, proxy_read_timeout, proxy_send_timeout
        )

    @staticmethod
    def _use_shared_proxy_include(
        acl_include: str,
        proxy_read_timeout: str,
        proxy_send_timeout: Optional[str],
    ) -> bool:
        # Shared include is 60s-only; expand when ACL or long timeouts apply.
        return (
            not acl_include
            and proxy_read_timeout == _DEFAULT_READ
            and not proxy_send_timeout
        )

    @staticmethod
    def _expanded_tls_proxy(
        head: str,
        acl_include: str,
        proxy_read_timeout: str,
        proxy_send_timeout: Optional[str],
    ) -> str:
        return (
            head
            + "    resolver 127.0.0.11 valid=10s ipv6=off;\n\n"
            + "    include /etc/nginx/gate/acme_challenge.inc;\n\n"
            + AclProxyLocation.location_slash(
                acl_include=acl_include,
                read_timeout=proxy_read_timeout,
                send_timeout=proxy_send_timeout,
            )
            + "\n"
            + AclProxyLocation.offline_and_forbidden(acl_include=acl_include)
            + "}\n"
        )

    @staticmethod
    def _tls_server_head(app: App, *, names: str, stem: str) -> str:
        return (
            f"# Generated by raft render — PEMs: services/{app.name}/certs/{stem}.{{pem,key}}\n"
            "server {\n"
            "    listen 443 ssl;\n"
            f"    server_name {names};\n"
            "\n"
            f"    ssl_certificate     /etc/nginx/services/{app.name}/certs/{stem}.pem;\n"
            f"    ssl_certificate_key /etc/nginx/services/{app.name}/certs/{stem}.key;\n"
            "\n"
        )
