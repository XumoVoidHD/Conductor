# Adding a strategy

Strategies live in the **strategy vault** (DB metadata + source on disk/URL), not hard-coded in the API.

---

## What a strategy needs

1. **Slug / id** — stable identifier used in deploy (`strategy_id`)  
2. **Source** — Python module path or URL the node can load  
3. **Access** — owner + optional shared users  
4. **Runtime assumptions** — Nautilus Trader strategy class compatible with `trading_node` bootstrap  

Exact packaging conventions: follow existing entries under the vault path used by register/deploy (see Bruno **Strategies** + `backend` strategy services).

---

## Register (API)

`POST /api/v1/dashboard/strategies/register` with file upload or `source_url` / path fields (see Bruno).

Then share if needed:

`POST /api/v1/dashboard/strategies/{slug}/access`

---

## Deploy

`POST /api/v1/dashboard/deploy` with `{ "strategy_id": "<slug>", "config": {} }`.

Conductor builds/runs a trading-node container with strategy source mounted or fetched, injects broker env (today Bybit from backend settings), allocates a control port, and registers the node.

---

## Config

`config` is strategy-specific JSON. Keep secrets out of config — use vault/env for keys.

---

## Testing

1. Register via Bruno  
2. Deploy under quota  
3. Confirm Nodes row + Traders summary  
4. Run / stop / delete lifecycle  

Document new strategies in the vault README or this docs site if they are first-party examples.
