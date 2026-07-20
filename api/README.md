# Conductor API

Self-contained FastAPI authentication service for the Conductor platform.

## Layout

```
api/
├── app/                 # FastAPI application package
│   ├── api/v1/          # HTTP routes
│   ├── core/            # config, security, database, logging
│   ├── db/models/       # SQLAlchemy models
│   ├── schemas/         # Pydantic request/response
│   ├── services/        # business logic
│   ├── repositories/    # DB access
│   └── main.py
├── alembic/             # DB migrations
├── alembic.ini
├── docker-compose.yml   # Postgres for this API only
├── Dockerfile           # optional API container
├── requirements.txt
├── .env.example
└── README.md
```

Static UI for registration lives in the sibling `../frontend/` folder.

## Bruno (API collection)

Request docs / examples are maintained as a Bruno collection in `bruno/`.

1. Open Bruno → **Open Collection** → `api/bruno`
2. Select environment **Local**
3. Run **Health** or **Register** against a running API

See `bruno/README.md` for conventions when adding new endpoints.

## Quick start (from `api/`)

```powershell
cd api

# 1. Copy env
copy .env.example .env

# 2. Start Postgres (API-owned compose)
docker compose up -d postgres

# 3. Install deps
pip install -r requirements.txt

# 4. Migrate
alembic upgrade head

# 5. Run API locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

## Register

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"vedansh\",\"email\":\"vedansh@example.com\",\"password\":\"Password@123\"}"
```

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.0 + Alembic
- PostgreSQL (this folder's Docker Compose)
- Passlib (Argon2) + Python-JOSE (JWT helpers for login later)
