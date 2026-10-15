# Serve: Trends named views

Named **views** in `raft serve` Trends save the explorer graph configuration so operators can reopen a familiar layout (services/metrics/range) without re-picking filters each visit.

Design lock: [issue #202](https://github.com/danielnachumdev/raft/issues/202) (UX brief on the issue).

## What a view stores

| Field | Meaning |
|-------|---------|
| Metrics | Checked Resources / HTTP metric ids |
| View mode | Per service, per group, avg all, avg group |
| Selection | All services/groups, none, or an explicit id list |
| Range | Preset / custom / absolute lookback (same as the Range control) |

One chart in the existing Trends panel — not a multi-tile dashboard. Service Runtime charts on a service page are separate and are not saved as views.

## Where it appears

Trends sidebar → **Saved view** (above Range). Actions: **Save…**, and when a named view is active: **Update**, **Rename…**, **Delete**.

## Persistence (v1)

Browser **`localStorage`** key `raft-serve-trends-views` (same machine/browser only). Not written under `~/.raft/`. Clearing site data removes views.

## Default landing

- No active view: live **Explorer** defaults (same as before named views).
- Later visits: last active view id is restored if it still exists.

## Removed services / groups

Opening a view intersects saved service or group ids with the live catalog. Missing ids are dropped; a short muted notice reports how many saved ids are gone. If every saved id is gone, Trends shows the usual empty selection copy plus that notice. Views that saved “all” (`selected: null`) do not treat catalog churn as stale.

## Out of scope

Prometheus/Grafana, autoscaling from metrics, stream/host request metrics, exposing Trends beyond localhost, replacing status tables.
