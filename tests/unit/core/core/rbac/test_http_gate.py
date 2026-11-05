"""HTTP path → permission mapping (#307)."""

from raft.core.core.rbac import RbacHttpGate
from tests.unit.base import RaftTestCase


class TestRbacHttpGate(RaftTestCase):
    def test_prefixes_and_runtime(self) -> None:
        gate = RbacHttpGate()
        assert gate.permission("GET", "/api/firewall") == "firewall:read"
        assert gate.permission("PUT", "/api/firewall") == "firewall:write"
        assert gate.permission("POST", "/api/purge") == "runtime:write"
        assert (
            gate.permission("POST", "/api/service/demo-api/redeploy")
            == "runtime:write"
        )
        assert gate.permission("GET", "/api/rbac") == "rbac:read"
        assert gate.permission("GET", "/api/dashboard/session") is None
        assert gate.permission("GET", "/api/service/demo-api") == "service:read"
        assert gate.permission("GET", "/api/service/demo-api/logs") == "logs:read"
        assert (
            gate._service_permission("POST", "/api/service/demo-api/up")
            == "runtime:write"
        )
