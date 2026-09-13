# Mailu-shaped example (HTTP admin + host-published mail ports)

Illustrative App manifest for a mail stack. Mail ports use `expose: host`
so the app publishes them directly (recommended for client-IP accuracy).
TLS for the web UI is opt-in via `tls: origin`.

Operator settings need matching `edge:` listeners only for ports the **gate**
publishes. Host-exposed ports skip the gate.

```bash
# Optional: declare nothing extra in edge: for host-only mail ports.
# For gate stream proxy instead, set edge.streams and use expose: stream.
raft apply --file examples/mailu/.raft/app.yaml
# Install PEMs because tls: origin
# ~/.raft/certs/mailu/origin.{pem,key}
raft up
# After changing edge: published ports:
raft gate recreate
```
