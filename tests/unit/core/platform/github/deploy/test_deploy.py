"""GitHub deploy next-steps + job store unit tests."""

from __future__ import annotations

from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec, VolumeSpec
from raft.core.core.models.ports import PortSpec
from raft.core.platform.github.deploy import DeployJobStore
from raft.core.platform.github.deploy import DeployNextSteps

from tests.unit.base import RaftTestCase


class TestDeployNextSteps(RaftTestCase):
    def test_builds_dns_tls_env_volume_key(self) -> None:
        app, spec = self._origin_app_spec()
        steps = DeployNextSteps().build(
            app, spec, deploy_pubkey="ssh-ed25519 AAAA", key_fingerprint="SHA256:x"
        )
        titles = {s["title"] for s in steps}
        assert {
            "DNS",
            "Origin TLS material",
            "Env file",
            "Host volumes",
            "Add deploy key on GitHub",
        } <= titles
        self._assert_acme_and_bare(app)

    def _origin_app_spec(self):
        app = App(
            name="web",
            public_host="web.test",
            source="local",
            path="services/web/checkout",
        )
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            tls="origin",
            env_file="/tmp/web.env",
            volumes=(VolumeSpec(host_path="/data", container_path="/data"),),
        )
        return app, spec

    def _assert_acme_and_bare(self, app: App) -> None:
        acme = DeployNextSteps().build(app, AppSpec(ports=(), tls="acme"))
        assert any(s["title"] == "ACME prerequisites" for s in acme)
        bare = DeployNextSteps().build(
            App(name="w", public_host="", source="local", path="services/w/checkout"),
            AppSpec(ports=()),
        )
        assert bare[0]["title"] == "Verify the site"


class TestDeployJobStore(RaftTestCase):
    def test_claim_skips_finished_same_name(self) -> None:
        store = DeployJobStore()
        done = store.create("demo/api", "main")
        done.status = "succeeded"
        assert store.active_for("demo/api") is None
        job, coalesced = store.claim_or_create("demo/api", "main")
        assert coalesced is False
        assert job.id != done.id
        assert job.status == "pending"

    def test_claim_ignores_other_full_names(self) -> None:
        store = DeployJobStore()
        other = store.create("demo/other", "main")
        job, coalesced = store.claim_or_create("demo/api", "main")
        assert coalesced is False
        assert job.id != other.id
        assert store.active_for("demo/api") is job

    def test_claim_separates_manifest_paths(self) -> None:
        store = DeployJobStore()
        first, coalesced = store.claim_or_create(
            "demo/api", "main", manifest_path="a/.raft/app.yaml"
        )
        assert coalesced is False
        second, again = store.claim_or_create(
            "demo/api", "main", manifest_path="b/.raft/app.yaml"
        )
        assert again is False
        assert second.id != first.id
        same, coalesced_same = store.claim_or_create(
            "demo/api", "main", manifest_path="a/.raft/app.yaml"
        )
        assert coalesced_same is True
        assert same.id == first.id
