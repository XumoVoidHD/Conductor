# Troubleshooting

---

## Stack won’t start

- Confirm compose file: `conductor-core/docker-compose.yml`  
- `docker compose … ps` — postgres/redis healthy before backend  
- Migrations: `docker compose -f conductor-core/docker-compose.yml run --rm backend alembic upgrade head`

---

## Login / CORS

- Frontend must call `http://127.0.0.1:8000` (see `frontend/config.js`)  
- `CORS_ORIGINS` must include `http://127.0.0.1:5500`  
- Hard-refresh after frontend rebuild (`app.js?v=…` cache bust)

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

## Traders all offline

- Nodes stopped → expected offline stubs  
- Old trading-node image → summary falls back to snapshot; if both fail, check host/port in DB  
- Backend must share `conductor-net` with nodes  

---

## Logs

```bash
docker logs conductor-backend
docker logs conductor-orchestrator
docker logs conductor-tn-........
```
