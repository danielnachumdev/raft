"""GitHub Actions workflow text for serve CI PR setup (v1)."""

from __future__ import annotations

from .provider import GithubRepo

WORKFLOW_REL = ".github/workflows/raft-apply.yml"
BRANCH_NAME = "raft/ci-apply"


class RaftApplyWorkflow:
    """Render the ``raft apply`` Actions workflow committed via PR."""

    def render(self, repo: GithubRepo, default_branch: str) -> str:
        return "\n".join(
            [
                *self._on_block(default_branch),
                *self._job_env(repo),
                *self._run_script(),
                "",
            ]
        )

    @staticmethod
    def _on_block(default_branch: str) -> list[str]:
        return [
            "# Added by raft serve — deploy App on push via SSH to the raft host.",
            "name: raft apply",
            "",
            "on:",
            "  push:",
            f'    branches: ["{default_branch}"]',
            "  workflow_dispatch:",
            "",
            "jobs:",
            "  apply:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
        ]

    @staticmethod
    def _job_env(repo: GithubRepo) -> list[str]:
        return [
            "      - name: Apply on raft host via SSH",
            "        env:",
            "          RAFT_SSH_HOST: ${{ secrets.RAFT_SSH_HOST }}",
            "          RAFT_SSH_USER: ${{ secrets.RAFT_SSH_USER }}",
            "          RAFT_SSH_KEY: ${{ secrets.RAFT_SSH_KEY }}",
            "          REF: ${{ github.sha }}",
            f"          REPO: {repo.ssh_url}",
            "        run: |",
        ]

    @staticmethod
    def _run_script() -> list[str]:
        return [
            "          set -euo pipefail",
            '          if [ -z "${RAFT_SSH_HOST:-}" ] || [ -z "${RAFT_SSH_KEY:-}" ]; then',
            '            echo "Set repo secrets RAFT_SSH_HOST, RAFT_SSH_USER, RAFT_SSH_KEY"',
            "            exit 1",
            "          fi",
            "          mkdir -p ~/.ssh",
            "          printf '%s\\n' \"$RAFT_SSH_KEY\" > ~/.ssh/id_ed25519",
            "          chmod 600 ~/.ssh/id_ed25519",
            '          USER="${RAFT_SSH_USER:-root}"',
            "          ssh -o StrictHostKeyChecking=accept-new \\",
            '            "${USER}@${RAFT_SSH_HOST}" \\',
            "            \"raft apply --git '${REPO}' --ref '${REF}'\"",
        ]

    @staticmethod
    def pr_body() -> str:
        return (
            "Adds `.github/workflows/raft-apply.yml` so pushes to the default "
            "branch run `raft apply --git … --ref $SHA` on your raft host over SSH.\n\n"
            "After merge, set repository secrets: `RAFT_SSH_HOST`, "
            "`RAFT_SSH_USER`, `RAFT_SSH_KEY` (private key for the host)."
        )
