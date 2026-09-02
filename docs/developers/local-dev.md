# Local development

---

## Layout

| Path | Role |
|------|------|
| `conductor-core/docker-compose.yml` | Full stack |
| `backend/` | FastAPI |
| `conductor_node/` | Orchestrator |
| `trading_node/` | Worker image + runtime |
| `frontend/` | Vite + React UI |
| `docs/` | GitBook source (`.gitbook.yaml` → `root: ./docs`) |

---

## Typical loop

1. `docker compose -f conductor-core/docker-compose.yml up -d --build`  
2. Migrate if needed: `… run --rm backend alembic upgrade head`  
3. Edit backend / conductor with bind mounts where compose allows  
4. **Frontend dev:** `cd frontend && npm install && npm run dev` (hot reload; proxies `/api` → :8000)  
5. Rebuild trading-node image after runtime/TCP changes  
6. Hit Bruno or http://127.0.0.1:5500  

---

## Hot tips

- **Frontend:** see [Frontend (Vite + React)](frontend.md); legacy UI in `frontend/legacy/`  
- **Conductor code:** recreate `conductor` service after orchestrator changes  
- **Port allocator:** unique host ports require Conductor rebuild; delete old nodes if stuck  
- **Quota ghosts:** soft-delete via API delete or gone-node path  
- **GitBook:** edit `docs/` + `docs/SUMMARY.md`; push to the repo GitBook syncs from  

---

## Tests & quality

Prefer Bruno for end-to-end paths. Add unit tests next to the service you change when logic is non-trivial (quota, gone-node, summary fallback).

---

## Docs

Edit Markdown under `docs/`. Update `docs/SUMMARY.md` when adding pages. GitBook reads `.gitbook.yaml` at repo root (`structure.summary: SUMMARY.md`).
