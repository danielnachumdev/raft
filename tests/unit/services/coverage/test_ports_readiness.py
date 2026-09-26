"""Port and readiness parse/timing coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.ports import PortSpec, parse_ports
from raft.models.readiness_parser import parse_readiness
from raft.models.readiness_spec import ReadinessSpec

from ...base import RaftTestCase

PATH = Path("app.yaml")

PORT_VALIDATE_CASES = [
    (dict(name="x", container_port=80, expose="quic"), "expose must be"),
    (dict(name="x", container_port=80, expose="http", protocol="sctp"), "protocol must be"),
    (dict(name="x", container_port=0, expose="http"), "containerPort out of range"),
    (
        dict(name="x", container_port=25, expose="stream", public_port=0),
        "publicPort out of range",
    ),
    (
        dict(name="x", container_port=80, expose="http", public_port=80),
        "publicPort is only valid",
    ),
]

PARSE_PORTS_CASES = [
    ({}, "spec.ports is required"),
    ({"ports": []}, "non-empty list"),
    ({"ports": ["x"]}, "must be an object"),
    ({"ports": [{"containerPort": 80}]}, "name is required"),
    ({"ports": [{"name": "http"}]}, "containerPort is required"),
]

READINESS_TIMING_ERROR_CASES = [
    ({"timeoutSeconds": 30, "startPeriodSeconds": 45}, "greater than startPeriodSeconds"),
    (
        {"timeoutSeconds": 46, "startPeriodSeconds": 45, "intervalSeconds": 2},
        "at least startPeriodSeconds \\+ interval",
    ),
    ({"retries": 0}, "must be > 0"),
    ({"timeoutSeconds": "slow"}, "timeoutSeconds must be a number"),
    ({"startPeriodSeconds": 0}, "startPeriodSeconds must be > 0"),
    ({"retries": "many"}, "retries must be an integer"),
]


class TestPortsAndReadinessCoverage(RaftTestCase):
    def test_port_validation_errors(self) -> None:
        for kwargs, match in PORT_VALIDATE_CASES:
            with pytest.raises(ValueError, match=match):
                PortSpec(**kwargs).validate(path=PATH)
        for raw, match in PARSE_PORTS_CASES:
            with pytest.raises(ValueError, match=match):
                parse_ports(raw, PATH)

    def _ports(self):
        return (
            PortSpec(name="http", container_port=80, expose="http"),
            PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),
        )

    def test_readiness_paths(self) -> None:
        ports = self._ports()
        self._assert_readiness_parse_errors(ports)
        self._assert_readiness_defaults(ports)
        self._assert_resolve_port(ports)

    def _assert_readiness_parse_errors(self, ports) -> None:
        with pytest.raises(ValueError, match="must be an object"):
            parse_readiness({"readiness": "x"}, ports, PATH)
        with pytest.raises(ValueError, match="readiness.type must be"):
            parse_readiness({"readiness": {"type": "udp"}}, ports, PATH)
        with pytest.raises(ValueError, match="not in ports"):
            parse_readiness({"readiness": {"type": "tcp", "port": "missing"}}, ports, PATH)
        with pytest.raises(ValueError, match="requires an expose=http"):
            parse_readiness({"readiness": {"type": "http", "port": "smtp"}}, ports, PATH)

    def _assert_readiness_defaults(self, ports) -> None:
        r = parse_readiness({"readiness": {"type": "none"}}, ports, PATH)
        assert r.type == "none" and r.timeout_seconds == 120.0
        assert r.start_period_seconds == 45.0
        assert (
            parse_readiness({"readiness": {"type": "http", "path": "ready"}}, ports, PATH).path
            == "/ready"
        )
        assert parse_readiness({}, ports, PATH).port == "http"
        r4 = parse_readiness({}, (ports[1],), PATH)
        assert r4.type == "tcp"

    def _assert_resolve_port(self, ports) -> None:
        assert ReadinessSpec(type="http", port=None, path="/").resolve_port(ports).name == "http"
        with pytest.raises(KeyError):
            ReadinessSpec(type="tcp", port="nope").resolve_port(ports)
        assert ReadinessSpec(type="none").resolve_port(ports) is None
        assert ReadinessSpec(type="tcp").resolve_port(()) is None

    def _http_ports(self):
        return (PortSpec(name="http", container_port=80, expose="http"),)

    def test_readiness_timing_defaults(self) -> None:
        defaults = parse_readiness(
            {"readiness": {"type": "tcp", "port": "http"}}, self._http_ports(), PATH
        )
        assert defaults.timeout_seconds == 120.0
        assert defaults.start_period_seconds == 45.0
        assert defaults.interval_seconds == 2.0 and defaults.retries == 15
        assert "timeoutSeconds=120s" in defaults.timing_summary()

    def test_readiness_timing_custom_and_auto_bump(self) -> None:
        ports = self._http_ports()
        custom = parse_readiness(
            {"readiness": self._custom_timing_raw()},
            ports,
            PATH,
        )
        assert custom.timeout_seconds == 180.0 and custom.start_period_seconds == 60.0
        assert custom.interval_seconds == 3.0 and custom.retries == 10
        long_start = parse_readiness(
            {"readiness": {"type": "tcp", "port": "http", "startPeriodSeconds": 90}},
            ports,
            PATH,
        )
        assert long_start.timeout_seconds >= 90 + 15 * 2 + 15

    @staticmethod
    def _custom_timing_raw() -> dict:
        return {
            "type": "tcp",
            "port": "http",
            "timeoutSeconds": 180,
            "startPeriodSeconds": 60,
            "intervalSeconds": 3,
            "probeTimeoutSeconds": 2,
            "retries": 10,
        }

    def test_readiness_timing_validation_errors(self) -> None:
        ports = self._http_ports()
        for extra, match in READINESS_TIMING_ERROR_CASES:
            readiness = {"type": "tcp", "port": "http", **extra}
            with pytest.raises(ValueError, match=match):
                parse_readiness({"readiness": readiness}, ports, PATH)
