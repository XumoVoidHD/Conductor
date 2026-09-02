# Dashboard UI

Modern React dashboard at **http://127.0.0.1:5500** (`frontend/` — Vite + React + Tailwind).

Visual style: **minimal dark theme** (black + green accent) with **glassmorphism** panels (frosted blur, subtle borders) on the authenticated dashboard.

---

## Header

| Element | Purpose |
|---------|---------|
| Logo + section nav | Jump to Strategies / Nodes / Trades anchors |
| **Mode switcher** | Oval tabs: **Live** · **Paper** · **Backtest** (UI scaffold — see [Trading modes](trading-modes.md)) |
| Status badge | Redis connectivity |
| User chip + Sign out | Session |

---

## Sections

1. **Overview stats** — node quota, strategy count, open positions, filtered node count  
2. **Strategies** — vault cards; **Deploy worker** disabled when quota is full  
3. **Nodes** — lifecycle table + quota `used / max` + **Logs** (WebSocket stream)  
4. **Trades** — Positions / Orders / Fills tabs (aggregated across nodes via `GET /dashboard/trades`)

Shared **filters** (node, broker) on the Nodes panel apply to Nodes and Trades **without** re-calling the API.

The legacy **Traders** panel was removed from the UI; trader summaries remain on the API (`GET /dashboard/traders`) — see [Traders panel](traders.md).

---

## Behavior worth knowing

| Behavior | Detail |
|----------|--------|
| Toasts | Sonner, top-right; auto-dismiss |
| Optimistic status | Starting / Stopping / Restarting / Deleting until refresh |
| Node poll | ~10s |
| Strategies / trades poll | ~15s |
| Gone node | `410` / `node_gone` → toast + row removed + quota updates |
| Logs | Modal streams **Docker logs** (`docker logs -f` parity) via WebSocket; Redis fallback if Docker unavailable |

---

## Configuration

| Setting | Where |
|---------|--------|
| API base (production) | `frontend/.env` → `VITE_API_BASE` (default `http://127.0.0.1:8000`) |
| CORS | Backend `CORS_ORIGINS` must include the browser origin |
| Dev proxy | `vite.config.ts` proxies `/api` → backend :8000 |

**Local dev:** `cd frontend && npm install && npm run dev`

Full frontend notes: [Frontend (Vite + React)](../developers/frontend.md).

Halt exists on the API but is not exposed as a button in the UI yet.
