"""Doctor checks for docker image sources and certs."""

from __future__ import annotations

from unittest.mock import MagicMock

from ....base import make_app, make_stack, write_applied_app
from .base import DoctorTestCase


class TestDoctorDockerCerts(DoctorTestCase):
    def _hub_docker_app(self, **kwargs):
        self.seed_compose()
        self.write_certs("hub")
        return make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main", **kwargs
        )

    def _hub_with_repo(self):
        self.seed_generated_apps()
        return self._hub_docker_app(
            repo="git@github.com:org/hub.git", path="apps/hub"
        )

    def test_docker_source_image_checks(self) -> None:
        stack = make_stack(self.tmp_path, (self._hub_docker_app(),))
        results = self.run_keyed(
            stack, shell=self.mock_shell(), docker=self.mock_docker(), auth=MagicMock()
        )
        assert results[("hub", "sync")].status == "ok"
        assert "ghcr.io/org/hub:main" in results[("hub", "sync")].detail
        assert results[("hub", "auth")].status == "ok"
        assert "registry auth" in results[("hub", "auth")].detail
        assert results[("hub", "contract")].status == "fail"

    def test_docker_with_repo_checks_contract_and_auth(self) -> None:
        app = self._hub_with_repo()
        (self.tmp_path / "apps" / "hub").mkdir(parents=True)
        self._write_hub_registry()
        auth = MagicMock()
        auth.is_configured.return_value = True
        results = self.run_keyed(
            make_stack(self.tmp_path, (app,)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=auth,
        )
        assert results[("hub", "contract")].status == "ok"
        assert results[("hub", "auth")].status == "ok"
        assert "deploy key present" in results[("hub", "auth")].detail

    def _write_hub_registry(self) -> None:
        reg = self.tmp_path / "state" / "apps" / "hub.yaml"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: hub\nspec:\n"
            "  publicHost: hub.test\n  source: docker\n  image: ghcr.io/org/hub\n"
            "  ref: main\n  repo: git@github.com:org/hub.git\n  path: apps/hub\n"
            "  www: false\n  ports:\n"
            "    - name: http\n      containerPort: 80\n      expose: http\n",
            encoding="utf-8",
        )

    def test_docker_with_repo_warns_without_deploy_key(self) -> None:
        app = self._hub_with_repo()
        (self.tmp_path / "apps" / "hub").mkdir(parents=True)
        auth = MagicMock()
        auth.is_configured.return_value = False
        results = self.run_keyed(
            make_stack(self.tmp_path, (app,)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=auth,
        )
        assert results[("hub", "auth")].status == "warn"
        assert results[("hub", "contract")].status == "fail"

    def test_contract_invalid_content(self) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        self.write_certs("app")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        self._write_bad_registry()
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_app("app"),)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
        )
        assert results[("app", "contract")].status == "fail"
        assert "apiVersion" in results[("app", "contract")].detail

    def _write_bad_registry(self) -> None:
        reg = self.tmp_path / "state" / "apps" / "app.yaml"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(
            "apiVersion: nope\nkind: App\nmetadata:\n  name: app\nspec:\n"
            "  publicHost: app.test\n  source: local\n",
            encoding="utf-8",
        )

    def test_docker_source_image_missing(self) -> None:
        stack = make_stack(self.tmp_path, (self._hub_docker_app(),))
        results = self.run_keyed(
            stack,
            shell=self.mock_shell(),
            docker=self.mock_docker(image_rc=1, image_out=""),
            auth=MagicMock(),
        )
        assert results[("hub", "sync")].status == "fail"
        fix = results[("hub", "sync")].fix or ""
        assert "ghcr.io/org/hub:main" in fix
        assert "https://github.com/settings/tokens/new?scopes=read:packages" in fix
        assert "docker login ghcr.io" in fix and "raft sync hub" in fix

    def test_certs_partial_pair_fails(self) -> None:
        self.seed_compose()
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        write_applied_app(self.tmp_path, "app", tls="origin")
        d = self.tmp_path / "certs" / "app"
        d.mkdir(parents=True)
        (d / "origin.pem").write_text("pem\n", encoding="utf-8")
        results = self.run_keyed(shell=self.mock_shell(), docker=self.mock_docker(), auth=MagicMock())
        assert results[("app", "certs")].status == "fail"
        assert "origin.key" in results[("app", "certs")].detail
        assert "tls: origin" in results[("app", "certs")].fix
