"""Collect edge + scaling + ACME redirect fragments for one render pass."""

from __future__ import annotations

from pathlib import Path

from raft.adapters.nginx import NginxUpstreamText
from raft.config.settings_types import EdgeConfig
from raft.errors.cta import OperatorError
from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.state.scaling_store import ScalingStore
from raft.acme.http_redirect import AcmeHttpRedirect
from raft.acme.paths import AcmePaths

from .edge import EDGE_HANDLERS, EdgeFragments, TlsEdge
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

    def collect(self, apps: list[App], resolved: dict[str, AppSpec]) -> EdgeFragments:
        fragments = EdgeFragments()
        for app in apps:
            fragments.merge(self._for_app(app, resolved[app.name]))
        return fragments

    def _for_app(self, app: App, app_spec: AppSpec) -> EdgeFragments:
        frag = EdgeFragments()
        frag.merge(self._tls_fragment(app, app_spec))
        absent = self._store.is_scaled_to_zero(app.name)
        frag.merge(self._port_fragments(app, app_spec, absent=absent))
        frag.merge(
            self._scaling.contribute_http(
                app, app_spec, edge=self._edge, data_home=self._root
            )
        )
        frag.merge(
            self._redirect.contribute(
                app, app_spec, edge=self._edge, data_home=self._root
            )
        )
        return frag

    def _port_fragments(self, app: App, app_spec: AppSpec, *, absent: bool) -> EdgeFragments:
        frag = EdgeFragments()
        for port in app_spec.ports:
            port_frag = EDGE_HANDLERS[port.expose].contribute(
                app, app_spec, port, edge=self._edge
            )
            if absent:
                self._park_http_upstreams(port_frag, app, port)
            frag.merge(port_frag)
        return frag

    def _tls_fragment(self, app: App, app_spec: AppSpec) -> EdgeFragments:
        if app_spec.tls in {"origin", "acme"} and app_spec.scaling is not None:
            return self._scaling_tls_fragment(app, app_spec)
        return self._tls.contribute_app(
            app, app_spec, edge=self._edge, data_home=self._root
        )

    def _scaling_tls_fragment(self, app: App, app_spec: AppSpec) -> EdgeFragments:
        if app_spec.tls == "acme":
            self._tls.require_acme_edge(app, self._edge)
            if not AcmePaths(self._root).live_material_present(app.name):
                return EdgeFragments()
        elif self._edge.https is None:
            raise OperatorError(
                f"{app.name}: tls=origin requires edge.https in settings.yaml.\n"
                f"Fix: set edge.https (e.g. 443) in ~/.raft/settings.yaml, then: raft render"
            )
        body = self._scaling.contribute_tls(app, app_spec)
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
