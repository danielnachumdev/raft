# Operator system events (timeline)

Consolidated host activity journal (#267): apply/redeploy, scale wake/idle-stop,
purge, firewall apply, gate reload, and alert fire/resolve — one append-only
log for CLI and serve.

Trends chart markers stay on **GraphEvents** (`host/events/graph.jsonl`).
This timeline is complementary; it does not replace Trends markers.

## Dual-write vs merge (lock)

**Choice: dual-write.** Paths that already append GraphEvents also write a
mapped row into `ops.jsonl` (same `id` when assigned). Ops-only paths
(purge, firewall apply, alert fire/resolve, gate reload) write only to
`ops.jsonl`.

Serve `/api/events` and `raft events` read **only** `ops.jsonl` (+ sealed
archives). Trends / Runtime continue to read **only** `graph.jsonl`. Shared
kinds stay consistent because both writes happen in the same producer call.

Do **not** merge-on-read for v1 (avoids divergent filters and double-counting).

## Persistence

| Path | Role |
|------|------|
| `~/.raft/host/events/ops.jsonl` | Active append target |
| `~/.raft/host/events/ops.jsonl.YYYY-MM-DD[.N]` | Sealed archives (`LogRotationBootstrap`) |
| `~/.raft/host/events/graph.jsonl` | Trends markers (unchanged) |

Default retention: **14 days** age and **5 MiB** active file size (seal + age
delete archives). Not configurable in settings for v1.

## Event shape (PII-safe)

```json
{
  "id": "…",
  "kind": "deploy.apply",
  "ts": "2026-10-18T12:00:00+00:00",
  "summary": "Deploy demo-api",
  "service": "demo-api",
  "metadata": {"app": "demo-api", "ref": "abc1234", "action": "apply"}
}
```

No secrets, raw notification bodies, or live inventory names in fixtures/docs —
use `demo-api`, `demo-api-cpu-high`, `ops-webhook`, `192.0.2.0/24`.

### Kinds (v1)

| Kind | Typical producer |
|------|------------------|
| `deploy.apply` / `deploy.redeploy` | Apply / redeploy cutover (`GraphEventStore.record_deployment`) |
| `scale.wake` / `scale.idle_stop` | Controller scaler (GraphEvent dual-write) |
| `service.up` / `service.down` | Serve/CLI up/down (GraphEvent dual-write) |
| `stack.up` / `stack.down` / `raft.update` / `gate.redeploy` | Stack lifecycle (GraphEvent dual-write) |
| `stack.purge` | `Purge.execute` finish |
| `firewall.apply` | `FirewallService.put` |
| `gate.reload` | Orchestrator render when gate nginx reloads |
| `alert.fired` / `alert.resolved` | Alert engine notify transitions |

## Surfaces

| Plane | Entry |
|-------|--------|
| Serve UI | **Events** nav → `/events`: day-grouped timeline, toned kind chips, service links; window / kind / service filters; quiet 15s refresh while the tab is visible |
| Serve API | `GET /api/events?hours=24&service=demo-api&kind=alert.fired` |
| CLI | `raft events --hours=6 --service=demo-api` / `--json` |

Read-only in v1.

## How new mutative ops should append

1. Prefer a shared core capability (CLI + serve adapters only).
2. If the op already records a GraphEvent for Trends, rely on dual-write from
   `GraphEventStore.append` (map new graph kinds in `OpsKindFromGraph` when needed).
3. If ops-only (no Trends marker), call `OpsEventStore(home).record_*` or
   `append(OpsEvent(...))` with PII-safe `summary` + `metadata`.
4. Fail soft on `OSError` so mutative success does not depend on the journal FS.
5. Add a unit test with `demo-api`-style fixtures only.

## Example CLI

```bash
raft events --hours=24
raft events --kind=deploy.redeploy --service=demo-api --json
```
