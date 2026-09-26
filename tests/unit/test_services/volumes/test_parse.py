"""Parse errors for group / env / volumes fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument
from raft.models.ports import PortSpec, port_by_name
from raft.services.compose_apps import compose_str

from .base import VolumesTestCase

VOLUME_PARSE_CASES = [
    ("nope", "volumes must be a list"),
    (["x"], "must be an object"),
    ([{"containerPath": "/data"}], "hostPath is required"),
    ([{"hostPath": "/data"}], "containerPath is required"),
    ([{"hostPath": "/data", "containerPath": "relative"}], "must be absolute"),
    (
        [{"hostPath": "/data", "containerPath": "/x", "readOnly": "yes"}],
        "readOnly must be a boolean",
    ),
]


class TestVolumesParse(VolumesTestCase):
    def test_compose_str_and_port_by_name_empty(self) -> None:
        assert compose_str("") == '""'
        assert compose_str("a:b") == '"a:b"'
        assert compose_str("plain") == "plain"
        with pytest.raises(KeyError, match="unknown port"):
            port_by_name((), "x")
        ports = (
            PortSpec(name="http", container_port=80, expose="http"),
            PortSpec(name="redis", container_port=6379, expose="none"),
        )
        assert port_by_name(ports, "redis") is ports[1]

    def test_group_parse_ok_and_errors(self) -> None:
        data = self.base_docker()
        data["spec"]["group"] = "demo"
        _, spec = AppDocument.parse(data, path=Path("a.yaml"))
        assert spec.group == "demo"
        self._assert_group_errors()
        self._assert_group_blank_and_bad_name()

    def _assert_group_errors(self) -> None:
        for payload, match in (
            ({"group": 123}, "spec.group must be a string"),
            ({"groups": ["demo"]}, "use spec.group"),
            ({"group": ["demo", "other"]}, "not a list"),
        ):
            data = self.base_docker()
            data["spec"].update(payload)
            with pytest.raises(ValueError, match=match):
                AppDocument.parse(data, path=Path("b.yaml"))

    def _assert_group_blank_and_bad_name(self) -> None:
        data = self.base_docker()
        data["spec"]["group"] = "  "
        _, spec = AppDocument.parse(data, path=Path("o.yaml"))
        assert spec.group is None
        data2 = self.base_docker()
        data2["spec"]["group"] = "Bad_Name"
        with pytest.raises(ValueError, match="spec.group"):
            AppDocument.parse(data2, path=Path("o2.yaml"))

    def test_depends_on_parse(self) -> None:
        data = self.base_docker()
        data["spec"]["dependsOn"] = "stack-redis"
        _, spec = AppDocument.parse(data, path=Path("b4.yaml"))
        assert spec.depends_on == ("stack-redis",)
        data_bad = self.base_docker()
        data_bad["spec"]["dependsOn"] = 123
        with pytest.raises(ValueError, match="must be a string or array"):
            AppDocument.parse(data_bad, path=Path("b5.yaml"))
        data_dup = self.base_docker()
        data_dup["spec"]["dependsOn"] = ["a", "a", ""]
        _, spec_dup = AppDocument.parse(data_dup, path=Path("b6.yaml"))
        assert spec_dup.depends_on == ("a",)

    def test_env_file_and_env_errors(self) -> None:
        self._assert_env_file_errors()
        self._assert_env_map_errors()

    def _assert_env_file_errors(self) -> None:
        data = self.base_docker()
        data["spec"]["envFile"] = 1
        with pytest.raises(ValueError, match="envFile must be a string"):
            AppDocument.parse(data, path=Path("c.yaml"))
        data4 = self.base_docker()
        data4["spec"]["envFile"] = "   "
        _, spec4 = AppDocument.parse(data4, path=Path("d.yaml"))
        assert spec4.env_file is None
        data5 = self.base_docker()
        data5["spec"]["envFile"] = "/tmp/../secret"
        with pytest.raises(ValueError, match="must not contain"):
            AppDocument.parse(data5, path=Path("e.yaml"))

    def _assert_env_map_errors(self) -> None:
        for payload, match in (
            ({"env": {"K": None}}, "must not be null"),
            ({"env": []}, "spec.env must be an object"),
            ({"env": {"": "x"}}, "non-empty"),
        ):
            data = self.base_docker()
            data["spec"].update(payload)
            with pytest.raises(ValueError, match=match):
                AppDocument.parse(data, path=Path("f.yaml"))

    def test_volume_parse_errors(self) -> None:
        for volumes, match in VOLUME_PARSE_CASES:
            data = self.base_docker()
            data["spec"]["volumes"] = volumes
            with pytest.raises(ValueError, match=match):
                AppDocument.parse(data, path=Path("v.yaml"))
        data16 = self.base_docker()
        data16["spec"]["volumes"] = [
            {"hostPath": "/data", "containerPath": "/x", "name": ""}
        ]
        _, spec16 = AppDocument.parse(data16, path=Path("p.yaml"))
        assert spec16.volumes[0].name is None
