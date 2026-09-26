"""Image refs, tmp containers, router network."""

from unittest.mock import patch

import pytest

from raft.models.ports import PortSpec
from raft.services.ops.certs import MissingOriginCerts

from ...base import make_app
from .base import DockerTestCase


class TestDockerImagesTmp(DockerTestCase):
    def test_container_image_ref_named_ok(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("raft-app:latest\n"),
            self.ok("sha256:abc\n"),
        ]
        assert self.docker.container_image_ref("cid") == "raft-app:latest"

    def test_container_image_ref_commits_when_unnamed(self) -> None:
        self.shell.docker.side_effect = [self.ok(""), self.ok()]
        assert self.docker.container_image_ref("abcdefghijklmn") == "raft-snapshot:abcdefghijkl"

    def test_container_image_ref_commits_when_named_missing(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("gone:tag\n"),
            self.ok("", returncode=1),
            self.ok(),
        ]
        assert self.docker.container_image_ref("cid1234567890") == "raft-snapshot:cid123456789"

    def test_container_image_id_falls_back_to_ref(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("img:tag\n"),
            self.ok("sha256:id\n"),
            self.ok("  \n"),
        ]
        assert self.docker.container_image_id("cid") == "img:tag"

    def test_router_network_first_or_default(self) -> None:
        self.shell.compose.return_value = self.ok("routerid\n")
        self.shell.docker.return_value = self.ok("net_a\nnet_b\n")
        assert self.docker.router_network() == "net_a"
        self.shell.docker.return_value = self.ok("\n")
        assert self.docker.router_network() == "raft_default"

    def test_run_tmp_and_remove(self) -> None:
        self.shell.docker.return_value = self.ok()
        self.docker.run_tmp(name="n", alias="a", image="img", network="net")
        assert self.shell.docker.call_count >= 2

    def test_run_tmp_passes_env_file(self) -> None:
        self.shell.docker.return_value = self.ok()
        self.docker.run_tmp(
            name="n",
            alias="a",
            image="img",
            network="net",
            env_file="/tmp/app.env",
        )
        run_call = next(
            c
            for c in self.shell.docker.call_args_list
            if c.args and c.args[0] == "run"
        )
        assert "--env-file" in run_call.args
        assert "/tmp/app.env" in run_call.args

