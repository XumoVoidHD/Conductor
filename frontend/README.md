# Conductor Frontend (basic)

Minimal static UI for the Conductor API. Today: **user registration** only.

## Layout

```
frontend/
├── index.html
├── styles.css
├── app.js
├── config.js      # API base URL
└── README.md
```

## Prerequisites

1. API Postgres + migrations + uvicorn running (see `api/README.md`)
2. CORS allows this frontend origin (default includes `:5500` and `:3000`)

## Run

From the `frontend/` folder:

```powershell
cd frontend
python -m http.server 5500
```

Open: http://127.0.0.1:5500

Or open `index.html` via any static server (VS Code Live Server, etc.).

## Config

Edit `config.js` if the API is not on `http://127.0.0.1:8000`:

```js
window.CONDUCTOR_API_BASE = "http://127.0.0.1:8000";
```

If you change the frontend port, add that origin to `CORS_ORIGINS` in `api/.env`.
