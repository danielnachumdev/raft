"""Map serve HTTP method+path → RBAC permission code (#307)."""

from typing import Optional


class RbacHttpGate:
    """Prefix/action rules for ``/api/*`` (None = skip RBAC)."""

    _PREFIXES: tuple[tuple[str, str], ...] = (
        ("/api/firewall", "firewall"),
        ("/api/alerts", "alerts"),
        ("/api/notifications", "notifications"),
        ("/api/settings", "settings"),
        ("/api/rbac", "rbac"),
        ("/api/github", "github"),
        ("/api/update", "update"),
        ("/api/inbox", "inbox"),
        ("/api/events", "events"),
        ("/api/metrics", "metrics"),
        ("/api/exports", "metrics"),
        ("/api/status", "status"),
    )

    _SKIP_PREFIXES: tuple[str, ...] = (
        "/api/dashboard/",
        "/login",
        "/assets/",
        "/oauth2/",
    )

    def permission(self, method: str, path: str) -> Optional[str]:
        if self._skip(path):
            return None
        if path == "/api/purge" or self._runtime_action(path):
            return "runtime:write"
        resource = self._resource(path)
        if resource is None:
            if path.startswith("/api/service/"):
                return self._service_permission(method, path)
            return None
        action = "read" if method.upper() == "GET" else "write"
        return f"{resource}:{action}"

    def _skip(self, path: str) -> bool:
        if path in {"/", "/login"}:
            return True
        return any(path.startswith(prefix) for prefix in self._SKIP_PREFIXES)

    def _resource(self, path: str) -> Optional[str]:
        for prefix, resource in self._PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return resource
        return None

    @staticmethod
    def _runtime_action(path: str) -> bool:
        return path.endswith(("/up", "/down", "/redeploy"))

    def _service_permission(self, method: str, path: str) -> str:
        if self._runtime_action(path):
            return "runtime:write"
        if "/logs" in path:
            return "logs:read" if method.upper() == "GET" else "logs:write"
        return "service:read" if method.upper() == "GET" else "service:write"
