"""Shell / subprocess mock helpers for unit tests."""

from unittest.mock import MagicMock


class ShellMocks:
    @classmethod
    def completed(
        cls,
        stdout: str = "",
        returncode: int = 0,
        stderr: str = "",
    ) -> MagicMock:
        m = MagicMock()
        m.stdout = stdout
        m.returncode = returncode
        m.stderr = stderr
        return m

    @classmethod
    def stub_run(
        cls,
        shell: MagicMock,
        *,
        stdout: str = "",
        returncode: int = 0,
        stderr: str = "",
    ) -> MagicMock:
        shell.run.return_value = cls.completed(
            stdout=stdout, returncode=returncode, stderr=stderr
        )
        return shell

    @classmethod
    def git_call_args(cls, shell: MagicMock) -> list:
        return [c.args for c in shell.git.call_args_list]
