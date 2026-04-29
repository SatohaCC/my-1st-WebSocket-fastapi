from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, Response

ALLOWED_ORIGINS = {"http://localhost:8000"}
VALID_TOKENS = {"secret-token-alice", "secret-token-bob"}

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Cookie Auth</title>
    </head>
    <body>
        <h1>WebSocket Cookie 認証</h1>

        <h2>① ログイン（Cookie をセット）</h2>
        <form onsubmit="login(event)">
            <input type="text" id="token" placeholder="トークンを入力" autocomplete="off"/>
            <button>ログイン</button>
        </form>
        <p id="login-status"></p>

        <h2>② WebSocket 接続</h2>
        <button onclick="connect()">接続</button>
        <button onclick="disconnect()">切断</button>
        <p>状態: <span id="status">未接続</span></p>
        <form onsubmit="sendMessage(event)">
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

            async function login(event) {
                event.preventDefault();
                const token = document.getElementById("token").value;
                const res = await fetch("/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token }),
                });
                const data = await res.json();
                document.getElementById("login-status").textContent =
                    res.ok ? "ログイン成功（Cookie がセットされました）" : "失敗: " + data.detail;
            }

            function connect() {
                ws = new WebSocket("ws://localhost:8000/ws");

                ws.onopen = function () {
                    document.getElementById("status").textContent = "接続済み";
                    addMessage("[接続しました]");
                };
                ws.onmessage = function (event) {
                    addMessage(event.data);
                };
                ws.onclose = function (event) {
                    document.getElementById("status").textContent = "切断 (code=" + event.code + ")";
                    addMessage("[切断されました]");
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


@app.post("/login")
async def login(body: dict):
    print(f"login body: {body}")
    token = body.get("token", "")
    if token not in VALID_TOKENS:
        return JSONResponse({"detail": "invalid token"}, status_code=401)

    response = JSONResponse({"detail": "ok"})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="strict",
    )
    print(f"Set-Cookie: session={token}")
    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        await websocket.send_denial_response(
            JSONResponse({"detail": "forbidden origin"}, status_code=403)
        )
        return

    print(dict(websocket.cookies))
    token = websocket.cookies.get("session")
    if token not in VALID_TOKENS:
        await websocket.send_denial_response(
            JSONResponse({"detail": "unauthorized"}, status_code=401)
        )
        return

    await websocket.accept()
    async for data in websocket.iter_text():
        print(f"[{token}] {data}")
        await websocket.send_text(f"[{token}] {data}")
