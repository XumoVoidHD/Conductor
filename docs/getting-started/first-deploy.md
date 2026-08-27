# First deploy

From a running stack ([Quickstart](quickstart.md)), deploy and run a strategy.

---

## Option A — UI

1. Open http://127.0.0.1:5500  
2. Register → Sign in  
3. Under **Strategies**, click **Deploy** on e.g. `running_ping`  
4. Wait until the node shows **Ready** / **Initializing** then Ready  
5. Click **Run**  
6. Open **Traders** for live summary (positions/orders counts, reachable)

Filters (node / broker) apply to both Nodes and Traders without re-fetching.

---

## Option B — Bruno

Collection: `backend/bruno/` · Environment **Local** (`baseUrl=http://127.0.0.1:8000`).

1. **auth/Register** (once)  
2. **auth/Login** — saves `accessToken`  
3. **dashboard/Deploy Strategy** — `strategy_id: running_ping`  
4. Copy `node_id`  
5. **dashboard/Run Node**  
6. Optional: **List Traders**, **Node Snapshot**

---

## What “success” looks like

```bash
docker ps --filter label=conductor.role=trading-node
docker logs conductor-tn-........
```

Node listens on its allocated control port; Conductor and backend reach it as `conductor-{node_id}:{port}` on `conductor-net`.

---

## Common failures

| Symptom | Likely cause |
|---------|----------------|
| Deploy quota error | At `trading_nodes` limit — delete a node |
| Port already allocated | Old bug; ensure Conductor has unique port allocator + rebuild |
| Redis / timeout on deploy | Conductor not running or wrong `REDIS_URL` |
| Bybit credentials missing | Empty `BYBIT_TESTNET_*` in `.env` |
| Traders show offline | Node stopped, or old trading-node image without control; try Run / redeploy |

More: [Troubleshooting](../guides/troubleshooting.md).
