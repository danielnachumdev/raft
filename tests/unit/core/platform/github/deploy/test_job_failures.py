"""GithubDeployFailures next-step and auth messaging branches."""

from raft.core.platform.github.deploy.job_failures import GithubDeployFailures
from raft.core.platform.github.deploy.models import DeployJob


class TestGithubDeployFailures:
    def test_auth_steps_omits_link_without_url(self) -> None:
        job = DeployJob(id="j", full_name="orphan", ref="main")
        GithubDeployFailures().auth_steps(job, "SHA256:demo")
        assert job.deploy_key_url is None
        body = job.next_steps[0]["body"]
        assert "Fingerprint: SHA256:demo" in body
        assert "Link:" not in body

    def test_apply_steps_env_and_tls(self) -> None:
        failures = GithubDeployFailures()
        env_job = DeployJob(id="e", full_name="o/r", ref="main", app_name="demo-api")
        failures.apply_steps(
            env_job, "env file /x/secrets/env not found: no such file"
        )
        assert env_job.next_steps[0]["title"] == "Env file"
        assert "demo-api/secrets/env" in env_job.next_steps[0]["body"]

        tls_job = DeployJob(id="t", full_name="o/r", ref="main", app_name="demo-api")
        failures.apply_steps(tls_job, "origin TLS certs missing under certs/")
        assert tls_job.next_steps[0]["title"] == "Origin TLS material"

        skip = DeployJob(id="s", full_name="o/r", ref="main", app_name="demo-api")
        failures.apply_steps(skip, "origin hostname mismatch only")
        assert skip.next_steps == []

    def test_deploy_key_failure_variants_and_auth_message(self) -> None:
        assert GithubDeployFailures.is_deploy_key_failure(
            "Permission denied (publickey)"
        )
        assert GithubDeployFailures.is_deploy_key_failure(
            "deploy key was rejected by GitHub"
        )
        assert not GithubDeployFailures.is_deploy_key_failure("network timeout")
        detail = "Permission denied (publickey)"
        assert (
            GithubDeployFailures.auth_message(detail, "SHA256:x") == detail
        )
        wrapped = GithubDeployFailures.auth_message("clone failed", "SHA256:x")
        assert "fingerprint SHA256:x" in wrapped
