# Bruno — Conductor API

API requests for this service live in this folder as a [Bruno](https://www.usebruno.com/) collection (git-friendly, no cloud sync required).

## Open in Bruno

1. Install Bruno Desktop
2. **Open Collection** → select `api/bruno`
3. Environment → **Local** (`baseUrl` = `http://127.0.0.1:8000`)

## Requests

| Folder | Request | Method | Path |
|--------|---------|--------|------|
| health | Health | GET | `/health` |
| auth | Register | POST | `/api/v1/auth/register` |

## Adding endpoints

When you add a FastAPI route:

1. Create a matching `.bru` file under a tag folder (e.g. `auth/Login.bru`)
2. Use `{{baseUrl}}` for the host
3. Document status codes in the `docs` block
4. Keep body/examples aligned with Pydantic schemas

## Environments

| File | Use |
|------|-----|
| `environments/Local.bru` | Local uvicorn + Postgres |
