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
_redis: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=2,
    socket_timeout=2,
    decode_responses=True,
)


async def publish(message: dict) -> None:
    """メッセージを Redis Stream に追加する。MAXLEN で自動トリム。
    失敗時は次回 publish のためにクライアントを再生成する。"""
    global _redis
    try:
        await _redis.xadd(
            settings.REDIS_STREAM_KEY,
            {"data": json.dumps(message)},
            maxlen=1000,
        )
    except Exception as e:
        print(f"[publish] Redis エラー: {e}")
        await _redis.aclose()
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )


async def redis_subscriber() -> None:
    """Redis Stream を XREAD で読み続け、ローカルにブロードキャストする。
    last_id を保持することで再接続後に切断中のメッセージを読み直す。"""
    last_id = "$"  # 初回起動: 起動以降の新着のみ受け取る
    retry_sec = 1
    while True:
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            retry_sec = 1
            print(f"[redis_subscriber] Redis に接続しました（last_id={last_id}）")
            while True:
                results = await client.xread(
                    {settings.REDIS_STREAM_KEY: last_id},
                    count=100,
                    block=1000,  # 1秒待機（CancelledError を受け取れるよう短めに）
                )
                for _stream, entries in results:
                    for msg_id, fields in entries:
                        data = json.loads(fields["data"])
                        await manager.broadcast_local(data)
                        last_id = msg_id  # 読んだ位置を更新
        except asyncio.CancelledError:
            await client.aclose()
            raise
        except Exception as e:
            print(f"[redis_subscriber] 切断: {e}。{retry_sec}秒後に再接続します")
            await client.aclose()
            await asyncio.sleep(retry_sec)
            retry_sec = min(retry_sec * 2, 30)
            # last_id はそのまま保持 → 再接続後に切断中のメッセージを読み直す


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
