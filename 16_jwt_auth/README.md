# 16 JWT 認証 + WebSocket チャット

15_5 章（JWT 学習）に WebSocket チャットを追加した章。
REST エンドポイント（`POST /token`、`GET /me`）は 15_5 から引き継ぎ、
取得した JWT を WebSocket 接続時のクエリパラメータで渡してチャットに参加する。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 16_jwt_auth.main:app --reload

# フロントエンド（別ターミナル）
cd 16_jwt_auth/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`main.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

1. ユーザー名・パスワードを入力して「ログイン」→ JWT を取得、色分け表示とペイロードデコードを確認する
2. 「正しいトークンで GET /me」で 200、「トークンなし」で 401 を確認する
3. 「接続」で WebSocket チャットに参加する
4. 別タブで別ユーザーとしてログインして会話できることを確認する
5. 間違ったパスワードを入力するとエラーメッセージが表示される
6. バックエンドを止めると自動再接続する（JWT は再接続時にも使い回す）
7. 「ログアウト」で切断・トークン破棄・チャット履歴クリア

---

## 実装の解説

### なぜ WebSocket に JWT が必要か

ch07/ch08 は任意の文字列をトークンとして使い、サーバーが DB などで照合する方式だった。
JWT はトークン自体に署名とペイロードが含まれるため、DB を参照せずに検証できる。

```
ヘッダー.ペイロード.署名
eyJ...  .eyJzdWIiOiJhbGljZSIsImV4cCI6...  .署名
```

ペイロードには `sub`（ユーザー名）と `exp`（有効期限）が入る。
サーバーは秘密鍵で署名を検証するだけでユーザー名と有効期限を確認できる。

### バックエンド: JWT の生成と検証

```python
SECRET_KEY = "dev-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")  # ユーザー名を返す
    except jwt.InvalidTokenError:
        return None  # 署名不正・期限切れなど
```

`jwt.InvalidTokenError` は PyJWT が提供する基底例外で、署名不正・期限切れ・不正フォーマットをまとめて捕捉する。

### バックエンド: ログインエンドポイント

WebSocket ではなく通常の HTTP POST エンドポイントでトークンを発行する。

```python
@app.post("/token")
async def login(req: LoginRequest):
    if USERS.get(req.username) != req.password:
        raise HTTPException(status_code=401, detail="ユーザー名またはパスワードが違います")
    return {"access_token": create_token(req.username), "token_type": "bearer"}
```

### バックエンド: 保護された REST エンドポイント（GET /me）

15_5 と同じ構造。`Authorization: Bearer <token>` ヘッダーを検証し、ユーザー名を返す。

```python
@app.get("/me")
async def me(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization ヘッダーがありません")
    username = verify_token(authorization[len("Bearer "):])
    if not username:
        raise HTTPException(status_code=401, detail="無効なトークンです")
    return {"username": username, "message": f"こんにちは, {username}!"}
```

`verify_token` は WebSocket エンドポイントと共用するため `str | None` を返す設計にし、
`/me` 側で `None` を検知して `HTTPException` を raise する。

### バックエンド: WebSocket 接続時の JWT 検証

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    username = verify_token(token)
    if not username:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return
    # username は JWT のペイロードから取得済み。URL に username を渡す必要がない
    await manager.connect(username, websocket)
```

1008 は WebSocket の close コード「Policy Violation」で、認証失敗を示す慣習的なコード。

### なぜクエリパラメータでトークンを渡すのか

ブラウザの WebSocket API（`new WebSocket(url)`）はカスタム HTTP ヘッダーを設定できない。
`Authorization: Bearer <token>` を送れないため、クエリパラメータで代替する。

```
ws://localhost:8000/ws?token=eyJ...
```

トレードオフ: クエリパラメータはサーバーのアクセスログに残りやすい。
実務では短命な「チケットトークン」を REST で発行してそれを渡す方法も使われる。

### フロントエンド: UI 構成

15_5 の UI（①ログイン・②JWT表示・③GET /me）に④WebSocket チャットを追加した5セクション構成。
ログインすると JWT の色分け表示とペイロードデコードが現れ、GET /me で HTTP 認証を試してから
WebSocket に接続できる。

ログインフォームとログアウトは 15_5 と同じ2フェーズ構造を維持する。

```tsx
{token === null ? (
  // フェーズ1: ログイン（REST POST /token）
  <div>
    <input placeholder="ユーザー名" />
    <input placeholder="パスワード" type="password" />
    <button onClick={login}>ログイン</button>
  </div>
) : (
  // フェーズ2: WebSocket 接続（JWT を使用）
  <div>
    <span>ユーザー: {username}</span>
    <button onClick={connect}>接続</button>
    <button onClick={logout}>ログアウト</button>
  </div>
)}
```

### フロントエンド: tokenRef で再接続時に JWT を参照する

15_5 の `token` state を再接続のタイマーコールバックから参照するために `tokenRef` を使う。

```tsx
const tokenRef = useRef<string | null>(null);
useEffect(() => { tokenRef.current = token; }, [token]);

// setTimeout 内で呼ばれる関数。tokenRef.current で常に最新の JWT を参照できる
function connectWithToken() {
    if (wsRef.current || !tokenRef.current) return;
    const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(tokenRef.current)}`);
    ...
}
```

JWT がユーザー名を内包しているため、`usernameRef` は不要になった。`tokenRef` 1本で済む。

### フロントエンド: ログアウト処理

ログアウトは「切断」＋「トークン破棄」＋「チャット履歴クリア」の3操作。

```tsx
function logout() {
    isManualRef.current = true;  // 再接続を抑止
    clearPingTimeout();
    if (wsRef.current) {
        wsRef.current.close();   // 接続中なら切断
    } else {
        setStatus("disconnected");
    }
    setToken(null);    // トークンを破棄 → ログインフォームに戻る
    setPassword("");
    setMessages([]);
}
```

`setToken(null)` で `token === null` になると UI がログインフォームに切り替わる。
