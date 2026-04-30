import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

PING_INTERVAL = 10
PONG_TIMEOUT = 5

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Ping/Pong</title>
    </head>
    <body>
        <h1>WebSocket Ping/Pong</h1>
        <p>状態: <span id="status">接続中...</span></p>
        <p>最後のPing: <span id="last-ping">-</span></p>
        <ul id="messages"></ul>
        <script>
            let ws;
            let retryDelay = 1000;
            const MAX_DELAY = 30000;

            function addMessage(text) {
                const li = document.createElement("li");
                li.textContent = text;
                document.getElementById("messages").appendChild(li);
            }

            function connect() {
                ws = new WebSocket("ws://localhost:8000/ws");

                ws.onopen = function () {
                    document.getElementById("status").textContent = "接続済み";
                    retryDelay = 1000;
                    addMessage("[接続しました]");
                };

                ws.onmessage = function (event) {
                    const data = JSON.parse(event.data);
                    if (data.type === "ping") {
                        document.getElementById("last-ping").textContent = new Date().toLocaleTimeString();
                        ws.send(JSON.stringify({ type: "pong" }));
                        return;
                    }
                    addMessage(data.message);
                };

                ws.onclose = function () {
                    document.getElementById("status").textContent = `切断 (${retryDelay / 1000}秒後に再接続...)`;
                    addMessage(`[切断。${retryDelay / 1000}秒後に再接続します]`);
                    setTimeout(function () {
                        retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
                        connect();
                    }, retryDelay);
                };

                ws.onerror = function () {
                    ws.close();
                };
            }

            connect();
        </script>
    </body>
</html>
"""


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pong_event = asyncio.Event()

    async def heartbeat():
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
                await websocket.close(code=1001, reason="pong timeout")
                break

    task = asyncio.create_task(heartbeat())
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "pong":
                pong_event.set()
            else:
                await websocket.send_json(
                    {"type": "message", "message": f"Echo: {data}"}
                )
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
