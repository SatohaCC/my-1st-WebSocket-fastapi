import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>JSON Chat</title>
        <style>
            .system { color: gray; font-style: italic; }
            .error  { color: red; }
        </style>
    </head>
    <body>
        <h1>WebSocket JSON チャット</h1>
        <form onsubmit="connect(event)">
            <input type="text" id="username" placeholder="名前" autocomplete="off"/>
            <button type="submit" id="joinBtn">入室</button>
            <button type="button" id="leaveBtn" onclick="disconnect()" disabled>退室</button>
        </form>
        <p>状態: <span id="status">未接続</span></p>
        <form onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off" disabled/>
            <button type="submit" id="sendBtn" disabled>Send</button>
        </form>
        <ul id="messages"></ul>
        <script>
            let ws;

            function addMessage(text, className) {
                const li = document.createElement("li");
                li.textContent = text;
                if (className) li.className = className;
                document.getElementById("messages").appendChild(li);
            }

            function updateUI(connected) {
                document.getElementById("username").disabled = connected;
                document.getElementById("joinBtn").disabled = connected;
                document.getElementById("leaveBtn").disabled = !connected;
                document.getElementById("messageText").disabled = !connected;
                document.getElementById("sendBtn").disabled = !connected;
            }

            function connect(event) {
                event.preventDefault();
                const username = document.getElementById("username").value;
                ws = new WebSocket(`ws://${window.location.host}/ws?username=${username}`);

                ws.onopen = function () {
                    document.getElementById("status").textContent = "接続済み";
                    updateUI(true);
                };
                ws.onmessage = function (event) {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "message") {
                        addMessage(`${msg.username}: ${msg.text}`);
                    } else if (msg.type === "join") {
                        addMessage(`[${msg.username} が入室しました]`, "system");
                    } else if (msg.type === "leave") {
                        addMessage(`[${msg.username} が退室しました]`, "system");
                    } else if (msg.type === "error") {
                        addMessage(`[エラー: ${msg.text}]`, "error");
                    }
                };
                ws.onclose = function () {
                    document.getElementById("status").textContent = "切断";
                    updateUI(false);
                };
                ws.onerror = function () {
                    ws.close();
                };
            }

            function disconnect() {
                if (ws) ws.close();
            }

            function sendMessage(event) {
                event.preventDefault();
                const input = document.getElementById("messageText");
                if (ws && ws.readyState === WebSocket.OPEN && input.value) {
                    ws.send(JSON.stringify({ type: "message", text: input.value }));
                    input.value = "";
                }
            }
        </script>
    </body>
</html>
"""


class ChatManager:
    def __init__(self):
        self.connections: list[tuple[str, WebSocket]] = []

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.append((username, websocket))

    def disconnect(self, websocket: WebSocket):
        self.connections = [(u, ws) for u, ws in self.connections if ws is not websocket]

    async def broadcast(self, message: dict):
        for _, ws in self.connections:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                pass


manager = ChatManager()


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
                await manager.broadcast({
                    "type": "message",
                    "username": username,
                    "text": data.get("text", ""),
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "text": f"Unknown type: {data.get('type')!r}",
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({"type": "leave", "username": username})
