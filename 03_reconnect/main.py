from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Reconnect</title>
    </head>
    <body>
        <h1>WebSocket Reconnect</h1>
        <p>状態: <span id="status">接続中...</span></p>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id="messages"></ul>
        <script>
            const statusEl = document.getElementById("status");
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
                    statusEl.textContent = "接続済み";
                    retryDelay = 1000;
                    addMessage("[接続しました]");
                };

                ws.onmessage = function (event) {
                    addMessage(event.data);
                };

                ws.onclose = function () {
                    statusEl.textContent = `切断 (${retryDelay / 1000}秒後に再接続...)`;
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

            function sendMessage(event) {
                event.preventDefault();
                const input = document.getElementById("messageText");
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(input.value);
                }
                input.value = "";
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
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        pass
