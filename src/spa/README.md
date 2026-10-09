# Dashboard SPA

Source for the `raft serve` UI (React + Vite + TypeScript).

**Runtime is static only.** `npm run build` writes into [`src/raft/share/serve/spa/`](../raft/share/serve/spa/), which FastAPI serves from the same process as `/api/status` and `/api/metrics`. There is no separate Node server in production. Trends charts poll `/api/metrics` (Resources) or `/api/metrics/http` (HTTP edge) with a `since` cursor — no WebSocket.

**Status freshness:** the dashboard polls `GET /api/status` every `STATUS_POLL_MS` (**2s**) while the tab is visible. The API re-reads applied Apps from `state/apps/` on each request, so CLI/CI apply/update/delete (including no-port workers) appears within about one poll interval without restarting `raft serve` or hard-refreshing the browser.

Source layout under `src/`: `main.tsx` + lean `styles.css` (tokens, resets, shared primitives) at the root; each UI component imports a co-located `ComponentName.css`. Feature folders: `shell/` (`App`, `Dashboard`), `shared/`, `chrome/`, `status/`, `service/`, `logs/`, `export/`, and `trends/` with `panel/`, `chart/`, `runtime/` (plus root range/metrics helpers).

## Develop

```bash
cd src/spa
npm ci
npm run dev          # Vite on :5173; proxies /api → raft serve :8787
```

In another terminal: `raft serve` (or `uv run raft serve`).

## Ship FE changes

```bash
cd src/spa
npm ci
npm run build        # updates ../raft/share/serve/spa/
```

Commit the updated `spa/` assets with the Python package so `uv tool install` / `raft update` ships a working UI without Node on the host.
