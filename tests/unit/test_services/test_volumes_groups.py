"""Coverage for volumes/groups/envFile/expose none and related CLI."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.cli import get as get_cmd
from raft.models.manifest import parse_app_document
from raft.models.ports import PortSpec, port_by_name
from raft.models.stack import load_stack
from raft.services.apply import AppApply
from raft.services.doctor import CheckResult, Doctor, INFRA
from raft.services.render import StackRenderer, _compose_str

from ..base import RaftTestCase, write_applied_app


def _base_docker(*, name: str = "x") -> dict:
    return {
        "apiVersion": "raft/v1",
        "kind": "App",
        "metadata": {"name": name},
        "spec": {
            "source": "docker",
            "image": "redis",
            "path": f"apps/{name}",
            "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
            "readiness": {"type": "none"},
        },
    }


class TestVolumesGroupsCoverage(RaftTestCase):
    def test_compose_str_and_port_by_name_empty(self) -> None:
        assert _compose_str("") == '""'
        assert _compose_str("a:b") == '"a:b"'
        assert _compose_str("plain") == "plain"
        with pytest.raises(KeyError, match="unknown port"):
            port_by_name((), "x")
        ports = (
            PortSpec(
                name="http",
                container_port=80,
                expose="http",
                public_port=None,
                protocol="tcp",
                proxy_protocol=False,
            ),
            PortSpec(
                name="redis",
                container_port=6379,
                expose="none",
                public_port=None,
                protocol="tcp",
                proxy_protocol=False,
            ),
        )
        assert port_by_name(ports, "redis") is ports[1]

    def test_parse_name_list_and_env_volume_errors(self) -> None:
        data = _base_docker()
        data["spec"]["group"] = "demo"
        _, spec = parse_app_document(data, path=Path("a.yaml"))
        assert spec.group == "demo"

        data2 = _base_docker()
        data2["spec"]["group"] = 123
        with pytest.raises(ValueError, match="spec.group must be a string"):
            parse_app_document(data2, path=Path("b.yaml"))

        data2b = _base_docker()
        data2b["spec"]["groups"] = ["demo"]
        with pytest.raises(ValueError, match="use spec.group"):
            parse_app_document(data2b, path=Path("b2.yaml"))

        data2c = _base_docker()
        data2c["spec"]["group"] = ["demo", "other"]
        with pytest.raises(ValueError, match="not a list"):
            parse_app_document(data2c, path=Path("b3.yaml"))

        data2d = _base_docker()
        data2d["spec"]["dependsOn"] = "stack-redis"
        _, spec2d = parse_app_document(data2d, path=Path("b4.yaml"))
        assert spec2d.depends_on == ("stack-redis",)

        data2e = _base_docker()
        data2e["spec"]["dependsOn"] = 123
        with pytest.raises(ValueError, match="must be a string or array"):
            parse_app_document(data2e, path=Path("b5.yaml"))

        data2f = _base_docker()
        data2f["spec"]["dependsOn"] = ["a", "a", ""]
        _, spec2f = parse_app_document(data2f, path=Path("b6.yaml"))
        assert spec2f.depends_on == ("a",)

        data3 = _base_docker()
        data3["spec"]["envFile"] = 1
        with pytest.raises(ValueError, match="envFile must be a string"):
            parse_app_document(data3, path=Path("c.yaml"))

        data4 = _base_docker()
        data4["spec"]["envFile"] = "   "
        _, spec4 = parse_app_document(data4, path=Path("d.yaml"))
        assert spec4.env_file is None

        data5 = _base_docker()
        data5["spec"]["envFile"] = "/tmp/../secret"
        with pytest.raises(ValueError, match="must not contain"):
            parse_app_document(data5, path=Path("e.yaml"))

        data6 = _base_docker()
        data6["spec"]["env"] = {"K": None}
        with pytest.raises(ValueError, match="must not be null"):
            parse_app_document(data6, path=Path("f.yaml"))

        data7 = _base_docker()
        data7["spec"]["env"] = []
        with pytest.raises(ValueError, match="spec.env must be an object"):
            parse_app_document(data7, path=Path("g.yaml"))

        data8 = _base_docker()
        data8["spec"]["volumes"] = "nope"
        with pytest.raises(ValueError, match="volumes must be a list"):
            parse_app_document(data8, path=Path("h.yaml"))

        data9 = _base_docker()
        data9["spec"]["volumes"] = ["x"]
        with pytest.raises(ValueError, match="must be an object"):
            parse_app_document(data9, path=Path("i.yaml"))

        data10 = _base_docker()
        data10["spec"]["volumes"] = [{"containerPath": "/data"}]
        with pytest.raises(ValueError, match="hostPath is required"):
            parse_app_document(data10, path=Path("j.yaml"))

        data11 = _base_docker()
        data11["spec"]["volumes"] = [{"hostPath": "/data"}]
        with pytest.raises(ValueError, match="containerPath is required"):
            parse_app_document(data11, path=Path("k.yaml"))

        data12 = _base_docker()
        data12["spec"]["volumes"] = [
            {"hostPath": "/data", "containerPath": "relative"}
        ]
        with pytest.raises(ValueError, match="must be absolute"):
            parse_app_document(data12, path=Path("l.yaml"))

        data13 = _base_docker()
        data13["spec"]["volumes"] = [
            {"hostPath": "/data", "containerPath": "/x", "readOnly": "yes"}
        ]
        with pytest.raises(ValueError, match="readOnly must be a boolean"):
            parse_app_document(data13, path=Path("m.yaml"))

        data14 = _base_docker()
        data14["spec"]["env"] = {"": "x"}
        with pytest.raises(ValueError, match="non-empty"):
            parse_app_document(data14, path=Path("n.yaml"))

        data15 = _base_docker()
        data15["spec"]["group"] = "  "
        _, spec15 = parse_app_document(data15, path=Path("o.yaml"))
        assert spec15.group is None

        data15b = _base_docker()
        data15b["spec"]["group"] = "Bad_Name"
        with pytest.raises(ValueError, match="spec.group"):
            parse_app_document(data15b, path=Path("o2.yaml"))

        data16 = _base_docker()
        data16["spec"]["volumes"] = [
            {"hostPath": "/data", "containerPath": "/x", "name": ""}
        ]
        _, spec16 = parse_app_document(data16, path=Path("p.yaml"))
        assert spec16.volumes[0].name is None

    def test_get_apps_group_filter_and_spec_errors(self) -> None:
        write_applied_app(
            self.tmp_path,
            "a",
            extra={"group": "demo"},
        )
        write_applied_app(self.tmp_path, "b")
        stack = load_stack(self.tmp_path)
        get_cmd.get_apps(stack, group="demo")
        get_cmd.get_apps(stack, group="missing")
        get_cmd.get_app(stack, "a")
        get_cmd.get_apps(stack)

    def test_apply_warns_missing_depends_on(self) -> None:
        path = self.tmp_path / "app.yaml"
        doc = _base_docker(name="stack-front")
        doc["spec"]["dependsOn"] = ["stack-redis"]
        path.write_text(yaml.safe_dump(doc), encoding="utf-8")
        stack = load_stack(self.tmp_path)
        with patch("raft.services.apply.say") as say:
            AppApply(stack).apply_file(path, deploy=False)
        assert any("dependsOn not yet applied" in str(c) for c in say.call_args_list)

        shell = MagicMock()

        def clone_with_manifest(*args, **kwargs):
            if "clone" not in args:
                return
            target = Path(args[-1])
            (target / ".raft").mkdir(parents=True, exist_ok=True)
            git_doc = _base_docker(name="stack-admin")
            git_doc["spec"]["dependsOn"] = ["stack-redis"]
            (target / ".raft" / "app.yaml").write_text(
                yaml.safe_dump(git_doc), encoding="utf-8"
            )

        shell.git.side_effect = clone_with_manifest
        applier = AppApply(load_stack(self.tmp_path))
        applier.sh = shell
        with patch("raft.services.apply.say") as say_git:
            applier.apply_git("git@github.com:org/stack.git", deploy=False)
        assert any(
            "dependsOn not yet applied" in str(c) for c in say_git.call_args_list
        )

    def test_doctor_group_banner(self) -> None:
        write_applied_app(
            self.tmp_path,
            "stack-a",
            extra={"group": "demo"},
        )
        write_applied_app(self.tmp_path, "solo")
        stack = load_stack(self.tmp_path)
        d = Doctor(stack)
        d.sh = MagicMock()
        d.auth = MagicMock()
        d.docker = MagicMock()
        buf = StringIO()
        results = [
            CheckResult(INFRA, "docker", "ok", "fine"),
            CheckResult("demo-stack-a", "contract", "ok", "fine"),
            CheckResult("solo", "contract", "ok", "fine"),
        ]
        assert d.report(results, out=buf, color=False) == 0
        text = buf.getvalue()
        assert "demo\n" in text
        assert "  demo-stack-a\n" in text
        assert "ungrouped\n" not in text
        assert "solo\n" in text
        assert "group: demo" not in text
        assert "infra\n" not in text
        assert "raft\n" in text
        assert "  raft-gate\n" in text
        assert "  raft-router\n" in text

        only_grouped = self.tmp_path / "grouped-only"
        only_grouped.mkdir()
        write_applied_app(
            only_grouped,
            "stack-b",
            extra={"group": "demo"},
        )
        stack2 = load_stack(only_grouped)
        d2 = Doctor(stack2)
        d2.sh = MagicMock()
        d2.auth = MagicMock()
        d2.docker = MagicMock()
        buf3 = StringIO()
        assert (
            d2.report(
                [
                    CheckResult(INFRA, "docker", "ok", "fine"),
                    CheckResult("demo-stack-b", "contract", "ok", "fine"),
                ],
                out=buf3,
                color=False,
            )
            == 0
        )
        text3 = buf3.getvalue()
        assert "ungrouped\n" not in text3
        assert "demo\n" in text3
        assert "  demo-stack-b\n" in text3

    def test_render_quoted_env(self) -> None:
        write_applied_app(
            self.tmp_path,
            "svc",
            source="docker",
            image="redis",
            public_host="",
            build_context=None,
            extra={
                "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
                "readiness": {"type": "none"},
                "env": {"EMPTY": "", "COLON": "a:b"},
            },
        )
        StackRenderer(load_stack(self.tmp_path)).render()
        text = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert 'EMPTY: ""' in text
        assert 'COLON: "a:b"' in text
