from fastapi import WebSocket, WebSocketDisconnect

from ..core.config import settings


class ChatManager:
    """WebSocket 接続を管理し、全クライアントへのブロードキャストを担う。"""

    def __init__(self) -> None:
        self.connections: list[tuple[str, WebSocket]] = []

    async def connect(self, username: str, websocket: WebSocket) -> None:
        """WebSocket を受け入れて接続リストに追加する。"""
        await websocket.accept()
        self.connections.append((username, websocket))
        print(f"[connect] {username} が入室 | 現在: {[u for u, _ in self.connections]}")

    def disconnect(self, websocket: WebSocket) -> None:
        """接続リストから指定の WebSocket を削除する。既に削除済みの場合は何もしない。"""
        self.connections = [
            (u, ws) for u, ws in self.connections if ws is not websocket
        ]
        print(f"[disconnect] 退室 | 残り: {[u for u, _ in self.connections]}")

    async def broadcast(self, message: dict) -> None:
        """全接続クライアントにメッセージを送る。送信失敗した接続は削除する。"""
        dead: list[WebSocket] = []
        for _, ws in self.connections:
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def connect_and_broadcast(self, username: str, websocket: WebSocket) -> None:
        """接続を確立し、入室を全員に通知する。"""
        await self.connect(username, websocket)
        await self.broadcast({"type": "join", "username": username})

    async def disconnect_and_broadcast(
        self, websocket: WebSocket, username: str
    ) -> None:
        """接続を解除し、退室を全員に通知する。"""
        self.disconnect(websocket)
        await self.broadcast({"type": "leave", "username": username})


manager = ChatManager()


import asyncio

async def heartbeat(websocket: WebSocket, pong_event: asyncio.Event) -> None:
    """PING_INTERVAL 秒ごとに ping を送り、PONG_TIMEOUT 秒以内に pong が返らなければ切断する。"""
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
