# 17 例外処理の改善

16 章のコードに残っていた `broadcast` と `heartbeat` の例外捕捉漏れを修正した章。
フロントエンドは 16 章と同一。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 17_exception_handling.main:app --reload

# フロントエンド（別ターミナル）
cd 17_exception_handling/frontend
npm install   # 初回のみ
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`main.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

 **フロントエンドの変更なし**: `frontend/` は 16 章のコードをそのまま使用している。
 今章の修正はすべてバックエンド（`main.py`）のみ。

16 章と同じ手順で動作する。違いはサーバーログにエラーが出なくなる点。

---

## 実装の解説

### 問題: `WebSocketDisconnect` しか捕捉していなかった

16 章の `broadcast` と `heartbeat` は、送信失敗時に `WebSocketDisconnect` だけを捕捉していた。

```python
# 16 章（修正前）
try:
    await ws.send_json(message)
except WebSocketDisconnect:   # ← この1種類しか捕捉できない
    dead.append(ws)
```

### なぜ `WebSocketDisconnect` では不十分か

`WebSocketDisconnect` は **`receive()` 系の呼び出し**でクライアントの切断を検知したときに発生する。
`send()` 系の呼び出しで切断済み接続に書き込もうとすると、Starlette は別の例外を投げる。

| 操作 | クライアント切断時の例外 |
|------|----------------------|
| `receive_json()` | `WebSocketDisconnect` |
| `send_json()` | `RuntimeError`（接続状態が DISCONNECTED の場合）|

クライアントが切断してから Python の asyncio がそれを処理するまでの間（次の `await` ポイントまで）に
`broadcast` が走ると、`send_json()` が `RuntimeError` を投げて `except WebSocketDisconnect` を素通りする。

結果として:
- `dead` リストに入らないのでゾンビ接続がリストに残り続ける
- `broadcast` がループの途中で例外終了するため、以降のクライアントにメッセージが届かない

### 修正: `except Exception` に変更

```python
# 17 章（修正後）
async def broadcast(self, message: dict):
    dead: list[WebSocket] = []
    for _, ws in self.connections:
        try:
            await ws.send_json(message)
        except Exception:
            # WebSocketDisconnect だけでなく RuntimeError も捕捉する
            dead.append(ws)
    for ws in dead:
        self.disconnect(ws)
```

`heartbeat` の ping 送信も同じ理由で修正する。

```python
async def heartbeat(websocket: WebSocket, pong_event: asyncio.Event):
    while True:
        await asyncio.sleep(PING_INTERVAL)
        pong_event.clear()
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:   # ← RuntimeError も含めて捕捉してループを抜ける
            break
        ...
```

### `except Exception` の範囲について

`Exception` は Python の組み込み例外階層で `BaseException` の直下に位置し、
`RuntimeError`・`WebSocketDisconnect`・`OSError` など送信失敗につながる例外を網羅する。
`KeyboardInterrupt` や `SystemExit`（`BaseException` の直接サブクラス）は捕捉しない。

送信の失敗はすべて「接続が使えない」という同じ意味を持つため、種類を問わず `dead` に入れる方針で問題ない。
