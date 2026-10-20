"""Shared read contracts for status (and doctor) — CLI + serve/FE.

Canonical status JSON matches ``raft status --json`` / ``StatusSnapshot.to_dict()``:

.. code-block:: json

    {
      "host": { "hostname", "cpus", "loadavg", "memory", "disk", "uptime_seconds" },
      "containers": [
        {
          "service", "role", "app", "group", "status", "uptime_seconds",
          "cpu_percent", "memory", "allocated", "network", "block_io", "pids"
        }
      ]
    }

``role`` is ``gate`` | ``router`` | ``controller`` | ``dashboard`` | ``app``.
Numeric fields are raw (bytes, percents, seconds) — format in the UI or CLI
human path. ``dashboard`` appears in ``control_plane`` only when enabled.

Serve ``GET /api/status`` returns that snapshot **plus** presentation lists
``control_plane`` / ``apps`` (display labels + human cpu/memory/started/uptime
strings, Compose ``service`` id for deep links, ``external_urls`` from
``publicHost`` + edge scheme/port, and ``depends_on`` Compose ids from App
``spec.dependsOn`` for SPA parent/child tree layout), ``registry_issues``
(skipped invalid ``services/<name>/app.yaml`` entries), and ``version``
(``package`` + human ``line`` from ``InstalledVersion``) for SPA chrome.
Prefer ``containers`` for new FE work (#35/#9).

Serve ``GET /api/service/{name}`` returns ``host`` + one ``container`` object
plus a ``presentation`` row (including ``external_urls``) for that Compose
service id (404 if unknown).

Serve ``GET /api/metrics`` returns historical **resource** series from
``host/metrics/resources.jsonl`` via ``MetricsRead`` (window, optional
``start``/``end`` absolute range, optional ``since`` cursor for SPA polling),
plus ``events`` from ``host/events/graph.jsonl``. Payload includes ``bounds``
from metrics retention (``retentionMaxAgeDays`` / earliest sample).

Serve ``GET /api/metrics/http`` returns historical **HTTP edge** series from
sibling ``host/metrics/http.jsonl`` via ``HttpMetricsRead`` (same window /
``since`` shape; ``kind: http``). Percentiles are over the controller sample
window (``metrics.intervalSeconds``). Live updates use HTTP polling — simpler
and durable for one FastAPI process than WebSockets. Serve status endpoints
reload ``services/`` on each call so out-of-band apply/delete is visible on
the next SPA poll (~2s when the tab is visible).

Serve ``GET /api/service/{name}/http-requests`` returns recent **per-request**
rows for Host-routed Apps (``expose: http`` + ``publicHost``) via
``HttpRequestsRead`` (tail of ``host/metrics/gate-http/access.log``). Trends
HTTP stays aggregate-only; see ``docs/serve-http-requests.md``.

Doctor JSON is deferred for a full dashboard health view; see
``DoctorRead.intended_payload_shape`` and ``DoctorRead.from_results``.
"""

from .depends import ServeDependsMap
from .doctor import DoctorRead
from .external_urls import ExternalUrlBuilder
from .http_requests import HttpRequestsRead
from .metrics import HttpMetricsRead, MetricsRead
from .serve_row import ServeRow
from .snapshot_view import ServeSnapshotView
from .status import StatusRead

__all__ = [
    "DoctorRead",
    "ExternalUrlBuilder",
    "HttpMetricsRead",
    "HttpRequestsRead",
    "MetricsRead",
    "ServeDependsMap",
    "ServeRow",
    "ServeSnapshotView",
    "StatusRead",
]
