# Broker credentials

How secrets reach a trading node today — and the intended multi-tenant model.

---

## Today (temporary)

Dashboard Bybit deploys inject API key/secret from the **server `.env`** (`BYBIT_TESTNET_*`). Every user shares the same testnet credentials. That is fine for local demos; it is **not** the long-term product model.

---

## Target: private broker vault

Separate from the **strategy vault**. Each user stores their own profiles:

- Adapter + profile name (e.g. `bybit-testnet`, `bybit-live`)
- Encrypted secret payload
- Never returned in full after save; never shared across users

On deploy, the API resolves `broker_profile_id` (or a default) → builds opaque `broker.config` → Conductor passes it through → trading node broker module interprets it.

**Why opaque config?** Conductor must not grow exchange-specific validation. The trading node’s broker adapters already know Bybit/IBKR shapes. The orchestrator allowlists adapter names only.

---

## API-key brokers vs IBKR

| Kind | What the vault holds | Runtime |
|------|----------------------|---------|
| Bybit (and most others) | API key + secret (+ env) | Trading node connects to exchange APIs directly |
| IBKR | Username, password, paper/live, optional read-only | Conductor starts a **dockerized IB Gateway** (Nautilus pattern / `ghcr.io/gnzsnz/ib-gateway`); node connects to that container on `conductor-net` |

IBKR needs a Gateway process; treating it as a labeled companion container keeps lifecycle aligned with the trading node (stop/delete tears Gateway down too).

---

## Security rules for implementers

1. Never accept raw broker secrets from the browser into logs or Conductor events.
2. Encrypt at rest; mask on list endpoints.
3. Inject secrets only into bootstrap / container env for that node.
4. Prefer short-lived env in the container over writing secrets into world-readable bootstrap files when you refine the design.

Roadmap: [Status & roadmap](../status-and-roadmap.md).
