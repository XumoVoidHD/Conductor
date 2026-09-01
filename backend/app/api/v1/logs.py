"""WebSocket routes for observe streams (logs)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.ws_auth import user_from_access_token
from app.repositories.trading_node_repository import TradingNodeRepository
from app.services.docker_log_stream import DockerLogStreamService
from app.services.observe_log_stream import ObserveLogStreamService

router = APIRouter(prefix="/dashboard", tags=["dashboard-logs"])


def _container_ref(row) -> str:
    return row.container_id or row.container_name or f"conductor-{row.node_id}"


@router.websocket("/nodes/{node_id}/logs/stream")
async def stream_node_logs(
    websocket: WebSocket,
    node_id: str,
    token: str = Query(..., description="JWT access token"),
) -> None:
    await websocket.accept()

    db: Session = SessionLocal()
    try:
        user = user_from_access_token(token, db)
        row = TradingNodeRepository(db).get_by_node_id(node_id)
        if row is None or row.user_id != user.id:
            await websocket.send_json({"error": "Node not found"})
            await websocket.close(code=4404)
            return
        username = user.username
        runtime = row.runtime
        container_ref = _container_ref(row)
    except HTTPException as exc:
        await websocket.send_json({"error": str(exc.detail)})
        await websocket.close(code=4401)
        return
    finally:
        db.close()

    try:
        await websocket.send_json({"type": "connected", "node_id": node_id})

        if runtime == "docker":
            docker_service = DockerLogStreamService()
            async for line in docker_service.stream_logs(container_ref):
                await websocket.send_json(
                    {
                        "type": "log",
                        "line": line,
                        "level": "INFO",
                        "source": "docker",
                    },
                )
            return

        observe_service = ObserveLogStreamService()
        async for event in observe_service.stream_logs(
            user_id=username,
            node_id=node_id,
        ):
            await websocket.send_json({"type": "log", **event, "source": "redis"})
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:  # noqa: BLE001
            pass
