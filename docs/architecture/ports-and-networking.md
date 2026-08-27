# Ports & networking

How control ports are chosen and how containers talk to each other.

---

## Docker network

Compose attaches core services to **`conductor-net`**. Spawned trading nodes join the same network so Conductor and the backend can reach them by **container name** (e.g. `conductor-tn-a1b2c3d4`).

| From | To | How |
|------|----|-----|
| Conductor | Trading node | `control_host` = container name, `control_port` = allocated port |
| Backend (snapshot/traders) | Trading node | Same — backend is on `conductor-net` |
| Browser | Backend | Host published `:8000` |
| Browser | Frontend | Host published `:5500` |

---

## Control port allocation

Implemented in `conductor_node/registry.py` → `allocate_control_port`.

1. Base from `CONDUCTOR_CONTROL_PORT_BASE` (default **9000**).
2. On deploy, take the next free port: 9000, 9001, 9002, …
3. Unique across **all users**.
4. Reserved until **delete** (stopped nodes keep their port).
5. Also skips ports already published by labeled trading-node containers (`host_ports_in_use`).
6. Failed deploy calls `release_control_port`.

Inside the container the process listens on that port (`CONTROL_BIND_HOST=0.0.0.0`). With `DOCKER_PUBLISH_CONTROL_PORT=true` (compose default for Conductor), Docker also maps `host:port → container:port` for host-side debugging.

**Why not one shared 9000?** The second node would fail with “port already allocated”. Unique ports are required for multi-node / multi-user Docker publish.

---

## Important env vars

| Variable | Role |
|----------|------|
| `CONDUCTOR_CONTROL_PORT_BASE` | First candidate port |
| `DOCKER_NETWORK` | Usually `conductor-net` |
| `DOCKER_PUBLISH_CONTROL_PORT` | Publish host ports when true |
| `DOCKER_NODES_VOLUME` | Shared volume for bootstrap files when Conductor runs in Docker |
| `TRADING_NODE_IMAGE` | Image Conductor `docker run`s |

See [Environment variables](../getting-started/environment.md).
