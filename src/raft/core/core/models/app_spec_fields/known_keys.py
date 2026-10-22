"""Known ``spec`` keys and rejection of unsupported fields."""

import re
from pathlib import Path
from typing import Any

from raft.core.core.errors.cta import OperatorError

GROUP_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# Keys read by AppDocument / field parsers. Legacy aliases and keys that only
# exist to emit a specific Fix CTA (port, readinessProbe, groups) stay listed.
KNOWN_SPEC_KEYS = frozenset(
    {
        "source",
        "repo",
        "image",
        "ref",
        "path",
        "publicHost",
        "public_host",
        "ports",
        "port",
        "tls",
        "readiness",
        "readinessProbe",
        "extraHosts",
        "extra_hosts",
        "build",
        "scaling",
        "deployment",
        "resources",
        "dependsOn",
        "depends_on",
        "envFile",
        "env_file",
        "env",
        "volumes",
        "group",
        "groups",
    }
)


class AppSpecKnownKeys:
    """Reject unknown App ``spec`` keys with an operator Fix CTA."""

    @staticmethod
    def reject_unknown(spec: dict[str, Any], path: Path) -> None:
        unknown = sorted(set(spec) - KNOWN_SPEC_KEYS)
        if not unknown:
            return
        keys = ", ".join(unknown)
        raise OperatorError(
            f"{path}: unsupported spec field(s): {keys}\n"
            f"Fix: remove unknown keys from spec "
            f"(supported fields: see AGENTS.md / core models)"
        )
