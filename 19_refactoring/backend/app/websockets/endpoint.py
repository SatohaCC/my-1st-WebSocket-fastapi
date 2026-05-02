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

from ..core.config import ALLOWED_ORIGIN
from ..core.security import verify_token
from ..schemas.message import ChatMessage, PongMessage, WebSocketMessage
from .manager import heartbeat, manager

router = APIRouter()


async def get_authenticated_user(
    websocket: WebSocket,
    token: str = Query(...),
) -> str:
    """Origin 検証と JWT 検証を行う依存関数。"""
    # 1. Origin 検証
    if websocket.headers.get("origin", "") != ALLOWED_ORIGIN:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    # 2. トークン検証
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
) -> None:
    """メッセージの種類に応じた処理を行う。"""
    if isinstance(msg, PongMessage):
        pong_event.set()
    elif isinstance(msg, ChatMessage):
        await manager.broadcast(
            {"type": "message", "username": username, "text": msg.text}
        )
    else:
        await websocket.send_json({"type": "error", "text": "Unknown message type"})


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    username: Annotated[str, Depends(get_authenticated_user)],
):
    """チャットのメインループ"""
    await manager.connect_and_broadcast(username, websocket)

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

            await process_message(msg, username, websocket, pong_event)

    except (WebSocketDisconnect, RuntimeError):
        await manager.disconnect_and_broadcast(websocket, username)
    finally:
        task.cancel()
