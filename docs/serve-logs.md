# Service logs (CLI + serve)

Operators read Compose stdout/stderr via shared `raft.core.observe.ops.logs.Logs`
(`raft logs`, serve Logs panel, download).

## Live vs retained

| Mode | When | Source |
|------|------|--------|
| **Follow** (`-f` / SSE) | Container running | Live `docker compose logs -f` |
| **Snapshot** / download | Always (known target) | Retained files under `~/.raft/state/service-logs/<compose-id>/`, with a one-shot Docker fallback if the container still exists and nothing is retained yet |

Unknown / never-applied names still fail with the unknown-target CTA (404 on serve).

When a service is scaled to zero, recreated, or removed, snapshot shows retained
history or an empty panel — not a hard “not running” that blocks all history.
Follow still requires a running container.

## Retention layout

```text
~/.raft/state/service-logs/
  demo-api/
    current.log              # active append target
    current.log.2026-10-14   # sealed archives (LogArchiveNames)
    meta.json                # container id + Docker timestamp cursor
  raft-gate/
  raft-router/
  raft-controller/
```

Rotation reuses `LogRotationBootstrap` (same seal/age pattern as host `logs/raft.log`
and metrics JSONL). Settings: `serviceLogs` in `~/.raft/host/settings.yaml`
(see `examples/settings.yaml`).

## Capture

1. **Controller shipper** (`ServiceLogsShipper`) polls running containers and appends
   new `docker logs --timestamps` lines.
2. **Final drain** before `remove_container`, force-recreate, rebuild, gate/router
   recreate, and stack down — best-effort so cutover/`rm` does not race the last lines.

The controller needs a writable bind of `./state/service-logs` (packaged compose).

## Privacy

Stdout may contain secrets. Retained files are mode `0600` under the data home.
Do not commit them; fixtures and docs use dummy names only (`demo-api`).
There is no automatic redaction in v1.
