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

from ...application.use_cases.get_messages import GetMessagesUseCase
from ...application.use_cases.send_message import SendMessageUseCase
from ...core.config import settings
from ...core.security import verify_token
from ...domain.repositories.event_publisher import EventPublisher
from ...domain.repositories.message_repository import MessageRepository
from ..dependencies import get_event_publisher, get_message_repo
from .manager import heartbeat, manager
from .schemas import ChatMessage, PongMessage, WebSocketMessage

router = APIRouter()


async def get_authenticated_user(
    websocket: WebSocket,
    token: str = Query(...),
) -> str:
    if websocket.headers.get("origin", "") != settings.ALLOWED_ORIGIN:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    username = verify_token(token)
    if not username:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
        )

    return username


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    username: Annotated[str, Depends(get_authenticated_user)],
    repo: Annotated[MessageRepository, Depends(get_message_repo)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
    last_id: int | None = Query(default=None),
) -> None:
    send_uc = SendMessageUseCase(repo=repo, publisher=publisher)
    get_uc = GetMessagesUseCase(repo=repo)

    await manager.connect(username, websocket)
    if last_id is None:
        await publisher.publish({"type": "join", "username": username})

    history = (
        await get_uc.execute_after(last_id)
        if last_id is not None
        else await get_uc.execute_recent()
    )
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

            if isinstance(msg, PongMessage):
                pong_event.set()
            elif isinstance(msg, ChatMessage):
                await send_uc.execute(username=username, text=msg.text)

    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket)
        await publisher.publish({"type": "leave", "username": username})
    finally:
        task.cancel()
