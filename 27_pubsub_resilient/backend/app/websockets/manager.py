import asyncio
import json

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from ..core.config import settings


class ChatManager:
    """WebSocket 接続をローカルで管理する。ブロードキャストは Redis 経由で行う。"""

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

    async def broadcast_local(self, message: dict) -> None:
        """このインスタンスのローカル接続にのみ送信する。Redis subscriber から呼ばれる。"""
        dead: list[WebSocket] = []
        for _, ws in self.connections:
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ChatManager()
_redis: aioredis.Redis = aioredis.from_url(settings.REDIS_URL)


async def publish(message: dict) -> None:
    """メッセージを Redis チャンネルに publish する。"""
    await _redis.publish(settings.REDIS_CHANNEL, json.dumps(message))


async def redis_subscriber() -> None:
    """Redis チャンネルを購読し、受信したメッセージをローカルにブロードキャストする。"""
    client = aioredis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(settings.REDIS_CHANNEL)
    async for raw in pubsub.listen():
        if raw["type"] == "message":
            data = json.loads(raw["data"])
            await manager.broadcast_local(data)


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
