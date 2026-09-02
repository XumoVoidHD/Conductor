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
| `docs/` | GitBook source |

---

## Typical loop

1. `docker compose -f conductor-core/docker-compose.yml up -d --build`  
2. Migrate if needed: `… run --rm backend alembic upgrade head`  
3. Edit backend / conductor with bind mounts where compose allows  
4. Frontend dev: `cd frontend && npm run dev` (hot reload on :5500)  
5. Rebuild trading-node image after runtime/TCP changes  
6. Hit Bruno or http://127.0.0.1:5500  

---

## Hot tips

- **Frontend:** production build via Docker or `npm run build`; legacy vanilla UI in `frontend/legacy/`  
- **Conductor code:** recreate `conductor` service after orchestrator changes  
- **Port allocator:** unique host ports require Conductor rebuild; delete old nodes if stuck  
- **Quota ghosts:** soft-delete via API delete or gone-node path  

---

## Tests & quality

Prefer Bruno for end-to-end paths. Add unit tests next to the service you change when logic is non-trivial (quota, gone-node, summary fallback).

---

## Docs

Edit Markdown under `docs/`. Update `docs/SUMMARY.md` when adding pages. GitBook syncs from the linked repo (see `.gitbook.yaml` → `root: ./docs`).
