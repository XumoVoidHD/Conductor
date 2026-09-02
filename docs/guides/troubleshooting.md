# Troubleshooting

---

## Stack won’t start

- Confirm compose file: `conductor-core/docker-compose.yml`  
- `docker compose … ps` — postgres/redis healthy before backend  
- Migrations: `docker compose -f conductor-core/docker-compose.yml run --rm backend alembic upgrade head`
- If host port **5432** is busy, set `POSTGRES_PORT=5433` (or another free port) in `.env`

---

## Login / CORS / “failed to fetch”

| Context | Fix |
|---------|-----|
| **`npm run dev`** | Backend must run on **8000**; Vite proxies `/api` — no `VITE_API_BASE` needed |
| **Docker frontend** | Build with `VITE_API_BASE=http://127.0.0.1:8000`; `CORS_ORIGINS` must include `http://127.0.0.1:5500` |
| **Vite on another port** (e.g. 5501) | Add that origin to `CORS_ORIGINS` if not using the dev proxy |
| **Stale assets** | Hard-refresh after frontend Docker rebuild (`Ctrl+Shift+R`) |

See [Frontend (Vite + React)](../developers/frontend.md).

---

## Deploy fails

| Message | Fix |
|---------|-----|
| Trading node limit | Delete a node (stop is not enough) |
| Bybit credentials missing | Set `BYBIT_TESTNET_*` in `.env`, recreate backend |
| Timed out waiting for Conductor | Start/recreate `conductor`; check Redis URL |
| docker run / port allocated | Rebuild Conductor with unique port allocator; remove stale containers |

---

## Node stuck / ghost rows

- Command on missing container → should soft-delete and free quota  
- After Conductor restart, DB still lists nodes but live registry is empty → redeploy or delete ghosts  
- `docker ps -f label=conductor.role=trading-node`

---

## Trades empty or stale

- Nodes stopped → no live positions/orders  
- Old trading-node image → redeploy after `trading-node` image rebuild  
- Backend must share `conductor-net` with nodes  
- Dashboard polls every ~15s — use **Refresh** or wait for next cycle

---

## Log stream won’t connect

- Backend needs Docker socket mount for `docker logs -f` (see compose `conductor` / `backend` volumes)  
- WebSocket URL: `ws://<api>/api/v1/dashboard/nodes/{node_id}/logs/stream?token=...`  
- In dev, open the app via Vite so the WS proxies to the backend

---

## Logs (CLI)

```bash
docker logs conductor-backend
docker logs conductor-orchestrator
docker logs conductor-tn-........
```
