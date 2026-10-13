# Serve ordered firewall (gate)

`raft serve` manages an **ordered** edge firewall on the **gate** (not a middle hop).

Settings → **Firewall** (`/settings/edge-access`).

## Design

| Decision | Choice |
|----------|--------|
| Enforcement | **Gate nginx** (`$remote_addr`) |
| Model | Ordered rules; **first match wins** |
| Fields | CIDR, port, protocol, service (`any` or App), action |
| Persist | `~/.raft/state/firewall/rules.yaml` |
| Apply | Persist → `raft render` → **gate nginx reload** (never recreate for rule-only edits) |
| Compile | Heavy work at Save/render: merge adjacent same-action CIDRs; emit `allow`/`deny` + drop maps |

### Actions → nginx

| Action | Nginx |
|--------|--------|
| `permit` | `allow <cidr>;` |
| `deny` | `deny <cidr>;` → HTTP **403** + `forbidden.html` |
| `drop` | `geo` map + `return 444;` (connection closed, no response body) |

ACME HTTP-01 stays on a sibling `location ^~ /.well-known/acme-challenge/` **outside** the ACL/firewall `location /`.

### Eligibility

Host-routed HTTP edge only (`expose: http` + `publicHost`), same spirit as ACL v1. Stream / host / worker are out of scope.

### Migration from ACL v1 (#195)

- Until `state/firewall/rules.yaml` exists, GET `/api/firewall` returns an **in-memory migration** of `acl.gate` + `state/acl/apps/*.json` (`source: acl-v1-migrated`). Render still uses legacy ACL includes.
- **Save** (or import) writes the firewall document and **adopts** it: render uses compiled firewall includes and clears generated ACL includes. Legacy ACL settings remain on disk but no longer drive nginx until the firewall file is removed.

## Operator API

| Method | Path | Role |
|--------|------|------|
| `GET`/`PUT`/`DELETE` | `/api/firewall` | Load / save / clear rules (Save applies) |
| `GET` | `/api/firewall/export` | Serializable document (no `source`) |
| `POST` | `/api/firewall/import` | Validate + save + apply |
| `GET` | `/api/firewall/services` | Dropdown: `any` + eligible Apps |

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
    }
  ]
}
```

Related: flat ACL UI/API remains under `/api/acl/*` and [`docs/serve-acl.md`](serve-acl.md). Epic [#207](https://github.com/danielnachumdev/raft/issues/207), delivery [#211](https://github.com/danielnachumdev/raft/issues/211).
