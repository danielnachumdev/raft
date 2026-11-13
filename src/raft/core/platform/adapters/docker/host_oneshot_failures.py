"""Operator-facing messages when a host Docker one-shot fails."""

from typing import Optional


class HostOneshotFailures:
    """Map shell/Docker failure detail to a short CTA message."""

    def message(self, exc: BaseException) -> str:
        detail = self.detail(exc)
        known = self.known_message(detail)
        if known is not None:
            return known
        summary = self.summary(detail)
        return (
            "host Docker one-shot failed: "
            f"{summary}\n"
            "Fix: check Docker, RAFT_HOST_HOME, and outbound network, "
            "then continue from the dashboard or run the command on the host"
        )

    def known_message(self, detail: str) -> Optional[str]:
        lower = detail.lower()
        if "permission denied (publickey)" in lower:
            return self._publickey_message()
        if "env file" in lower and "not found" in lower:
            return self._env_file_message(detail)
        if "origin" in lower and (
            "cert" in lower or "pem" in lower or "tls" in lower
        ):
            return self._origin_tls_message()
        if "timed out waiting" in lower:
            return self._readiness_timeout_message()
        return None

    @staticmethod
    def _readiness_timeout_message() -> str:
        return (
            "App readiness wait timed out.\n"
            "Fix: confirm the App serves its readiness path on the "
            "public host, check `docker compose ps` health (not just "
            "container running), raise readiness.timeoutSeconds / "
            "startPeriodSeconds if cold starts need longer, then "
            "continue installation."
        )

    @staticmethod
    def _publickey_message() -> str:
        return (
            "GitHub rejected the SSH deploy key (publickey).\n"
            "Fix: add the public key shown in the UI as a read-only "
            "Deploy key, then continue installation."
        )

    def _env_file_message(self, detail: str) -> str:
        path = self.env_path_from_detail(detail) or (
            "~/.raft/services/<app>/secrets/env"
        )
        return (
            f"App env file is missing: {path}\n"
            "Fix: create that file (mode 0600; secrets dir 0700) with the "
            "secrets the App expects, then continue installation."
        )

    @staticmethod
    def _origin_tls_message() -> str:
        return (
            "Origin TLS certificates are missing for this App.\n"
            "Fix: install origin.pem + origin.key under "
            "services/<app>/certs/, then continue installation."
        )

    def env_path_from_detail(self, detail: str) -> Optional[str]:
        for line in detail.splitlines():
            text = line.strip()
            if "env file" in text.lower() and "not found" in text.lower():
                if text.lower().startswith("env file "):
                    rest = text[9:]
                    cut = rest.lower().find(" not found")
                    if cut > 0:
                        return rest[:cut].strip()
        return None

    def summary(self, detail: str) -> str:
        lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
        while lines and lines[-1].lower().startswith("run `raft doctor`"):
            lines.pop()
        lines = self.drop_fix_tail(lines)
        if not lines:
            return "unknown error"
        preferred = [ln for ln in lines if self.looks_like_error(ln)]
        pick = preferred[-3:] if preferred else lines[-3:]
        return "\n".join(pick)

    @staticmethod
    def looks_like_error(line: str) -> bool:
        low = line.lower()
        if low.startswith("image ") or " building" in low:
            return False
        tokens = (
            "timed out",
            "failed",
            "error",
            "not found",
            "denied",
            "unhealthy",
            "cannot ",
            "fix:",
        )
        return any(token in low for token in tokens)

    def drop_fix_tail(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for ln in lines:
            low = ln.lower()
            if low in {"fix:", "fix"} or low.startswith("fix:"):
                break
            if low.startswith("hint:"):
                break
            if self.is_fix_step_line(ln):
                break
            if ln.startswith("---") and ln.endswith("---"):
                break
            out.append(ln)
        return out

    @staticmethod
    def is_fix_step_line(line: str) -> bool:
        stripped = line.lstrip()
        if len(stripped) < 3 or not stripped[0].isdigit():
            return False
        dot = stripped.find(".")
        return 0 < dot <= 3 and stripped[dot : dot + 2] == ". "

    @staticmethod
    def detail(exc: BaseException) -> str:
        detail = str(exc).strip()
        stderr = getattr(exc, "stderr", None)
        if isinstance(stderr, str) and stderr.strip():
            return stderr.strip()
        out = getattr(exc, "output", None)
        if isinstance(out, str) and out.strip():
            return out.strip()
        return detail
