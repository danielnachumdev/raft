"""Manifest parse edge coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument

from ...base import RaftTestCase

PATH = Path("x.yaml")

PARSE_ERROR_DOCS = [
    (
        {"apiVersion": "raft/v1", "kind": "App", "metadata": "nope"},
        "metadata must be an object",
    ),
    (
        {"apiVersion": "raft/v1", "kind": "App", "metadata": {}},
        "metadata.name is required",
    ),
    (
        {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "a"},
            "spec": [],
        },
        "spec must be an object",
    ),
    (
        {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "a"},
            "spec": {
                "publicHost": "a.test",
                "source": "local",
                "tls": True,
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        },
        "YAML true is not valid",
    ),
    (
        {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "a"},
            "spec": {
                "source": "local",
                "tls": "origin",
                "ports": [
                    {
                        "name": "smtp",
                        "containerPort": 25,
                        "expose": "stream",
                        "publicPort": 25,
                    }
                ],
            },
        },
        "tls=origin requires",
    ),
]

NULL_RESOURCES_YAML = """\
apiVersion: raft/v1
kind: App
metadata:
  name: web
spec:
  publicHost: web.test
  source: local
  ports:
    - name: http
      containerPort: 80
      expose: http
  resources:
    limits:
      cpu: null
      memory: null
    requests:
      cpu: ""
      memory: ""
"""


class TestManifestCoverage(RaftTestCase):
    def test_more_parse_errors(self) -> None:
        for doc, match in PARSE_ERROR_DOCS:
            with pytest.raises(ValueError, match=match):
                AppDocument.parse(doc, path=PATH)

    def test_resources_memory_helpers(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(NULL_RESOURCES_YAML, encoding="utf-8")
        c = AppDocument.load_contract(checkout)
        assert c.cpus_limit == "0.50"
        assert c.memory_limit == "128M"
