# 03 再接続（Reconnect）

切断されたときに自動で再接続するクライアント実装。サーバー側は 01_echo と同じエコー。

## 起動

```bash
poetry run uvicorn 03_reconnect.main:app --reload
```

## 確認

1. http://localhost:8000 を開く
2. uvicorn を `Ctrl+C` で止める → 「切断。1秒後に再接続します」と表示される
3. uvicorn を再起動する → 自動で再接続され「接続しました」と表示される

---

## 実装の解説

### フロントエンド（JavaScript）

#### 再接続の仕組み

```javascript
function connect() {
    ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = function () {
        retryDelay = 1000;   // 成功したらディレイをリセット
    };

    ws.onclose = function () {
        setTimeout(function () {
            retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
            connect();       // 再帰的に呼び出す
        }, retryDelay);
    };

    ws.onerror = function () {
        ws.close();          // onclose に処理を一本化
    };
}
```

`ws.onclose` が発火したら `setTimeout` で遅延させてから `connect()` を再帰呼び出しする。`WebSocket` は一度閉じると再利用できないため、毎回 `new WebSocket(...)` で作り直す。

#### onerror を onclose に一本化する理由

WebSocketでエラーが起きたとき、ブラウザは必ず `onerror → onclose` の順に発火する。両方に再接続処理を書くと `connect()` が2回呼ばれてしまうため、`onerror` では `ws.close()` を呼ぶだけにして再接続処理は `onclose` に一本化する。

#### Exponential Backoff（指数バックオフ）

再接続のたびにウェイト時間を2倍にし、上限（30秒）で頭打ちにする。

```
1秒 → 2秒 → 4秒 → 8秒 → 16秒 → 30秒 → 30秒 → ...
```

```javascript
retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
```

固定間隔で再接続すると、サーバー障害時に大量のクライアントが一斉に再接続してサーバーを叩き続ける（Thundering Herd）。指数バックオフはこれを緩和するための定番パターン。接続が成功したら `retryDelay = 1000` でリセットする。

#### ws.readyState

送信前に接続状態を確認している。

```javascript
if (ws.readyState === WebSocket.OPEN) {
    ws.send(input.value);
}
```

| 値 | 定数 | 意味 |
|----|------|------|
| 0 | `WebSocket.CONNECTING` | 接続中 |
| 1 | `WebSocket.OPEN` | 接続済み（送受信可能） |
| 2 | `WebSocket.CLOSING` | 切断処理中 |
| 3 | `WebSocket.CLOSED` | 切断済み |

`OPEN` 以外のときに `send()` を呼ぶと例外が投げられるため、切断中に送信しようとしてもメッセージが捨てられる（このコードでは未送信メッセージの保持はしていない）。

---

### バックエンド（Python）

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        pass
```

01_echo との違いは `except WebSocketDisconnect: pass` を書いている点のみ。

01_echo では切断時に `WebSocketDisconnect` がハンドリングされずにスタックトレースがログに出力されていた。このコードでは `pass` で握りつぶしている。再接続はクライアント側が担うため、サーバー側は切断を検知したら静かに終了するだけでよい。
