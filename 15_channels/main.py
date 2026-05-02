import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGIN = "http://localhost:3000"
PING_INTERVAL = 10
PONG_TIMEOUT = 5
CHANNELS = ["general", "tech", "random"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChannelManager:
    """WebSocket接続とチャネル購読を管理する。"""

    def __init__(self):
        self.connections: list[tuple[str, WebSocket]] = []
        self.subscriptions: dict[str, set[WebSocket]] = {ch: set() for ch in CHANNELS}

    async def connect(self, username: str, websocket: WebSocket):
        """WebSocket を受け入れて接続リストに追加する。"""
        await websocket.accept()
        self.connections.append((username, websocket))
        print(f"[connect] {username} が接続 | 接続数: {len(self.connections)}")

    def disconnect(self, websocket: WebSocket):
        """接続リストとすべてのチャネルから指定の WebSocket を削除する。"""
        self.connections = [
            (u, ws) for u, ws in self.connections if ws is not websocket
        ]
        for subs in self.subscriptions.values():
            subs.discard(websocket)
        print(f"[disconnect] 切断 | 接続数: {len(self.connections)}")

    def get_username(self, websocket: WebSocket) -> str:
        """WebSocket に対応するユーザー名を返す。"""
        for u, ws in self.connections:
            if ws is websocket:
                return u
        return ""

    async def subscribe(self, websocket: WebSocket, channel: str):
        """websocket をチャネルに追加し、参加通知を購読者へブロードキャストする。"""
        self.subscriptions[channel].add(websocket)
        username = self.get_username(websocket)
        print(f"[subscribe] {username} が #{channel} に参加")
        await self.broadcast_to_channel(
            channel, {"type": "join", "channel": channel, "username": username}
        )

    async def unsubscribe(self, websocket: WebSocket, channel: str):
        """websocket をチャネルから削除し、退室通知を購読者へブロードキャストする。"""
        username = self.get_username(websocket)
        self.subscriptions[channel].discard(websocket)
        print(f"[unsubscribe] {username} が #{channel} から退室")
        await self.broadcast_to_channel(
            channel, {"type": "leave", "channel": channel, "username": username}
        )

    async def broadcast_to_channel(self, channel: str, message: dict):
        """チャネルの購読者全員にメッセージを送る。送信失敗した接続は削除する。"""
        dead: list[WebSocket] = []
        for ws in list(self.subscriptions.get(channel, set())):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ChannelManager()


async def heartbeat(websocket: WebSocket, pong_event: asyncio.Event):
    """PING_INTERVAL 秒ごとに ping を送り、PONG_TIMEOUT 秒以内に pong が返らなければ切断する。"""
    while True:
        await asyncio.sleep(PING_INTERVAL)
        pong_event.clear()
        try:
            await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            break
        try:
            await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
        except asyncio.TimeoutError:
            print("[timeout] pong が返らなかったため切断")
            await websocket.close(code=1001, reason="pong timeout")
            break


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket エンドポイント。オリジン検証後に接続し、チャネル操作を処理する。"""
    origin = websocket.headers.get("origin", "")
    if origin != ALLOWED_ORIGIN:
        await websocket.close(code=1008)
        return

    username = websocket.query_params.get("username", "anonymous")
    await manager.connect(username, websocket)

    pong_event = asyncio.Event()
    task = asyncio.create_task(heartbeat(websocket, pong_event))

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "text": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            if msg_type == "pong":
                pong_event.set()
            elif msg_type == "subscribe":
                channel = data.get("channel", "")
                if channel in CHANNELS:
                    await manager.subscribe(websocket, channel)
                else:
                    await websocket.send_json(
                        {"type": "error", "text": f"Unknown channel: {channel!r}"}
                    )
            elif msg_type == "unsubscribe":
                channel = data.get("channel", "")
                if channel in CHANNELS:
                    await manager.unsubscribe(websocket, channel)
            elif msg_type == "message":
                channel = data.get("channel", "")
                text = data.get("text", "")
                if channel not in CHANNELS:
                    await websocket.send_json(
                        {"type": "error", "text": f"Unknown channel: {channel!r}"}
                    )
                elif websocket not in manager.subscriptions[channel]:
                    await websocket.send_json(
                        {"type": "error", "text": f"#{channel} に参加していません"}
                    )
                elif text:
                    await manager.broadcast_to_channel(
                        channel,
                        {
                            "type": "message",
                            "channel": channel,
                            "username": username,
                            "text": text,
                        },
                    )
            else:
                await websocket.send_json(
                    {"type": "error", "text": f"Unknown type: {msg_type!r}"}
                )
    except WebSocketDisconnect:
        # disconnect() が購読を全削除する前に、退室通知の宛先チャネルを記録する
        subscribed = [
            ch for ch, subs in manager.subscriptions.items() if websocket in subs
        ]
        manager.disconnect(websocket)
        for channel in subscribed:
            await manager.broadcast_to_channel(
                channel, {"type": "leave", "channel": channel, "username": username}
            )
    finally:
        task.cancel()
