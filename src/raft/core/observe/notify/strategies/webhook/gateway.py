"""Raw HTTP transport for webhook delivery (no product vocabulary)."""

from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WebhookHttpGateway:
    """POST bytes to a URL; return status code or raise transport errors."""

    def __init__(self, *, opener: Optional[Any] = None) -> None:
        self._opener = opener or urlopen

    def post(
        self,
        url: str,
        data: bytes,
        headers: Mapping[str, str],
        *,
        timeout: float,
    ) -> int:
        request = Request(url, data=data, headers=dict(headers), method="POST")
        try:
            with self._opener(request, timeout=timeout) as response:
                code = getattr(response, "status", None) or response.getcode()
                return int(code)
        except HTTPError as exc:
            return int(exc.code)
        except (URLError, TimeoutError, OSError):
            raise
