import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGIN = "http://localhost:3000"

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
        await websocket.accept()
        self.connections.append((username, websocket))

    def disconnect(self, websocket: WebSocket):
        self.connections = [
            (u, ws) for u, ws in self.connections if ws is not websocket
        ]

    async def broadcast(self, message: dict):
        dead: list[WebSocket] = []
        for _, ws in self.connections:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ChatManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    if origin != ALLOWED_ORIGIN:
        await websocket.close(code=1008)
        return

    username = websocket.query_params.get("username", "anonymous")
    await manager.connect(username, websocket)
    await manager.broadcast({"type": "join", "username": username})
    try:
        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "text": "Invalid JSON"})
                continue

            if data.get("type") == "message":
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
