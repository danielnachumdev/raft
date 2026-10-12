"""Gateway: raw ssh-keygen invocations via Shell."""

from raft.core.platform.adapters.shell import Shell


class SshKeygenGateway:
    """Transport-level ssh-keygen; no deploy-key product rules."""

    def __init__(self, shell: Shell) -> None:
        self.shell = shell

    def exec(self, argv: list[str]) -> None:
        self.shell.run(argv, capture=True)
