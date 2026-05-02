import asyncio
import json
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ALLOWED_ORIGIN = "http://localhost:3000"
PING_INTERVAL = 10
PONG_TIMEOUT = 5

# 学習用のシークレット。実務では環境変数から読み込む
SECRET_KEY = "dev-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

# 学習用のインメモリユーザーストア。実務ではDBを使う
USERS: dict[str, str] = {
    "alice": "password1",
    "bob": "password2",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    """ログインリクエストのボディ。"""

    username: str
    password: str


def create_token(username: str) -> str:
    """JWT を生成して返す。"""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str | None:
    """JWT を検証し、有効なら sub（ユーザー名）を返す。無効なら None。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


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
        """接続リストから指定の WebSocket を削除する。既に削除済みの場合は何もしない。"""
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
            except (WebSocketDisconnect, RuntimeError):
                # WebSocketDisconnect: クライアントが close フレームを送った正常切断
                # RuntimeError: Starlette が接続状態 CLOSING/DISCONNECTED を検知した場合
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
        except (WebSocketDisconnect, RuntimeError):
            # ping 送信が失敗した時点で接続が死んでいるため、ここで connections から除去する。
            # main ループの receive_json() が WebSocketDisconnect を上げるまで待つと
            # TCP がハーフオープン状態のときにゾンビが残り続けるリスクがある。
            manager.disconnect(websocket)
            break
        try:
            await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
        except asyncio.TimeoutError:
            print("[timeout] pong が返らなかったため切断")
            await websocket.close(code=1001, reason="pong timeout")
            break


@app.post("/token")
async def login(req: LoginRequest):
    """ユーザー名とパスワードを検証し、JWT を返す。"""
    if USERS.get(req.username) != req.password:
        raise HTTPException(status_code=401, detail="ユーザー名またはパスワードが違います")
    token = create_token(req.username)
    print(f"[login] {req.username} がログイン")
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me")
async def me(authorization: str = Header(default="")):
    """Authorization: Bearer <token> ヘッダーを検証し、ユーザー情報を返す。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization ヘッダーがありません")
    token = authorization[len("Bearer "):]
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="無効なトークンです")
    return {"username": username, "message": f"こんにちは, {username}!"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket エンドポイント。JWT 検証後にチャットに参加し、ハートビートを開始する。"""
    origin = websocket.headers.get("origin", "")
    if origin != ALLOWED_ORIGIN:
        await websocket.close(code=1008)
        return

    # クエリパラメータの JWT を検証する
    token = websocket.query_params.get("token", "")
    username = verify_token(token)
    if not username:
        # 1008 = Policy Violation（認証失敗）
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

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
    except (WebSocketDisconnect, RuntimeError):
        # WebSocketDisconnect: クライアントの正常切断
        # RuntimeError: heartbeat が send_json() 失敗後に application_state が DISCONNECTED に
        #   なった状態で receive_json() の状態チェック(L149)が raise するケース
        manager.disconnect(websocket)
        await manager.broadcast({"type": "leave", "username": username})
    finally:
        task.cancel()
