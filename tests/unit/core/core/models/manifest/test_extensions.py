"""AppSpec group/volumes extensions and package root."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from raft.core.core.config.paths import PackageRootFinder
from raft.core.core.models.app_document import AppDocument

from tests.unit.core.core.models.manifest.base import ManifestTestCase

GROUP_VOL_DOC = {
    "apiVersion": "raft/v1",
    "kind": "App",
    "metadata": {"name": "stack-redis"},
    "spec": {
        "source": "docker",
        "image": "redis",
        "ref": "alpine",
        "path": "services/stack-redis/checkout",
        "group": "demo",
        "dependsOn": ["stack-front"],
        "envFile": "/home/raft/.raft/demo.env",
        "env": {"A": "1"},
        "volumes": [
            {
                "name": "data",
                "hostPath": "/mnt/raft-data/demo/redis",
                "containerPath": "/data",
                "readOnly": True,
            }
        ],
        "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
        "readiness": {"type": "tcp", "port": "redis"},
    },
}

BAD_BASE = {
    "apiVersion": "raft/v1",
    "kind": "App",
    "metadata": {"name": "x"},
    "spec": {
        "source": "docker",
        "image": "redis",
        "path": "services/x/checkout",
        "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
        "readiness": {"type": "none"},
    },
}


class TestAppSpecExtensions(ManifestTestCase):
    def test_parse_group_volumes_env(self) -> None:
        app, spec = AppDocument.parse(GROUP_VOL_DOC, path=Path("app.yaml"))
        assert app.public_host == ""
        assert spec.group == "demo"
        assert spec.depend_names() == ("stack-front",)
        assert spec.env_file == "/home/raft/.raft/demo.env"
        assert spec.env == (("A", "1"),)
        assert len(spec.volumes) == 1 and spec.volumes[0].read_only is True
        assert spec.none_ports()[0].name == "redis"

    def test_rejects_bad_group_and_volume_traversal(self) -> None:
        bad_group = yaml.safe_load(yaml.safe_dump(BAD_BASE))
        bad_group["spec"]["group"] = "Mailu"
        with pytest.raises(ValueError, match="spec.group"):
            AppDocument.parse(bad_group, path=Path("g.yaml"))
        bad_vol = yaml.safe_load(yaml.safe_dump(BAD_BASE))
        bad_vol["spec"]["volumes"] = [{"hostPath": "/tmp/../etc/passwd", "containerPath": "/data"}]
        with pytest.raises(ValueError, match="must not contain"):
            AppDocument.parse(bad_vol, path=Path("v.yaml"))


class TestFindPackageRoot(ManifestTestCase):
    def test_bundled(self) -> None:
        root = PackageRootFinder().find()
        assert (root / "compose.yaml").is_file()
        assert (root / "nginx" / "gate" / "nginx.conf").is_file()
