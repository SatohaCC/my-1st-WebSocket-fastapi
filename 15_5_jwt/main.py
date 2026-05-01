from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

SECRET_KEY = "dev-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

# 学習用のインメモリユーザーストア
USERS: dict[str, str] = {
    "alice": "password1",
    "bob": "password2",
}

html = """
<!DOCTYPE html>
<html>
<head>
    <title>JWT 学習</title>
    <style>
        body { font-family: monospace; padding: 1rem; }
        input { margin: 0.2rem; padding: 0.3rem; }
        button { margin: 0.2rem; padding: 0.3rem 0.8rem; cursor: pointer; }
        pre {
            background: #f4f4f4; padding: 0.8rem;
            border-radius: 4px; white-space: pre-wrap; word-break: break-all;
        }
        .error { color: red; }
        .ok { color: green; }
        .section { margin-top: 1.5rem; border-top: 1px solid #ccc; padding-top: 1rem; }
        .jwt-part { display: inline-block; padding: 0 2px; border-radius: 3px; }
        .jwt-header  { background: #ffd6d6; }
        .jwt-payload { background: #d6ffd6; }
        .jwt-sig     { background: #d6d6ff; }
    </style>
</head>
<body>
    <h1>JWT 学習</h1>

    <!-- ① ログイン -->
    <div class="section">
        <h2>① ログイン（POST /token）</h2>
        <input id="username" placeholder="ユーザー名" value="alice" />
        <input id="password" placeholder="パスワード" type="password" value="password1" />
        <button onclick="login()">ログイン</button>
        <p id="login-result"></p>
    </div>

    <!-- ② JWT の中身を見る -->
    <div class="section">
        <h2>② 取得した JWT</h2>
        <p>JWT は <span class="jwt-part jwt-header">ヘッダー</span>.<span class="jwt-part jwt-payload">ペイロード</span>.<span class="jwt-part jwt-sig">署名</span> の3パートを . でつないだ文字列。</p>
        <pre id="token-raw">（ログイン後に表示）</pre>

        <h3>ペイロードのデコード（base64）</h3>
        <p>ペイロードは base64 なのでブラウザ側でも中身を読める（署名の検証はしない）。</p>
        <pre id="payload-decoded">（ログイン後に表示）</pre>
    </div>

    <!-- ③ 保護されたエンドポイントを叩く -->
    <div class="section">
        <h2>③ 保護されたエンドポイント（GET /me）</h2>
        <p>リクエストヘッダー: <code>Authorization: Bearer &lt;token&gt;</code></p>
        <button onclick="fetchMe(true)">正しいトークンで GET /me</button>
        <button onclick="fetchMe(false)">トークンなしで GET /me</button>
        <pre id="me-result">（ボタンを押すと表示）</pre>
    </div>

    <!-- ④ ログ -->
    <div class="section">
        <h2>④ HTTP ログ</h2>
        <ul id="log"></ul>
    </div>

    <script>
        let currentToken = null;

        function log(msg, isError) {
            const li = document.createElement("li");
            li.textContent = msg;
            if (isError) li.className = "error";
            document.getElementById("log").prepend(li);
        }

        // JWT の各パートを色分けして表示する
        function colorizeJwt(token) {
            const parts = token.split(".");
            if (parts.length !== 3) return token;
            return (
                '<span class="jwt-part jwt-header">'  + parts[0] + '</span>' +
                '.' +
                '<span class="jwt-part jwt-payload">' + parts[1] + '</span>' +
                '.' +
                '<span class="jwt-part jwt-sig">'     + parts[2] + '</span>'
            );
        }

        // base64url → JSON（ブラウザ側でのデコード。署名検証なし）
        function decodePayload(token) {
            const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
            const json = atob(base64);
            const obj = JSON.parse(json);
            // exp をわかりやすく変換
            if (obj.exp) obj["exp_readable"] = new Date(obj.exp * 1000).toLocaleString();
            return JSON.stringify(obj, null, 2);
        }

        async function login() {
            const username = document.getElementById("username").value;
            const password = document.getElementById("password").value;
            log(`POST /token  username=${username}`);

            const res = await fetch("/token", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });
            const data = await res.json();

            if (!res.ok) {
                document.getElementById("login-result").textContent = "失敗: " + data.detail;
                document.getElementById("login-result").className = "error";
                log(`  → ${res.status} ${data.detail}`, true);
                return;
            }

            currentToken = data.access_token;
            document.getElementById("login-result").textContent = "成功！";
            document.getElementById("login-result").className = "ok";
            document.getElementById("token-raw").innerHTML = colorizeJwt(currentToken);
            document.getElementById("payload-decoded").textContent = decodePayload(currentToken);
            log(`  → 200 OK  トークン取得成功`);
        }

        async function fetchMe(withToken) {
            const headers = {};
            if (withToken && currentToken) {
                headers["Authorization"] = "Bearer " + currentToken;
                log(`GET /me  Authorization: Bearer ${currentToken.slice(0, 20)}...`);
            } else {
                log("GET /me  （Authorization ヘッダーなし）");
            }

            const res = await fetch("/me", { headers });
            const data = await res.json();
            const text = JSON.stringify(data, null, 2);
            document.getElementById("me-result").textContent = `${res.status}\\n${text}`;
            log(`  → ${res.status}  ${JSON.stringify(data)}`, !res.ok);
        }
    </script>
</body>
</html>
"""

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    """ログインリクエストのボディ。"""

    username: str
    password: str


def create_token(username: str) -> str:
    """JWT を生成して返す。ペイロードに sub（ユーザー名）と exp（有効期限）を含める。"""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    """JWT を検証し sub（ユーザー名）を返す。無効なら 401 を raise する。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無効なトークンです")


@app.get("/")
async def get():
    """学習用 HTML を返す。"""
    return HTMLResponse(html)


@app.post("/token")
async def login(req: LoginRequest):
    """ユーザー名とパスワードを検証し、JWT を返す。"""
    if USERS.get(req.username) != req.password:
        raise HTTPException(status_code=401, detail="ユーザー名またはパスワードが違います")
    return {"access_token": create_token(req.username), "token_type": "bearer"}


@app.get("/me")
async def me(authorization: str = Header(default="")):
    """Authorization: Bearer <token> ヘッダーを検証し、ユーザー情報を返す。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization ヘッダーがありません")
    token = authorization[len("Bearer "):]
    username = verify_token(token)
    return {"username": username, "message": f"こんにちは, {username}!"}
