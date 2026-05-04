import asyncio
import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.security import verify_token
from ..crud.message import create_message, get_messages_after, get_recent_messages
from ..db.session import get_db
from ..schemas.message import ChatMessage, PongMessage, WebSocketMessage
from .manager import heartbeat, manager, publish

router = APIRouter()


async def get_authenticated_user(
    websocket: WebSocket,
    token: str = Query(...),
) -> str:
    """Origin 検証と JWT 検証を行う依存関数。"""
    if websocket.headers.get("origin", "") != settings.ALLOWED_ORIGIN:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    username = verify_token(token)
    if not username:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
        )

    return username


async def process_message(
    msg: WebSocketMessage,
    username: str,
    websocket: WebSocket,
    pong_event: asyncio.Event,
    db: AsyncSession,
) -> None:
    """メッセージの種類に応じた処理を行う。"""
    if isinstance(msg, PongMessage):
        pong_event.set()
    elif isinstance(msg, ChatMessage):
        db_message = await create_message(db, username, msg.text)
        await publish({"type": "message", "username": username, "text": msg.text, "id": db_message.id})
    else:
        await websocket.send_json({"type": "error", "text": "Unknown message type"})


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    username: Annotated[str, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    last_id: int | None = Query(default=None),
):
    """チャットのメインループ。
    last_id が指定された場合はその ID 以降の差分のみ送る（再接続時の重複防止）。"""
    await manager.connect(username, websocket)
    if last_id is None:
        await publish({"type": "join", "username": username})

    history = await get_messages_after(db, last_id) if last_id is not None \
              else await get_recent_messages(db)
    for h in history:
        await websocket.send_json(
            {"type": "message", "username": h.username, "text": h.text, "id": h.id, "is_history": True}
        )

    pong_event = asyncio.Event()
    task = asyncio.create_task(heartbeat(websocket, pong_event))

    try:
        while True:
            try:
                data = await websocket.receive_json()
                msg = TypeAdapter(WebSocketMessage).validate_python(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "text": "Invalid JSON"})
                continue
            except ValidationError as e:
                await websocket.send_json({"type": "error", "text": str(e)})
                continue

            await process_message(msg, username, websocket, pong_event, db)

    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket)
        await publish({"type": "leave", "username": username})
    finally:
        task.cancel()
