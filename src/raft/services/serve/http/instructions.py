"""Stdout connection instructions for localhost-only serve."""


import sys
from typing import Optional, TextIO


class ServeInstructions:
    """Print bind URL and a generic port-forward example before listening."""

    def __init__(
        self,
        port: int,
        *,
        always_on_url: Optional[str] = None,
        public_url: Optional[str] = None,
    ) -> None:
        self.port = port
        self._always_on = always_on_url
        self._public = public_url

    def print(self, out: Optional[TextIO] = None) -> None:
        stream = out if out is not None else sys.stdout
        stream.write(self.render())
        stream.flush()

    def render(self) -> str:
        lines = self._base_lines()
        lines.extend(self._always_on_lines())
        lines.append("")
        return "\n".join(lines) + "\n"

    def _base_lines(self) -> list[str]:
        port = self.port
        url = f"http://127.0.0.1:{port}/"
        return [
            f"raft serve listening on {url} (localhost only)",
            "",
            "Open that URL on the host, or forward the port from elsewhere:",
            "",
            f"  ssh -L {port}:127.0.0.1:{port} USER@HOST",
            "",
            f"Then open {url} in a browser.",
            "Stop with Ctrl+C, or from another shell: raft serve --stop",
        ]

    def _always_on_lines(self) -> list[str]:
        if not self._always_on:
            return []
        lines = ["", f"Always-on dashboard is also up at {self._always_on}"]
        if self._public:
            lines.append(f"Public URL: {self._public}")
        return lines
