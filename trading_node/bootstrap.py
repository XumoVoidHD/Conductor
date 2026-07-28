"""Load bootstrap JSON written by Conductor Node."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BrokerBootstrap:
    adapter: str
    config: dict[str, Any]


@dataclass(frozen=True)
class StrategyBootstrap:
    module: str
    class_name: str
    config_class: str
    config: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    source_path: str | None = None
    artifact_dir: str | None = None


@dataclass(frozen=True)
class TradingNodeBootstrap:
    node_id: str
    user_id: str
    trader_id: str
    control_host: str
    control_port: int
    broker: BrokerBootstrap
    strategy: StrategyBootstrap


def load_bootstrap() -> TradingNodeBootstrap:
    raw_json = os.getenv("CONDUCTOR_BOOTSTRAP_JSON")
    if raw_json:
        data = json.loads(raw_json)
    else:
        path = os.getenv("CONDUCTOR_BOOTSTRAP")
        if not path:
            raise SystemExit("CONDUCTOR_BOOTSTRAP or CONDUCTOR_BOOTSTRAP_JSON env var is required")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    broker = data["broker"]
    strategy = data["strategy"]

    return TradingNodeBootstrap(
        node_id=str(data["node_id"]),
        user_id=str(data["user_id"]),
        trader_id=str(data["trader_id"]),
        control_host=str(data["control_host"]),
        control_port=int(data["control_port"]),
        broker=BrokerBootstrap(
            adapter=str(broker["adapter"]),
            config=dict(broker["config"]),
        ),
        strategy=StrategyBootstrap(
            module=str(strategy["module"]),
            class_name=str(strategy["class_name"]),
            config_class=str(strategy["config_class"]),
            config=dict(strategy.get("config") or {}),
            source_url=strategy.get("source_url"),
            source_path=strategy.get("source_path"),
            artifact_dir=strategy.get("artifact_dir"),
        ),
    )
