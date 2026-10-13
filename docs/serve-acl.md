# Serve access control (IP/CIDR ACL)

> **Superseded long-term by ordered firewall (#211).** See [`docs/serve-firewall.md`](serve-firewall.md). Flat ACL still works until a firewall document is saved under `state/firewall/rules.yaml`.

`raft serve` can manage **whitelist** or **blacklist** rules for:

- **Gate (edge-wide)** — Settings → **Firewall** (`/settings/edge-access`) — legacy panel below the ordered table
- **Per-App** — service detail → **Access control** (Host-routed HTTP Apps only)

## Design (v1)

| Decision | Choice |
|----------|--------|
| Enforcement | **Gate nginx** (`$remote_addr` is the real client; router sees the gate) |
| Match | Client **IP / CIDR** only |
| Modes | One mode per scope: `off` \| `whitelist` \| `blacklist` |
| Host override | Active **App ACL replaces gate** for that Host; otherwise the Host inherits gate |
| Persist | Gate → `~/.raft/settings.yaml` `acl.gate`; Apps → `~/.raft/state/acl/apps/<name>.json` |
| Apply | `raft render` + **gate nginx reload** (not `gate recreate`) |
| Deny UX | HTTP **403** + product `forbidden.html` |

### Supported Apps

- **Supported:** `expose: http` + `publicHost` (including TLS origin/acme and scaling Host servers).
- **Out of scope / rejected with Fix CTA:** `stream`, `host`, `none`, worker Apps (no HTTP Host), and edge services other than configuring **gate** ACL.

## Operator API

| Method | Path | Role |
|--------|------|------|
| `GET`/`PUT`/`DELETE` | `/api/acl/gate` | Gate policy |
| `GET`/`PUT`/`DELETE` | `/api/acl/apps/{name}` | Per-App policy |
| `GET` | `/api/acl/apps/{name}/meta` | Eligibility for the SPA |

Example gate body:

```json
{
  "mode": "whitelist",
  "entries": [
    { "id": "lab", "cidr": "192.0.2.0/24", "comment": "TEST-NET" }
  ]
}
```

## Settings sketch

```yaml
# ~/.raft/settings.yaml
acl:
  gate:
    mode: whitelist          # off | whitelist | blacklist
    entries:
      - id: lab
        cidr: 192.0.2.0/24
        comment: TEST-NET
```
