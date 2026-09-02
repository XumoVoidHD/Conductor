# Dashboard UI

React dashboard at http://127.0.0.1:5500 (`frontend/` — Vite + React + Tailwind).

---

## Sections

1. **Strategies** — vault cards; **Deploy** disabled when quota is full  
2. **Nodes** — lifecycle table + quota `used / max` + log streaming  
3. **Trades** — Positions / Orders / Fills tabs (aggregated across nodes)

Shared **filters** (node, broker) sit above Nodes and apply to Nodes and Trades **without** re-calling the API.

---

## Behavior worth knowing

| Behavior | Detail |
|----------|--------|
| Toasts | Sonner top-right; success/warning/error; auto-dismiss |
| Optimistic status | Starting / Stopping / Restarting / Deleting until refresh |
| Node poll | ~10s |
| Trades poll | ~15s |
| Gone node | Command returns `410` / `node_gone` → toast + row removed + quota updates |
| Logs | Modal streams Docker logs (or Redis fallback) via WebSocket |

API base: `VITE_API_BASE` in `frontend/.env` (default `http://127.0.0.1:8000`; must match `CORS_ORIGINS`).

**Dev:** `cd frontend && npm install && npm run dev`

Halt exists on the API but is not in the UI yet.
