# Serve ordered firewall (gate)

`raft serve` and **`raft firewall …`** manage an **ordered** edge firewall on the **gate** (not a middle hop). Both paths share `FirewallService` (persist → render → gate nginx **reload**; never recreate for rule-only edits).

Settings → **Firewall** (`/settings/edge-access`).

## CLI

```bash
raft firewall show
raft firewall replace --file rules.yaml
raft firewall export --file rules.yaml
raft firewall import_document --file rules.json
raft firewall services
raft firewall recommendations
raft firewall dismiss permit-port-80
raft firewall draft --client-ip=192.0.2.1 --service=demo-api
raft firewall apply_inspection --client-ip=192.0.2.1 --service=demo-api
raft firewall remove_inspection --client-ip=192.0.2.1
```

| Command | Serve API |
|---------|-----------|
| `show` / `replace --file` | `GET`/`PUT` `/api/firewall` |
| `export` / `import_document --file` | `GET` export / `POST` import |
| `services` | `GET` `/api/firewall/services` |
| `recommendations` / `dismiss` | list / dismiss recommendation |
| `draft` / `apply_inspection` / `remove_inspection` | from-inspection draft / apply / remove |

Examples use documentation CIDRs (`192.0.2.0/24`) and `demo-api` only.

## Design

| Decision | Choice |
|----------|--------|
| Enforcement | **Gate nginx** (`$remote_addr`) |
| Model | Ordered rules; **first match wins** |
| Fields | CIDR, port (`number` or `any`), protocol, service (`any` or App), action |
| Persist | `~/.raft/host/firewall/rules.yaml` |
| Apply | Persist → `raft render` → **gate nginx reload** (never recreate for rule-only edits) |
| Compile | Heavy work at Save/render: merge adjacent same-action CIDRs; emit `allow`/`deny` + drop maps |
| Recommendations | Per published HTTP edge port **permit** + **default deny any**; dismissals in `state/firewall/dismissed-recommendations.json` |

### Actions → nginx

| Action | Nginx |
|--------|--------|
| `permit` | `allow <cidr>;` |
| `deny` | `deny <cidr>;` → HTTP **403** + `forbidden.html` |
| `drop` | `geo` map + `return 444;` (connection closed, no response body) |

ACME HTTP-01 stays on a sibling `location ^~ /.well-known/acme-challenge/` **outside** the firewall `location /`.

### Eligibility

Host-routed HTTP edge only (`expose: http` + `publicHost`) for **service**-scoped rules. Stream / host / worker are out of scope for service dropdown; use `service: any` for edge-wide policy.

### Flat ACL retired (#195 / #312)

Legacy flat ACL UI/API (`acl.gate`, `state/acl/`, `/api/acl/*`, Settings allow/deny lists) are **removed**. Edge policy is **only** the ordered firewall document under `host/firewall/rules.yaml`. Leftover ACL files on disk are ignored; render clears stale `gate-http/acl/*.inc` and uses firewall includes. Operators who still need old ACL policy must reconstruct rules under Settings → Firewall (or import) after upgrade — see [releases.md](releases.md) upgrade notes.

### Recommendation defaults

| Kind | Rule inserted |
|------|----------------|
| `permit-port-<N>` | `0.0.0.0/0` / port `N` / `tcp` / `any` → **permit** (prepended) |
| `default-deny` | `0.0.0.0/0` / port `any` / protocol `any` / service `any` → **deny** (appended) |

Apply inserts into the local table (Save still required). Dismiss persists under `~/.raft/state/firewall/dismissed-recommendations.json`.

## Operator API

| Method | Path | Role |
|--------|------|------|
| `GET`/`PUT` | `/api/firewall` | Load / save rules (Save applies) |
| `GET` | `/api/firewall/export` | Serializable document (no `source`) |
| `POST` | `/api/firewall/import` | Validate + save + apply |
| `GET` | `/api/firewall/services` | Dropdown: `any` + eligible Apps |
| `GET` | `/api/firewall/recommendations` | Open baseline suggestions |
| `POST` | `/api/firewall/recommendations/{id}/dismiss` | Hide a suggestion |
| `GET` | `/api/firewall/from-inspection` | Prefill draft + matching host-CIDR rules (from HTTP inspection) |
| `POST` | `/api/firewall/from-inspection` | Upsert rule and **prepend** + apply (reload) |
| `POST` | `/api/firewall/from-inspection/remove` | Remove rules matching client host CIDR + apply |

### Inspection → rule (#198)

From a service HTTP request row, **Firewall** / **Remove** call the `from-inspection` endpoints. Rules are **prepended** (not appended) so a client-specific deny/permit is not shadowed by an earlier broad permit. Operators may widen the CIDR in the form before apply.

There is **no** clear-all / DELETE endpoint in the operator UI path (mass wipe is intentionally hard).

Example document:

```json
{
  "version": 1,
  "rules": [
    {
      "id": "lab",
      "cidr": "192.0.2.0/24",
      "port": 443,
      "protocol": "tcp",
      "service": "any",
      "action": "permit"
    },
    {
      "id": "default-deny",
      "cidr": "0.0.0.0/0",
      "port": "any",
      "protocol": "any",
      "service": "any",
      "action": "deny"
    }
  ]
}
```

Epic [#207](https://github.com/danielnachumdev/raft/issues/207), delivery [#211](https://github.com/danielnachumdev/raft/issues/211). Former flat ACL path removed in #312.
