# Serve ordered firewall (gate)

`raft serve` manages an **ordered** edge firewall on the **gate** (not a middle hop).

Settings → **Firewall** (`/settings/edge-access`).

## Design

| Decision | Choice |
|----------|--------|
| Enforcement | **Gate nginx** (`$remote_addr`) |
| Model | Ordered rules; **first match wins** |
| Fields | CIDR, port (`number` or `any`), protocol, service (`any` or App), action |
| Persist | `~/.raft/state/firewall/rules.yaml` |
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

### Migration from ACL v1 (#195)

Legacy flat ACL UI/API (`/api/acl/*`, Settings allow/deny lists, per-App Access control) are **removed**.

- Until `state/firewall/rules.yaml` exists, GET `/api/firewall` returns an **in-memory migration** of leftover `acl.gate` + `state/acl/apps/*.json` (`source: acl-v1-migrated`).
- Render **always** uses ordered-firewall includes (and clears leftover `gate-http/acl/*.inc`).
- **Save** (or import) writes the durable firewall document.

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

Epic [#207](https://github.com/danielnachumdev/raft/issues/207), delivery [#211](https://github.com/danielnachumdev/raft/issues/211). Former flat ACL notes: [`docs/serve-acl.md`](serve-acl.md) (retired).
