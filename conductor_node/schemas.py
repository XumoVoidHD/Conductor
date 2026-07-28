"""Redis command and event schemas for Conductor Node.

Conductor validates structure and forwards broker config opaquely.
Broker-specific contract / client / instrument logic belongs in trading_node.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any

# Allowlist of adapters this Conductor build can spawn. Shape of config is opaque.
SUPPORTED_BROKER_ADAPTERS = frozenset({"bybit", "interactive_brokers"})


@dataclass
class BrokerDeployConfig:
    adapter: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyDeployConfig:
    module: str
    class_name: str
    config_class: str
    config: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    source_path: str | None = None
    # Set by Conductor after materializing a cloud/local artifact into the node dir.
    artifact_dir: str | None = None


@dataclass
class DeployPayload:
    user_id: str
    node_id: str | None = None
    trader_id: str | None = None
    control_host: str | None = None
    control_port: int | None = None
    broker: BrokerDeployConfig | None = None
    strategy: StrategyDeployConfig | None = None


@dataclass
class ConductorCommand:
    command: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    node_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConductorCommand:
        return cls(
            command=str(data["command"]).strip().lower(),
            correlation_id=str(data.get("correlation_id") or uuid.uuid4()),
            user_id=data.get("user_id"),
            node_id=data.get("node_id"),
            payload=dict(data.get("payload") or {}),
        )


@dataclass
class ConductorEvent:
    correlation_id: str
    command: str
    status: str
    message: str
    user_id: str | None = None
    node_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_broker(broker_raw: dict[str, Any]) -> BrokerDeployConfig:
    adapter = broker_raw.get("adapter")
    if not adapter:
        raise ValueError("broker.adapter is required")
    adapter = str(adapter)
    if adapter not in SUPPORTED_BROKER_ADAPTERS:
        raise ValueError(
            f"unsupported broker adapter: {adapter} "
            f"(supported: {', '.join(sorted(SUPPORTED_BROKER_ADAPTERS))})",
        )

    config = broker_raw.get("config")
    if config is None:
        raise ValueError("broker.config is required")
    if not isinstance(config, dict):
        raise ValueError("broker.config must be an object")
    if not config:
        raise ValueError("broker.config must not be empty")

    return BrokerDeployConfig(adapter=adapter, config=dict(config))


def _parse_strategy(strategy_raw: dict[str, Any]) -> StrategyDeployConfig:
    module = strategy_raw.get("module")
    class_name = strategy_raw.get("class_name")
    config_class = strategy_raw.get("config_class")

    missing = [
        name
        for name, value in (
            ("strategy.module", module),
            ("strategy.class_name", class_name),
            ("strategy.config_class", config_class),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"required fields missing: {', '.join(missing)}")

    return StrategyDeployConfig(
        module=str(module),
        class_name=str(class_name),
        config_class=str(config_class),
        config=dict(strategy_raw.get("config") or {}),
        source_url=strategy_raw.get("source_url"),
        source_path=strategy_raw.get("source_path"),
        artifact_dir=strategy_raw.get("artifact_dir"),
    )


def parse_deploy_payload(cmd: ConductorCommand) -> DeployPayload:
    raw = cmd.payload

    broker_raw = raw.get("broker")
    if not broker_raw or not isinstance(broker_raw, dict):
        raise ValueError("payload.broker is required")

    strategy_raw = raw.get("strategy")
    if not strategy_raw or not isinstance(strategy_raw, dict):
        raise ValueError("payload.strategy is required")

    control_port = raw.get("control_port")
    return DeployPayload(
        user_id=str(cmd.user_id or raw.get("user_id") or ""),
        node_id=cmd.node_id or raw.get("node_id"),
        trader_id=raw.get("trader_id"),
        control_host=raw.get("control_host"),
        control_port=int(control_port) if control_port is not None else None,
        broker=_parse_broker(broker_raw),
        strategy=_parse_strategy(strategy_raw),
    )
