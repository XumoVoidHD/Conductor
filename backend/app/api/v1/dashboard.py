"""Dashboard / strategy control routes (JWT required)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.db.models.user import User
from app.schemas.strategy import StrategyGrantAccessRequest
from app.schemas.strategy import StrategyRegisterRequest
from app.schemas.strategy import StrategyResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


class DeployRequest(BaseModel):
    strategy_id: str = Field(..., examples=["running_ping"])
    config: dict[str, Any] = Field(default_factory=dict)


class NodeActionRequest(BaseModel):
    node_id: str = Field(..., examples=["tn-abc123"])


class NodeSnapshotRequest(BaseModel):
    """Identify the trading node by node_id or Docker container name."""

    node_id: str | None = Field(default=None, examples=["tn-abc123"])
    container_name: str | None = Field(default=None, examples=["conductor-tn-abc123"])
    node: str | None = Field(
        default=None,
        description="Alias for either node_id or container_name",
        examples=["tn-abc123"],
    )


def _service(current_user: User, db: Session) -> DashboardService:
    return DashboardService(current_user, db)


@router.get(
    "/status",
    summary="Dashboard / Redis status",
    description="Check Redis connectivity; user_id is the authenticated username.",
)
def dashboard_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).conductor_status()


@router.get(
    "/strategies",
    summary="List available strategies",
    description=(
        "Strategies the user can deploy: global (SYSTEM), owned, or shared via strategy_access."
    ),
    response_model=dict[str, list[StrategyResponse]],
)
def get_strategies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"strategies": _service(current_user, db).list_strategies()}


@router.post(
    "/strategies/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a strategy artifact",
    description=(
        "Provide either `filename` (local `strategies/` shorthand) or "
        "`source_url` + `source_path` (local://, s3://, or gs://). "
        "Full URI is source_url/source_path. ADMIN → SYSTEM/global; USER → owned."
    ),
    response_model=StrategyResponse,
)
def register_strategy(
    payload: StrategyRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from shared.artifacts import ArtifactLocation

    service = _service(current_user, db)
    if payload.filename:
        return service.register_strategy_from_file(payload.filename)
    assert payload.source_url and payload.source_path
    location = ArtifactLocation.from_parts(payload.source_url, payload.source_path)
    return service.register_strategy_from_location(location)


@router.post(
    "/strategies/{slug}/access",
    status_code=status.HTTP_201_CREATED,
    summary="Grant another user access to your strategy",
)
def grant_strategy_access(
    slug: str,
    payload: StrategyGrantAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).grant_strategy_access(slug, payload.username)


@router.get(
    "/nodes",
    summary="List trading nodes",
    description=(
        "List nodes owned by the authenticated user. "
        "Includes stopped nodes (they still count toward trading_nodes quota)."
    ),
)
def get_nodes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = _service(current_user, db).list_nodes()
    data = event.get("data") or {}
    return {
        "status": event.get("status"),
        "message": event.get("message"),
        "nodes": data.get("nodes", []),
        "node_count": data.get("node_count", len(data.get("nodes", []))),
        "max_trading_nodes": data.get("max_trading_nodes", current_user.trading_nodes),
        "raw": event,
    }


@router.post(
    "/deploy",
    status_code=status.HTTP_201_CREATED,
    summary="Deploy a strategy",
    description=(
        "Deploy a trading node with the selected strategy on Bybit "
        "(credentials from server .env). Strategy starts STOPPED — call /run next. "
        "Fails if the user already has trading_nodes slots in use "
        "(stopped nodes still count; delete to free a slot)."
    ),
)
def deploy(
    payload: DeployRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = _service(current_user, db).deploy_strategy(
        payload.strategy_id,
        config_overrides=payload.config or None,
    )
    return {
        "status": event.get("status"),
        "message": event.get("message"),
        "node_id": event.get("node_id"),
        "data": event.get("data") or {},
        "raw": event,
    }


@router.post("/nodes/run", summary="Start strategy (starts container if stopped)")
def run_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("run", payload.node_id)


@router.post(
    "/nodes/stop",
    summary="Stop trading node container/process",
    description="Stops the node but keeps the slot. Use /delete to free quota.",
)
def stop_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("stop", payload.node_id)


@router.post("/nodes/status", summary="Node / strategy status")
def status_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("status", payload.node_id)


@router.post(
    "/nodes/restart",
    summary="Restart trading node",
    description="Restarts the container/process. Strategy comes back STOPPED.",
)
def restart_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("restart", payload.node_id)


@router.post(
    "/nodes/delete",
    summary="Delete trading node",
    description="Destroys the container/process and frees a trading_nodes slot.",
)
def delete_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("delete", payload.node_id)


@router.post("/nodes/halt", summary="Halt strategy only (node stays running)")
def halt_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("halt", payload.node_id)


@router.get(
    "/traders",
    summary="List trader summaries for your nodes",
    description=(
        "Phase-1 observe: one lightweight summary per active trading node "
        "(trader_id, strategy state, open positions/orders, reachable). "
        "Queries nodes directly over TCP (summary, with snapshot fallback). "
        "Returns offline stubs for unreachable nodes. Filter client-side."
    ),
)
def list_traders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).list_traders()


@router.post(
    "/nodes/snapshot",
    summary="Full Nautilus node snapshot",
    description=(
        "On-demand observe snapshot for one trading node: positions, orders, fills, "
        "balances, portfolio stats, subscriptions, instruments, strategy state, "
        "indicators, risk, logs, errors, and health. "
        "Provide `node_id`, `container_name`, or `node` (either). "
        "Queries the trading node directly when running; if stopped/unreachable, "
        "returns an offline snapshot from the database (reachable=false)."
    ),
)
def snapshot_node(
    payload: NodeSnapshotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ref = payload.node_id or payload.container_name or payload.node
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide node_id, container_name, or node",
        )
    return _service(current_user, db).get_node_snapshot(ref)
