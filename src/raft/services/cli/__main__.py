"""``python -m raft.services.cli`` entry."""

from .cli import RaftCLI


def main() -> None:
    RaftCLI().run()


if __name__ == "__main__":
    main()
