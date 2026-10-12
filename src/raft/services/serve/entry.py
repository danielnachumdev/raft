"""Process entry for ``python -m raft.services.serve``."""

import argparse
import sys
from typing import Optional

from raft.core.core.models.stack import load_stack

from .service import DEFAULT_SERVE_PORT, Serve


class ServeMain:
    """Bootstrap stack and delegate to :class:`Serve`."""

    def run(self, argv: Optional[list[str]] = None) -> None:
        args = self._parse(argv)
        serve = Serve(load_stack())
        if args.stop:
            serve.stop(port=args.port)
            return
        serve.run(port=args.port)

    def _parse(self, argv: Optional[list[str]]) -> argparse.Namespace:
        parser = argparse.ArgumentParser(prog="python -m raft.services.serve")
        parser.add_argument("--port", type=int, default=DEFAULT_SERVE_PORT)
        parser.add_argument(
            "--stop",
            action="store_true",
            help="stop an already-running serve on this port",
        )
        return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main() -> None:
    """Console / ``python -m raft.services.serve`` entry."""
    ServeMain().run()
