from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse

ALLOWED_ORIGINS = {"http://localhost:8000"}
VALID_TOKENS = {"secret-token-alice", "secret-token-bob"}

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Auth</title>
    </head>
    <body>
        <h1>WebSocket 認証</h1>
        <form id="login" onsubmit="connect(event)">
            <input type="text" id="token" placeholder="トークンを入力" autocomplete="off"/>
            <button>接続</button>
        </form>
        <p>状態: <span id="status">未接続</span></p>
        <form id="chat" onsubmit="sendMessage(event)" style="display:none">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id="messages"></ul>
        <script>
            let ws;

            function addMessage(text) {
                var li = document.createElement("li");
                li.textContent = text;
                document.getElementById("messages").appendChild(li);
            }

            function connect(event) {
                event.preventDefault();
                const token = document.getElementById("token").value;
                ws = new WebSocket("ws://localhost:8000/ws?token=" + token);

                ws.onopen = function () {
                    document.getElementById("status").textContent = "接続済み";
                    document.getElementById("chat").style.display = "";
                    addMessage("[接続しました]");
                };

                ws.onmessage = function (event) {
                    addMessage(event.data);
                };

                ws.onclose = function (event) {
                    document.getElementById("status").textContent = "切断 (code=" + event.code + ")";
                    document.getElementById("chat").style.display = "none";
                    addMessage("[切断されました]");
                };

                ws.onerror = function () {
                    ws.close();
                };
            }

            function sendMessage(event) {
                event.preventDefault();
                const input = document.getElementById("messageText");
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(input.value);
                }
                input.value = "";
            }
        </script>
    </body>
</html>
"""


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        await websocket.send_denial_response(
            JSONResponse({"detail": "forbidden origin"}, status_code=403)
        )
        return

    token = websocket.query_params.get("token")
    if token not in VALID_TOKENS:
        await websocket.send_denial_response(
            JSONResponse({"detail": "unauthorized"}, status_code=401)
        )
        return

    await websocket.accept()
    async for data in websocket.iter_text():
        await websocket.send_text(f"[{token}] {data}")
