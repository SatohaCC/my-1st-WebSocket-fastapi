# 02 複数クライアント + ブロードキャスト

https://fastapi.tiangolo.com/ja/advanced/websockets/#handling-disconnections-and-multiple-clients

`ConnectionManager` で複数クライアントの接続を管理し、全員にメッセージをブロードキャストする。

## 起動

```bash
poetry run uvicorn 02_chat.main:app --reload
```

## 確認

1. http://localhost:8000 を複数のタブで開く
2. どれかのタブからメッセージを送ると、全タブに届く
3. タブを閉じると「Client #xxx left the chat」が全員に通知される

---

## 実装の解説

### ConnectionManager

接続中の全クライアントを `active_connections` リストで管理するクラス。

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
```

| メソッド | 役割 |
|---------|------|
| `connect()` | 接続を受け入れ、リストに追加 |
| `disconnect()` | リストから削除 |
| `send_personal_message()` | 特定の1人にだけ送信 |
| `broadcast()` | 全員に送信 |

---

### クライアントIDをURLパスで受け取る

```python
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
```

ブラウザ側では `Date.now()`（タイムスタンプ）をIDとして使い、`ws://localhost:8000/ws/1234567890` のようにURLに埋め込む。サーバーはパスパラメータとして受け取る。

---

### メッセージ送信の流れ

```python
data = await websocket.receive_text()
await manager.send_personal_message(f"You wrote: {data}", websocket)  # 自分だけに
await manager.broadcast(f"Client #{client_id} says: {data}")          # 全員に
```

送信者には `"You wrote: ..."` を個別送信し、全員（自分含む）には `"Client #xxx says: ..."` をブロードキャストする。

---

### 切断の検知

```python
try:
    while True:
        data = await websocket.receive_text()
        ...
except WebSocketDisconnect:
    manager.disconnect(websocket)
    await manager.broadcast(f"Client #{client_id} left the chat")
```

クライアントがタブを閉じると `receive_text()` が `WebSocketDisconnect` 例外を投げる。それを `except` で捕まえてリストから削除し、残りの全員に退出通知を送る。

#### WebSocketDisconnect とは

Starletteが提供する例外クラス。クライアントとの接続が切れたときに `receive_text()` / `receive_bytes()` から送出される。

```python
class WebSocketDisconnect(Exception):
    def __init__(self, code: int = 1000, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or ""
```

`except WebSocketDisconnect` を書かずに放置すると、切断のたびにサーバーがエラーログを吐き、`active_connections` にゾンビ接続が残り続けるため必ず処理する。

#### WebSocketDisconnect が発生する条件

ソースコードから、発生経路は **2つ** ある。

---

**経路1: 受信時 — クライアントが切断した**

`receive_text()` / `receive_bytes()` / `receive_json()` を呼んだとき、受け取った ASGIメッセージの `type` が `"websocket.disconnect"` だった場合。

```python
# Starlette内部
async def receive_text(self) -> str:
    message = await self.receive()
    self._raise_on_disconnect(message)        # ← ここで判定
    return cast(str, message["text"])

def _raise_on_disconnect(self, message: Message) -> None:
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message["code"], message.get("reason"))
```

`receive_text()` 自身が切断を検知しているのではなく、ASGIランタイムから届いたメッセージの種別で判断している。`code` と `reason` はクライアントが送ってきた値がそのまま入る。

---

**経路2: 送信時 — すでに切れていた接続に送ろうとした**

`send_text()` / `send_bytes()` を呼んだとき、内部の `send()` が `OSError` を受け取った場合。`code=1006`（Abnormal Closure）固定で送出される。

```python
# Starlette内部 send() メソッド
try:
    await self._send(message)
except OSError:
    self.application_state = WebSocketState.DISCONNECTED
    raise WebSocketDisconnect(code=1006)   # ← OSError を WebSocketDisconnect に変換
```

クライアントがネットワーク断などで正常なクローズハンドシェイクを行わずに消えた場合、サーバーは次に「送ろうとしたとき」に初めて切断を知る。

---

まとめると:

| 発生元 | タイミング | code |
|--------|-----------|------|
| `receive_text()` など | 次のメッセージを待っていたら切断通知が来た | クライアント送信値 |
| `send_text()` など | 送ろうとしたら既に繋がっていなかった | 1006 固定 |

#### WebSocketState

`WebSocket` オブジェクトは `client_state` と `application_state` の2つの状態を持つ。

```python
class WebSocketState(enum.Enum):
    CONNECTING = 0
    CONNECTED  = 1
    DISCONNECTED = 2
    RESPONSE   = 3
```

| 状態変数 | 意味 |
|---------|------|
| `client_state` | クライアント（ブラウザ）側の接続状態 |
| `application_state` | サーバー（アプリ）側の接続状態 |

`accept()` を呼ぶと両方が `CONNECTED` に遷移し、`receive_text()` は `application_state == CONNECTED` でなければ `RuntimeError` を投げる。これが `accept()` を最初に呼ばなければならない理由。

> **Starlette とは**
> FastAPIが内部で使っているASGI Webフレームワーク。WebSocket・ルーティング・ミドルウェアなどの低レベルな仕組みはStarletteが担っており、FastAPIはその上にDI・バリデーション・OpenAPI生成などを追加している。`WebSocketDisconnect` もStarletteが定義しており、FastAPIは再エクスポートしているだけ。
