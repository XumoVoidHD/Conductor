# Repository layout

Where code lives and what to open when you need to change behavior.

```text
Conductor/
├── docs/                   # GitBook source (this site)
├── .gitbook.yaml
├── cmd.txt                 # Operator command cheat sheet
├── ARCHITECTURE.md         # Legacy mirror — prefer docs/
├── PROJECT_VISION.md       # Legacy mirror — prefer docs/
├── TASKS.md                # Engineering checklist — mirrored in Status & roadmap
├── .env                    # Secrets (not committed)
├── conductor-core/
│   └── docker-compose.yml  # Canonical compose
├── backend/                # FastAPI + Alembic + Bruno
│   ├── app/
│   │   ├── api/v1/         # HTTP routes
│   │   ├── services/       # dashboard_service, conductor_client, node_control_client
│   │   ├── repositories/
│   │   └── db/models/
│   ├── alembic/
│   └── bruno/
├── frontend/               # Vite + React dashboard (legacy static UI in frontend/legacy/)
│   ├── src/pages/          # AuthPage, DashboardPage
│   ├── src/components/     # UI, layout, LogDialog
│   ├── src/lib/            # api, auth-context, trading-mode-context
│   ├── Dockerfile          # nginx :5500
│   └── vite.config.ts      # dev proxy /api → backend
├── conductor_node/         # Orchestrator
│   ├── handlers.py         # Command dispatch
│   ├── deploy.py           # Spawn/stop/restart/delete
│   ├── registry.py         # Ports + RunningNode
│   ├── docker_runtime.py
│   └── control_client.py   # TCP to nodes
├── trading_node/           # Nautilus worker
│   ├── runtime.py          # TCP server + commands
│   ├── snapshot.py         # snapshot + summary builders
│   └── brokers/
├── strategies/             # Example strategies (+ vault seeds)
├── scripts/                # CLI → Redis
├── shared/                 # env loader, artifacts
└── docker/                 # Dockerfiles
```

### Legacy prototypes

`worker.py` / `control.py` — early local TCP worker. Production path is `trading_node/`.

---

## Migrations

| Rev | Purpose |
|-----|---------|
| 001 | users (+ `trading_nodes` quota column) |
| 002 | strategies + strategy_access + seeds |
| 003 | strategy source_url / source_path |
| 004 | durable `trading_nodes` table |

```bash
docker compose -f conductor-core/docker-compose.yml run --rm backend alembic upgrade head
```
