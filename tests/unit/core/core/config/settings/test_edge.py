"""Edge settings validation coverage."""

import pytest

from raft.core.core.config.settings import load_config

from tests.unit.base import RaftTestCase

EDGE_ERROR_CASES = [
    ("edge: nope\n", "edge must be a mapping"),
    ("edge:\n  http: 99999\n", "out of range"),
    ("edge:\n  streams: {}\n", "must be a list"),
    ("edge:\n  streams:\n    - x\n", "must be an object"),
    ("edge:\n  streams:\n    - port: 25\n", "name is required"),
    (
        "edge:\n  streams:\n    - name: a\n      port: 25\n" "    - name: a\n      port: 26\n",
        "duplicate name",
    ),
    ("edge:\n  streams:\n    - name: a\n", "port is required"),
    ("edge:\n  streams:\n    - name: a\n      port: 0\n", "out of range"),
    (
        "edge:\n  http: 25\n  streams:\n    - name: a\n      port: 25\n",
        "conflicts with edge.http",
    ),
    (
        "edge:\n  https: 25\n  streams:\n    - name: a\n      port: 25\n",
        "conflicts with edge.https",
    ),
    (
        "edge:\n  streams:\n    - name: a\n      port: 25\n" "      protocol: sctp\n",
        "protocol must be",
    ),
]


class TestSettingsEdge(RaftTestCase):
    def test_load_edge_section(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            """
logging:
  level: INFO
edge:
  http: 8080
  https: null
  streams:
    - name: smtp
      port: 25
      protocol: tcp
""",
            encoding="utf-8",
        )
        cfg = load_config(self.tmp_path)
        assert cfg.edge.http == 8080
        assert cfg.edge.https is None
        assert len(cfg.edge.streams) == 1
        assert cfg.edge.streams[0].name == "smtp"
        assert cfg.edge.published_ports() == [(8080, "tcp"), (25, "tcp")]

    def test_edge_rejects_duplicate_stream_port(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            """
edge:
  streams:
    - name: a
      port: 25
    - name: b
      port: 25
""",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="duplicate port"):
            load_config(self.tmp_path)


class TestSettingsEdgeErrors(RaftTestCase):
    def test_edge_validation_errors(self) -> None:
        for body, match in EDGE_ERROR_CASES:
            (self.tmp_path / "settings.yaml").write_text(body, encoding="utf-8")
            with pytest.raises(RuntimeError, match=match):
                load_config(self.tmp_path)
