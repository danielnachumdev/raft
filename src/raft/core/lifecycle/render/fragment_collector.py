"""Collect edge + scaling + ACME redirect fragments for one render pass."""

from pathlib import Path
from typing import Optional

from raft.core.lifecycle.acme.http_redirect import AcmeHttpRedirect
from raft.core.lifecycle.acme.paths import AcmePaths
from raft.core.platform.adapters.nginx import NginxUpstreamText
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.ports import PortSpec
from raft.core.core.models.state.scaling_store import ScalingStore
from .acl.http_gate_host import HttpGateHost
from .edge.fragments import EdgeFragments
from .edge.handlers import EDGE_HANDLERS
from .edge.tls import TlsEdge
from .firewall.policy_includes import PolicyIncludes
from .scaling_gate import ScalingGate


class FragmentCollector:
    """Build the merged ``EdgeFragments`` bag for ``StackRenderer``."""

    def __init__(self, *, root: Path, edge: EdgeConfig) -> None:
        self._root = root
        self._edge = edge
        self._tls = TlsEdge()
        self._scaling = ScalingGate()
        self._redirect = AcmeHttpRedirect()
        self._store = ScalingStore(root)
        self._http_acl_host = HttpGateHost()
        self._policy: Optional[PolicyIncludes] = None

    def collect(self, apps: list[App], resolved: dict[str, AppSpec]) -> EdgeFragments:
        gate_http_dir = self._root / "generated" / "nginx" / "gate-http"
        self._policy = PolicyIncludes(self._root, self._edge, gate_http_dir)
        dash_cfg = SettingsLoader().load(self._root).dashboard
        fw_apps = list(apps) + self._dashboard_firewall_apps(dash_cfg)
        self._policy.write_all(fw_apps)
        fragments = EdgeFragments()
        for app in apps:
            fragments.merge(self._for_app(app, resolved[app.name]))
        fragments.merge(self._dashboard_fragments(dash_cfg))
        return fragments

    def _dashboard_firewall_apps(self, dash_cfg) -> list[App]:
        from raft.core.lifecycle.dashboard.target import DashboardTarget

        return DashboardTarget().firewall_apps(dash_cfg)

    def _dashboard_fragments(self, dash_cfg) -> EdgeFragments:
        from raft.core.lifecycle.dashboard.edge_render import DashboardEdgeRender
        from raft.core.lifecycle.dashboard.target import DashboardTarget

        assert self._policy is not None
        name = DashboardTarget.SERVICE_NAME
        https_inc = self._include(name, self._edge.https)
        return DashboardEdgeRender().contribute(
            dash_cfg,
            edge=self._edge,
            data_home=self._root,
            acl_include=https_inc,
        )

    def _for_app(self, app: App, app_spec: AppSpec) -> EdgeFragments:
        http_inc = self._include(app.name, self._edge.http)
        https_inc = self._include(app.name, self._edge.https)
        frag = EdgeFragments()
        frag.merge(self._tls_fragment(app, app_spec, acl_include=https_inc))
        absent = self._store.is_scaled_to_zero(app.name)
        frag.merge(self._port_fragments(app, app_spec, absent=absent))
        frag.merge(self._scaling_and_redirect(app, app_spec, http_inc))
        frag.merge(self._plain_http_acl_host(app, app_spec, acl_include=http_inc))
        return frag

    def _include(self, name: str, port: Optional[int]) -> str:
        assert self._policy is not None
        if port is None:
            return ""
        return self._policy.host_include(name, port)

    def _scaling_and_redirect(
        self, app: App, app_spec: AppSpec, acl_include: str
    ) -> EdgeFragments:
        kw = dict(edge=self._edge, data_home=self._root, acl_include=acl_include)
        frag = self._scaling.contribute_http(app, app_spec, **kw)
        frag.merge(
            EdgeFragments(gate_http=self._redirect.contribute(app, app_spec, **kw))
        )
        return frag

    def _plain_http_acl_host(
        self, app: App, app_spec: AppSpec, *, acl_include: str
    ) -> EdgeFragments:
        assert self._policy is not None
        if not self._policy.needs_host_gate_server(app.name):
            return EdgeFragments()
        if app_spec.scaling is not None:
            return EdgeFragments()
        if self._acme_owns_http(app, app_spec):
            return EdgeFragments()
        return self._http_acl_host.contribute(
            app, app_spec, edge=self._edge, acl_include=acl_include
        )

    def _acme_owns_http(self, app: App, app_spec: AppSpec) -> bool:
        if app_spec.tls != "acme":
            return False
        return AcmePaths(self._root).live_material_present(app.name)

    def _port_fragments(
        self, app: App, app_spec: AppSpec, *, absent: bool
    ) -> EdgeFragments:
        frag = EdgeFragments()
        for port in app_spec.ports:
            port_frag = EDGE_HANDLERS[port.expose].contribute(
                app, app_spec, port, edge=self._edge
            )
            if absent:
                self._park_http_upstreams(port_frag, app, port)
            frag.merge(port_frag)
        return frag

    def _tls_fragment(
        self, app: App, app_spec: AppSpec, *, acl_include: str
    ) -> EdgeFragments:
        if app_spec.tls in {"origin", "acme"} and app_spec.scaling is not None:
            return self._scaling_tls_fragment(app, app_spec, acl_include=acl_include)
        return self._tls.contribute_app(
            app,
            app_spec,
            edge=self._edge,
            data_home=self._root,
            acl_include=acl_include,
        )

    def _scaling_tls_fragment(
        self, app: App, app_spec: AppSpec, *, acl_include: str
    ) -> EdgeFragments:
        if app_spec.tls == "acme":
            self._tls.require_acme_edge(app, self._edge)
            if not AcmePaths(self._root).live_material_present(app.name):
                return EdgeFragments()
        elif self._edge.https is None:
            raise OperatorError(
                f"{app.name}: tls=origin requires edge.https in settings.yaml.\n"
                f"Fix: set edge.https (e.g. 443) in ~/.raft/host/settings.yaml, then: raft render"
            )
        body = self._scaling.contribute_tls(app, app_spec, acl_include=acl_include)
        return EdgeFragments(gate_tls={f"{app.name}.conf": body})

    @staticmethod
    def _park_http_upstreams(frag: EdgeFragments, app: App, port: PortSpec) -> None:
        if port.expose != "http" or not frag.upstreams:
            return
        filename = f"{app.name}-{port.name}.conf"
        if filename not in frag.upstreams:
            return
        frag.upstreams[filename] = NginxUpstreamText.block(
            f"{app.name}_{port.name}",
            NginxUpstreamText.ABSENT_HOSTNAME,
            port.container_port,
        )
