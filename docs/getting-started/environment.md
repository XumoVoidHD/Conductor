# Environment variables

Single `.env` at **repo root**. The API loads it via settings (also checks `backend/.env` if present).

---

## Template

```env
# --- PostgreSQL ---
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=conductor
POSTGRES_PASSWORD=conductor
POSTGRES_DB=conductor

# --- API ---
ENVIRONMENT=development
CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
SECRET_KEY=change-me-to-a-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CONDUCTOR_EVENT_TIMEOUT_SEC=20

# --- Bybit (dashboard deploy — temporary shared keys) ---
BYBIT_ENVIRONMENT=testnet
BYBIT_TESTNET_API_KEY=
BYBIT_TESTNET_API_SECRET=
BYBIT_PRODUCT_TYPE=linear
BYBIT_INSTRUMENT_ID=BTCUSDT-LINEAR.BYBIT

# --- Conductor / Redis ---
REDIS_URL=redis://127.0.0.1:6379/0
CONDUCTOR_COMMANDS_KEY=conductor:commands
CONDUCTOR_EVENTS_KEY=conductor:events
CONDUCTOR_NODES_DIR=data/nodes
CONDUCTOR_CONTROL_PORT_BASE=9000
CONDUCTOR_NODE_RUNTIME=subprocess
TRADING_NODE_IMAGE=conductor-trading-node:latest
DOCKER_NETWORK=conductor-net
DOCKER_PUBLISH_CONTROL_PORT=false
```

In compose, backend/conductor typically override hosts to service names (`postgres`, `redis`) and set `CONDUCTOR_NODE_RUNTIME=docker`, `DOCKER_PUBLISH_CONTROL_PORT=true`, `DOCKER_NODES_VOLUME=conductor-nodes`.

---

## Who uses what

| Variable | Used by | Purpose |
|----------|---------|---------|
| `POSTGRES_*` | API | Database |
| `SECRET_KEY` | API | JWT signing |
| `BYBIT_TESTNET_*` | API dashboard | Injected into deploy `broker.config` |
| `REDIS_URL` | API, Conductor, CLI | Control plane |
| `CONDUCTOR_NODE_RUNTIME` | Conductor | `subprocess` or `docker` |
| `CONDUCTOR_CONTROL_PORT_BASE` | Conductor | Port allocator base |
| `CONDUCTOR_EVENT_TIMEOUT_SEC` | API | Wait for Conductor event |
| `DOCKER_*` | Conductor | Network, volume, publish, image |

Never commit real secrets. Per-user broker vault will replace shared Bybit env — see [Broker credentials](../concepts/broker-credentials.md).
