"""``python -m raft.services.cli`` entry."""

import sys

from raft.core.observe.ops.version import InstalledVersion
from raft.services.cli.utils.deps import RaftCLI
from raft.services.cli.utils.version_argv import VersionArgv


def main() -> None:
    argv = sys.argv[1:]
    if VersionArgv.is_request(argv):
        print(InstalledVersion().line(), flush=True)
        return
    RaftCLI().run()


if __name__ == "__main__":
    main()
