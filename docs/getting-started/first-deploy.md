# First deploy

From a running stack ([Quickstart](quickstart.md)), deploy and run a strategy.

---

## Option A — UI

1. Open http://127.0.0.1:5500 (or the port shown by `npm run dev` if developing locally)
2. Register → Sign in
3. (Optional) Use the header mode switcher — **Live** / **Paper** / **Backtest**. Today all modes behave the same; see [Trading modes](../guides/trading-modes.md).
4. Under **Strategies**, click **Deploy worker** on e.g. `running_ping`
5. Wait until the node shows **Ready** / **Initializing** then Ready
6. Click **Run**
7. Open **Trades** for positions, orders, and fills; use **Logs** on a node row for live container output

Filters (node / broker) apply to Nodes and Trades without re-fetching.

---

## Option B — Bruno

Collection: `backend/bruno/` · Environment **Local** (`baseUrl=http://127.0.0.1:8000`).

1. **auth/Register** (once)  
2. **auth/Login** — saves `accessToken`  
3. **dashboard/Deploy Strategy** — `strategy_id: running_ping`  
4. Copy `node_id`  
5. **dashboard/Run Node**  
6. Optional: **List Trades**, **List Traders**, **Node Snapshot**

---

## What “success” looks like

```bash
docker ps --filter label=conductor.role=trading-node
docker logs conductor-tn-........
```

Node listens on its allocated control port; Conductor and backend reach it as `conductor-{node_id}:{port}` on `conductor-net`.

You can also tail logs from the dashboard **Logs** button (WebSocket).

---

## Common failures

| Symptom | Likely cause |
|---------|----------------|
| Deploy quota error | At `trading_nodes` limit — delete a node |
| Port already allocated | Old bug; ensure Conductor has unique port allocator + rebuild |
| Redis / timeout on deploy | Conductor not running or wrong `REDIS_URL` |
| Bybit credentials missing | Empty `BYBIT_TESTNET_*` in `.env` |
| Trades empty / offline nodes | Node stopped, or node unreachable — try Run / check logs |
| Login “failed to fetch” | Backend not on :8000; in dev use `npm run dev` (proxy) or set `VITE_API_BASE` + CORS |

More: [Troubleshooting](../guides/troubleshooting.md).
