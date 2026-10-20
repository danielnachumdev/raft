# Alert rules

Alert rules decide **when** something is wrong. Notification channels decide **where** to send. Rules evaluate metrics (`host/metrics/resources.jsonl`, `http.jsonl`) and control-plane signals, then emit `NotificationEvent`s into the existing `Notifier` (no parallel delivery stack).

## Dual-plane lock (#264 / epic #256)

Mutative and inspect ops ship on **both** planes through shared core services
(`AlertRulesService`, `AlertEngine`, `AlertTester` under `observe/alerts/`).
Serve (`/api/alerts/*`) and CLI (`raft alerts …`) are thin adapters only — no
alert business logic lives in FastAPI handlers. Shipped with [#236](https://github.com/danielnachumdev/raft/issues/236)
(PR #251); this document is the operator-facing lock for [#264](https://github.com/danielnachumdev/raft/issues/264).

## Persistence

| Path | Role |
|------|------|
| `~/.raft/host/alerts/rules.yaml` | Desired rules document (versioned) |
| `~/.raft/host/alerts/runtime.json` | Controller-owned firing / pending / cool-down state |
| `~/.raft/host/settings.yaml` `alerts:` | Master switch + evaluation interval only |

## Settings

```yaml
alerts:
  enabled: true
  intervalSeconds: 60   # min 15; requires controller restart to pick up
  timeoutSeconds: 30
```

After installing a raft version that adds the controller `host/alerts` mount, run `raft up` so the controller can write `runtime.json`. Until then evaluation fails closed (no notifications) with a Fix CTA in the logs.

## Example (PII-safe)

```yaml
version: 1
rules:
  - id: demo-api-5xx-rate
    name: demo-api 5xx error rate
    severity: error
    description: More than 5% of demo-api requests returned 5xx.
    for: 2m
    cooldown: 15m
    notifyOnRecovery: true
    channelIds: [ops-primary]
    condition:
      signal: metrics.http
      select: {target: demo-api, metric: error_rate_5xx}
      kind: threshold
      params: {aggregate: avg, window: 5m, op: gt, value: 0.05}
```

## CLI

```bash
raft alerts list
raft alerts validate --file rules.yaml
raft alerts apply --file rules.yaml
raft alerts dry-run demo-api-5xx-rate
raft alerts test demo-api-5xx-rate
raft alerts status
```

## Serve

Settings → **Alerts**: list/create/edit/enable rules, see currently firing instances, dry-run and send test. Channels stay under Settings → Notifications; a rule may list `channelIds` (empty = all enabled channels).

## Signals (v1)

| `signal` | Notes |
|----------|--------|
| `metrics.resources` | Host/service CPU, memory, I/O from `resources.jsonl` |
| `metrics.http` | Edge/service rates and durations; derived `error_rate_5xx` / `error_rate_4xx` |
| `control.container_status` | Latest container status (skips intentional scale-to-zero) |
| `control.events` | Lifecycle graph events (`deployment`, `scaling`, …) |

Firewall-derived edge deny alerts are a follow-on (still policy-on-gate; no middle hop).

## Troubleshooting

- **Stale evaluation** in the SPA: controller not running or missing writable `host/alerts` mount → `raft doctor` / `raft up`.
- **Document error**: hand-edited invalid `rules.yaml` → `raft alerts validate`.
- Metrics windows shorter than ~2× `metrics.intervalSeconds` may warn about flush lag.
