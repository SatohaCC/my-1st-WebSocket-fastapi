import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGIN = "http://localhost:3000"
PING_INTERVAL = 10
PONG_TIMEOUT = 5

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatManager:
    """WebSocket接続を管理し、全クライアントへのブロードキャストを担う。"""

    def __init__(self):
        self.connections: list[tuple[str, WebSocket]] = []

    async def connect(self, username: str, websocket: WebSocket):
        """WebSocket を受け入れて接続リストに追加する。"""
        await websocket.accept()
        self.connections.append((username, websocket))
        names = [u for u, _ in self.connections]
        print(f"[connect] {username} が入室 | 現在のセッション: {names}")

    def disconnect(self, websocket: WebSocket):
        """接続リストから指定の WebSocket を削除する。"""
        self.connections = [
            (u, ws) for u, ws in self.connections if ws is not websocket
        ]
        names = [u for u, _ in self.connections]
        print(f"[disconnect] 退室 | 残りのセッション: {names}")

    async def broadcast(self, message: dict):
        """全接続クライアントにメッセージを送る。送信失敗した接続は削除する。"""
        dead: list[WebSocket] = []
        for _, ws in self.connections:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ChatManager()


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
    """WebSocket エンドポイント。オリジン検証後にチャットに参加し、ハートビートを開始する。"""
    origin = websocket.headers.get("origin", "")
    if origin != ALLOWED_ORIGIN:
        await websocket.close(code=1008)
        return

    username = websocket.query_params.get("username", "anonymous")
    await manager.connect(username, websocket)
    await manager.broadcast({"type": "join", "username": username})

    pong_event = asyncio.Event()
    task = asyncio.create_task(heartbeat(websocket, pong_event))

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "text": "Invalid JSON"})
                continue

            if data.get("type") == "pong":
                pong_event.set()
            elif data.get("type") == "message":
                await manager.broadcast(
                    {
                        "type": "message",
                        "username": username,
                        "text": data.get("text", ""),
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "text": f"Unknown type: {data.get('type')!r}",
                    }
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({"type": "leave", "username": username})
    finally:
        task.cancel()
