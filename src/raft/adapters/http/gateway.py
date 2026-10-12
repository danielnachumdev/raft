"""Raw HTTP GET against a URL (no Host-routing product rules)."""

import logging
import urllib.error
import urllib.request
from typing import Mapping, Optional

logger = logging.getLogger(__name__)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Keep the first response — oauth gates 302 off-box and break follow-based probes."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class HttpGateway:
    """Transport-level HTTP GET; returns status code or ``None`` on failure."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect)

    def get(
        self,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        timeout: float = 3.0,
    ) -> Optional[int]:
        request = urllib.request.Request(
            url,
            headers=dict(headers or {}),
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return int(response.status)
        except urllib.error.HTTPError as exc:
            # No-redirect opener surfaces 3xx as HTTPError; status is still useful.
            return int(exc.code)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            logger.debug("http get %s failed: %s", url, exc)
            return None
