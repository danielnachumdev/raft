# Serve: reusable dashboard kit

The SPA ships a **dashboard kit** (`src/spa/src/dashboard-kit/`) so Trends overview, service inspection, and future ops surfaces share one shell, query model, and embed contract instead of forking chart chrome. Design lock: [issue #249](https://github.com/danielnachumdev/raft/issues/249) (Phase 1 comment on the issue).

Trends operator UX (default graphs, range controls, persistence keys) remains documented in [`serve-trends.md`](serve-trends.md). This page is the kit contract.

## What ships in v1

| Piece | Behavior |
|-------|----------|
| Shell | Grid (half/full → 12-col `span` 6/12), panels, edit/view, empty/stale, expand, undo-on-remove, per-graph CSV + expanded PNG export |
| Panels | `timeseries` against raft metrics (resources + HTTP aggregate). `stat` reserved, not rendered |
| Time | Shared dashboard range only; live poll on rolling windows; **no** per-panel range |
| Variables | Embed `variables.service` / `variables.group`; `${service}` / `${group}` in titles; hooks for later dropdown chrome |
| Queries | First-class `MetricsPanelQuery` per panel; **one fetch per metric plane**, client-side fan-out |
| Annotations | Optional markers from the metrics payload (`GraphEvent[]`); alert rules (#236) stay orthogonal |
| Persistence | Browser-local via `PersistenceAdapter` (Trends keys unchanged) |

## Embed contract

```tsx
import { DashboardKit } from "../dashboard-kit";

<DashboardKit
  embedId="trends"                 // a11y / DOM id
  mode="edit"                      // or "view"
  variables={{ service: "demo-api" }}
  scope={{ services: ["demo-api"] }}
  api={storeApi}                   // load/edit/remove/undo
  blankDraft={blankDraft}
  restoreDefaults={restoreDefaultPanels}
  chrome={{
    title: "Trends",
    showDashboardPicker: true,     // overview; false for service
    downloadServices: ["demo-api"],
  }}
/>
```

**In-tree consumer today:** Trends overview (`TrendsDashboard` → `DashboardKit` with `embedId="trends"`). Service Trends still uses its parallel shell; migrating it onto the kit is a follow-on.

## Persistence (operator behavior)

| Surface | Key | Scope |
|---------|-----|-------|
| Overview dashboards | `raft-serve-trends-dashboards` | Same browser profile only |
| Service layouts | `raft-serve-service-trends` | Same browser profile only |

Nothing under `~/.raft/` yet. Clearing site data resets to Overview / default six service graphs. The kit’s `createLocalStorageAdapter` is the plug-in point for a later hybrid (data-home + local cache) without reshaping the shell.

## Queries vs fetches

Panels declare metrics + view mode + selection. The runtime unions planes (`resources` / `http`) and calls `/api/metrics` and/or `/api/metrics/http` **once each** for the shared range (optionally `services=`), then every panel filters that payload. Adding a graph does not add HTTP requests.

## Per-graph export

Shared Trends graph chrome (`GraphCell` / `ExpandedGraph`) owns export, so Overview kit embeds and service Trends both get it:

| Action | Where | What |
|--------|-------|------|
| Export CSV | Graph ⋯ menu and expanded footer | Client CSV of that graph's **visible** series; same dialect as panel Download CSV (HTTP metrics appended when needed) |
| Export PNG | Expanded footer only | High-DPI (`html-to-image`, 3×) screenshot of the expanded graph card |

Panel-level **Download** in `KitHead` remains the full-window metrics attachment (not per-graph).

## Non-goals

Prometheus replacement, multi-tenant SaaS hosting, alert rules engine, always-on Compose dashboard packaging (#36), middle firewall hop, per-panel time ranges.
