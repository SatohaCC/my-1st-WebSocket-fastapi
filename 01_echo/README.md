# 01 Echo

https://fastapi.tiangolo.com/ja/advanced/websockets/

送ったメッセージをそのまま返すだけのシンプルなWebSocket。

## 起動

```bash
poetry run uvicorn 01_echo.main:app --reload
```

## 確認

http://localhost:8000 を開いてメッセージを送ると、サーバーがそのまま返してくる。

---

## 実装の解説

### 接続の確立

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
```

`@app.websocket("/ws")` でWebSocketエンドポイントを定義する。ブラウザが `ws://localhost:8000/ws` に接続してきたとき、この関数が呼ばれる。

`accept()` を呼ぶまで接続は保留状態のまま。`accept()` を呼んで初めてデータの送受信ができるようになる（呼ばずに `receive_text()` を呼ぶと `RuntimeError` になる）。

---

### メッセージのループ

```python
while True:
    data = await websocket.receive_text()
    await websocket.send_text(f"Message text was: {data}")
```

`receive_text()` はメッセージが来るまでここで待ち続ける（非同期に）。メッセージが来たら `send_text()` で返す、を繰り返す。

`while True` のまま終了処理を書いていないため、クライアントが切断すると `receive_text()` が `WebSocketDisconnect` を投げてこの関数ごと終了する（02_chat ではこれを `except` で捕まえて後処理している）。

---

### HTMLの配信

```python
@app.get("/")
async def get():
    return HTMLResponse(html)
```

ブラウザが `http://localhost:8000/` にアクセスすると、Python文字列として定義したHTMLをそのまま返す。このHTMLの中のJSが `ws://localhost:8000/ws` へのWebSocket接続を開く。

HTTP（`/`）とWebSocket（`/ws`）は別のエンドポイントで、プロトコルも異なる。
