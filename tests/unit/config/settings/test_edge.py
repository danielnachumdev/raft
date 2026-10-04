"""Edge settings validation coverage."""

from __future__ import annotations

import pytest

from raft.config.settings import load_config

from ...base import RaftTestCase

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


class TestSettingsEdgeErrors(RaftTestCase):
    def test_edge_validation_errors(self) -> None:
        for body, match in EDGE_ERROR_CASES:
            (self.tmp_path / "settings.yaml").write_text(body, encoding="utf-8")
            with pytest.raises(RuntimeError, match=match):
                load_config(self.tmp_path)
