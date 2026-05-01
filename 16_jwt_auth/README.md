# 16 JWT 認証

14章の再接続機能に JWT 認証を追加した章。
接続前に REST エンドポイントでログインし、取得した JWT を WebSocket 接続時のクエリパラメータで渡す。

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

1. ユーザー名・パスワードを入力して「ログイン」→ JWT を取得、接続フォームに切り替わる
2. 「接続」でチャットに参加する
3. 別タブで別ユーザーとしてログインして会話できることを確認する
4. 間違ったパスワードを入力するとエラーメッセージが表示される
5. バックエンドを止めると自動再接続する（JWT は再接続時にも使い回す）
6. 「ログアウト」で切断・トークン破棄・チャット履歴クリア

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

### フロントエンド: 2フェーズ UI

14章との最大の違いは、接続前にログインフェーズを挟む点。

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

14章の `usernameRef`（setTimeout のクロージャ問題）と同じ理由で `tokenRef` を使う。

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

14章では `usernameRef` を使って `connectWithUsername(usernameRef.current)` を呼んでいたが、
ch16 では JWT がユーザー名を内包しているため `usernameRef` は不要になった。

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
