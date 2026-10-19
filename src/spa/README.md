# Dashboard SPA

Source for the `raft serve` UI (React + Vite + TypeScript).

**Runtime is static only.** `npm run build` writes into [`src/raft/core/platform/share/serve/spa/`](../raft/core/platform/share/serve/spa/), which FastAPI serves from the same process as `/api/status` and `/api/metrics`. There is no separate Node server in production. Trends charts poll `/api/metrics` (Resources) or `/api/metrics/http` (HTTP edge) with a `since` cursor — no WebSocket.

**Status freshness:** the dashboard polls `GET /api/status` every `STATUS_POLL_MS` (**2s**) while the tab is visible. The API re-reads applied Apps from `state/apps/` on each request, so CLI/CI apply/update/delete (including no-port workers) appears within about one poll interval without restarting `raft serve` or hard-refreshing the browser.

Source layout under `src/`: `main.tsx` + `styles.css`, which only imports the global design system from `styles/` (`tokens`, `base`, `buttons`, `forms`, `surfaces`); each UI component imports a co-located `ComponentName.css` for layout only. Use the shared primitives instead of restyling controls per feature: buttons `.btn` (+ `.btn-primary`, `.btn-danger`, `.btn-ghost`, `.btn-sm`; `.refresh` / `.action-btn` are legacy aliases), fields `.field` (stacked) / `.field-caps` (toolbar caps label) / `.check` (inline checkbox), surfaces `.panel`, `.toolbar`, `.callout-*`, `.chip-*`, `.empty-state`. Native inputs/selects/checkboxes are themed by zero-specificity defaults in `styles/forms.css`. Dialogs use `chrome/Modal` / `ConfirmPopup` (never `window.confirm`). Feature folders: `shell/` (`AppShell` top bar + `PageHeader` used by every route), `shared/api/` (eager package surface), `chrome/` (toast, modal, stat tiles), `status/` (+ `model/`), `service/`, `logs/` (+ `model/`), `export/`, `deploy/` (`github/`, `oauth/`, `model/`), `notifications/`, and `trends/` with `panel/`, `chart/`, `runtime/`, `range/`, and `strategies/` (metric type + resource/HTTP catalogs next to root registries). SPA unit tests under `test/` mirror those folders; shared arrange helpers live in `test/fixtures.ts`.

## Develop

```bash
cd src/spa
npm ci
npm run dev          # Vite on :5173; proxies /api → raft serve :8787
```

In another terminal: `raft serve` (or `uv run raft serve`). For editable installs, bake once so the packaged path has assets:

```bash
cd src/spa && npm ci && npm run build
```

## Ship FE changes

Change **`src/spa/` only**. Do **not** commit hashed files under `share/serve/spa/` (gitignored; `.gitkeep` keeps the directory).

Operators get the UI from the **Release wheel** (bake happens in the Release job — see [`docs/releases.md`](../../docs/releases.md)). PR CI builds the SPA for tests; a failed bake/build on Release publish fails the release.

Local packaging / `raft serve` in a checkout still needs `npm run build` into the share path before you exercise the packaged UI.
