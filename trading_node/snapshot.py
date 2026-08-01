"""Build an on-demand snapshot of Nautilus TradingNode state.

Called on the node's event loop thread. Each section is best-effort so a
missing Nautilus API never fails the whole response.
"""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import StrategyId
from nautilus_trader.trading.strategy import Strategy


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        return repr(value)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_jsonable(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth > 4:
        return _safe_str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v, depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return _to_jsonable(value.to_dict(), depth=depth + 1)
        except Exception:  # noqa: BLE001
            pass
    return _safe_str(value)


def _call(obj: Any, method: str, *args: Any, default: Any = None) -> Any:
    fn = getattr(obj, method, None)
    if not callable(fn):
        return default
    try:
        return fn(*args)
    except TypeError:
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return default
    except Exception:  # noqa: BLE001
        return default


def _serialize_order(order: Any) -> dict[str, Any]:
    return {
        "client_order_id": _safe_str(getattr(order, "client_order_id", None)),
        "venue_order_id": _safe_str(getattr(order, "venue_order_id", None)),
        "instrument_id": _safe_str(getattr(order, "instrument_id", None)),
        "side": _safe_str(getattr(order, "side", None)),
        "order_type": _safe_str(getattr(order, "order_type", None)),
        "status": _safe_str(getattr(order, "status", None)),
        "quantity": _safe_str(getattr(order, "quantity", None)),
        "filled_qty": _safe_str(getattr(order, "filled_qty", None)),
        "leaves_qty": _safe_str(getattr(order, "leaves_qty", None)),
        "price": _safe_str(getattr(order, "price", None)),
        "avg_px": _safe_str(getattr(order, "avg_px", None)),
        "strategy_id": _safe_str(getattr(order, "strategy_id", None)),
    }


def _serialize_position(position: Any) -> dict[str, Any]:
    return {
        "id": _safe_str(getattr(position, "id", None)),
        "instrument_id": _safe_str(getattr(position, "instrument_id", None)),
        "side": _safe_str(getattr(position, "side", None)),
        "quantity": _safe_str(getattr(position, "quantity", None)),
        "peak_qty": _safe_str(getattr(position, "peak_qty", None)),
        "avg_px_open": _safe_str(getattr(position, "avg_px_open", None)),
        "avg_px_close": _safe_str(getattr(position, "avg_px_close", None)),
        "realized_pnl": _safe_str(getattr(position, "realized_pnl", None)),
        "unrealized_pnl": _safe_str(getattr(position, "unrealized_pnl", None)),
        "ts_opened": _safe_str(getattr(position, "ts_opened", None)),
        "ts_closed": _safe_str(getattr(position, "ts_closed", None)),
        "is_open": bool(getattr(position, "is_open", False)),
        "is_closed": bool(getattr(position, "is_closed", False)),
    }


def _serialize_account(account: Any) -> dict[str, Any]:
    balances = []
    raw_balances = getattr(account, "balances", None)
    if callable(raw_balances):
        try:
            raw_balances = raw_balances()
        except Exception:  # noqa: BLE001
            raw_balances = None
    if isinstance(raw_balances, dict):
        for currency, balance in raw_balances.items():
            balances.append(
                {
                    "currency": _safe_str(currency),
                    "total": _safe_str(getattr(balance, "total", balance)),
                    "locked": _safe_str(getattr(balance, "locked", None)),
                    "free": _safe_str(getattr(balance, "free", None)),
                },
            )
    return {
        "id": _safe_str(getattr(account, "id", None)),
        "account_type": _safe_str(getattr(account, "account_type", None)),
        "base_currency": _safe_str(getattr(account, "base_currency", None)),
        "balances": balances,
        "raw": _to_jsonable(account),
    }


def _serialize_instrument(instrument: Any) -> dict[str, Any]:
    return {
        "id": _safe_str(getattr(instrument, "id", None)),
        "raw_symbol": _safe_str(getattr(instrument, "raw_symbol", None)),
        "asset_class": _safe_str(getattr(instrument, "asset_class", None)),
        "instrument_class": _safe_str(getattr(instrument, "instrument_class", None)),
        "price_precision": getattr(instrument, "price_precision", None),
        "size_precision": getattr(instrument, "size_precision", None),
        "price_increment": _safe_str(getattr(instrument, "price_increment", None)),
        "size_increment": _safe_str(getattr(instrument, "size_increment", None)),
        "multiplier": _safe_str(getattr(instrument, "multiplier", None)),
        "raw": _to_jsonable(instrument),
    }


def _collect_fills(cache: Any) -> list[dict[str, Any]]:
    fills: list[dict[str, Any]] = []
    # Prefer closed/open orders' fill fields; Nautilus does not always expose a fills() list.
    for getter in ("orders_closed", "orders"):
        orders = _call(cache, getter, default=[]) or []
        for order in orders:
            filled_qty = getattr(order, "filled_qty", None)
            try:
                has_fill = filled_qty is not None and float(filled_qty) > 0
            except (TypeError, ValueError):
                has_fill = filled_qty is not None and str(filled_qty) not in {"0", "0.0"}
            if not has_fill:
                continue
            fills.append(
                {
                    "client_order_id": _safe_str(getattr(order, "client_order_id", None)),
                    "instrument_id": _safe_str(getattr(order, "instrument_id", None)),
                    "side": _safe_str(getattr(order, "side", None)),
                    "filled_qty": _safe_str(filled_qty),
                    "avg_px": _safe_str(getattr(order, "avg_px", None)),
                    "status": _safe_str(getattr(order, "status", None)),
                    "ts_last": _safe_str(getattr(order, "ts_last", None)),
                },
            )
    return fills


def _collect_subscriptions(strategy: Strategy | None) -> dict[str, Any]:
    if strategy is None:
        return {"bars": [], "quotes": [], "trades": [], "instruments": [], "other": []}
    # Strategy keeps internal topic sets; expose whatever is discoverable.
    out: dict[str, Any] = {
        "bars": [],
        "quotes": [],
        "trades": [],
        "instruments": [],
        "other": [],
    }
    for attr, key in (
        ("_bar_types", "bars"),
        ("_quote_subscriptions", "quotes"),
        ("_trade_subscriptions", "trades"),
        ("_instrument_ids", "instruments"),
    ):
        raw = getattr(strategy, attr, None)
        if raw is None:
            continue
        try:
            items = list(raw) if not isinstance(raw, dict) else list(raw.keys())
            out[key] = [_safe_str(x) for x in items]
        except Exception:  # noqa: BLE001
            continue
    # Fall back to cache bar types as "active market data"
    return out


def _collect_indicators(strategy: Strategy | None) -> list[dict[str, Any]]:
    if strategy is None:
        return []
    indicators = list(getattr(strategy, "registered_indicators", []) or [])
    result: list[dict[str, Any]] = []
    for ind in indicators:
        value = None
        for attr in ("value", "count", "initialized"):
            if hasattr(ind, attr):
                try:
                    value = {
                        **(value or {}),
                        attr: _to_jsonable(getattr(ind, attr)),
                    }
                except Exception:  # noqa: BLE001
                    pass
        result.append(
            {
                "name": _safe_str(getattr(ind, "name", type(ind).__name__)),
                "type": type(ind).__name__,
                "initialized": bool(getattr(ind, "initialized", False)),
                "value": value if value is not None else _to_jsonable(ind),
            },
        )
    return result


def _collect_portfolio_stats(node: TradingNode) -> dict[str, Any]:
    portfolio = getattr(node, "portfolio", None)
    if portfolio is None:
        return {}
    stats: dict[str, Any] = {
        "initialized": bool(getattr(portfolio, "initialized", False)),
        "is_completely_flat": _call(portfolio, "is_completely_flat", default=None),
    }
    for method in (
        "net_exposures",
        "realized_pnls",
        "unrealized_pnls",
        "total_pnls",
        "balances_locked",
        "margins_init",
        "margins_maint",
        "mark_values",
    ):
        stats[method] = _to_jsonable(_call(portfolio, method, default=None))

    analyzer = getattr(portfolio, "analyzer", None)
    if analyzer is not None:
        stats["analyzer"] = {
            "sharpe_ratio": _to_jsonable(_call(analyzer, "sharpe_ratio", default=None)),
            "sortino_ratio": _to_jsonable(_call(analyzer, "sortino_ratio", default=None)),
            "profit_factor": _to_jsonable(_call(analyzer, "profit_factor", default=None)),
            "max_drawdown": _to_jsonable(_call(analyzer, "max_drawdown", default=None)),
            "returns": _to_jsonable(_call(analyzer, "get_performance_stats_pnls", default=None)),
            "raw": _to_jsonable(_call(analyzer, "get_stats_pnls_by_currency", default=None)),
        }
    return stats


def _collect_risk(node: TradingNode) -> dict[str, Any]:
    risk = getattr(getattr(node, "kernel", None), "risk_engine", None)
    if risk is None:
        return {}
    return {
        "state": _safe_str(getattr(risk, "state", None)),
        "trading_state": _safe_str(getattr(risk, "trading_state", None)),
        "is_running": bool(getattr(risk, "is_running", False)),
        "is_bypassed": bool(getattr(risk, "is_bypassed", False)),
        "is_degraded": bool(getattr(risk, "is_degraded", False)),
        "is_faulted": bool(getattr(risk, "is_faulted", False)),
        "command_count": getattr(risk, "command_count", None),
        "event_count": getattr(risk, "event_count", None),
        "max_notionals_per_order": _to_jsonable(
            _call(risk, "max_notionals_per_order", default=None),
        ),
        "max_order_submit_rate": _safe_str(getattr(risk, "max_order_submit_rate", None)),
        "max_order_modify_rate": _safe_str(getattr(risk, "max_order_modify_rate", None)),
    }


def _collect_strategy_state(strategy: Strategy | None, strategy_id: StrategyId) -> dict[str, Any]:
    if strategy is None:
        return {"id": str(strategy_id), "state": "missing"}
    return {
        "id": _safe_str(strategy.id),
        "state": "running" if strategy.is_running else ("stopped" if strategy.is_stopped else "unknown"),
        "is_running": bool(strategy.is_running),
        "is_stopped": bool(strategy.is_stopped),
        "order_id_count": getattr(strategy, "order_id_count", None),
        "indicators_initialized": bool(getattr(strategy, "indicators_initialized", False)),
        "config": _to_jsonable(getattr(getattr(strategy, "config", None), "__dict__", None)),
    }


def build_node_snapshot(
    node: TradingNode,
    *,
    strategy_id: StrategyId,
    node_id: str,
    user_id: str,
    recent_logs: list[str] | None = None,
    recent_errors: list[str] | None = None,
    shutting_down: bool = False,
) -> dict[str, Any]:
    """Return a JSON-serializable snapshot of the live trading node."""
    cache = getattr(node, "cache", None)
    strategy = None
    for s in node.trader.strategies():
        if s.id == strategy_id:
            strategy = s
            break

    section_errors: list[str] = list(recent_errors or [])

    def section(name: str, fn):  # noqa: ANN001
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            section_errors.append(f"{name}: {exc}")
            return None

    positions_open = section(
        "positions_open",
        lambda: [_serialize_position(p) for p in (_call(cache, "positions_open", default=[]) or [])],
    )
    positions_closed = section(
        "positions_closed",
        lambda: [_serialize_position(p) for p in (_call(cache, "positions_closed", default=[]) or [])],
    )
    orders_open = section(
        "orders_open",
        lambda: [_serialize_order(o) for o in (_call(cache, "orders_open", default=[]) or [])],
    )
    orders_closed = section(
        "orders_closed",
        lambda: [_serialize_order(o) for o in (_call(cache, "orders_closed", default=[]) or [])],
    )
    accounts = section(
        "accounts",
        lambda: [_serialize_account(a) for a in (_call(cache, "accounts", default=[]) or [])],
    )
    instruments = section(
        "instruments",
        lambda: [_serialize_instrument(i) for i in (_call(cache, "instruments", default=[]) or [])],
    )
    fills = section("fills", lambda: _collect_fills(cache))
    subscriptions = section("subscriptions", lambda: _collect_subscriptions(strategy))
    # Enrich subscriptions with cache bar types when strategy internals are empty
    if isinstance(subscriptions, dict) and cache is not None:
        bar_types = _call(cache, "bar_types", default=[]) or []
        if bar_types and not subscriptions.get("bars"):
            subscriptions["bars"] = [_safe_str(b) for b in bar_types]

    return {
        "schema_version": 1,
        "captured_at": _now_iso(),
        "node": {
            "node_id": node_id,
            "user_id": user_id,
            "trader_id": _safe_str(getattr(node, "trader_id", None)),
            "is_running": bool(_call(node, "is_running", default=False)),
            "shutting_down": shutting_down,
        },
        "health": {
            "node_running": bool(_call(node, "is_running", default=False)),
            "shutting_down": shutting_down,
            "strategy_state": _collect_strategy_state(strategy, strategy_id).get("state"),
            "kernel_loop_alive": getattr(getattr(node, "kernel", None), "loop", None) is not None,
            "data_engine_running": bool(
                getattr(getattr(getattr(node, "kernel", None), "data_engine", None), "is_running", False),
            ),
            "exec_engine_running": bool(
                getattr(getattr(getattr(node, "kernel", None), "exec_engine", None), "is_running", False),
            ),
            "risk_engine_running": bool(
                getattr(getattr(getattr(node, "kernel", None), "risk_engine", None), "is_running", False),
            ),
        },
        "strategy": section("strategy", lambda: _collect_strategy_state(strategy, strategy_id)),
        "indicators": section("indicators", lambda: _collect_indicators(strategy)),
        "positions": {
            "open": positions_open or [],
            "closed": positions_closed or [],
            "open_count": _call(cache, "positions_open_count", default=len(positions_open or [])),
            "closed_count": _call(cache, "positions_closed_count", default=len(positions_closed or [])),
        },
        "orders": {
            "open": orders_open or [],
            "closed": orders_closed or [],
            "inflight": section(
                "orders_inflight",
                lambda: [_serialize_order(o) for o in (_call(cache, "orders_inflight", default=[]) or [])],
            )
            or [],
            "open_count": _call(cache, "orders_open_count", default=len(orders_open or [])),
            "closed_count": _call(cache, "orders_closed_count", default=len(orders_closed or [])),
        },
        "fills": fills or [],
        "balances": accounts or [],
        "portfolio": section("portfolio", lambda: _collect_portfolio_stats(node)) or {},
        "market_data_subscriptions": subscriptions or {},
        "instruments": instruments or [],
        "risk": section("risk", lambda: _collect_risk(node)) or {},
        "logs": list(recent_logs or [])[-200:],
        "errors": section_errors[-200:],
    }
