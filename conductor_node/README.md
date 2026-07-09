# Conductor Node

Shared orchestrator service. Consumes **Redis commands**, spawns **trading nodes** as subprocesses (local dev) or **Docker containers** (production compose).

## Model

The deploy command is **complete**. Conductor does not invent broker fields or allocate
IBKR client ids. It validates the envelope, writes bootstrap JSON, and starts the runtime.
Broker-specific validation lives in `trading_node/brokers/{adapter}.py`.

## Commands

| Command | Purpose |
|---------|---------|
| `deploy` | Spawn trading node (subprocess or container) |
| `stop` | Destroy trading node |
| `list` | List nodes for `user_id` |
| `run` | Start strategy on a deployed node |
| `halt` | Stop strategy |
| `status` | Strategy state |
| `reset` | Reset strategy (must be halted) |

## Standardized deploy command

```json
{
  "command": "deploy",
  "correlation_id": "uuid",
  "user_id": "alice",
  "node_id": "optional",
  "payload": {
    "broker": {
      "adapter": "bybit",
      "config": { }
    },
    "strategy": {
      "module": "strategies.running_ping",
      "class_name": "RunningPing",
      "config_class": "RunningPingConfig"
    },
    "control_port": 9001
  }
}
```

`broker.config` is **opaque to Conductor**. Shape depends on `adapter`.

### `bybit` config (required fields)

```json
{
  "api_key": "YOUR_TESTNET_API_KEY",
  "api_secret": "YOUR_TESTNET_API_SECRET",
  "environment": "testnet",
  "product_types": ["linear"],
  "instrument_ids": ["BTCUSDT-LINEAR.BYBIT"]
}
```

`environment`: `testnet` | `mainnet` | `demo`  
`product_types`: `spot` | `linear` | `inverse` | `option`

### `interactive_brokers` config (later — needs TWS/Gateway)

```json
{
  "account_id": "DU1234567",
  "ibg_host": "127.0.0.1",
  "ibg_port": 7497,
  "ibg_client_id": 25,
  "load_contracts": [
    {"secType": "STK", "symbol": "AAPL", "exchange": "SMART", "currency": "USD"}
  ]
}
```

Use `ibg_host: host.docker.internal` when trading nodes run in Docker.

## Run locally (subprocess)

```bash
pip install -r requirements-conductor.txt
export CONDUCTOR_NODE_RUNTIME=subprocess
python -m conductor_node
```

```bash
python scripts/send_conductor_command.py deploy --user-id alice
python scripts/send_conductor_command.py run --user-id alice --node-id tn-...
python scripts/send_conductor_command.py events
```

## Run in Docker

```bash
docker compose build trading-node
docker compose up -d redis conductor
```

Deploy with Bybit testnet (set keys in `.env`):

```bash
python scripts/send_conductor_command.py deploy --user-id alice
python scripts/send_conductor_command.py run --user-id alice --node-id tn-...
```

IBKR later: `python scripts/send_conductor_command.py deploy --user-id alice --broker interactive_brokers`

Events go to `conductor:events`.
