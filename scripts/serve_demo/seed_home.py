"""Fabricate a PII-safe demo data home for ``raft serve`` screenshots.

Usage: python3 scripts/serve_demo/seed_home.py /tmp/raft-demo/home

Writes demo Apps (``demo-*``), settings with notification channels, an ordered
firewall, alert rules, an ops event timeline, 3h of metrics JSONL, and a gate
access log. Only documentation hosts/CIDRs (``*.demo.example``, RFC 5737).
"""

import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit("usage: seed_home.py DATA_HOME")
home = Path(sys.argv[1]).expanduser().resolve()
if home == (Path.home() / ".raft").resolve():
    sys.exit("refusing to seed the real ~/.raft; pass a throwaway directory")
random.seed(7)
now = datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def write(path, text):
    p = home / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


APPS = {
    "demo-api": ("shop", "api.demo.example", 8080, ["demo-db"]),
    "demo-web": ("shop", "www.demo.example", 3000, ["demo-api"]),
    "demo-db": ("shop", None, 5432, []),
    "demo-worker": (None, None, None, []),
    "demo-docs": (None, "docs.demo.example", 80, []),
}
for name, (group, host, port, deps) in APPS.items():
    lines = ["apiVersion: raft/v1", "kind: App", "metadata:", f"  name: {name}"]
    lines += ["spec:"] + ([f"  group: {group}"] if group else []) + [ "  source: docker", f"  image: ghcr.io/example/{name}", "  ref: latest", "  tls: off"]
    if host:
        lines.append(f"  publicHost: {host}")
    if deps:
        lines.append("  dependsOn: [" + ", ".join(deps) + "]")
    if port is None:
        lines += ["  ports: []", "  readiness:", "    type: none"]
    else:
        expose = "http" if host else "none"
        lines += ["  ports:", "    - name: main", f"      containerPort: {port}", f"      expose: {expose}"]
    if name == "demo-docs":
        lines += ["  scaling:", "    idleSeconds: 300", "    minUpSeconds: 60"]
    write(f"state/apps/{name}.yaml", "\n".join(lines) + "\n")

write(
    "settings.yaml",
    """logging:
  dir: logs
  file: raft.log
  level: INFO
edge:
  http: 80
  https: 443
  streams: []
healing:
  enabled: false
  intervalSeconds: 15
metrics:
  intervalSeconds: 60
serviceLogs:
  enabled: true
  includeEdge: true
acme:
  email: ops@example.com
  challenge: http-01
github:
  sessionTtlSeconds: 3600
notifications:
  enabled: true
  channels:
    - id: ops-primary
      enabled: true
      type: whatsapp
      settings:
        apiUrl: https://api.green-api.com
        idInstance: "1101000001"
        apiTokenInstance: "replace-me"
        chatId: 79001234567@c.us
    - id: ops-backup
      enabled: false
      type: whatsapp
      settings:
        apiUrl: https://api.green-api.com
        idInstance: "1101000002"
        apiTokenInstance: "replace-me"
        chatId: 79007654321@c.us
alerts:
  enabled: true
  intervalSeconds: 60
acl:
  gate:
    mode: "off"
    entries: []
""",
)

write(
    "state/firewall/rules.yaml",
    """version: 1
rules:
  - {id: r1, cidr: 192.0.2.0/24, port: any, protocol: tcp, service: any, action: permit}
  - {id: r2, cidr: 198.51.100.7/32, port: 80, protocol: http, service: demo-api, action: deny}
  - {id: r3, cidr: 203.0.113.0/24, port: any, protocol: tcp, service: any, action: drop}
  - {id: r4, cidr: 0.0.0.0/0, port: 80, protocol: tcp, service: any, action: permit}
""",
)

write(
    "state/alerts/rules.yaml",
    """version: 1
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
  - id: demo-worker-cpu
    name: demo-worker CPU high
    severity: warning
    description: Worker CPU above 80% for 10 minutes.
    for: 10m
    cooldown: 30m
    notifyOnRecovery: false
    channelIds: []
    condition:
      signal: metrics.resources
      select: {target: demo-worker, metric: cpu_percent}
      kind: threshold
      params: {aggregate: avg, window: 10m, op: gt, value: 80}
""",
)

# --- ops + graph events -------------------------------------------------
events = [
    (180, "deploy.apply", "shop-demo-api", "Applied demo-api (ref latest)", {"action": "apply"}),
    (150, "firewall.apply", None, "Firewall saved: 4 rules", {}),
    (149, "gate.reload", None, "Gate nginx reloaded", {}),
    (120, "deploy.redeploy", "shop-demo-web", "Redeployed demo-web", {"action": "redeploy"}),
    (95, "scale.idle_stop", "demo-docs", "demo-docs scaled to zero after 300s idle", {}),
    (40, "scale.wake", "demo-docs", "demo-docs woke on request", {}),
    (26, "alert.fired", "shop-demo-api", "demo-api 5xx error rate firing (7.4%)", {"severity": "error"}),
    (18, "alert.resolved", "shop-demo-api", "demo-api 5xx error rate resolved", {}),
    (12, "service.stop", "demo-worker", "Stopped demo-worker", {}),
    (11, "service.start", "demo-worker", "Started demo-worker", {}),
    (3, "stack.purge", None, "Purged unused images (1.2 GB reclaimed)", {}),
]
ops = []
for i, (mins, kind, svc, summary, meta) in enumerate(events):
    row = {"id": f"ev{i}", "kind": kind, "ts": iso(now - timedelta(minutes=mins)), "summary": summary}
    if svc:
        row["service"] = svc
    if meta:
        row["metadata"] = meta
    ops.append(json.dumps(row))
write("state/events/ops.jsonl", "\n".join(ops) + "\n")

# --- metrics ------------------------------------------------------------
step = timedelta(seconds=30)
n = int(3 * 3600 / 30)
SERVICES = [("shop-demo-api", "shop"), ("shop-demo-web", "shop"), ("shop-demo-db", "shop"), ("demo-worker", None)]
net = {s: [0.0, 0.0] for s, _ in SERVICES}


def wave(i, period, lo, hi, phase=0.0):
    return lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * i / period + phase))


def incident(i):
    return math.exp(-((i - (n - 50)) ** 2) / 30.0)


res, http = [], []
for i in range(n):
    ts = iso(now - (n - 1 - i) * step)
    inc = incident(i)
    cpu = {
        "shop-demo-api": wave(i, 120, 18, 38) + 45 * inc + random.uniform(-2, 2),
        "shop-demo-web": wave(i, 90, 6, 14, 1.0) + random.uniform(-1, 1),
        "shop-demo-db": wave(i, 70, 4, 9, 0.5) + random.uniform(-1, 1),
        "demo-worker": wave(i, 40, 35, 70, 2.0) + random.uniform(-3, 3),
    }
    rps = {"shop-demo-api": wave(i, 160, 10, 22) + random.uniform(-1, 1), "shop-demo-web": wave(i, 160, 28, 46, 0.4)}
    containers = []
    for svc, group in SERVICES:
        rx = (rps.get(svc, 2) * 2400 + random.uniform(0, 800)) * 30
        net[svc][0] += rx
        net[svc][1] += rx * 1.4
        mem = 30 + 20 * (hash(svc) % 3) / 3 + 5 * inc
        containers.append({
            "service": svc, "group": group, "role": "app",
            "cpu_percent": round(max(0.5, cpu[svc]), 2),
            "memory": {"used_percent": round(mem, 2), "used_bytes": int(mem / 100 * 512 * 1024**2), "limit_bytes": 512 * 1024**2},
            "uptime_seconds": 7200 + i * 30, "pids": 12 + (i % 7),
            "network": {"rx_bytes": int(net[svc][0]), "tx_bytes": int(net[svc][1])},
            "block_io": {"read_bytes": i * 12288, "write_bytes": i * 36864},
        })
    res.append({"ts": ts, "host": {"loadavg": [round(1.2 + 0.6 * inc, 2), 1.0, 0.9], "cpus": 4,
                "memory": {"used_percent": 61.0 + 3 * inc, "used_bytes": 5 * 1024**3}}, "containers": containers})
    by = {}
    for svc in ("shop-demo-api", "shop-demo-web"):
        base = 140 if svc == "shop-demo-api" else 45
        p95 = base + wave(i, 80, 0, base * 0.4) + (650 * inc if svc == "shop-demo-api" else 0)
        reqs = rps[svc] * 30
        by[svc] = {"rps": round(rps[svc], 2), "requests": int(reqs),
                   "duration_ms": {"avg": round(p95 * 0.45, 1), "p50": round(p95 * 0.35, 1), "p95": round(p95, 1), "p99": round(p95 * 1.6, 1)},
                   "status_class": {"2xx": int(reqs * 0.95), "3xx": int(reqs * 0.01), "4xx": int(reqs * 0.03),
                                    "5xx": int(40 * inc) if svc == "shop-demo-api" else 0}}
    total = sum(v["rps"] for v in by.values())
    http.append({"ts": ts, "rps": round(total, 2), "requests": int(total * 30), "in_flight": 3 + int(10 * inc),
                 "active_connections": 24, "duration_ms": {"avg": 60, "p50": 40, "p95": 180, "p99": 300},
                 "status_class": {"2xx": int(total * 28), "3xx": 3, "4xx": 12, "5xx": int(40 * inc)}, "by_service": by})
write("state/metrics/resources.jsonl", "".join(json.dumps(r) + "\n" for r in res))
write("state/metrics/http.jsonl", "".join(json.dumps(r) + "\n" for r in http))

# --- scale-to-zero marker (demo-docs idle) --------------------------------
write("state/scaling/demo-docs.json", json.dumps({"scaledToZero": True}) + "\n")

# --- gate access log ----------------------------------------------------
paths = ["/", "/api/orders", "/api/orders/42", "/api/cart", "/health", "/api/login", "/static/app.js"]
ips = ["192.0.2.10", "192.0.2.44", "198.51.100.7", "203.0.113.9", "192.0.2.81"]
lines = []
for k in range(160):
    t = now - timedelta(seconds=(160 - k) * 7)
    status = random.choices([200, 201, 304, 404, 500, 502], [70, 5, 8, 8, 6, 3])[0]
    host = random.choice(["api.demo.example", "www.demo.example"])
    method = random.choice(["GET", "GET", "GET", "POST"])
    lines.append(
        f"{random.uniform(0.003, 0.9):.3f} {status} {host} {t.strftime('%Y-%m-%dT%H:%M:%S+00:00')} "
        f"{method} {random.choice(paths)} {random.choice(ips)} \"Mozilla/5.0 (demo)\""
    )
# Retained history for the scaled-to-zero docs App (operators still inspect these).
for k in range(12):
    t = now - timedelta(minutes=40 + k * 3)
    lines.append(
        f"{random.uniform(0.004, 0.2):.3f} 200 docs.demo.example "
        f"{t.strftime('%Y-%m-%dT%H:%M:%S+00:00')} GET /guide/{k} 192.0.2.10 "
        f"\"Mozilla/5.0 (demo)\""
    )
write("state/metrics/gate-http/access.log", "\n".join(lines) + "\n")
print("demo home at", home)
