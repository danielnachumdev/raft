"""Empty / omitted ``spec.ports`` allow/deny matrix (worker Apps)."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument

from .base import ManifestTestCase

PATH = Path("worker.yaml")

_WORKER_BASE = {
    "apiVersion": "raft/v1",
    "kind": "App",
    "metadata": {"name": "worker"},
}


def _doc(spec: dict) -> dict:
    return {**_WORKER_BASE, "spec": spec}


class TestEmptyPortsWorker(ManifestTestCase):
    def test_allow_omit_ports_and_empty_list(self) -> None:
        for ports_spec in ({"source": "local"}, {"source": "local", "ports": []}):
            _app, spec = AppDocument.parse(_doc(ports_spec), path=PATH)
            assert spec.ports == ()
            assert spec.readiness.type == "none"
            assert spec.tls == "off"

    def test_allow_explicit_readiness_none(self) -> None:
        _app, spec = AppDocument.parse(
            _doc({"source": "local", "ports": [], "readiness": {"type": "none"}}),
            path=PATH,
        )
        assert spec.readiness.type == "none"

    def test_deny_http_or_tcp_readiness(self) -> None:
        for rtype in ("http", "tcp"):
            with pytest.raises(ValueError, match="readiness requires a named port"):
                AppDocument.parse(
                    _doc({"source": "local", "ports": [], "readiness": {"type": rtype}}),
                    path=PATH,
                )

    def test_deny_tls_origin_and_acme(self) -> None:
        for tls in ("origin", "acme"):
            with pytest.raises(ValueError, match="empty ports use tls: off"):
                AppDocument.parse(
                    _doc(
                        {
                            "source": "local",
                            "publicHost": "w.test",
                            "ports": [],
                            "tls": tls,
                        }
                    ),
                    path=PATH,
                )

    def test_deny_scaling(self) -> None:
        with pytest.raises(ValueError, match="expose: http"):
            AppDocument.parse(
                _doc(
                    {
                        "source": "local",
                        "publicHost": "w.test",
                        "ports": [],
                        "scaling": {
                            "idleSeconds": 30,
                            "minUpSeconds": 15,
                        },
                    }
                ),
                path=PATH,
            )

    def test_deny_non_list_ports(self) -> None:
        with pytest.raises(ValueError, match="spec.ports must be a list"):
            AppDocument.parse(_doc({"source": "local", "ports": {}}), path=PATH)

    def test_repo_without_source_still_git(self) -> None:
        app, spec = AppDocument.parse(
            _doc({"repo": "git@github.com:org/worker.git", "ports": []}),
            path=PATH,
        )
        assert app.source == "git" and spec.ports == ()
