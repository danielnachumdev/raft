"""Whether a detached host oneshot container is still running."""

from raft.core.platform.adapters.shell import Shell


class HostOneshotAlive:
    """Probe ``docker inspect`` for a oneshot container id."""

    def __init__(self, shell: Shell) -> None:
        self._shell = shell

    def running(self, job_id: str) -> bool:
        cid = (job_id or "").strip()
        if not cid:
            return False
        completed = self._shell.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                cid,
            ],
            check=False,
            capture=True,
            timeout=15.0,
        )
        if getattr(completed, "returncode", 1) != 0:
            return False
        out = getattr(completed, "stdout", "") or ""
        return out.strip().lower() == "true"
