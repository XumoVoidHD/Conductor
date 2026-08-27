# Bruno API testing

Preferred way to exercise the API during development.

---

## Setup

1. Open the collection at `backend/bruno/`  
2. Select environment **Local** (`baseUrl=http://127.0.0.1:8000`)  
3. Run **auth/Login** (or Register once) — script saves `accessToken`  
4. Dashboard requests use Bearer auth automatically  

Stack must be up: Postgres (migrated) + Redis + Conductor + backend (+ trading-node image for Docker deploys).

---

## Useful requests

| Folder | Examples |
|--------|----------|
| auth | Register, Login, Me |
| health | Health |
| dashboard | Status, Strategies, Deploy, Nodes, Run/Stop/Halt/Status/Restart/Delete, Snapshot, **List Traders** |

---

## Tips

- Copy `node_id` from Deploy or List Nodes into subsequent bodies.  
- Snapshot accepts `node_id`, `container_name`, or `node`.  
- List Traders returns offline stubs for unreachable nodes — still HTTP 200.
