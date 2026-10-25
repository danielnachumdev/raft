"""HostPaths resolves control-plane locations under host/."""

from pathlib import Path

from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.config.paths.service_paths import ServicePaths

from tests.unit.base import RaftTestCase


class TestHostAndServicePaths(RaftTestCase):
    def test_host_paths_resolve_under_host(self) -> None:
        home = Path(self.tmp_path)
        hp = HostPaths(home)
        assert hp.root() == home / "host"
        assert hp.settings() == home / "host" / "settings.yaml"
        assert hp.locks() == home / "host" / "locks"
        assert hp.firewall() == home / "host" / "firewall"
        assert hp.alerts() == home / "host" / "alerts"
        assert hp.inbox() == home / "host" / "inbox"
        assert hp.events() == home / "host" / "events"
        assert hp.metrics() == home / "host" / "metrics"
        assert hp.acme() == home / "host" / "acme"
        assert hp.serve() == home / "host" / "serve"
        assert hp.secrets() == home / "host" / "secrets"
        assert hp.logs() == home / "host" / "logs"
        assert hp.edge_service_logs() == home / "host" / "logs" / "services"
        assert hp.gate_nginx_fingerprint() == home / "host" / "gate-nginx.fingerprint"
        assert hp.router_nginx_fingerprint() == (
            home / "host" / "router-nginx.fingerprint"
        )

    def test_service_default_checkout_rel(self) -> None:
        assert ServicePaths.default_checkout_rel("demo-api") == (
            "services/demo-api/checkout"
        )
