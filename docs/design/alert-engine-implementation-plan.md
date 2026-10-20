# Alert engine — implementation plan

Status: **implementation plan** for [#236](https://github.com/danielnachumdev/raft/issues/236) (alert engine and rules layer above notification sinks).
Design source of truth: the Phase 1 brief on the issue ([comment](https://github.com/danielnachumdev/raft/issues/236#issuecomment-6233956275)). This document turns that brief into concrete files, schemas, signatures, and PRs. Where this plan makes a decision the brief left open, it is marked **Decision** with a short rationale so the implementer does not have to re-litigate it.

Audience: the agent implementing the engine. Read [`AGENTS.md`](../../AGENTS.md) first (code style, locks, packaging, SPA bake, screenshots, PII rules). All examples use PII-safe placeholders only: `demo-api`, `demo-web`, `ops-primary`, `192.0.2.0/24`.

---

## 1. Overview

### 1.1 What we are building

An **in-process alert rules engine** under `src/raft/core/observe/alerts/`. A controller interval job loads durable rules from `~/.raft/host/alerts/rules.yaml`, queries registered **signal sources** (metrics JSONL, control-plane facts, later firewall/edge), evaluates registered **rule kinds** combined with `all` / `any` compositions over time windows, tracks per-instance state (pending / firing / cool-down / recovery) in `~/.raft/host/alerts/runtime.json`, and emits existing `NotificationEvent`s into the existing `Notifier`, which fans out to the channels configured in `settings.yaml` `notifications:`.

Operators manage rules from **both** the CLI (`raft alerts …`) and `raft serve` (new **Alerts** settings page). Both are editors over the same rules document through one shared service class. **Parity lock:** [#264](https://github.com/danielnachumdev/raft/issues/264) / epic [#256](https://github.com/danielnachumdev/raft/issues/256) — satisfied when v1 shipped dual-plane via PR #251 (no serve-first waiver).

### 1.2 Goals

- Open-closed engine: new signal sources and rule kinds register through registries + catalogs (mirrors `observe/notify/` strategies, `NotificationRegistry`, `NotificationCatalogs`, `CatalogField`) without editing the evaluator.
- Thresholds on `host/metrics/resources.jsonl` and `host/metrics/http.jsonl` (first proving adapter).
- Control-plane conditions (container status, lifecycle graph events).
- Compositions (`all` / `any`, nested), aggregation windows, `for` durations, severity, dedupe by fingerprint, cool-down, optional recovery notification, optional repeat.
- Optional per-rule routing (`channelIds`); empty means all enabled channels.
- CLI and serve parity for list / validate / dry-run / test / enable-disable / CRUD / apply-from-file.
- Controller job that can never crash the controller and never spams when it cannot persist state.

### 1.3 Non-goals (v1)

- Any parallel delivery stack (email / webhook / WhatsApp stay in `observe/notify/strategies`).
- A middle firewall hop or `raft-firewall` service (rejected in #207). Firewall signals are observed from the gate access path only.
- Prometheus / `remote_write` / an external TSDB as the only path.
- Replacing `NotificationStrategy`, `NotificationCatalogs`, or the `ControlPlaneEvents` factories. Those producers keep calling `Notifier` directly.
- Rules stored only in `settings.yaml`; customer-specific alert catalogs in the git repo.
- Trends named views / browser `localStorage` as an alert source.
- Multi-host federation, silences UI with schedules, templated message languages, per-channel formatting.

---

## 2. Architecture

### 2.1 Layering

```text
                 ┌────────────────────────── ~/.raft/host/alerts/ ───────────────────────────┐
                 │  rules.yaml (desired, versioned)          runtime.json (controller-owned)   │
                 └───────▲──────────────────────────────────────────────▲────────────────────┘
   CLI (raft alerts) ────┤ AlertRulesService (alerts.lock)              │ AlertRuntimeStore
   serve /api/alerts/* ──┘    validate / upsert / delete / enable       │ (atomic JSON)
                                                                        │
 controller "alerts" job ──► AlertEngine.tick(now)                      │
                               │ load rules (AlertRulesStore)           │
                               │ SignalContext (per-tick memo)          │
                               ▼                                        │
         SignalRegistry ──► SignalSource.query(select, window, ctx) → SubjectSeries[]
                               ▼
         RuleKindRegistry ─► RuleKind.evaluate(series, params, now) → LeafResult[]
                               ▼
                       ConditionEvaluator (all/any, subject join) → SubjectOutcome[]
                               ▼
                       AlertStateMachine (pending/firing/cooldown/recovery) ─────────┘
                               ▼ transitions that should notify
                       AlertEventFactory → NotificationEvent(kind="alert.firing"|"alert.resolved")
                               ▼
                       Notifier.notify(event, channel_ids=rule.channel_ids)   (existing sinks)
```

### 2.2 Placement rules

- Engine, models, stores, registries, sources, kinds, shared service: `src/raft/core/observe/alerts/` (library; no FastAPI, no Fire).
- Controller job wiring: `src/raft/services/controller/jobs/alerts/`.
- CLI component: `src/raft/services/cli/commands/alerts.py` (+ small formatter module).
- Serve API: `src/raft/services/serve/alerts/`.
- SPA: `src/spa/src/alerts/` (+ one shared catalog-form extraction under `src/spa/src/shared/catalogForm/`).
- Lock: `src/raft/core/platform/locking/alerts_lock.py`.
- Settings: thin `alerts:` section (interval / enabled only).

### 2.3 Python package layout

Every file below should stay well under 200 lines; methods ≤ ~20 lines (meta guard: files < 300, bodies ≤ 20). Each package `__init__.py` has eager imports and `__all__` (no lazy `__getattr__`).

```text
src/raft/core/observe/alerts/
  __init__.py                    # eager exports of the public surface below
  constants.py                   # KIND_ALERT_FIRING="alert.firing", KIND_ALERT_RESOLVED="alert.resolved",
                                 # KIND_ALERT_TEST="alert.test", ALERTS_STATE_DIR, RULES_NAME, RUNTIME_NAME,
                                 # limits (MAX_RULES=200, MAX_LEAVES=8, MAX_DEPTH=3, MAX_WINDOW_SECONDS=86400…)
  catalogs.py                    # AlertCatalogs.default() -> AlertRegistries (composition root)
  registries.py                  # AlertRegistries dataclass(signals: SignalRegistry, kinds: RuleKindRegistry)
  model/
    __init__.py
    duration.py                  # AlertDuration.parse("5m") -> int seconds; format(seconds) -> "5m"
    condition.py                 # ConditionLeaf, ConditionGroup (all|any), ConditionNode = Union[…]
    condition_parser.py          # ConditionParser.parse(raw, path) -> ConditionNode (depth/leaf limits)
    rule.py                      # AlertRule (frozen dataclass) + to_public()
    rule_parser.py               # AlertRuleParser.parse(raw, path, registries) -> AlertRule
    document.py                  # AlertRulesDocument(version, rules) + from_mapping / to_export / to_public
    issues.py                    # ValidationIssue(path, message, level="error"|"warning"); ValidationReport
  signals/
    __init__.py
    signal_source.py             # SignalSource ABC
    signal_registry.py           # SignalRegistry (type_id -> SignalSource)
    series.py                    # SignalPoint, SubjectSeries, ValueType enum (NUMERIC|STATE|EVENT)
    context.py                   # SignalContext: now, home, per-tick sample memo, apps snapshot
    metrics/
      __init__.py
      metric_keys.py             # RESOURCE_METRICS / HTTP_METRICS: tuple[MetricKey(key,label,unit,scopes)]
      samples.py                 # MetricsSampleCache: read JSONL once per (file, max window) per tick
      resources_source.py        # ResourcesMetricSource (type_id "metrics.resources")
      http_source.py             # HttpMetricSource (type_id "metrics.http"), derived error rates
      targets.py                 # MetricTargets: resolve "host" | "edge" | "<service>" | "*"
    control/
      __init__.py
      container_status_source.py # ContainerStatusSource (type_id "control.container_status")
      graph_events_source.py     # GraphEventsSource (type_id "control.events")
  kinds/
    __init__.py
    rule_kind.py                 # RuleKind ABC
    kind_registry.py             # RuleKindRegistry (kind_id -> RuleKind)
    aggregates.py                # Aggregates.apply(name, values) -> Optional[float]
    operators.py                 # Comparison.apply(op, left, right) -> bool
    threshold.py                 # ThresholdKind ("threshold")
    state_match.py               # StateMatchKind ("state")
    event_count.py               # EventCountKind ("event_count")
  catalog/
    __init__.py
    alert_catalog.py             # AlertCatalog.build(registries, apps) -> dict for serve/CLI forms
  engine/
    __init__.py
    leaf_result.py               # LeafResult, SubjectOutcome dataclasses
    condition_evaluator.py       # ConditionEvaluator (tree walk + subject join)
    rule_evaluator.py            # AlertRuleEvaluator (one rule -> SubjectOutcome[] or RuleError)
    state_machine.py             # AlertStateMachine.step(instance, outcome, rule, now) -> Transition
    fingerprint.py               # AlertFingerprint.of(rule_id, subject) ; rule_hash(rule)
    event_factory.py             # AlertEventFactory.firing/resolved/test -> NotificationEvent
    dispatch.py                  # AlertDispatch: Notifier adapter honoring channel_ids
    engine.py                    # AlertEngine.tick(now) / dry_run(rule, now)
    report.py                    # EvaluationReport, DryRunReport (to_public())
  store/
    __init__.py
    atomic.py                    # AtomicText.write(path, text, mode=0o600) (tempfile + os.replace)
    rules_store.py               # AlertRulesStore (rules.yaml)
    runtime_state.py             # AlertInstanceState, AlertRuntime dataclasses (+ from/to mapping)
    runtime_store.py             # AlertRuntimeStore (runtime.json)
  service/
    __init__.py
    rules_service.py             # AlertRulesService: list/get/create/replace/delete/set_enabled/apply_document
    status_view.py               # AlertStatusView: joins rules + runtime for CLI/serve
    tester.py                    # AlertTester: send alert.test through routing, return deliveries

src/raft/core/platform/locking/alerts_lock.py   # AlertsLock (alerts.lock)

src/raft/core/core/config/settings/
  alerts_config.py               # AlertsConfig dataclass + defaults (kept out of types.py, which is ~197 lines)
  strategies/alerts.py           # settings section parser (mirror strategies/metrics.py)

src/raft/services/controller/jobs/alerts/
  __init__.py
  job.py                         # AlertsJob(ControllerJob)

src/raft/services/cli/commands/
  alerts.py                      # AlertsCLI (Fire component)
  alerts_output.py               # AlertsCliOutput: tables / json / yaml rendering (keeps alerts.py small)

src/raft/services/serve/alerts/
  __init__.py
  api.py                         # ServeAlertsApi (route registration + HTTP error mapping)
  handlers.py                    # ServeAlertsHandlers (body → service calls), if api.py grows > ~150 lines
```

### 2.4 SPA layout

```text
src/spa/src/alerts/
  alertsApi.ts                   # typed client + CachedResourceProxy instances
  alertsHelpers.ts               # pure helpers (durations, condition tree ops, summaries, draft <-> API)
  AlertsSettingsPage.tsx/.css    # route page
  AlertsStatusPanel.tsx/.css     # last evaluation + currently firing/pending list
  AlertRuleList.tsx/.css         # rule rows + actions
  AlertStateChip.tsx             # state → chip
  AlertRuleFormModal.tsx/.css    # create / edit dialog (Modal size="wide")
  ConditionEditor.tsx/.css       # recursive all/any group editor
  ConditionLeafEditor.tsx        # one leaf: signal, select fields, kind, params
  ChannelRoutingPicker.tsx/.css  # channelIds picker from notifications channels
  DryRunPanel.tsx/.css           # dry-run results table (form + row action)
src/spa/src/shared/catalogForm/
  CatalogFields.tsx              # generic catalog-declared inputs (text/url/secret/number/checkbox/select/duration)
  catalogFormHelpers.ts          # moved from notificationsHelpers: coerce/settingsFrom/fieldStateFrom
src/spa/test/alerts/
  alertsHelpers.test.ts
src/spa/test/shared/
  catalogFormHelpers.test.ts
```

---

## 3. Data model

### 3.1 `~/.raft/host/alerts/rules.yaml` (desired, versioned)

Top level:

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `version` | int | no (default `1`) | Only `1` accepted; anything else → `OperatorError` with `Fix: set version: 1` (same style as `FirewallDocument._parse_version`). |
| `rules` | list | no (default `[]`) | ≤ `MAX_RULES` (200). Ids unique. Order is preserved (display order). |

Rule:

| Key | Type | Default | Validation |
|-----|------|---------|------------|
| `id` | str | — (required) | `^[a-z0-9][a-z0-9-]{0,62}$`; unique; immutable once created (rename = delete + create). |
| `name` | str | `id` | 1–120 chars. |
| `enabled` | bool | `true` | |
| `severity` | str | `warning` | One of `NotificationSeverity` values: `info`, `warning`, `error`, `critical`. |
| `description` | str | `""` | ≤ 500 chars; copied into notification body. |
| `for` | duration | `0s` | 0 – 24h. Condition must hold continuously this long before firing. |
| `cooldown` | duration | `15m` | 0 – 7d. After a resolve, suppress a new firing notification for the same fingerprint until it elapses. |
| `repeatEvery` | duration | `0s` | 0 (never) or 5m – 7d. Re-notify while still firing. |
| `notifyOnRecovery` | bool | `true` | Send `alert.resolved` when an instance recovers. |
| `noData` | str | `ok` | `ok` (no data = condition false), `alerting` (no data = true), `keep` (no data = keep previous instance state, no transition). |
| `channelIds` | list[str] | `[]` | Empty = all enabled channels. Each id must exist in `settings.yaml` `notifications.channels` **at write time** (error); missing at runtime = warning log, deliver to the remaining ids. |
| `condition` | node | — (required) | Leaf or group (below). Depth ≤ 3, leaves ≤ 8. |

Duration format (`AlertDuration`): integer seconds, or string `^\d+(s|m|h|d)$` (`30s`, `5m`, `1h`, `7d`). Exported/serialized as the shortest exact string (`300` → `5m`).

Condition node — exactly one of:

- **Group:** `{all: [node, …]}` or `{any: [node, …]}` with 1–8 children.
- **Leaf:**

| Key | Type | Notes |
|-----|------|-------|
| `signal` | str | `SignalSource.type_id` registered in `SignalRegistry`. |
| `select` | map | Source-specific selector, validated by `SignalSource.validate_select`. |
| `kind` | str | `RuleKind.kind_id`; must accept the source's `value_type`. |
| `params` | map | Kind-specific, validated by `RuleKind.validate_params`. |

Example (PII-safe; also used verbatim as the docs example and a unit fixture):

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

  - id: any-app-cpu-and-latency
    name: App hot and slow
    severity: warning
    for: 5m
    condition:
      all:
        - signal: metrics.resources
          select: {target: "*", metric: cpu_percent}
          kind: threshold
          params: {aggregate: avg, window: 5m, op: gt, value: 85}
        - signal: metrics.http
          select: {target: "*", metric: duration_p95_ms}
          kind: threshold
          params: {aggregate: avg, window: 5m, op: gt, value: 1500}

  - id: demo-web-not-running
    name: demo-web container not running
    severity: critical
    for: 3m
    noData: alerting
    condition:
      signal: control.container_status
      select: {target: demo-web}
      kind: state
      params: {match: notIn, values: [running]}

  - id: deploy-churn
    name: Frequent deployments
    severity: info
    notifyOnRecovery: false
    condition:
      signal: control.events
      select: {target: "*", eventKind: deployment}
      kind: event_count
      params: {window: 1h, op: gte, value: 5}
```

Persistence: `AlertRulesStore.save` writes `document.to_export()` with `yaml.safe_dump(sort_keys=False)` through `AtomicText.write(..., mode=0o600)` (same approach as `FirewallStore`). Missing file = empty document (not an error). Unreadable / invalid YAML on **load** raises `OperatorError` with a Fix line; the controller job catches it, records it in `runtime.json` `lastEvaluation.errors`, and evaluates nothing that tick (no spurious resolves).

**Decision — strict load:** unlike the app registry, the rules document is validated as a whole (CLI/serve writes are strict and atomic, so a bad file means a hand edit). A single invalid rule makes the whole document fail to load with a path-qualified message (`rules[2].condition.all[0].params.value`), surfaced by `raft alerts validate`, the serve status endpoint, and `raft doctor` (PR 8).

### 3.2 `~/.raft/host/alerts/runtime.json` (controller-owned)

Written only by the controller job (single writer; `QueuePolicy.SKIP_IF_RUNNING` prevents overlap). CLI and serve read it; never hand-edited as source of truth. Atomic JSON write, mode `0o600`.

```json
{
  "version": 1,
  "lastEvaluation": {
    "startedAt": "2026-10-17T12:00:00+00:00",
    "finishedAt": "2026-10-17T12:00:00.420000+00:00",
    "durationMs": 420,
    "rulesTotal": 4,
    "rulesEvaluated": 3,
    "rulesSkippedDisabled": 1,
    "notificationsSent": 1,
    "errors": [
      {"ruleId": "deploy-churn", "message": "control.events: cannot read host/events/graph.jsonl"}
    ],
    "documentError": null
  },
  "instances": {
    "demo-api-5xx-rate|demo-api": {
      "ruleId": "demo-api-5xx-rate",
      "subject": "demo-api",
      "ruleHash": "sha256:3f1c…",
      "state": "firing",
      "pendingSince": "2026-10-17T11:57:00+00:00",
      "firingSince": "2026-10-17T11:59:00+00:00",
      "lastNotifiedAt": "2026-10-17T11:59:00+00:00",
      "lastResolvedAt": null,
      "cooldownUntil": null,
      "suppressed": false,
      "lastEvaluatedAt": "2026-10-17T12:00:00+00:00",
      "lastValues": [
        {"path": "condition", "signal": "metrics.http", "metric": "error_rate_5xx",
         "value": 0.071, "matched": true, "noData": false}
      ]
    }
  }
}
```

Instance `state` values: `ok` (implicit; instances in `ok` with no cooldown are pruned), `pending`, `firing`. Instances whose rule was deleted, disabled, or whose `ruleHash` changed are dropped/reset **without** sending a resolved notification (logged at INFO).

Fingerprint: `f"{rule_id}|{subject}"` (readable, stable; used as runtime key and in `NotificationEvent.context["fingerprint"]`). Subject is `"-"` when the rule has no wildcard leaf. `ruleHash` = `sha256` of the canonical JSON of the rule's `condition`, `for`, `noData` (changes to name/severity/channels do **not** reset state).

### 3.3 Settings (`settings.yaml`) — thin runtime switch only

```yaml
alerts:
  enabled: true          # master switch for the controller job (default true)
  intervalSeconds: 60    # evaluation period (default 60, min 15)
  timeoutSeconds: 30     # soft timeout for the job (default 30)
```

**Decision:** the interval lives in settings (like `metrics:` / `healing:`), not in `rules.yaml`, because the controller registers its `JobSpec` at startup from `RaftConfig`. Rules stay in `host/alerts/`; channels stay in `notifications:`. Changing `alerts:` needs a controller restart (document it), rules do not (re-read every tick).

### 3.4 `NotificationEvent` mapping

Built only by `AlertEventFactory` (mirrors `ControlPlaneEvents`; no channel knowledge).

| Field | Firing | Resolved | Test |
|-------|--------|----------|------|
| `kind` | `alert.firing` | `alert.resolved` | `alert.test` |
| `severity` | `rule.severity` | `NotificationSeverity.INFO` | `NotificationSeverity.INFO` |
| `title` | `"[FIRING] {rule.name}"` + `": {subject}"` when subject ≠ `-` | `"[RESOLVED] …"` same suffix | `"[TEST] {rule.name}"` |
| `body` | `description` (if any) + newline + one line per leaf: `"{signal} {metric/target} {aggregate}({window}) = {value} {op} {threshold}"`; plus `"Firing since {firingSince}"` | `"Recovered after {duration}"` + last values | `"Test notification for alert rule {id}; no condition was evaluated."` |
| `context` | see below | same keys, `state="resolved"`, `resolved_at` | `rule_id`, `rule_name`, `test=true` |

`context` keys (flat, JSON-safe, all strings/numbers/bools/lists): `rule_id`, `rule_name`, `fingerprint`, `subject`, `state` (`firing`/`resolved`), `severity`, `firing_since`, `values` (list of `{path, signal, metric, value, matched}`), `channel_ids` (list, may be empty). Body/title must never include settings secrets (they cannot: rules hold no secrets).

---

## 4. Python core

### 4.1 Signals

```python
class ValueType(str, Enum):
    NUMERIC = "numeric"   # SignalPoint.value: Optional[float]
    STATE = "state"       # SignalPoint.value: Optional[str]
    EVENT = "event"       # one SignalPoint per event; value: label/kind str

@dataclass(frozen=True)
class SignalPoint:
    ts: datetime
    value: Any

@dataclass(frozen=True)
class SubjectSeries:
    subject: str                    # "-" | service name | "host" | "edge"
    points: tuple[SignalPoint, ...] # chronological; may be empty (no data)
    wildcard: bool                  # True when produced by a "*" selector expansion

class SignalContext:
    """Per-tick read memo + facts shared by all sources in one evaluation."""
    def __init__(self, home: Path, now: datetime, *, app_names: Sequence[str]) -> None: ...
    @property
    def now(self) -> datetime: ...
    @property
    def home(self) -> Path: ...
    @property
    def app_names(self) -> tuple[str, ...]: ...
    def memo(self, key: str, load: Callable[[], T]) -> T: ...   # load once per tick

class SignalSource(ABC):
    @property
    @abstractmethod
    def type_id(self) -> str: ...
    @property
    @abstractmethod
    def value_type(self) -> ValueType: ...
    def catalog_entry(self) -> Dict[str, Any]:            # label, value_type, select fields, metrics
        return AlertCatalogEntry.source(self.type_id, label=self.type_id, value_type=self.value_type)
    @abstractmethod
    def validate_select(self, select: Mapping[str, Any], *, path: str) -> List[ValidationIssue]: ...
    @abstractmethod
    def query(self, select: Mapping[str, Any], *, window_seconds: int,
              ctx: SignalContext) -> List[SubjectSeries]: ...
    def describe(self, select: Mapping[str, Any]) -> str: ...  # "demo-api error_rate_5xx" for bodies/summaries

class SignalRegistry:          # same shape as NotificationRegistry
    def register(self, source: SignalSource) -> None: ...      # duplicate -> ValueError
    def get(self, type_id: str) -> SignalSource: ...            # unknown -> OperatorError with Fix CTA
    def has(self, type_id: str) -> bool: ...
    def catalog(self) -> List[Dict[str, Any]]: ...
```

Sources must raise only `OperatorError` / `OSError` from `query`; the rule evaluator converts those into a per-rule error (other rules still evaluate).

### 4.2 Rule kinds

```python
@dataclass(frozen=True)
class LeafResult:
    subject: str
    matched: Optional[bool]       # None = no data
    value: Any                    # aggregated value / latest state / event count
    detail: str                   # human line for bodies + dry-run

class RuleKind(ABC):
    @property
    @abstractmethod
    def kind_id(self) -> str: ...
    @property
    @abstractmethod
    def value_types(self) -> frozenset[ValueType]: ...
    def catalog_entry(self) -> Dict[str, Any]: ...            # label, value_types, param fields
    @abstractmethod
    def validate_params(self, params: Mapping[str, Any], *, path: str) -> List[ValidationIssue]: ...
    @abstractmethod
    def window_seconds(self, params: Mapping[str, Any]) -> int: ...  # 0 = latest point only
    @abstractmethod
    def evaluate(self, series: SubjectSeries, params: Mapping[str, Any], *, now: datetime) -> LeafResult: ...

class RuleKindRegistry:       # register / get / has / catalog; same error style
```

Shipped kinds (v1):

| `kind_id` | Value types | Params | Semantics |
|-----------|-------------|--------|-----------|
| `threshold` | NUMERIC | `aggregate` ∈ `avg,min,max,sum,last`; `window` duration (1m–24h); `op` ∈ `gt,gte,lt,lte,eq,ne`; `value` float | Drop `None` points; no remaining points → `matched=None`. Else `Comparison.apply(op, Aggregates.apply(aggregate, values), value)`. |
| `state` | STATE | `match` ∈ `in,notIn`; `values` list[str] (1–10) | Latest point in the last 2× metrics interval (cap 10m) → membership test; none → `matched=None`. |
| `event_count` | EVENT | `window` duration; `op`; `value` int ≥ 0 | `count = len(points)`; always has data (0 is a value) → `matched = Comparison.apply(op, count, value)`. |

### 4.3 Composition and subject join (`ConditionEvaluator`)

Each leaf yields `List[LeafResult]` keyed by subject. Subjects come from the source:

- A leaf whose selector target is concrete (`demo-api`, `host`, `edge`) yields one result. It is **global**: it applies to every subject in a composition.
- A leaf whose target is `"*"` expands to one result per discovered subject (services present in the window, or applied apps for container status).

Algorithm for a group with children results `C1..Cn`:

1. Subject universe `U` = union of subjects from wildcard children. If `U` is empty (no wildcard children), `U = {"-"}`.
2. For each subject `s ∈ U`, child value `v_i(s)` = the child's result for `s` if the child is wildcard, else the child's single global result. A wildcard child with no result for `s` → `None` (no data).
3. `all`: `False` if any `False`; else `None` if any `None`; else `True`. `any`: `True` if any `True`; else `None` if any `None`; else `False` (Kleene three-valued logic).
4. A top-level leaf is treated as a group of one.
5. Apply the rule's `noData` to each subject's final `None`: `ok` → `False`, `alerting` → `True`, `keep` → leave `None` (state machine makes no transition).

Output: `SubjectOutcome(subject, matched: Optional[bool], leaves: tuple[LeafValue, ...])`, where `LeafValue` carries `path` (e.g. `condition.all[1]`), signal, metric/target description, value, matched — used for bodies, dry-run, and `runtime.json.lastValues`.

### 4.4 State machine (`AlertStateMachine`)

```python
@dataclass(frozen=True)
class Transition:
    instance: Optional[AlertInstanceState]   # None = prune
    notify: Optional[str]                    # None | "firing" | "resolved"

class AlertStateMachine:
    def step(self, prev: Optional[AlertInstanceState], outcome: SubjectOutcome,
             rule: AlertRule, *, now: datetime) -> Transition: ...
```

Rules (prev state `ok` means "no instance"):

| Prev | Outcome | Next | Notify |
|------|---------|------|--------|
| ok | True, `for == 0` | firing (`firingSince=now`) | `firing` unless `now < cooldownUntil` → set `suppressed=true`, no notify |
| ok | True, `for > 0` | pending (`pendingSince=now`) | — |
| pending | True and `now - pendingSince ≥ for` | firing | as above (cool-down check) |
| pending | True, not yet | pending | — |
| pending | False | ok (prune unless cool-down active) | — |
| firing | True | firing | `firing` again if `repeatEvery > 0` and `now - lastNotifiedAt ≥ repeatEvery` and not suppressed |
| firing | False | ok, `lastResolvedAt=now`, `cooldownUntil=now+cooldown` (keep instance while cool-down active) | `resolved` if `notifyOnRecovery` **and** the firing was not suppressed |
| any | None (`noData: keep`) | unchanged (update `lastEvaluatedAt`) | — |

Cool-down only suppresses notifications; state still reflects reality so serve shows "firing (suppressed)". A suppressed firing that later resolves sends nothing.

### 4.5 Engine (`AlertEngine`)

```python
class AlertEngine:
    def __init__(self, home: Path, *, registries: Optional[AlertRegistries] = None,
                 rules_store: Optional[AlertRulesStore] = None,
                 runtime_store: Optional[AlertRuntimeStore] = None,
                 dispatch: Optional[AlertDispatch] = None,
                 app_names: Optional[Callable[[], Sequence[str]]] = None) -> None: ...

    def tick(self, now: Optional[datetime] = None) -> EvaluationReport: ...
    def dry_run(self, rule: AlertRule, now: Optional[datetime] = None) -> DryRunReport: ...
```

`tick` steps (each a ≤20-line helper):

1. `runtime = runtime_store.load()` (missing/corrupt → empty runtime + logged warning; corrupt file is renamed to `runtime.json.corrupt-<ts>` once).
2. **Writability probe:** `runtime_store.ensure_writable()`; if it fails (e.g. read-only mount on an old controller container), log ERROR once per process with a Fix CTA (`raft up` to recreate the controller with the new mount) and **return without notifying** (fail closed — otherwise every tick would re-notify because state never persists).
3. Load the document; on `OperatorError` record `documentError`, save runtime, return.
4. Build one `SignalContext` (now, home, app names from `Stack.load_apps(home)` — same read-only-safe call the metrics recorder uses).
5. For each enabled rule: `AlertRuleEvaluator.evaluate(rule, ctx)` inside `try/except Exception` → per-rule error entry, existing instances untouched.
6. For each `SubjectOutcome`: `state_machine.step(...)`; collect transitions; reconcile (drop instances of deleted/disabled rules or with changed `ruleHash`).
7. **Persist runtime first, then notify** (`dispatch.send(...)` per transition). If persisting fails, do not notify.
8. Return `EvaluationReport` (also written as `lastEvaluation`).

`dry_run` runs steps 4–5 for one (possibly unsaved) rule, then simulates `step` against the current runtime instance **without** saving or notifying. `DryRunReport.to_public()`:

```json
{
  "ruleId": "demo-api-5xx-rate",
  "evaluatedAt": "2026-10-17T12:00:00+00:00",
  "error": null,
  "subjects": [
    {"subject": "demo-api", "matched": true, "currentState": "pending",
     "wouldState": "firing", "wouldNotify": "firing",
     "leaves": [{"path": "condition", "signal": "metrics.http", "describe": "demo-api error_rate_5xx",
                 "value": 0.071, "matched": true, "detail": "avg(5m) = 0.071 > 0.05", "noData": false}]}
  ]
}
```

### 4.6 Notifier adapter and the small `Notifier` change

`Notifier` today always fans out to every enabled channel and returns nothing. Two additive changes in `src/raft/core/observe/notify/notifier.py` (existing call sites unchanged):

```python
def notify(self, event: NotificationEvent, *, channel_ids: Optional[Sequence[str]] = None) -> None:
    try:
        self.deliver(event, channel_ids=channel_ids)
    except Exception:  # noqa: BLE001 — producers must not crash the controller
        logger.exception("notification dispatch failed kind=%s", event.kind)

def deliver(self, event: NotificationEvent, *,
            channel_ids: Optional[Sequence[str]] = None) -> List[ChannelDelivery]:
    """Like notify, but returns per-channel results and may raise (used by alert tests)."""
```

`_deliverable` gains an id filter: when `channel_ids` is non-empty, keep only channels whose id is listed (still requiring `enabled` and a known type); log a WARNING for listed ids that do not exist. Global `notifications.enabled: false` still short-circuits to `[]`.

```python
class AlertDispatch:
    def __init__(self, notifier: Notifier) -> None: ...
    def send(self, rule: AlertRule, event: NotificationEvent) -> None:
        self._notifier.notify(event, channel_ids=rule.channel_ids or None)
```

### 4.7 Stores

```python
class AlertRulesStore:
    def __init__(self, home: Path, *, registries: Optional[AlertRegistries] = None) -> None: ...
    path: Path                                   # home / "host/alerts/rules.yaml"
    def exists(self) -> bool: ...
    def load(self) -> AlertRulesDocument: ...    # missing -> empty document
    def load_raw(self) -> Any: ...               # for validate without raising on first error
    def save(self, document: AlertRulesDocument) -> None: ...

class AlertRuntimeStore:
    def __init__(self, home: Path) -> None: ...
    path: Path                                   # home / "host/alerts/runtime.json"
    def load(self) -> AlertRuntime: ...          # missing/corrupt -> AlertRuntime.empty()
    def save(self, runtime: AlertRuntime) -> None: ...
    def ensure_writable(self) -> None: ...       # raise OSError when dir not writable
```

`store/atomic.py` (`AtomicText.write`) is new and used by both stores. Do **not** refactor the existing `FirewallStore` / `AclStore` writers in this work.

### 4.8 Shared service (one model, two editors)

`AlertRulesService` is the only writer of `rules.yaml`. CLI and serve both call it; every mutating method holds `AlertsLock` for the whole read-modify-validate-write.

```python
class AlertRulesService:
    def __init__(self, home: Path, *, registries: Optional[AlertRegistries] = None) -> None: ...
    def document(self) -> AlertRulesDocument: ...
    def get(self, rule_id: str) -> AlertRule: ...                          # KeyError when missing
    def validate_document(self, raw: Any) -> ValidationReport: ...          # never raises for content
    def validate_rule(self, raw: Any) -> ValidationReport: ...
    def create(self, raw: Mapping[str, Any]) -> AlertRule: ...              # duplicate id -> RuleConflict
    def replace(self, rule_id: str, raw: Mapping[str, Any]) -> AlertRule: ...  # id mismatch -> OperatorError
    def set_enabled(self, rule_id: str, enabled: bool) -> AlertRule: ...
    def delete(self, rule_id: str) -> None: ...
    def apply_document(self, raw: Any, *, prune: bool) -> ApplySummary: ... # upsert by id; prune removes others
    def export_document(self) -> Dict[str, Any]: ...
```

`ValidationReport` = `{ok: bool, errors: [{path, message}], warnings: [{path, message}]}`. Warnings (non-blocking): metric target is a service that is not currently applied; `channelIds` given while `notifications.enabled` is false; `repeatEvery` shorter than `alerts.intervalSeconds`. Errors raise `OperatorError` from write methods with all error lines joined (first line summary, then `- path: message`, then a `Fix:` line).

`ApplySummary` = `{created: [...], updated: [...], unchanged: [...], deleted: [...]}`.

`AlertStatusView.build(home) -> Dict` joins document + runtime + settings for both CLI `status` and `GET /api/alerts/status` (shape in §8).

`AlertTester.send(rule_id) -> List[ChannelDelivery]` builds `AlertEventFactory.test(rule)` and calls `Notifier.deliver(event, channel_ids=rule.channel_ids or None)`.

### 4.9 Catalog

Extend `src/raft/core/observe/notify/catalog_field.py` `CatalogField.define` with two optional keyword args (backward compatible; notifications keep working):

- `options: Optional[List[Dict[str, str]]] = None` → emitted as `"options": [{"value", "label"}]` when given (`kind="select"`).
- `default: Any = None` → emitted as `"default"` when not `None`.

New field kinds used by alerts: `select`, `duration`, `number`, `text`, `string_list` (comma-separated input → list). Notifications SPA ignores unknown kinds (falls back to text), so no notifications change is required.

`AlertCatalog.build(registries, app_names, channels)` returns:

```json
{
  "sources": [
    {"type_id": "metrics.http", "label": "HTTP metrics (gate)", "value_type": "numeric",
     "select_fields": [
       {"key": "target", "label": "Target", "kind": "select", "required": true,
        "options": [{"value": "edge", "label": "Edge (all traffic)"}, {"value": "*", "label": "Each app"},
                    {"value": "demo-api", "label": "demo-api"}]},
       {"key": "metric", "label": "Metric", "kind": "select", "required": true,
        "options": [{"value": "error_rate_5xx", "label": "5xx error rate (0–1)"}]}
     ],
     "metrics": [{"key": "error_rate_5xx", "label": "5xx error rate", "unit": "ratio", "scopes": ["edge", "service"]}]}
  ],
  "kinds": [
    {"kind_id": "threshold", "label": "Threshold", "value_types": ["numeric"],
     "fields": [{"key": "aggregate", "kind": "select", "options": [...]}, {"key": "window", "kind": "duration", "default": "5m"},
                {"key": "op", "kind": "select", "options": [...]}, {"key": "value", "kind": "number", "required": true}]}
  ],
  "severities": ["info", "warning", "error", "critical"],
  "noData": ["ok", "alerting", "keep"],
  "limits": {"maxRules": 200, "maxLeaves": 8, "maxDepth": 3}
}
```

Target options are dynamic (applied app names from `Stack.load_apps` plus fixed `host`/`edge`/`*`), so `catalog_entry` takes no args and `AlertCatalog` injects target options. Channels are **not** in the catalog: the SPA reuses `GET /api/notifications/channels`; the CLI validates ids against settings directly.

---

## 5. Signal sources

### 5.0 Prep: break the metrics import cycle (PR 1)

`raft.core.observe.read.metrics.{http,resources}` import `METRICS_DIR` / `METRICS_FILENAME` / `HTTP_METRICS_FILENAME` from `raft.services.controller.jobs.metrics`, which executes `raft.services.controller.jobs/__init__.py`. Once that `__init__` imports the new `AlertsJob` (which imports `raft.core.observe.alerts`, which imports `raft.core.observe.read.metrics`), importing `raft.core.observe.alerts` first (CLI, serve) would hit a partially initialized module.

Fix: move the three constants (plus `GATE_HTTP_LOG_DIR`, `ACCESS_LOG_NAME` for the later firewall phase) into a new core module `src/raft/core/core/config/paths/metrics_paths.py` (`class MetricsPaths` with `dir(home)`, `resources(home)`, `http(home)`, `gate_access_log(home)` plus module constants). `controller/jobs/metrics` re-exports them from there (keep existing names in its `__all__`); `observe/read/metrics` and `observe/alerts` import from core. Acceptance check: both `python -c "import raft.core.observe.alerts"` and `python -c "import raft.services.controller.jobs"` succeed in a fresh interpreter (add a unit test that runs both in subprocesses).

### 5.1 `metrics.resources` (`ResourcesMetricSource`)

- File: `host/metrics/resources.jsonl` (+ sealed archives) via `MetricsJsonlReader(path).samples_in_window(from_ts=now - window)`.
- Sample shape (from `Status.collect().to_dict()` + `ts`): `host` dict (`cpus`, `loadavg`, `memory.used_percent`, `memory.used_bytes`, …) and `containers` list of rows (`service`, `role`, `app`, `group`, `status`, `uptime_seconds`, `cpu_percent`, `memory.{used_bytes,limit_bytes,used_percent}`, `network.{rx_bytes,tx_bytes}`, `block_io.{read_bytes,write_bytes}`, `pids`).
- **Reuse, do not re-parse:** call `MetricsSeriesBuilder().build(samples, wanted=…)`; each series has `points` with flat keys. Read the metric key from each point.
- `select`: `{target: "host" | "<service>" | "*", metric: <key>}`. `"*"` = every series whose `role == "app"` (exclude gate/router/controller).
- Metric keys (`RESOURCE_METRICS`): host scope — `cpu_percent`, `memory_used_percent`, `memory_used_bytes`; service scope — `cpu_percent`, `memory_used_percent`, `memory_used_bytes`, `memory_limit_bytes`, `pids`, `uptime_seconds`, `network_rx_bytes`, `network_tx_bytes`, `block_read_bytes`, `block_write_bytes`. Validation rejects a metric not valid for the target's scope.
- Guard test: a unit test builds a fixture sample, runs `MetricsSeriesBuilder.build`, and asserts every `RESOURCE_METRICS` key appears in the produced points (so a builder rename breaks the test, not production).

### 5.2 `metrics.http` (`HttpMetricSource`)

- File: `host/metrics/http.jsonl`. Sample top level = edge window (`requests`, `rps`, `duration_ms.{avg,p50,p95,p99}`, `status_class.{2xx,3xx,4xx,5xx,other}`, `in_flight`, `active_connections`, `interval_seconds`), plus `by_host` and `by_service` maps of the same window shape (from `HttpMetricsAggregator._window`).
- Reuse `HttpMetricsSeriesBuilder().build(...)`; point keys: `rps`, `requests`, `duration_avg_ms`, `duration_p50_ms`, `duration_p95_ms`, `duration_p99_ms`, `status_2xx`, `status_3xx`, `status_4xx`, `status_5xx`, and edge-only `in_flight`, `active_connections`.
- Derived per point (computed in the source, not the builder): `error_rate_5xx = status_5xx / requests`, `error_rate_4xx = status_4xx / requests` (`None` when `requests` is 0 or missing, so idle periods are "no data", not 0%).
- `select`: `{target: "edge" | "<service>" | "*", metric}`; `"*"` = every key in `by_service` seen in the window.
- Same builder-key guard test as 5.1.

Latency note for docs: samples are buffered by the metrics recorder (`batch_size` 10, `flush_seconds` 60, interval 60 s by default), so the newest data on disk can lag by up to one flush. Windows shorter than `2 × metrics.intervalSeconds` produce a validation **warning**.

Per-tick IO: `MetricsSampleCache` memoizes (via `SignalContext.memo`) one read per file using the largest window any enabled leaf needs for that file, then slices per leaf. Cap total window at 24 h.

### 5.3 `control.container_status` (`ContainerStatusSource`, STATE)

- Reads the latest `resources.jsonl` samples within `min(10m, 2 × metrics interval)` (memoized with 5.1) and emits one STATE point per sample per container: `value = row["status"]` (e.g. `running`, `exited`).
- `select`: `{target: "<service>" | "*"}`; `"*"` expands to **applied app names** (from `SignalContext.app_names`), so an app missing from samples yields an empty series → no data → `noData` applies (`noData: alerting` catches "container gone").
- Skips apps intentionally scaled to zero: use the existing `ScalingStore(home).is_scaled_to_zero(name)` (`services/<name>/scaling/`, `scaledToZero`) and drop those subjects (healing ≠ scaling invariant; never alert on intentional idle stop).

### 5.4 `control.events` (`GraphEventsSource`, EVENT)

- Reads `GraphEventStore(home).events_in_window(from_ts=now - window, to_ts=now)`.
- `select`: `{target: "<service>" | "*" | "-", eventKind: <GraphEvent kind>, action?: <metadata.action>}`. Kinds from `graph_event_kinds.py`: `deployment`, `stop`, `start`, `scaling`, `up`, `down`, `update`, `gate_recreate`; `action` filters scaling (`idle_stop`, `wake`). `"-"` = stack-level events (no service); `"*"` = per-service subjects.

### 5.5 Later phase: control-plane facts not in graph events

Heal escalate, scale wake timeout, ACME `lastError`, serve deploy failed are delivered by `ControlPlaneEvents` directly and are not durable. Follow-on (separate issue): a `ControlPlaneJournal` that `Notifier.notify` appends to (`host/events/control.jsonl`, bounded) plus a `control.notifications` EVENT source. Out of v1 to keep producers untouched.

### 5.6 Later phase: firewall / edge signals (`edge.denies`)

Policy stays on the gate (#207/#211). Plan for the follow-on PR:

1. Extend `HttpMetricsAggregator` (controller, already tails `host/metrics/gate-http/access.log` with an offset) to also count firewall outcomes per window: `firewall: {"403": n, "444": n, "by_prefix": {"192.0.2.0/24": n, …}}`, with `by_prefix` bucketed by IPv4 `/24` and IPv6 `/64`, bounded top-N (20) to keep JSONL small. Use enriched access-log fields (`client_ip`) via `HttpAccessLineParser`; legacy lines without client IP count only totals.
2. Add `edge.denies` NUMERIC source reading that block from `http.jsonl`: `select: {target: "edge" | "<cidr>", status: "403" | "444" | "any"}`.
3. Docs: "sustained 403/444 from 192.0.2.0/24" example. No new nginx hop, no gate restart.

Do not tail the access log independently from the alert job (it would race the scraper's rotation/offset handling).

---

## 6. Controller integration

### 6.1 Job

```python
class AlertsJob(ControllerJob):
    def __init__(self, home: Path, config: AlertsConfig, *, engine: Optional[AlertEngine] = None) -> None: ...
    @property
    def job_id(self) -> str: return JobIds.ALERTS          # "alerts"
    def tick(self) -> None:
        try:
            self._engine.tick()
        except Exception:  # noqa: BLE001 — alert evaluation must never stop the controller
            logger.exception("alerts tick failed")
    def attach(self, orch: JobOrchestrator) -> None:
        if not self._config.enabled:
            return
        orch.register(JobSpec(job_id=self.job_id, schedule=IntervalSchedule(cfg.interval_seconds),
                              timeout_seconds=cfg.timeout_seconds,
                              queue_policy=QueuePolicy.SKIP_IF_RUNNING, run=self.tick))
```

- Add `JobType.ALERTS = "alerts"` and `JobIds.ALERTS`.
- Add `AlertsJob(self._home, self._config.alerts)` to `ControllerLoop._jobs` and a `_log_alerts()` startup line (`alerts enabled interval=60s path=host/alerts/`).
- The orchestrator already catches job exceptions; the extra `try` keeps the log line specific and protects direct `tick()` calls in tests.

### 6.2 Data-home mount and directories

The controller mounts the data home **read-only** (`.:/raft:ro`) with specific writable sub-mounts. Required changes:

- `src/raft/core/platform/share/compose.yaml` `raft-controller.volumes`: add `- ./host/alerts:/raft/host/alerts`.
- `src/raft/core/core/config/paths/constants.py` `DATA_DIR_RELS`: add `"host/alerts"` (bind-mount source must exist before `compose up`).
- Existing installs pick up the mount only when the controller container is recreated (`raft up`). Until then the writability probe (§4.5 step 2) fails closed and logs a Fix CTA; `raft doctor` reports it (PR 8). Document this in the release notes / operator doc.

### 6.3 Locking

- The job takes **no** flock. It reads `rules.yaml` (atomic replace guarantees a consistent file) and is the only writer of `runtime.json`.
- `alerts.lock` (new, §7.3) serializes CLI/serve writers of `rules.yaml` only.
- The job never takes `stack.lock` / `app-*.lock` (it does not mutate the stack).

### 6.4 Notifications from the controller

The controller already has `settings.yaml` read access, and `Notifier` loads channels per call. No new mounts for delivery.

---

## 7. CLI

### 7.1 Wiring

- `src/raft/services/cli/commands/alerts.py`: `class AlertsCLI` (Fire component). `RaftCLICommands.__init__` adds `self.alerts = AlertsCLI(self._stack)` (one line + import; that file is already ~237 lines, so put nothing else there). Export from `commands/__init__.py`.
- Output rendering lives in `alerts_output.py` (`AlertsCliOutput`) using `OperatorSay.say` / `say_err`; `json: bool = False` flags follow the `raft status --json` precedent.

### 7.2 Commands

| Command | Behavior | Lock | Exit |
|---------|----------|------|------|
| `raft alerts list [--json]` | Table: `ID  ENABLED  SEVERITY  STATE  CONDITION` (STATE from runtime: `ok` / `pending` / `firing (n)` / `suppressed` / `error`; CONDITION = one-line summary). `--json` = `{rules:[…], status:{…}}`. Empty: "No alert rules. Add one with `raft alerts apply --file …` or Settings → Alerts in `raft serve`." | none | 0 |
| `raft alerts show <rule_id> [--json]` | Rule as YAML (export form) + runtime instances. | none | 0; 1 unknown id (OperatorError with Fix: `raft alerts list`) |
| `raft alerts validate [--file PATH]` | Validate `PATH` (or current `rules.yaml`). Prints `OK (n rules)` or each `path: message`; warnings prefixed `warning:`. | none | 0 ok (warnings allowed); 1 errors |
| `raft alerts dry-run <rule_id>` / `raft alerts dry-run --file PATH [--rule ID]` | Evaluate now, no state write, no notify. Prints per subject: subject, matched, current → would state, would notify, leaf details. `--json` available. With `--file`, all rules in the file unless `--rule`. | none | 0 (even if matching); 1 on validation/read error |
| `raft alerts test <rule_id>` | Send `alert.test` through the rule's routing via `Notifier.deliver`. Prints one line per channel `id  type  delivered|failed|skipped  error`. | none | 0 if ≥1 delivered; 1 if none delivered or notifications disabled (message says why) |
| `raft alerts enable <rule_id>` / `disable <rule_id>` | `AlertRulesService.set_enabled`. Prints `Enabled demo-api-5xx-rate.` | alerts.lock | 0; 1 unknown id |
| `raft alerts apply --file PATH [--prune]` | `apply_document`: upsert by id; `--prune` deletes rules absent from the file. Validates the merged document before writing. Prints created/updated/unchanged/deleted. | alerts.lock | 0; 1 on validation error (nothing written) |
| `raft alerts delete <rule_id>` | Remove rule. | alerts.lock | 0; 1 unknown id |
| `raft alerts export [--file PATH]` | Write export YAML to stdout or `PATH`. | none | 0 |
| `raft alerts status [--json]` | Last evaluation (time, duration, errors, document error), alerts enabled/interval, firing + pending instances. Warns when last evaluation is older than 3 × interval ("controller not evaluating — check `raft doctor`"). | none | 0 |

Errors use `OperatorError` (mapped to exit 1 by `CliExitMapper`). Lock timeouts already map through `DomainErrors.deploy_lock_busy`. The CLI must not require the controller to be running for anything except fresh `status` data.

---

## 8. Serve API

New `ServeAlertsApi(stack, *, service=None, registries=None)` in `src/raft/services/serve/alerts/api.py`, registered in `ServeAppFactory` exactly like `ServeNotificationsApi` / `ServeFirewallApi` (constructor kwarg `alerts: Optional[ServeAlertsApi] = None`, default construction in `create`, `alerts.register(app)` in `_register_api`). Serve binds `127.0.0.1` only; no change.

All handlers delegate to `AlertRulesService` / `AlertEngine.dry_run` / `AlertStatusView` / `AlertTester` / `AlertCatalog`. Error mapping: `OperatorError` → 400 `{"detail": str}`; unknown id → 404 with `Fix: GET /api/alerts/rules`; duplicate id on create → 409; lock timeout → 503 with the lock message. String `detail` keeps the SPA's existing `detailOf` helper working.

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/api/alerts/rules` | — | `{"version": 1, "rules": [Rule]}` |
| GET | `/api/alerts/rules/{rule_id}` | — | `Rule` |
| POST | `/api/alerts/rules` | `Rule` (with `id`) | `Rule` (normalized: defaults filled, durations canonical) |
| PUT | `/api/alerts/rules/{rule_id}` | full `Rule`; body `id` optional, must equal path | `Rule` |
| POST | `/api/alerts/rules/{rule_id}/enabled` | `{"enabled": bool}` | `Rule` |
| DELETE | `/api/alerts/rules/{rule_id}` | — | `{"ok": true, "deleted": "<id>"}` |
| POST | `/api/alerts/validate` | `{"rule": Rule}` or `{"document": {...}}` | `ValidationReport` (always 200) |
| POST | `/api/alerts/dry-run` | `{"rule": Rule}` (unsaved draft) or `{"ruleId": "<id>"}` | `DryRunReport`; 400 if the rule is invalid |
| POST | `/api/alerts/rules/{rule_id}/test` | — | `{"ok": bool, "deliveries": [{"channel_id","type_id","status","error"}], "message": str}` |
| GET | `/api/alerts/status` | — | Status (below) |
| GET | `/api/alerts/catalog` | — | Catalog (§4.9) |
| GET | `/api/alerts/export` | — | export document (`version`, `rules`) |
| POST | `/api/alerts/import` | `{"document": {...}, "prune": bool}` | `ApplySummary` |

`Rule` JSON is the YAML rule shape (§3.1) with camelCase keys, durations as canonical strings, and defaults filled.

Status shape:

```json
{
  "enabled": true,
  "intervalSeconds": 60,
  "notificationsEnabled": true,
  "stale": false,
  "lastEvaluation": { "...": "as runtime.json lastEvaluation, or null" },
  "documentError": null,
  "rules": {
    "demo-api-5xx-rate": {"state": "firing", "firingCount": 1, "pendingCount": 0, "suppressedCount": 0, "error": null}
  },
  "instances": [
    {"fingerprint": "demo-api-5xx-rate|demo-api", "ruleId": "demo-api-5xx-rate", "ruleName": "demo-api 5xx error rate",
     "severity": "error", "subject": "demo-api", "state": "firing", "suppressed": false,
     "since": "2026-10-17T11:59:00+00:00", "lastValues": [ ... ]}
  ]
}
```

`stale` = `lastEvaluation.finishedAt` older than `3 × intervalSeconds` (or missing while rules exist and alerts are enabled).

Locking: create / replace / enabled / delete / import take `alerts.lock` (inside the service). Validate, dry-run, test, status, catalog, export are lock-free reads.

---

## 9. SPA UI

### 9.1 Route and navigation

- `src/spa/src/shell/App.tsx`: add `<Route path="/settings/alerts" element={<AlertsSettingsPage />} />` next to the notifications route.
- `src/spa/src/shell/AppShell.tsx` `NAV`: insert `{ to: "/settings/alerts", label: "Alerts", id: "nav-alerts" }` between Firewall and Notifications.
- `raft serve`'s SPA fallback route already serves `/settings/alerts`.

### 9.2 API client — `src/spa/src/alerts/alertsApi.ts`

Mirror `notificationsApi.ts` (same `readJson` / `detailOf` / `jsonRequest` pattern; copy the three small helpers locally as notifications/firewall do).

Types: `AlertSeverity`, `AlertNoData`, `AlertConditionLeaf {signal, select: Record<string, unknown>, kind, params: Record<string, unknown>}`, `AlertConditionGroup {all?: AlertCondition[]; any?: AlertCondition[]}`, `AlertCondition = AlertConditionLeaf | AlertConditionGroup`, `AlertRule`, `AlertRulesPayload`, `AlertValidationReport`, `AlertDryRunReport`, `AlertStatusPayload`, `AlertInstance`, `AlertCatalogPayload`, `AlertCatalogField` (extends `NotificationStrategyField` with `options?`, `default?`), `AlertTestResult`.

Cached resources (`CachedResourceProxy` + `appResourceCache`):

- `rulesProxy` — `resourceId("alerts", "rules")`; `createAlertRule`, `replaceAlertRule`, `setAlertRuleEnabled`, `deleteAlertRule`, `importAlertRules` use `mutateAndInvalidate`.
- `catalogProxy` — `resourceId("alerts", "catalog")`; read-only (invalidate when the page mounts so new apps appear: call `catalogProxy.refresh()` in `load`).
- Status is **not** cached: `fetchAlertStatus()` is a plain `jsonRequest` (polled).

Functions: `fetchAlertRules`, `fetchAlertCatalog`, `fetchAlertStatus`, `createAlertRule`, `replaceAlertRule`, `setAlertRuleEnabled`, `deleteAlertRule`, `validateAlertRule`, `dryRunAlertRule(draft | {ruleId})`, `testAlertRule(id)`, `exportAlertRules`, `importAlertRules`.

Channels: reuse `fetchNotificationChannels` from `../notifications/notificationsApi` (single source of truth).

### 9.3 Helpers — `src/spa/src/alerts/alertsHelpers.ts` (pure, unit-tested)

- `parseAlertDuration(text) -> number | null`, `formatAlertDuration(seconds) -> string` (same grammar as Python `AlertDuration`; distinct names because `shared/format.ts` already exports a display-oriented `formatDuration`).
- `isGroup(node)`, `groupOp(node) -> "all" | "any"`, `groupChildren(node)`.
- Tree edits by path (immutable): `addLeaf(tree, path, leaf)`, `addGroup(tree, path, op)`, `removeNode(tree, path)`, `setGroupOp(tree, path, op)`, `replaceLeaf(tree, path, leaf)`, `wrapInGroup(tree, path, op)`; `countLeaves(tree)`, `depth(tree)`; `canAddChild(tree, path, limits)`.
- `defaultLeaf(catalog)` — first numeric source + `threshold` with catalog defaults.
- `kindsForSource(catalog, signal)` — kinds whose `value_types` include the source's `value_type`.
- `summarizeCondition(tree, catalog) -> string` (e.g. `avg(error_rate_5xx) of demo-api over 5m > 0.05 AND …`) used in the rule list.
- `emptyRuleDraft(catalog)`, `draftFromRule(rule)`, `ruleFromDraft(draft)`; `validateDraft(draft) -> string[]` (client-side quick checks: id pattern, name, durations parse; server stays authoritative).
- `ruleStateFor(status, ruleId, enabled) -> "disabled" | "ok" | "pending" | "firing" | "suppressed" | "error" | "unknown"`.
- `routingLabel(channelIds, channels) -> string` (`All enabled channels` / `ops-primary, …` / `ops-primary (missing)`).
- `relativeTime(iso, now)` for "evaluated 12s ago" (`shared/format.ts` has no relative-time helper today; its `formatDuration(seconds)` can format the delta).

### 9.4 Shared catalog form extraction

Create `src/spa/src/shared/catalogForm/CatalogFields.tsx` and `catalogFormHelpers.ts`:

- Move `coerceFieldValue`, `settingsFromFieldState`, `fieldStateFromSettings` from `notificationsHelpers.ts` into `catalogFormHelpers.ts`, extend for `select` (value as-is), `duration` (validated with `parseAlertDuration`, stored as string), `string_list` (comma split/trim/drop empty ↔ join). `notificationsHelpers.ts` re-imports them (keep its exported names working for existing callers/tests by re-exporting).
- `CatalogFields` props: `{ fields: CatalogField[]; values: Record<string, string>; busy: boolean; idPrefix: string; onChange: (key: string, value: string) => void }`; renders text/url/secret/number/checkbox like `ChannelSettingsFields` today, plus `<select>` for `select` (with `options`) and a text input with `placeholder="5m"` + inline parse hint for `duration`.
- `ChannelSettingsFields` becomes a usage of `CatalogFields` with `idPrefix="channel-setting-"` so existing DOM ids (`channel-setting-url`, …) and visuals do not change. Verify with a screenshot of the notifications form before/after.

### 9.5 Component tree

```text
AlertsSettingsPage
├── PageHeader (title "Alerts", meta chips, actions)
├── [loading | error | stale callouts]
├── AlertsStatusPanel
│   └── AlertStateChip (per instance)
├── section.panel#alerts-rules
│   └── AlertRuleList
│       └── AlertRuleRow × n → AlertStateChip, row actions
├── AlertRuleFormModal (create/edit)
│   ├── basic fields (id, name, severity, enabled, description)
│   ├── timing fields (for, cooldown, repeatEvery, notifyOnRecovery, noData)
│   ├── ChannelRoutingPicker
│   ├── ConditionEditor (recursive)
│   │   └── ConditionLeafEditor → CatalogFields (select fields) + CatalogFields (params)
│   └── DryRunPanel (inline result for the draft)
├── Modal#alerts-dry-run (row action) → DryRunPanel
├── ConfirmPopup (delete)
└── (toasts via chrome/toast)
```

#### `AlertsSettingsPage` — `src/spa/src/alerts/AlertsSettingsPage.tsx`

- Props: none.
- State: `rules: AlertRule[]`, `catalog: AlertCatalogPayload | null`, `channels: NotificationChannel[]`, `notificationsEnabled: boolean`, `status: AlertStatusPayload | null`, `busy` (initial load), `error: string | null`, `busyId: string | null` (row action in flight), `formOpen`, `formMode: "create" | "edit"`, `editing: AlertRule | null`, `formBusy`, `pendingDelete: AlertRule | null`, `dryRunFor: AlertRule | null`, `dryRun: AlertDryRunReport | null`, `dryRunBusy`, `live: boolean` (polling active).
- `load()`: `Promise.all([fetchAlertRules(), catalogProxy refresh, fetchNotificationChannels(), fetchAlertStatus()])`, same try/catch/finally shape as `NotificationsSettingsPage.load`.
- Polling: status only, every **10 s** while the tab is visible, using `bindStatusPolling(onTick, setLive, 10_000)` — extend `shell/statusPolling.ts` `bindStatusPolling` with an optional third `intervalMs` param defaulting to `STATUS_POLL_MS` (no behavior change for the dashboard). Status is cheap (two small files).
- `PageHeader`: title `Alerts`; subtitle `Rules that watch metrics and control-plane signals and send through your notification channels.`; `meta`: chip `Evaluating every 60s` (from status) or `Alerts disabled in settings.yaml`; chip `Notifications off` (warn) when `notificationsEnabled` is false, linking to `/settings/notifications`; `LiveIndicator` (chrome) for polling. `actions`: `Add rule` (`#alerts-add`, `btn-primary`, disabled while loading or catalog empty), `Export` (downloads YAML/JSON via `exportAlertRules`), `Import` (file input → `importAlertRules` with a ConfirmPopup "Replace or merge?" offering merge (default) / replace (`prune`)).
- Callouts (`callout callout-warn` / `callout callout-bad`, existing classes):
  - `#alerts-stale` when `status.stale`: "The controller has not evaluated alerts recently. Run `raft doctor`."
  - `#alerts-document-error` when `status.documentError`: shows the message; rule editing still works (service re-validates on save).
  - `#alerts-no-channels` when there are no enabled channels: "Alerts will evaluate but nothing will be delivered. Add a channel in Notifications."
- Action handlers: `openCreate`, `openEdit(rule)`, `saveRule(draft)` (create/replace → toast.good → close → `load()`; on error `toast.bad(message)` and keep modal open with the message in the form error slot), `toggleEnabled(rule)`, `confirmDelete()`, `runDryRun(rule)`, `sendTest(rule)` (toast summarises deliveries: `Test sent to 1 of 2 channels` / `toast.bad` with the first error).

#### `AlertsStatusPanel` — `AlertsStatusPanel.tsx`

- Props: `{ status: AlertStatusPayload | null; rules: AlertRule[]; now: number }`.
- Renders `section.panel#alerts-status` with header "Currently firing" + count, last-evaluation line (`Last evaluated 12s ago · 420 ms · 3 rules`), errors list (rule id + message) collapsed under a `<details>` when present.
- Instance list (firing first, then pending; severity order critical → info): `AlertStateChip`, rule name (button that calls `onEdit`-less "scroll to rule" via anchor `#alert-rule-<id>`), subject, since (relative), last values compact (`error_rate_5xx 0.071`), `suppressed` hint "in cool-down".
- Empty state (`.empty-state#alerts-none-firing`): "Nothing firing." + last evaluation time; before first evaluation: "Waiting for the first evaluation (controller runs every 60s)."

#### `AlertStateChip` — `AlertStateChip.tsx`

- Props: `{ state: ReturnType<typeof ruleStateFor> | "firing" | "pending"; suppressed?: boolean }`.
- Maps to `chip chip-ok` (ok), `chip chip-warn` (pending, suppressed), `chip chip-bad` (firing, error), `chip` (disabled, unknown). `chip-warn` and `chip-bad` do not exist yet: add them to `src/spa/src/styles.css` next to `.chip-ok` using the existing warn/bad color tokens used by `.callout-warn` / `.callout-bad`.

#### `AlertRuleList` — `AlertRuleList.tsx` (+ `AlertRuleList.css`)

- Props: `{ rules; status; channels; catalog; busyId; onEdit; onToggle; onDelete; onDryRun; onTest }`.
- Pattern: copy `ChannelList` structure (`ul.alert-rule-list` / `li.alert-rule-row[data-rule-id]`, `channel-row-main` / `-actions` equivalents).
- Row main: name (bold) + id (`code`), `AlertStateChip`, severity chip, enabled chip, one-line `summarizeCondition`, timing summary (`for 2m · cool-down 15m`), routing `routingLabel`.
- Row actions (`action-btn`, ids `alert-toggle-<id>`, `alert-edit-<id>`, `alert-dryrun-<id>`, `alert-test-<id>`, `alert-delete-<id>`): Enable/Disable, Edit, Dry run, Send test (disabled with title when no deliverable channel), Delete (`action-btn-danger`).
- Empty state `#alerts-empty`: "No alert rules yet." + muted "Use *Add rule*, or `raft alerts apply --file rules.yaml` on the host."

#### `AlertRuleFormModal` — `AlertRuleFormModal.tsx` (+ css)

- Props: `{ open; mode: "create" | "edit"; rule: AlertRule | null; catalog: AlertCatalogPayload; channels: NotificationChannel[]; busy; error: string | null; onClose; onSubmit(rule: AlertRule) }`.
- Uses `Modal` with `size="wide"`, `closeOnOverlay={!busy}`, footer like `ChannelFormModal` (Cancel, **Dry run**, Save with spinner; Save is `type="submit" form="alert-rule-form"`).
- State: `draft` (from `draftFromRule` / `emptyRuleDraft`), `formError`, `dryRun: AlertDryRunReport | null`, `dryRunBusy`. Reset on open like `ChannelFormModal.resetForm`.
- Layout (`form#alert-rule-form`, sections with `h3`):
  1. **Rule** — Id (`#alert-id`, disabled in edit; pattern hint), Name, Severity `<select>` from `catalog.severities`, Enabled checkbox, Description textarea.
  2. **Condition** — `ConditionEditor`.
  3. **Timing** — For, Cool-down, Repeat every (duration inputs with inline parse errors), Notify on recovery checkbox, No data `<select>` (`ok` "Treat as OK", `alerting` "Treat as alerting", `keep` "Keep last state").
  4. **Delivery** — `ChannelRoutingPicker`.
  5. **Dry run result** — `DryRunPanel` when `dryRun` is set.
- Dry run button: `validateDraft` locally → `dryRunAlertRule({rule: ruleFromDraft(draft)})` → show result (does not save). Server 400 → `formError`.
- Submit: `validateDraft` → `onSubmit(ruleFromDraft(draft))`. Parent passes server error back via `error` prop (rendered `p.error#alert-form-error`).

#### `ConditionEditor` — `ConditionEditor.tsx` (+ css)

- Props: `{ node: AlertCondition; path: number[]; catalog; limits; busy; onChange(next: AlertCondition): void; onRemove?: () => void; depth: number }`.
- Root renders either a leaf (via `ConditionLeafEditor`) or a group box:
  - Group header: segmented toggle **All of (AND)** / **Any of (OR)** (`setGroupOp`), remove-group button (non-root).
  - Children rendered recursively with indentation + left border (`.cond-group`), each child with a remove button.
  - Footer buttons: `+ Condition` (`addLeaf` with `defaultLeaf(catalog)`), `+ Group` (`addGroup`, hidden when `depth >= limits.maxDepth - 1`); both disabled when `countLeaves >= limits.maxLeaves`, with title text explaining the limit.
- Root leaf shows a `Combine with…` button that calls `wrapInGroup(root, [], "all")`.
- All edits go through helper functions (immutable), so the component holds no tree state itself.

#### `ConditionLeafEditor` — `ConditionLeafEditor.tsx`

- Props: `{ leaf: AlertConditionLeaf; catalog; busy; idPrefix: string; onChange(next) }`.
- Signal `<select>` from `catalog.sources` (label). Changing signal resets `select` to source defaults and `kind` to the first compatible kind (`kindsForSource`) with that kind's defaults.
- Source select fields via `CatalogFields` (`fields = source.select_fields`, `idPrefix = "${idPrefix}select-"`). Metric `<select>` options filtered by the chosen target's scope (`host` / `edge` / service) using `source.metrics[].scopes`.
- Kind `<select>` from compatible kinds; params via `CatalogFields` (`idPrefix = "${idPrefix}param-"`).
- A muted one-line preview `summarizeCondition(leaf)` under the inputs.
- Values are stored in the draft as form strings and converted by `ruleFromDraft` using the catalog field kinds (`coerceFieldValue`).

#### `ChannelRoutingPicker` — `ChannelRoutingPicker.tsx` (+ css)

- Props: `{ channels: NotificationChannel[]; notificationsEnabled: boolean; value: string[]; busy; onChange(ids: string[]) }`.
- Radio: **All enabled channels** (value `[]`) / **Only selected channels**. When "selected": checkbox list of channels (`id` + `type` + Disabled chip; disabled channels selectable but flagged "won't receive while disabled").
- Ids in `value` that no longer exist render as a struck-through row "ops-old (missing)" with a remove button (server rejects saving unknown ids).
- Empty channels: muted text + link `Add a channel in Notifications` (`/settings/notifications`). Global off: inline warn text.

#### `DryRunPanel` — `DryRunPanel.tsx` (+ css)

- Props: `{ report: AlertDryRunReport | null; busy: boolean; error?: string | null }`.
- Header: `Evaluated now (dry run — nothing saved or sent)` + timestamp.
- Table per subject: Subject · Matched (`yes` / `no` / `no data`) · Current → Would be (chips) · Would notify (`firing` / `resolved` / `—`). Expandable row with leaf details (`detail` strings, e.g. `avg(5m) = 0.071 > 0.05`).
- Empty subjects: "No series matched this selector in the window (no data). Check the target and that metrics are being recorded."
- Used inline in the form and inside a `Modal` (`#alerts-dry-run`) opened from the row action.

### 9.6 States checklist

| State | Where | Rendering |
|-------|-------|-----------|
| Initial loading | page | existing `.loading` + spinner block ("Loading alerts…") |
| Load error | page | `p.error#alerts-error` (role alert) + Retry button calling `load()` |
| Catalog empty (no sources registered) | page | `callout-warn#alerts-empty-catalog`; Add rule disabled |
| No rules | list | `.empty-state#alerts-empty` |
| Nothing firing | status panel | `.empty-state#alerts-none-firing` |
| Never evaluated / stale | header + callout | `callout-warn#alerts-stale` |
| Document error | callout | `callout-bad#alerts-document-error` |
| Notifications off / no channels | header chip + callout | warn chip / `callout-warn#alerts-no-channels` |
| Row action in flight | row | buttons disabled for `busyId` |
| Save / dry-run in flight | modal | button spinner (`is-loading`) |

### 9.7 Build and proof

- `cd src/spa && npm run lint && npm test && npm run build` → commit the rebuilt bundle under `src/raft/core/platform/share/serve/spa/`.
- Screenshots (agent-browser) attached to the PR with `gh pr edit --attach`: empty page, rule list with one firing + one pending, create modal with a nested `all` group, dry-run result, routing picker, notifications form unchanged (after the catalog-form extraction). Use only `demo-api` / `demo-web` / `ops-primary` data (seed a temp `RAFT_DATA_HOME`).

---

## 10. Docs

- **New** `docs/serve-alerts.md`: what alerts are vs channels ("rules decide *when*, channels decide *where*"); rule document reference (fields table, durations, conditions, subject join for `*`, `noData`); signal source reference (metric keys per scope, derived error rates, latency note); state lifecycle (pending → firing → resolved, cool-down, repeat, suppressed); routing; CLI reference; serve page walkthrough; `alerts:` settings; troubleshooting (stale evaluation → controller mount / `raft up`, document error → `raft alerts validate`); full PII-safe example (§3.1).
- `docs/serve-notifications.md`: short "Alert rules" section linking to `serve-alerts.md`; mention `channelIds` routing.
- `AGENTS.md`: feature table row → `Alert rules engine (metrics/control-plane → notifications)` **Shipped**, pointing to #236 and `docs/serve-alerts.md`; keep a **Planned** row for firewall-derived alert signals; add `host/alerts/rules.yaml`, `host/alerts/runtime.json` to the data-home table; add `alerts.lock` to the locks table ("CLI/serve writes to `host/alerts/rules.yaml`"); add "Alert rules" to "Where to change what" (`core/observe/alerts/`, `services/serve/alerts/`, `services/controller/jobs/alerts/`, SPA `src/spa/src/alerts/`).
- `README.md`: update the "Alerts from firewall + graph metrics (via notifications)" row (currently 📋) — metrics/control-plane shipped, firewall planned.
- `src/raft/core/platform/locking/__init__.py` docstring: add `alerts.lock`.
- This plan stays in `docs/design/` as the historical record.

---

## 11. Testing plan

Unit tests mirror the source tree under `tests/unit/` and must keep **100% branch coverage** (`uv run pytest tests/unit`). Test files < 300 lines, test bodies ≤ 20 lines (meta guards apply to `tests/` too) — split by class.

| Area | Test module(s) | Must cover |
|------|----------------|------------|
| Duration | `tests/unit/core/observe/alerts/model/test_duration.py` | int/str forms, units, bounds, invalid strings, canonical format |
| Parsers / document | `…/model/test_condition_parser.py`, `test_rule_parser.py`, `test_document.py` | defaults, every validation error path with exact `path`, depth/leaf/rule limits, duplicate ids, version handling, export round-trip, unknown signal/kind, value-type mismatch |
| Registries + catalog | `…/signals/test_signal_registry.py`, `…/kinds/test_kind_registry.py`, `…/catalog/test_alert_catalog.py`, `tests/unit/core/observe/notify/test_catalog_field.py` (options/default) | duplicate register, unknown → OperatorError with Fix, catalog shape, dynamic target options, a fake third-party source/kind registers without engine changes (open-closed proof) |
| Kinds | `…/kinds/test_threshold.py`, `test_state_match.py`, `test_event_count.py`, `test_aggregates.py`, `test_operators.py` | each aggregate/op, None filtering, no data |
| Sources | `…/signals/metrics/test_resources_source.py`, `test_http_source.py`, `test_metric_keys_guard.py`, `…/signals/control/test_container_status_source.py`, `test_graph_events_source.py` | fixture JSONL in `tmp_path`, window slicing, `*` expansion, scope validation, derived error rates incl. `requests == 0`, memo reads file once, scaled-to-zero skip, builder-key guard |
| Condition evaluator | `…/engine/test_condition_evaluator.py` | truth tables for all/any with True/False/None, global vs wildcard join, nested groups, `noData` modes |
| State machine | `…/engine/test_state_machine.py` | every row of the §4.4 table, cool-down suppression, repeat, suppressed-resolve silence, `keep` |
| Engine | `…/engine/test_engine.py`, `test_dry_run.py` | end-to-end tick with fake sources + fake Notifier: firing, resolve, per-rule error isolation, document error, unwritable runtime → no notify, persist-before-notify ordering, ruleHash reset, disabled/deleted pruning, dry-run writes nothing |
| Event factory / dispatch | `…/engine/test_event_factory.py`, `test_dispatch.py`; `tests/unit/core/observe/notify/test_notifier.py` (extend) | kinds/severity/title/body/context keys; `channel_ids` filter, missing id warning, `deliver` returns results, `notify` still swallows |
| Stores | `…/store/test_rules_store.py`, `test_runtime_store.py`, `test_atomic.py` | atomic write, 0600 mode, missing file, corrupt runtime quarantine, `ensure_writable` failure |
| Service | `…/service/test_rules_service.py`, `test_status_view.py`, `test_tester.py` | CRUD, lock held (patch `AlertsLock` or assert lock file), apply merge/prune summary, unknown channel id error, warnings, stale computation |
| Lock | `tests/unit/core/platform/locking/test_alerts_lock.py` | path + kind |
| Settings | `tests/unit/core/core/config/settings/test_alerts_section.py` | defaults, bounds (`intervalSeconds ≥ 15`), invalid types |
| Import cycle | `tests/unit/core/observe/alerts/test_import_order.py` | subprocess imports in both orders (§5.0) |
| Controller | `tests/unit/services/controller/jobs/alerts/test_job.py`, extend `run/` loop test | attach registers spec when enabled / skips when disabled, tick swallows exceptions, `JobIds.ALERTS` |
| CLI | `tests/unit/services/cli/commands/test_alerts_cli.py` (+ split files) | each command's output and exit code, `--json`, `--file`, `--prune`, unknown id |
| Serve API | `tests/unit/services/serve/alerts/test_api.py` (+ split) using `TestClient` like `serve/notifications/test_api.py` | every route, 400/404/409/503 mapping, validate always 200, dry-run with draft and id, factory registration |
| Meta | existing `tests/meta` | size guards pass; `test_package_data.py` unaffected (no new share files except compose edit) |

SPA (`node --test`, pure TS helpers only — the repo has no React renderer tests):

- `src/spa/test/alerts/alertsHelpers.test.ts`: durations, every tree-edit helper (immutability, limits), `kindsForSource`, `summarizeCondition`, draft ↔ rule round-trip, `ruleStateFor`, `routingLabel`.
- `src/spa/test/shared/catalogFormHelpers.test.ts`: moved helpers + `select` / `duration` / `string_list`.
- Visible changes proven by screenshots (§9.7).

E2E: not required for v1 (unit + serve `TestClient` cover the surfaces; the controller mount change is covered by a unit test asserting the compose template contains the `host/alerts` volume). Optional follow-up: extend `tests/e2e/test_compose_up.py` to assert the controller can write `host/alerts/runtime.json` after `raft up`.

Commands:

```bash
uv sync --extra dev
uv run pytest tests/unit
uv run pytest tests/meta --no-cov
cd src/spa && npm run lint && npm test && npm run build
```

---

## 12. Phased delivery (PR breakdown)

Each PR is independently reviewable, keeps CI green, and links #236. Branch per PR from `main`.

### PR 1 — Prep: metrics path constants + `CatalogField` options + `Notifier` routing

- `MetricsPaths` core module; repoint `observe/read/metrics` and re-export from `controller/jobs/metrics` (§5.0).
- `CatalogField.define(options=…, default=…)`.
- `Notifier.notify(..., channel_ids=None)` + `Notifier.deliver(...)` (§4.6).
- **Accept:** no behavior change for existing producers; new unit tests; 100% coverage; import-order test passes.

### PR 2 — Engine core (models, registries, kinds, evaluator, state machine, stores)

- `observe/alerts/` model, signals ABC/registry/series/context, kinds (threshold/state/event_count), condition evaluator, state machine, fingerprint, event factory, dispatch, engine (`tick`, `dry_run`), stores, `AlertCatalogs.default()` with **no concrete sources yet** (tests use fake sources), `AlertsLock`, `AlertRulesService`, `AlertStatusView`, `AlertTester`, `AlertCatalog`.
- **Accept:** unit tests prove open-closed registration with fake source/kind; state-machine table fully covered; persist-before-notify and fail-closed tests; no controller/CLI/serve wiring yet.

### PR 3 — Metrics threshold adapters (first proving path)

- `metrics.resources`, `metrics.http` sources, `MetricsSampleCache`, metric-key guards; register in `AlertCatalogs.default()`.
- **Accept:** engine test with fixture `http.jsonl` for `demo-api` fires `alert.firing` (error) into a fake Notifier with the §3.4 context, then resolves.

### PR 4 — Controller job + settings + mount

- `AlertsConfig` + `strategies/alerts.py`; `JobType.ALERTS` / `JobIds.ALERTS`; `AlertsJob`; `ControllerLoop` wiring + startup log; `compose.yaml` volume; `DATA_DIR_RELS` entry.
- **Accept:** job tests; compose template test asserts the volume; manual check on a dev host: `raft up`, a rule on `demo-api` writes `runtime.json` and a webhook channel receives the event (note it in the PR body; no live endpoints in the repo).

### PR 5 — CLI `raft alerts`

- `AlertsCLI` + `AlertsCliOutput`; all commands in §7.2.
- **Accept:** CLI unit tests for each command / exit code; PR body shows sample output (PII-safe).

### PR 6 — Serve Alerts API

- `services/serve/alerts/` + `ServeAppFactory` registration (§8).
- **Accept:** `TestClient` tests for every route and error mapping.

### PR 7 — SPA Alerts page (+ catalog form extraction)

- `shared/catalogForm/`, `ChannelSettingsFields` on top of it, `bindStatusPolling` interval param, `chip-warn` / `chip-bad`, all `src/spa/src/alerts/*`, route + nav, helper tests, rebuilt bundle.
- **Accept:** lint/test/build green; bundle committed; screenshots attached (§9.7), including the unchanged notifications form.

### PR 8 — Control-plane sources + doctor + docs

- `control.container_status`, `control.events`; `raft doctor` checks (rules document invalid; alerts enabled with rules but evaluation stale; `host/alerts` not writable from the controller); `docs/serve-alerts.md`, notifications doc link, AGENTS/README rows (§10).
- **Accept:** source + doctor unit tests; docs reviewed for PII; AGENTS/README rows updated.

(PRs 5 and 6 can proceed in parallel after PR 3; PR 7 needs PR 6. If reviewers prefer, the docs part of PR 8 can land with PR 7 so the shipped surface is documented at release.)

### Follow-ons (separate issues, not v1)

- F1 — `edge.denies` firewall-derived source via `HttpMetricsAggregator` firewall counters (§5.6); update AGENTS planned row.
- F2 — Control-plane journal + `control.notifications` source (§5.5).
- F3 — Optional e2e: controller writes `runtime.json` after `raft up`.
- F4 — Silences / maintenance windows; message templates.

---

## 13. Open questions and risks

| # | Item | Proposed stance |
|---|------|-----------------|
| 1 | Existing installs keep the old controller container (read-only `host/alerts`) until recreated. | Fail closed (no notifications, logged Fix CTA), doctor check, release note "run `raft up` after updating". Confirm whether `raft update` should trigger a controller recreate in a separate issue. |
| 2 | Unknown `channelIds` at write time: error vs warning. | Error at write (strict like apply), warning at runtime (channel deleted later → deliver to remaining). Deleting a channel referenced by rules: notifications API could warn — follow-up. |
| 3 | Metrics flush lag (up to ~60 s) delays detection. | Document; validation warning for windows < 2 × interval. Do not change recorder batching in this work. |
| 4 | `*` subjects with mixed sources (resources app names vs HTTP `by_service` keys). | Both use the Compose service id; verify `by_service` keys equal `ContainerStatus.service` for grouped apps (`GROUP-NAME`) in PR 3 tests; normalize in `MetricTargets` if not. |
| 5 | Rules document strictness may block evaluation of all rules after a bad hand edit. | Accepted (writes via CLI/serve are validated); surfaced in status/doctor/SPA callout. Revisit with per-rule leniency if operators hit it. |
| 6 | Notification storms when many subjects flip at once (e.g. `*` rule during a host outage). | v1: per-fingerprint dedupe + cool-down only. Follow-up: per-rule max notifications per tick (grouped event). Note in docs. |
| 7 | `runtime.json` growth. | Prune `ok` instances without active cool-down every tick; bound `lastValues` to the rule's leaves; cap `errors` to 50. |
| 8 | Serve and controller clocks. | Same host; all timestamps UTC ISO-8601. SPA relative times use browser clock — acceptable. |
| 9 | Interval changes require controller restart. | Document in `serve-alerts.md`; the SPA shows the interval from settings so the operator can see it. |
| 10 | Heal/ACME/wake/deploy-failed are not yet composable signals. | Explicit follow-on F2; `ControlPlaneEvents` keep delivering directly in the meantime. |
