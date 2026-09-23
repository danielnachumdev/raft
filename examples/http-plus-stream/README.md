# HTTP + stream (gate L4)

Combines Host-routed HTTP with an `expose: stream` port (SMTP-shaped). The gate
must publish that stream port via `edge.streams` in settings.

## When to use

- You want nginx stream on the gate for a non-HTTP protocol
- You are fine with the gate as the public listener (vs `expose: host`)

For mail where client IP accuracy matters, prefer
[`../host-published-ports/`](../host-published-ports/) instead.

## Operator settings

Uncomment / add in `~/.raft/settings.yaml`, then recreate the gate:

```yaml
edge:
  http: 80
  https: 443
  streams:
    - name: smtp
      port: 25
      protocol: tcp
```

```bash
raft gate recreate
```

## Apply (recommended)

```bash
raft apply --file examples/http-plus-stream/.raft/app.yaml
# CI: raft apply --file .raft/app.yaml --ref "$SHA"
raft doctor
```

Deploy is on by default (first boot or cutover). No separate `raft up` needed
after apply unless you used `--no-deploy`.

No Dockerfile here — `source: docker` pulls `image:ref`. Swap to `source: git` +
`build:` if you build on the VPS.
