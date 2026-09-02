# Trading modes (Live / Paper / Backtest)

The dashboard header includes an oval **mode switcher** with three options:

| Mode | Target use | Backend today |
|------|------------|---------------|
| **Live** | Real broker connectivity (production or testnet keys from server config) | Default path — deploy/run uses live adapters |
| **Paper** | Simulated fills without risking capital | **UI only** — planned: Nautilus **sandbox** / paper adapter profile on deploy |
| **Backtest** | Historical replay and strategy validation | **UI only** — planned: backtest job or dedicated worker profile |

---

## Current behavior

- All three modes render the **same dashboard** (Strategies, Nodes, Trades, logs).
- The selected mode is stored in the browser (`localStorage` key `conductor_trading_mode`) and restored on refresh.
- **No API field** is sent yet — switching modes does not change deploy, broker config, or node runtime.

This is intentional scaffolding: the UI and `useTradingMode()` hook are in place before backend routing.

---

## Planned wiring

### Paper (sandbox)

1. Pass `trading_mode: "paper"` (or equivalent) on `POST /dashboard/deploy`.
2. Conductor sets node env / bootstrap so the trading node uses Nautilus **sandbox** or a paper broker adapter.
3. Optional: separate quota or labeling so paper nodes are visually distinct in the Nodes table.

### Backtest

1. `POST /dashboard/backtest` (or deploy with `mode=backtest`) enqueueing a bounded job.
2. Results surface in a future **Backtest** panel (runs list, equity curve, fills).
3. No long-lived `trading_nodes` row — or ephemeral rows that do not count toward live quota.

### Live

- Unchanged from today: Bybit testnet keys from server `.env`, durable node, TCP control + observe.

---

## Frontend implementation

| Piece | Location |
|-------|----------|
| Mode state + persistence | `frontend/src/lib/trading-mode-context.tsx` |
| Oval switcher UI | `frontend/src/components/layout/trading-mode-switcher.tsx` |
| Provider (dashboard only) | `frontend/src/App.tsx` → `TradingModeProvider` |

When implementing backend support, read `mode` from `useTradingMode()` in deploy mutations and query keys (e.g. separate cache per mode once APIs diverge).

---

## See also

- [Dashboard UI](dashboard.md)
- [First deploy](../getting-started/first-deploy.md)
- [Status & roadmap](../status-and-roadmap.md)
