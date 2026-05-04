import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from ...core.config import settings


class ChatManager:
    def __init__(self) -> None:
        self.connections: list[tuple[str, WebSocket]] = []

    async def connect(self, username: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append((username, websocket))
        print(f"[connect] {username} が入室 | 現在: {[u for u, _ in self.connections]}")

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections = [
            (u, ws) for u, ws in self.connections if ws is not websocket
        ]
        print(f"[disconnect] 退室 | 残り: {[u for u, _ in self.connections]}")

    async def broadcast_local(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for _, ws in self.connections:
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ChatManager()


async def heartbeat(websocket: WebSocket, pong_event: asyncio.Event) -> None:
    while True:
        await asyncio.sleep(settings.PING_INTERVAL)
        pong_event.clear()
        try:
            await websocket.send_json({"type": "ping"})
        except (WebSocketDisconnect, RuntimeError):
            manager.disconnect(websocket)
            break
        try:
            await asyncio.wait_for(pong_event.wait(), timeout=settings.PONG_TIMEOUT)
        except asyncio.TimeoutError:
            print("[timeout] pong が返らなかったため切断")
            await websocket.close(code=1001, reason="pong timeout")
            break
