"""Dashboard / strategy control routes (JWT required)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Depends
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
    summary="Register a strategy from strategies/",
    description=(
        "Pass a filename already present under the repo `strategies/` folder "
        "(e.g. `running_ping` or `running_ping.py`). Metadata is discovered "
        "from the module. ADMIN registers as SYSTEM (global); USER registers "
        "as their own strategy."
    ),
    response_model=StrategyResponse,
)
def register_strategy(
    payload: StrategyRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).register_strategy_from_file(payload.filename)


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
    description="List nodes owned by the authenticated user via Conductor Redis.",
)
def get_nodes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = _service(current_user, db).list_nodes()
    return {
        "status": event.get("status"),
        "message": event.get("message"),
        "nodes": (event.get("data") or {}).get("nodes", []),
        "raw": event,
    }


@router.post(
    "/deploy",
    status_code=status.HTTP_201_CREATED,
    summary="Deploy a strategy",
    description=(
        "Deploy a trading node with the selected strategy on Bybit "
        "(credentials from server .env). Strategy starts STOPPED — call /run next."
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


@router.post("/nodes/run", summary="Start strategy on a node")
def run_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("run", payload.node_id)


@router.post("/nodes/halt", summary="Stop strategy on a node")
def halt_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("halt", payload.node_id)


@router.post("/nodes/status", summary="Strategy status on a node")
def status_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("status", payload.node_id)


@router.post("/nodes/stop", summary="Destroy a trading node")
def stop_node(
    payload: NodeActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _service(current_user, db).node_action("stop", payload.node_id)
