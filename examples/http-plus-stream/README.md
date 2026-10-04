# HTTP + stream

Host-routed HTTP plus an `expose: stream` port (SMTP-shaped). The gate must publish that stream port via `edge.streams` in settings.

## When to use

- You want the gate to listen for a non-HTTP protocol (`stream {}`)
- You are fine with the gate as the public listener (vs `expose: host`)

When client IP accuracy on mail-like ports matters, prefer [`../host-published-ports/`](../host-published-ports/) instead.

## Settings

Add the stream listener in `~/.raft/settings.yaml`, then recreate the gate:

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

## Apply

```bash
raft apply --file examples/http-plus-stream/.raft/app.yaml --ref "$SHA"
raft doctor
```

This sample uses `source: docker` (pull `image:ref`). Swap to `source: git` + `build:` if you build on the host.
