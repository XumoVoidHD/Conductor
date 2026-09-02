# Frontend (Vite + React)

The dashboard lives in `frontend/`. Legacy vanilla HTML/JS is kept under `frontend/legacy/` for reference only.

---

## Stack

| Layer | Choice |
|-------|--------|
| Build | Vite 7 |
| UI | React 19 + TypeScript |
| Styling | Tailwind CSS 3 (glassmorphism panels, black + green theme) |
| Data | TanStack Query (polling) |
| Components | Radix UI primitives, Lucide icons, Sonner toasts |
| Auth | React context + JWT in `localStorage` |

---

## Commands

```bash
cd frontend
npm install
cp .env.example .env    # optional for production builds
npm run dev             # dev server (default port 5500)
npm run build           # dist/ for nginx Docker image
```

---

## API URL and CORS

### Local dev (`npm run dev`)

The Vite dev server **proxies** `/api` to `http://127.0.0.1:8000` (including WebSocket log streams). The app uses **relative** API URLs in dev — no CORS setup required as long as the backend is up on port 8000.

If port 5500 is taken, Vite picks the next free port (e.g. 5501). The proxy still works on that port.

### Docker / production build

Set `VITE_API_BASE` at **build time** (see `frontend/Dockerfile` and `frontend/.env.example`):

```env
VITE_API_BASE=http://127.0.0.1:8000
```

`CORS_ORIGINS` on the backend must include the origin users open in the browser (e.g. `http://127.0.0.1:5500`).

---

## Project layout

```text
frontend/
├── src/
│   ├── pages/
│   │   ├── AuthPage.tsx          # Login / register
│   │   └── DashboardPage.tsx     # Strategies, nodes, trades
│   ├── components/
│   │   ├── layout/               # App shell, mode switcher, ambient bg
│   │   ├── ui/                   # Button, card, table, tabs, …
│   │   └── LogDialog.tsx         # WebSocket log stream
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth-context.tsx
│   │   └── trading-mode-context.tsx
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css                 # Design tokens + glass utilities
├── Dockerfile                    # npm build → nginx :5500
├── vite.config.ts
└── legacy/                       # Old static UI
```

---

## Conventions

- **Polling:** nodes ~10s, strategies/trades ~15s — adjust in `DashboardPage.tsx` query `refetchInterval`.
- **Toasts:** use `sonner`; match success/error patterns already in node actions and deploy.
- **Filters:** node/broker filters are client-side on cached API responses (no extra round-trip).
- **Trading mode:** `useTradingMode()` — not wired to API yet; see [Trading modes](../guides/trading-modes.md).

---

## Docker rebuild

```bash
docker compose -f conductor-core/docker-compose.yml build frontend
docker compose -f conductor-core/docker-compose.yml up -d --force-recreate frontend
```

---

## See also

- [Dashboard UI](../guides/dashboard.md)
- [Local development tips](local-dev.md)
- [Troubleshooting](../guides/troubleshooting.md)
