from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse

ALLOWED_ORIGINS = {"http://localhost:8000"}

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Origin Check</title>
    </head>
    <body>
        <h1>WebSocket Origin Check</h1>
        <p>Origin: <code>http://localhost:8000</code>（許可済み）</p>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id="messages"></ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onopen = function () {
                var li = document.createElement("li");
                li.textContent = "[接続しました]";
                document.getElementById("messages").appendChild(li);
            };
            ws.onmessage = function (event) {
                var li = document.createElement("li");
                li.textContent = event.data;
                document.getElementById("messages").appendChild(li);
            };
            ws.onclose = function (event) {
                var li = document.createElement("li");
                li.textContent = "[切断: code=" + event.code + "]";
                document.getElementById("messages").appendChild(li);
            };
            function sendMessage(event) {
                event.preventDefault();
                var input = document.getElementById("messageText");
                ws.send(input.value);
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
    print(dict(websocket.headers))
    origin = websocket.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        await websocket.send_denial_response(
            JSONResponse({"detail": "forbidden", "origin": origin}, status_code=403)
        )
        return

    await websocket.accept()
    async for data in websocket.iter_text():
        await websocket.send_text(f"Message text was: {data}")
