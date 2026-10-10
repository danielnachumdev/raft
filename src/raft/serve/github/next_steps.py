"""Generic post-deploy operator steps raft cannot automate safely in v1."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from raft.models.app import App
from raft.models.manifest import AppSpec


class DeployNextSteps:
    """Build UI-facing instruction cards from the applied App + auth hints."""

    def build(
        self,
        app: App,
        spec: AppSpec,
        *,
        deploy_pubkey: Optional[str] = None,
        deploy_key_url: Optional[str] = None,
        key_fingerprint: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        steps: List[Dict[str, str]] = []
        steps.extend(self._dns(app, spec))
        steps.extend(self._tls(app, spec))
        steps.extend(self._env_file(spec))
        steps.extend(self._volumes(spec))
        steps.extend(self._deploy_key(deploy_pubkey, deploy_key_url, key_fingerprint))
        if not steps:
            steps.append(self._verify(app))
        return steps

    def ci_steps(self, ci_pr: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
        if not ci_pr:
            return []
        status = str(ci_pr.get("status") or "")
        if status == "opened" and ci_pr.get("pr_url"):
            return [self._ci_opened(str(ci_pr["pr_url"]))]
        if status == "exists":
            return [self._ci_exists()]
        if status == "failed":
            return [self._ci_failed(str(ci_pr.get("detail") or ""))]
        return []

    @staticmethod
    def _ci_opened(pr_url: str) -> Dict[str, str]:
        return {
            "title": "Merge CI PR",
            "body": (
                f"Review and merge {pr_url}, then set repo secrets "
                "RAFT_SSH_HOST, RAFT_SSH_USER, RAFT_SSH_KEY so push deploys run."
            ),
        }

    @staticmethod
    def _ci_exists() -> Dict[str, str]:
        return {
            "title": "CI workflow",
            "body": (
                "raft-apply workflow already present. Ensure "
                "RAFT_SSH_* secrets are set for automatic deploys."
            ),
        }

    @staticmethod
    def _ci_failed(detail: str) -> Dict[str, str]:
        return {
            "title": "CI PR setup failed",
            "body": detail or "Could not open CI PR. Re-login and retry.",
        }

    def _dns(self, app: App, spec: AppSpec) -> List[Dict[str, str]]:
        if not app.public_host:
            return []
        hosts = [app.public_host, *list(spec.extra_hosts)]
        listed = ", ".join(hosts)
        return [
            {
                "title": "DNS",
                "body": (
                    f"Point A/AAAA records for {listed} at this host before "
                    "trusting public HTTP/HTTPS."
                ),
            }
        ]

    def _tls(self, app: App, spec: AppSpec) -> List[Dict[str, str]]:
        if spec.tls == "origin":
            return [self._origin_tls(app.name)]
        if spec.tls == "acme":
            return [self._acme_tls(app.name)]
        return []

    @staticmethod
    def _origin_tls(app_name: str) -> Dict[str, str]:
        return {
            "title": "Origin TLS material",
            "body": (
                f"Install origin.pem + origin.key under certs/{app_name}/ "
                "before trusting HTTPS (raft never pastes PEMs for you)."
            ),
        }

    @staticmethod
    def _acme_tls(app_name: str) -> Dict[str, str]:
        return {
            "title": "ACME prerequisites",
            "body": (
                "Ensure DNS points here, TCP 80+443 are open, and "
                "acme.email is set in settings.yaml. Live material is "
                f"written to certs/{app_name}/acme.* by apply/controller."
            ),
        }

    def _env_file(self, spec: AppSpec) -> List[Dict[str, str]]:
        if not spec.env_file:
            return []
        return [
            {
                "title": "Env file",
                "body": (
                    f"Create the host env file at {spec.env_file} "
                    "(prefer ~/.raft/secrets/<app>/env, mode 0600; dir 0700) "
                    "with the secrets your App expects. Raft does not write "
                    "secret values into that file, the registry, or generated/. "
                    "Never mount App secrets into gate/router."
                ),
            }
        ]

    def _volumes(self, spec: AppSpec) -> List[Dict[str, str]]:
        if not spec.volumes:
            return []
        paths = ", ".join(v.host_path for v in spec.volumes)
        return [
            {
                "title": "Host volumes",
                "body": (
                    f"Ensure host directories exist and are writable as needed: {paths}."
                ),
            }
        ]

    def _deploy_key(
        self,
        pubkey: Optional[str],
        url: Optional[str],
        fingerprint: Optional[str],
    ) -> List[Dict[str, str]]:
        if not pubkey and not fingerprint:
            return []
        lines = [
            "Add a read-only deploy key on the GitHub repo (Settings → Deploy keys).",
        ]
        if fingerprint:
            lines.append(f"Fingerprint: {fingerprint}")
        if url:
            lines.append(f"Open: {url}")
        lines.append(
            "Copy the public key from the deploy progress panel — never screenshot "
            "private keys or OAuth tokens."
        )
        return [{"title": "Deploy key", "body": " ".join(lines)}]

    @staticmethod
    def _verify(app: App) -> Dict[str, str]:
        host = app.public_host or app.name
        return {
            "title": "Verify the site",
            "body": (
                "Automated steps finished. Run `raft doctor` and "
                f"`curl -H 'Host: {host}' http://127.0.0.1/` when the gate is up."
            ),
        }
