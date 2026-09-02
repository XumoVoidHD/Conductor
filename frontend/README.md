# Frontend (Vite + React)

```bash
npm install
npm run dev      # http://127.0.0.1:5500 (proxies /api → backend :8000)
npm run build
```

**Local dev:** The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so you don't need CORS setup while developing. Ensure the backend stack is running.

**Production / Docker:** Set API URL via `.env`:

```
VITE_API_BASE=http://127.0.0.1:8000
```

Legacy vanilla UI is in `legacy/`.