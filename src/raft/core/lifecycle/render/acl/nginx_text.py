"""Render nginx access-module directives from an :class:`AclPolicy`."""

from raft.core.core.models.acl_policy import AclPolicy

FORBIDDEN_ALIAS = "/usr/share/nginx/errors/forbidden.html"


class AclNginxText:
    """Produce indented ``allow`` / ``deny`` lines for a ``location`` body."""

    @staticmethod
    def location_rules(policy: AclPolicy, *, indent: str = "        ") -> str:
        if not policy.is_active():
            return ""
        lines: list[str] = [
            f"{indent}# raft ACL mode={policy.mode}",
            f"{indent}error_page 403 =403 /_raft_forbidden;",
        ]
        if policy.mode == "whitelist":
            for entry in policy.entries:
                lines.append(f"{indent}allow {entry.cidr};")
            lines.append(f"{indent}deny all;")
        else:
            for entry in policy.entries:
                lines.append(f"{indent}deny {entry.cidr};")
            lines.append(f"{indent}allow all;")
        return "\n".join(lines) + "\n"

    @staticmethod
    def forbidden_location(*, indent: str = "    ") -> str:
        return (
            f"{indent}location = /_raft_forbidden {{\n"
            f"{indent}    internal;\n"
            f"{indent}    default_type text/html;\n"
            f"{indent}    alias {FORBIDDEN_ALIAS};\n"
            f"{indent}}}\n"
        )

    @staticmethod
    def include_line(relative: str, *, indent: str = "        ") -> str:
        return f"{indent}include /etc/nginx/http-generated/acl/{relative};\n"
