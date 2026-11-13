"""Deploy-job next-step / auth failure messaging."""

from typing import Optional

from .models import DeployJob


class GithubDeployFailures:
    """Operator-facing next steps when apply or deploy-key auth fails."""

    def auth_steps(self, job: DeployJob, fp: str) -> None:
        url = job.deploy_key_url or self.deploy_key_url(job)
        job.deploy_key_url = url
        body = (
            "Copy Title + Key below into the repo Deploy keys form "
            f"(read-only), then press Continue installation. Fingerprint: {fp}."
        )
        if url:
            body = f"{body} Link: {url}"
        job.next_steps = [{"title": "Add deploy key on GitHub", "body": body}]

    def apply_steps(self, job: DeployJob, detail: str) -> None:
        lower = detail.lower()
        app = job.app_name or "<app>"
        env = self._env_file_steps(app, lower)
        if env is not None:
            job.next_steps = env
            return
        tls = self._origin_tls_steps(app, lower)
        if tls is not None:
            job.next_steps = tls

    @staticmethod
    def _env_file_steps(app: str, lower: str) -> Optional[list]:
        if "env file" not in lower or "not found" not in lower:
            return None
        return [
            {
                "title": "Env file",
                "body": (
                    f"Create ~/.raft/services/{app}/secrets/env "
                    "(mode 0600; dir 0700) with the secrets this App "
                    "expects, then press Continue installation. Raft "
                    "does not write secret values for you."
                ),
            }
        ]

    @staticmethod
    def _origin_tls_steps(app: str, lower: str) -> Optional[list]:
        if "origin" not in lower:
            return None
        if "cert" not in lower and "pem" not in lower and "tls" not in lower:
            return None
        return [
            {
                "title": "Origin TLS material",
                "body": (
                    f"Install origin.pem + origin.key under "
                    f"services/{app}/certs/, then press Continue "
                    "installation."
                ),
            }
        ]

    @staticmethod
    def is_deploy_key_failure(detail: str) -> bool:
        lower = detail.lower()
        return "permission denied (publickey)" in lower or (
            "deploy key" in lower and "rejected" in lower
        )

    @staticmethod
    def auth_message(detail: str, fp: str) -> str:
        text = detail.strip()
        if GithubDeployFailures.is_deploy_key_failure(text):
            return text
        return (
            f"{text}\n"
            "Add the deploy public key shown in the UI "
            f"(fingerprint {fp}), then continue installation."
        )

    @staticmethod
    def deploy_key_url(job: DeployJob) -> Optional[str]:
        if "/" not in job.full_name:
            return None
        return f"https://github.com/{job.full_name}/settings/keys/new"
