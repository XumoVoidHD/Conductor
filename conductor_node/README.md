# Conductor Node

Shared builder service on one host. Consumes **Redis commands**, spawns **trading node** subprocesses.

## Model

The deploy command is **complete**. Conductor does not invent broker fields or allocate
IBKR client ids. It validates the envelope, writes bootstrap JSON, and starts the process.
Broker-specific validation lives in `trading_node/brokers/{adapter}.py`.

## Standardized deploy command

```json
{
  "command": "deploy",
  "correlation_id": "uuid",
  "user_id": "alice",
  "node_id": "optional",
  "payload": {
    "broker": {
      "adapter": "interactive_brokers",
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

### `interactive_brokers` config (required fields)

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

## Run

```bash
pip install redis
python -m conductor_node
```

```bash
python scripts/send_conductor_command.py deploy --user-id alice
python scripts/send_conductor_command.py events
```

Control a deployed node (use `control_port` from the deploy event):

```bash
python control.py run
```

**stop** — `user_id`, `node_id`  
**list** — `user_id`  

Events go to `conductor:events`.
