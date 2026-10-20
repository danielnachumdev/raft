# Serve: Trends dashboards

Trends in `raft serve` is a multi-graph **dashboard**: several graphs side by side over one shared time range, so CPU, memory, traffic, latency, errors and network are visible at a glance. Operators add, edit, duplicate, resize, reorder and remove graphs, and can keep several named dashboards. Each **service inspection** page gets the same default graphs pinned to that service (see [Service page Trends](#service-page-trends)).

The **Overview** page is an embed of the reusable [dashboard kit](serve-dashboard-kit.md) (`src/spa/src/dashboard-kit/`, [issue #249](https://github.com/danielnachumdev/raft/issues/249)). Operator-facing behavior below is unchanged; the kit owns the shell, query model, and embed contract so service Trends and future surfaces can share it.

Design: [issue #238](https://github.com/danielnachumdev/raft/issues/238) (UX brief on the issue); supersedes the single-chart named views from [issue #202](https://github.com/danielnachumdev/raft/issues/202).

## Default layout (Overview)

A fresh browser opens the **Overview** dashboard: all services, last **1h**, per service, two columns on wide screens.

| Graph | Metrics |
|-------|---------|
| CPU | `cpu_percent` |
| Memory | `memory_used_percent` |
| Request rate | `rps` |
| Latency p95 | `duration_p95_ms` |
| Errors | `status_4xx` + `status_5xx` |
| Network | `network_rx_bytes` + `network_tx_bytes` |

**Restore default graphs…** (dashboard menu) puts this layout back on the open dashboard.

## What a graph stores

| Field | Meaning |
|-------|---------|
| Title | Optional; blank → metric labels (e.g. “Network RX · Network TX”) |
| Metrics | 1–2 metric **types** (dual Y-axis rule, same as before); any number of metrics within those types |
| View mode | Per service, per group, average of all, average per group |
| Selection | All services/groups (follows new ones), or an explicit id list |
| Width | Half (one grid column) or full (both columns) |

The time range belongs to the **dashboard**, not the graph.

## Using it

- **Toolbar:** dashboard switcher + ⋯ menu (New, Rename, Restore default graphs, Delete), shared **Range**, **+ Add graph**.
- **Add / edit graph:** modal with preset chips (CPU, Memory, Request rate, Latency p95, Errors, Network, Disk I/O, In-flight, Latency spread, Processes), title, view, width, metric and service/group pickers, and a **live preview** fed by the dashboard's data.
- **Graph ⋯ menu:** Expand, Edit…, Duplicate, Make full / half width, Move earlier / later, Remove.
- **Reorder:** drag a graph by its ⠿ handle onto another graph's slot (or use Move earlier / later).
- **Remove** is immediate with an inline **Undo** for a few seconds.
- **Expand:** click a graph title (or menu → Expand) for a near-fullscreen view; ←/→ step through the dashboard's graphs.
- **Header number:** each graph shows the latest sample rolled up — **peak now** (max across lines) for percent / latency, **total now** (sum) for rates / counts / bytes, **avg now** in “average of all”. Same-type pairs (4xx + 5xx, RX + TX) fold together; the HTTP edge series is not double-counted in totals.
- A service keeps the **same color on every graph**; the second metric of a two-metric graph is drawn dashed.

## Data fetching

The dashboard fetches each metric plane **once** for the shared range — `/api/metrics` (resources) and/or `/api/metrics/http` — only for planes some graph uses, then live-polls with `since` cursors. Every graph filters that shared series client-side; adding graphs does not add requests. Series with no samples for a graph's metrics (e.g. host on HTTP graphs) are left out of that graph.

CLI (same `MetricsRead` / `HttpMetricsRead` / `ExportService` cores; no browser required):

```bash
raft metrics history --window=3600 --service=demo-api
raft metrics history --http --window=900
raft metrics catalog
raft metrics export_metrics --service=demo-api --file=out.csv
raft metrics export_logs demo-api --format=txt --file=demo-api.log
```

## Persistence

Browser **`localStorage`** key `raft-serve-trends-dashboards` (version 2; same machine/browser only). Not written under `~/.raft/` (kit v1 stance: browser-local; see [dashboard kit](serve-dashboard-kit.md)). Clearing site data resets to Overview. Corrupt or foreign payloads are ignored and fall back to Overview; graphs with unknown metrics or more than two metric types are trimmed on load.

## Migration from named views (#202)

On first load, when `raft-serve-trends-dashboards` does not exist yet, saved named views under `raft-serve-trends-views` are migrated:

- Overview (defaults) comes first.
- Each named view becomes its **own dashboard** with the view's name and range and one full-width graph (its metrics, view mode and selection) — nothing saved before is lost.
- The last active named view opens; otherwise Overview.

The legacy key is left untouched (read-only) and is not consulted again once dashboards exist.

## Removed services / groups

Each graph intersects its saved service or group ids with the live catalog at render time and shows a muted notice (“1 saved service no longer available.”). The stored graph is not rewritten, so ids that come back reappear. Graphs that saved “all” do not treat catalog churn as stale.

## Service page Trends

Each service inspection page has the same multi-graph Trends experience, scoped to that Compose service:

- **Default:** the six Overview graphs (CPU, Memory, Request rate, Latency p95, Errors, Network), last **1h**, pinned to the open service — no setup required.
- **Edit / add / remove / reorder / expand / restore defaults** work like the global dashboard; the graph editor hides View and Services pickers and keeps every graph on this service.
- **Fetch:** `/api/metrics` and `/api/metrics/http` are requested with `services=<name>` so the page only loads that series.
- **Persistence:** browser **`localStorage`** key `raft-serve-service-trends` (version 1): a map of service name → `{ range, panels }`. Independent of the global Overview dashboards key. Missing or corrupt entries fall back to the default six graphs for that service.

## Out of scope

Prometheus/Grafana, server-side or shared dashboards, per-graph ranges, autoscaling from metrics, stream/host request metrics, exposing Trends beyond localhost, replacing status tables.
