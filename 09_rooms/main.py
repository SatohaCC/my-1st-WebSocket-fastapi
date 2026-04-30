from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Rooms</title>
    </head>
    <body>
        <h1>WebSocket ルームチャット</h1>
        <form onsubmit="connect(event)">
            <input type="text" id="room" placeholder="ルーム名" autocomplete="off"/>
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

            function addMessage(text) {
                const li = document.createElement("li");
                li.textContent = text;
                document.getElementById("messages").appendChild(li);
            }

            function updateUI(connected) {
                document.getElementById("room").disabled = connected;
                document.getElementById("username").disabled = connected;
                document.getElementById("joinBtn").disabled = connected;
                document.getElementById("leaveBtn").disabled = !connected;
                document.getElementById("messageText").disabled = !connected;
                document.getElementById("sendBtn").disabled = !connected;
            }

            function connect(event) {
                event.preventDefault();
                
                // 既存の接続があれば閉じる（1タブ1ルームの制限）
                if (ws && ws.readyState !== WebSocket.CLOSED) {
                    ws.close();
                }

                const room = document.getElementById("room").value;
                const username = document.getElementById("username").value;
                ws = new WebSocket(`ws://${window.location.host}/ws/${room}?username=${username}`);

                ws.onopen = function () {
                    document.getElementById("status").textContent = `接続済み（ルーム: ${room}）`;
                    addMessage("[入室しました]");
                    updateUI(true);
                };
                ws.onmessage = function (event) {
                    addMessage(event.data);
                };
                ws.onclose = function () {
                    document.getElementById("status").textContent = "切断";
                    addMessage("[退室しました]");
                    updateUI(false);
                };
                ws.onerror = function () {
                    ws.close();
                };
            }

            function disconnect() {
                if (ws) {
                    ws.close();
                }
            }

            function sendMessage(event) {
                event.preventDefault();
                const input = document.getElementById("messageText");
                if (ws && ws.readyState === WebSocket.OPEN && input.value) {
                    ws.send(input.value);
                    input.value = "";
                }
            }
        </script>
    </body>
</html>
"""


class RoomManager:
    """ルームごとに接続を管理するクラス。"""

    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        if room not in self.rooms:
            self.rooms[room] = []
        self.rooms[room].append(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        if room in self.rooms and websocket in self.rooms[room]:
            self.rooms[room].remove(websocket)
            if not self.rooms[room]:
                del self.rooms[room]

    async def broadcast(self, room: str, message: str):
        for connection in self.rooms.get(room, []):
            try:
                await connection.send_text(message)
            except Exception:
                # 接続が切れている場合は無視（disconnectで処理されるはず）
                pass


manager = RoomManager()


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str):
    username = websocket.query_params.get("username", "anonymous")
    await manager.connect(room, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(room, f"[{username}] {data}")
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
        await manager.broadcast(room, f"[{username}] が退室しました")
    except Exception:
        manager.disconnect(room, websocket)
