"""Resolve GitHub OAuth homepage / callback base for serve vs public dashboard."""

from typing import Optional, Tuple
from urllib.parse import urlparse


class GithubOauthPublicBase:
    """Pick https://publicHost when dashboard is public; else 127.0.0.1."""

    REDIRECT_PATH = "/api/github/callback"

    def urls(
        self,
        *,
        port: int,
        public_host: Optional[str] = None,
        tls: str = "off",
    ) -> Tuple[str, str]:
        base = self.base(port=port, public_host=public_host, tls=tls)
        return f"{base}/", f"{base}{self.REDIRECT_PATH}"

    def base(
        self,
        *,
        port: int,
        public_host: Optional[str] = None,
        tls: str = "off",
    ) -> str:
        host = self.normalize_host(public_host)
        if host:
            return f"{self._scheme(tls, host)}://{host}"
        return f"http://127.0.0.1:{int(port)}"

    def is_public(self, public_host: Optional[str] = None) -> bool:
        return self.normalize_host(public_host) is not None

    @staticmethod
    def normalize_host(raw: Optional[str]) -> Optional[str]:
        text = str(raw or "").strip()
        if not text:
            return None
        if "://" in text:
            parsed = urlparse(text)
            text = parsed.netloc or parsed.path
        text = text.strip().rstrip("/")
        if not text or text.startswith("127.0.0.1") or text == "localhost":
            return None
        return text

    @staticmethod
    def _scheme(tls: str, host: str) -> str:
        del host
        mode = str(tls or "off").strip().lower()
        return "https" if mode in {"origin", "acme"} else "http"
