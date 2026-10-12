"""Parse ``Total reclaimed space: …`` lines from docker prune output."""

import re

from ..host.docker_stats import DockerStatsText


class DockerPruneReclaim:
    """Parse ``Total reclaimed space: …`` lines from docker prune output."""

    _LINE = re.compile(
        r"Total reclaimed space:\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    @classmethod
    def parse(cls, text: str) -> int:
        """Return reclaimed bytes from prune stdout (0 when absent/unparsed)."""
        match = cls._LINE.search(text or "")
        if match is None:
            return 0
        parsed = DockerStatsText.parse_size(match.group(1).strip())
        return int(parsed) if parsed is not None else 0
