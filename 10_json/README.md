# 10 JSON メッセージ

`receive_json` / `send_json` を使い、テキストの代わりに JSON オブジェクトを送受信する。
メッセージに `type` フィールドを持たせることで、クライアント・サーバー両側で処理を分岐できる。

## 起動

```bash
poetry run uvicorn 10_json.main:app --reload
```

## 確認

1. http://localhost:8000 を複数のタブで開く
2. それぞれ異なる名前で入室する
3. どちらかのタブでメッセージを送ると、全員に届く
4. 退室すると、残ったタブに退室通知が届く

---

## 実装の解説

### メッセージプロトコル

このチャットではすべての WebSocket メッセージを JSON オブジェクトとして定義する。

| 方向 | type | フィールド | 意味 |
|------|------|-----------|------|
| Client → Server | `"message"` | `text` | チャットメッセージを送信 |
| Server → Client | `"join"` | `username` | 誰かが入室した |
| Server → Client | `"leave"` | `username` | 誰かが退室した |
| Server → Client | `"message"` | `username`, `text` | チャットメッセージを受信 |
| Server → Client | `"error"` | `text` | 不正なリクエストへのエラー応答 |

プレーンテキストで `"[alice] hello"` と送るのに対し、JSON にすると送信者・本文・種別を個別フィールドで扱えるため、クライアント側の表示ロジックがシンプルになる。

### receive_json / send_json

```python
data = await websocket.receive_json()
# → JSON 文字列を受け取り、dict/list にパースして返す

await websocket.send_json({"type": "message", "username": "alice", "text": "hello"})
# → dict を JSON 文字列にシリアライズして送信
```

Starlette の実装は以下のとおり。`text` モード（デフォルト）では JSON を UTF-8 文字列として送受信する。

```python
# Docs/starlette/websockets.py
async def receive_json(self, mode: str = "text") -> Any:
    message = await self.receive()
    self._raise_on_disconnect(message)
    if mode == "text":
        text = message["text"]
    else:
        text = message["bytes"].decode("utf-8")
    return json.loads(text)

async def send_json(self, data: Any, mode: str = "text") -> None:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if mode == "text":
        await self.send({"type": "websocket.send", "text": text})
    else:
        await self.send({"type": "websocket.send", "bytes": text.encode("utf-8")})
```

### type による分岐

サーバー側で受信した JSON を `type` フィールドで分岐する。

```python
data = await websocket.receive_json()

if data.get("type") == "message":
    await manager.broadcast({
        "type": "message",
        "username": username,
        "text": data.get("text", ""),
    })
else:
    await websocket.send_json({
        "type": "error",
        "text": f"Unknown type: {data.get('type')!r}",
    })
```

クライアント側も同様に `type` で分岐し、`join`/`leave` はグレーのシステムメッセージ、`error` は赤字、`message` は通常のチャット行として描画する。

```javascript
ws.onmessage = function (event) {
    const msg = JSON.parse(event.data);
    if (msg.type === "message") {
        addMessage(`${msg.username}: ${msg.text}`);
    } else if (msg.type === "join") {
        addMessage(`[${msg.username} が入室しました]`, "system");
    } else if (msg.type === "leave") {
        addMessage(`[${msg.username} が退室しました]`, "system");
    } else if (msg.type === "error") {
        addMessage(`[エラー: ${msg.text}]`, "error");
    }
};
```

### 不正 JSON のエラー処理

`receive_json` は内部で `json.loads` を呼ぶため、クライアントが壊れた JSON を送ると `json.JSONDecodeError` が発生する。これを捕捉してエラーを返し、接続は切らずに継続する。

```python
try:
    data = await websocket.receive_json()
except json.JSONDecodeError:
    await websocket.send_json({"type": "error", "text": "Invalid JSON"})
    continue
```
