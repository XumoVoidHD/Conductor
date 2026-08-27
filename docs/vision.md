# Project vision

What we are building, why, and what we deliberately refuse to build.

**Runtime foundation:** [Nautilus Trader](https://nautilus.trader/). Conductor is a control layer **around** Nautilus — not a replacement and not a new trading framework.

---

## The product

**Conductor** is a hosted control platform for **running your own Nautilus strategies** on live (or paper) workers.

Each account gets:

- A **strategy vault** — Nautilus strategy entrypoints and configs (code the user owns), plus shared SYSTEM examples
- **Trading nodes** — long-running workers connected to a broker, capped by a per-account quota
- A **UI / API** to deploy, run, stop, restart, delete, and inspect workers

The goal is **simplicity**: run standard Nautilus strategies remotely without building infrastructure from scratch. We orchestrate workers; Nautilus does the trading.

---

## What Conductor offers

- Deploy and manage **Nautilus `TradingNode` workers** (subprocess for local dev, Docker for the default stack)
- Connect workers to **Nautilus-supported brokers** we choose to operate and test
- A **private broker vault** per user (target) — API keys / login secrets for each supported exchange
- **Start, stop, restart, delete** workers; **run / halt** the strategy inside a running worker
- **Configuration** via Nautilus `StrategyConfig` (JSON-serializable) at deploy time
- **Per-user isolation** — vault, nodes, and (soon) credentials scoped to the account
- **Quota** — `users.trading_nodes` slots; a **stopped** node still occupies a slot until **deleted**

---

## What Conductor deliberately does not offer

| Non-goal | Why |
|----------|-----|
| Strategy builder / no-code designer | Users write normal Nautilus `Strategy` subclasses |
| Universal instrument catalog | Instruments come from the broker adapter Nautilus ships |
| Custom order engine or data models | If Nautilus can do it inside a `TradingNode`, we expose it; we don’t invent a parallel stack |
| Broad broker support | Only adapters we are willing to operate and test |
| Full artifact registry (devpi/commit) | Vault is storage + metadata, not a packaging platform |
| Shared platform broker keys (target) | Each user brings their own credentials |

---

## Strategy vault

The vault stores **runnable** strategy identity:

- Entrypoint — e.g. `strategies.ema_cross` + class / config class
- Default `StrategyConfig` values
- Artifact location — `source_url` + `source_path` (`local://`, `s3://`, `gs://`)

On deploy, the API resolves the vault row → builds a **complete** Conductor deploy payload (broker + strategy fully specified). Conductor does not invent broker fields.

**Today:** Postgres vault with SYSTEM seeds (`running_ping`, `hello_bars`, `ema_cross`), user-owned register-from-file, and share via `strategy_access`.

**Still open:** zip/package upload, strategy versioning.

---

## Brokers

Small, fixed set of mature Nautilus live adapters.

| Phase | Broker | Credential model |
|-------|--------|------------------|
| **Now (dev)** | Bybit testnet | Temporary: shared server `.env`. Target: per-user broker vault |
| Most API-key exchanges | e.g. Bybit live | Private broker vault — keys injected into deploy only |
| **IBKR** | Interactive Brokers | Vault holds IB user/pass + paper/live. Conductor starts a **dockerized IB Gateway** (Nautilus `DockerizedIBGateway` / `ghcr.io/gnzsnz/ib-gateway`). The trading node talks to that container on `conductor-net` — not a shared host TWS |

### Why IBKR is special

API-key brokers only need secrets in the worker process. IBKR requires a running **TWS / IB Gateway**. Conductor treats that Gateway as a **companion container** tied to the node lifecycle, matching how Nautilus itself supports dockerized Gateway for automation.

---

## Two layers of control

| Layer | Question |
|-------|----------|
| **Node orchestration** | Should this container/process exist? Bootstrap, credentials, control port? Stop vs delete? |
| **In-node control** | Inside a running worker, should this strategy start, stop, or reset? |

That split is intentional: Docker lifecycle and Nautilus strategy lifecycle are different problems. Mixing them into one “stop” button that sometimes deletes and sometimes halts is how operators lose money and slots.

---

## Success criterion

Conductor succeeds when a user can put Nautilus strategies in a vault, store their own broker credentials, deploy a worker from the UI within their quota (IBKR spinning up a dockerized Gateway when needed), start and stop it remotely, inspect live state when they need it, and trust ownership because lifecycle is durable — without SSH, without a custom strategy framework, and without brokers Nautilus does not already support.

---

## Related

- [Architecture](architecture/architecture.md) — components and wire paths
- [Status & roadmap](status-and-roadmap.md) — done vs planned
- [Control vs observe](concepts/control-vs-observe.md) — why live positions don’t go through Conductor
