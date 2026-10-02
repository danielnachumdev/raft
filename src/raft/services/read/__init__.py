"""Shared read contracts for status (and doctor) — CLI + serve/FE.

Canonical status JSON matches ``raft status --json`` / ``StatusSnapshot.to_dict()``:

.. code-block:: json

    {
      "host": { "cpus", "loadavg", "memory", "disk", "uptime_seconds" },
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
``control_plane`` / ``apps`` (display labels + human cpu/memory/uptime strings)
for the dashboard SPA tables. Prefer ``containers`` for new FE work (#35/#9).

Doctor JSON is deferred for a full dashboard health view; see
``DoctorRead.intended_payload_shape`` and ``DoctorRead.from_results``.
"""

from .doctor import DoctorRead
from .status import StatusRead
from .view import ServeRow, ServeSnapshotView

__all__ = ["DoctorRead", "ServeRow", "ServeSnapshotView", "StatusRead"]
