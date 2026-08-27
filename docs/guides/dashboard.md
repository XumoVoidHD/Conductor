# Dashboard UI

Static frontend at http://127.0.0.1:5500 (`frontend/`).

---

## Sections

1. **Strategies** — vault cards; **Deploy** disabled when quota is full  
2. **Nodes** — lifecycle table + quota `used / max`  
3. **Traders** — live summaries (trader id, strategy state, open pos/orders, reachable)

Shared **filters** (node, broker) sit above Nodes and apply to both Nodes and Traders **without** re-calling the API.

---

## Behavior worth knowing

| Behavior | Detail |
|----------|--------|
| Toasts | Top-right; green deploy/run, yellow stop/restart, red delete/errors; auto-dismiss ~3.5s |
| Optimistic status | Starting / Stopping / Restarting / Deleting until refresh |
| Node poll | ~10s |
| Traders poll | ~15s |
| Gone node | Command returns `410` / `node_gone` → toast + row removed + quota updates |

API base: `frontend/config.js` → `http://127.0.0.1:8000` (must match `CORS_ORIGINS`).

Halt exists on the API but is not in the UI yet.
