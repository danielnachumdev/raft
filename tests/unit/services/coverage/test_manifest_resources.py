"""Manifest resource / memory helper coverage edges."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument
from raft.models.app_spec_fields import AppSpecFields
from raft.models.stack import load_stack

from ...base import RaftTestCase

PATH = Path("x.yaml")
BASE_DOC = {
    "apiVersion": "raft/v1",
    "kind": "App",
    "metadata": {"name": "a"},
    "spec": {
        "publicHost": "a.test",
        "source": "local",
        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
    },
}


class TestManifestResourceCoverage(RaftTestCase):
    def test_manifest_extra_resource_branches(self) -> None:
        self._assert_resource_parse_errors()
        self._assert_tls_build_extra_hosts()
        self._assert_filename_stem_mismatch()

    def _assert_resource_parse_errors(self) -> None:
        with pytest.raises(ValueError, match="resources must be an object"):
            AppDocument.parse(
                {**BASE_DOC, "spec": {**BASE_DOC["spec"], "resources": []}}, path=PATH
            )
        with pytest.raises(ValueError, match="limits/requests"):
            AppDocument.parse(
                {
                    **BASE_DOC,
                    "spec": {**BASE_DOC["spec"], "resources": {"limits": [], "requests": {}}},
                },
                path=PATH,
            )
        with pytest.raises(ValueError, match="extraHosts"):
            AppDocument.parse(
                {**BASE_DOC, "spec": {**BASE_DOC["spec"], "extraHosts": {"a": 1}}}, path=PATH
            )
        with pytest.raises(ValueError, match="spec.build"):
            AppDocument.parse({**BASE_DOC, "spec": {**BASE_DOC["spec"], "build": []}}, path=PATH)

    def _assert_tls_build_extra_hosts(self) -> None:
        _app, spec = AppDocument.parse(
            {
                **BASE_DOC,
                "spec": {
                    **BASE_DOC["spec"],
                    "tls": False,
                    "build": {"context": "  ", "dockerfile": "  "},
                    "extraHosts": "alias.test",
                    "www": False,
                },
            },
            path=PATH,
        )
        assert spec.tls == "off"
        assert spec.build_context is None and spec.dockerfile is None
        assert spec.extra_hosts == ("alias.test",)

    def _assert_filename_stem_mismatch(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "wrong.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: a\nspec:\n"
            "  publicHost: a.test\n  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n"
            "      expose: http\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="filename stem"):
            load_stack(self.tmp_path)

    def test_parse_memory_gi_and_cpu_millis(self) -> None:
        assert AppSpecFields._parse_memory("2Gi", default="1M") == "2G"
        assert AppSpecFields._parse_memory(None, default="1M") == "1M"
        assert AppSpecFields._parse_memory("  ", default="1M") == "1M"
        assert AppSpecFields._parse_cpu(None, default="0.1") == "0.1"
        assert AppSpecFields._parse_cpu("  ", default="0.1") == "0.1"
        assert AppSpecFields._parse_cpu("500m", default="0.1") == "0.5"
