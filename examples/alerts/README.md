# Alert rules examples

Sample document for `~/.raft/host/alerts/rules.yaml`.

## Apply

- **UI:** Settings → Alerts → **Import** (JSON export), or copy fields from **Syntax** (YAML/JSON).
- **CLI:** `raft alerts apply --file examples/alerts/rules.yaml`

Notification **channels are optional**. Rules evaluate without them; delivery starts once channels exist (empty `channelIds` = every enabled channel).

## Primer

| Field | Meaning |
|-------|---------|
| `signal` | Catalog source (`metrics.http`, `metrics.resources`, `control.container_status`, …) |
| `select` | Subject (`target` = App compose id, or `*` for every App) |
| `kind` / `params` | Match style: `threshold` or `state` |
| `for` | How long the condition must stay true before firing |
| `cooldown` | Silence before re-notifying the same instance |
| `channelIds` | Optional delivery list |

See [`rules.yaml`](./rules.yaml) for a full demo document (`demo-api` only — no live inventory).

In the ops UI, open **Alerts → Syntax** to view the same shape as YAML or JSON and switch to **Your rules**.
