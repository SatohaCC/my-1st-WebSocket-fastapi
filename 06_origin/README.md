# 06 Origin 検証

フロントエンドが別ドメインにある想定で、許可されていない Origin からの WebSocket 接続を拒否する。

## 起動

```bash
poetry run uvicorn 06_origin.main:app --reload
```

## 確認

**許可される接続**: http://localhost:8000 を開いてメッセージを送る → 正常に動く
- http://127.0.0.1:8000/ は接続できない（`localhost` と `127.0.0.1` は別オリジン扱い）

**拒否の動作を確認したいとき**: `ALLOWED_ORIGINS` から `"http://localhost:8000"` を外して再起動する。

---

## 実装の解説

### フロントエンド（JavaScript）

変更なし。`ws.onclose` でサーバーに拒否されたときの `code` を表示するだけ追加している。

```javascript
ws.onclose = function (event) {
    console.log("切断: code=" + event.code);
};
```

拒否された場合、ブラウザ側では接続が確立されずに `onclose` が発火する（`onopen` は呼ばれない）。

---

### バックエンド（Python）

#### HTTPConnection の継承

`WebSocket` は `HTTPConnection` を継承している（[Docs/starlette/requests.py](../Docs/starlette/requests.py)）。HTTP リクエストと同様に接続時の情報を読み取れる。

```python
websocket.headers      # Headers オブジェクト（scope から遅延生成）
websocket.query_params # QueryParams オブジェクト (?token=xxx)
websocket.cookies      # dict[str, str]（headers の "cookie" を解析して生成）
websocket.client       # Address(host="127.0.0.1", port=12345) または None
websocket.url          # URL オブジェクト
websocket.path_params  # dict（/ws/{client_id} の client_id など）
```

これらはすべて `accept()` を呼ぶ前から読み取れる。WebSocket ハンドシェイクは HTTP アップグレードリクエストとして始まるため、ハンドシェイク時点でヘッダーやクエリパラメータが揃っている。

また、各プロパティは遅延評価（アクセス時に初めて生成）かつキャッシュされる。

```python
# requests.py
@property
def headers(self) -> Headers:
    if not hasattr(self, "_headers"):         # 初回アクセス時だけ生成
        self._headers = Headers(scope=self.scope)
    return self._headers
```

#### Origin ヘッダーの検証

```python
ALLOWED_ORIGINS = {"http://localhost:8000"}

origin = websocket.headers.get("origin")
if origin not in ALLOWED_ORIGINS:
    await websocket.send_denial_response(
        JSONResponse({"detail": "forbidden", "origin": origin}, status_code=403)
    )
    return

await websocket.accept()
```

ブラウザは WebSocket 接続時に必ず `Origin` ヘッダーを送る。これはページが読み込まれたオリジン（`scheme://host:port`）であり、JavaScript から改ざんできない。

#### HTTP の CORS との違い

| | HTTP CORS | WebSocket Origin |
|--|--|--|
| 誰がブロックするか | **ブラウザ**（サーバーが許可しなければレスポンスを捨てる） | **サーバー**（ブラウザはブロックしない） |
| FastAPI の対応 | `CORSMiddleware` | 自前で `Origin` ヘッダーを検証する |
| `CORSMiddleware` の効果 | HTTP リクエストに適用される | WebSocket には**適用されない** |

#### send_denial_response の内部動作

`accept()` を呼ぶ前に HTTP レスポンスを返して接続を拒否するメソッド。

```python
# websockets.py
async def send_denial_response(self, response: Response) -> None:
    if "websocket.http.response" in self.scope.get("extensions", {}):
        await response(self.scope, self.receive, self.send)
    else:
        raise RuntimeError(...)
```

`response(self.scope, self.receive, self.send)` は `Response.__call__()` を呼び出す。`Response.__call__()` は `scope["type"] == "websocket"` を検知すると、送信関数を `_wrap_websocket_denial_send()` でラップする（[Docs/starlette/responses.py](../Docs/starlette/responses.py)）。

```python
# responses.py
async def __call__(self, scope, receive, send):
    if scope["type"] == "websocket":
        send = self._wrap_websocket_denial_send(send)  # ← ラップする
    await send({"type": "http.response.start", "status": self.status_code, ...})
    await send({"type": "http.response.body", "body": self.body})

def _wrap_websocket_denial_send(self, send):
    async def wrapped(message):
        if message["type"] in {"http.response.start", "http.response.body"}:
            message = {**message, "type": "websocket." + message["type"]}
            # "http.response.start" → "websocket.http.response.start"
            # "http.response.body"  → "websocket.http.response.body"
        await send(message)
    return wrapped
```

つまり `Response` は HTTP 用に `http.response.start` / `http.response.body` を送るが、WebSocket コンテキストでは自動的に `websocket.` プレフィックスに書き換えてから送る。これにより通常の `JSONResponse` をそのまま `send_denial_response()` に渡せる。
