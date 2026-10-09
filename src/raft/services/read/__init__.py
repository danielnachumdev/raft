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

``role`` is ``gate`` | ``router`` | ``controller`` | ``app``. Numeric fields are
raw (bytes, percents, seconds) — format in the UI or CLI human path.

Serve ``GET /api/status`` returns that snapshot **plus** presentation lists
``control_plane`` / ``apps`` (display labels + human cpu/memory/started/uptime
strings, Compose ``service`` id for deep links, ``external_urls`` from
``publicHost`` + edge scheme/port, and ``depends_on`` Compose ids from App
``spec.dependsOn`` for SPA parent/child tree layout) and ``registry_issues``
(skipped invalid ``state/apps/*.yaml`` entries) for the dashboard tables.
Prefer ``containers`` for new FE work (#35/#9).

Serve ``GET /api/service/{name}`` returns ``host`` + one ``container`` object
plus a ``presentation`` row (including ``external_urls``) for that Compose
service id (404 if unknown).

Serve ``GET /api/metrics`` returns historical series from
``state/metrics/resources.jsonl`` via ``MetricsRead`` (window, optional
``start``/``end`` absolute range, optional ``since`` cursor for SPA polling),
plus ``events`` from ``state/events/graph.jsonl``. Payload includes ``bounds``
from metrics retention (``retentionMaxAgeDays`` / earliest sample).
Live updates use HTTP polling — simpler and durable for one FastAPI process
than WebSockets. Serve status endpoints reload ``state/apps/`` on each call so
out-of-band apply/delete is visible on the next SPA poll (~2s when the tab is
visible).

Doctor JSON is deferred for a full dashboard health view; see
``DoctorRead.intended_payload_shape`` and ``DoctorRead.from_results``.
"""

from .depends import ServeDependsMap
from .doctor import DoctorRead
from .external_urls import ExternalUrlBuilder
from .metrics import MetricsRead
from .status import StatusRead
from .view import ServeRow, ServeSnapshotView

__all__ = [
    "DoctorRead",
    "ExternalUrlBuilder",
    "MetricsRead",
    "ServeDependsMap",
    "ServeRow",
    "ServeSnapshotView",
    "StatusRead",
]
