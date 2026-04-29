# 05 iter_text / iter_json

`while True` + `try/except WebSocketDisconnect` を `async for` に置き換えるパターン。動作は 01_echo と同じ。

## 起動

```bash
poetry run uvicorn 05_iter.main:app --reload
```

---

## 実装の解説

### 01_echo との比較

```python
# 01_echo（while True パターン）
await websocket.accept()
try:
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
except WebSocketDisconnect:
    pass

# 05_iter（iter_text パターン）
await websocket.accept()
async for data in websocket.iter_text():
    await websocket.send_text(f"Message text was: {data}")
```

動作は同じで、`iter_text()` が `while True` と `except WebSocketDisconnect` を内部で担う。

---

### iter_text の内部実装（Starlette）

```python
async def iter_text(self) -> AsyncIterator[str]:
    try:
        while True:
            yield await self.receive_text()
    except WebSocketDisconnect:
        pass
```

`WebSocketDisconnect` が来るとループが終わる。これを `async for` で受け取るとイテレーションが終了する。

---

### async for とは

通常の `for` がイテレータを同期的に消費するのに対し、`async for` は非同期イテレータを消費する。

```python
async for data in websocket.iter_text():
    # data を受け取るたびにここが実行される
    # 切断されるとループを抜ける
```

非同期イテレータは `__aiter__` と `__anext__` を持つオブジェクト。`__anext__` が `StopAsyncIteration` を投げるとループが終わる（`iter_text` の場合は `WebSocketDisconnect` を内部で捕まえて `StopAsyncIteration` に変換している）。

---

### iter_text を使えない場面

切断時に後処理が必要な場合（例: 02_chat の `manager.disconnect()` や退出通知）は `iter_text` が `WebSocketDisconnect` を握りつぶすため使えない。

```python
# NG：切断を検知できない
async for data in websocket.iter_text():
    await manager.broadcast(...)
# ← ここで切断を知ることができず manager.disconnect() を呼べない

# OK：切断後の処理が必要な場合は while True パターン
try:
    while True:
        data = await websocket.receive_text()
        await manager.broadcast(...)
except WebSocketDisconnect:
    manager.disconnect(websocket)          # 後処理できる
    await manager.broadcast("left chat")
```

`iter_text` は後処理が不要なシンプルなエコー系の実装に向いている。

---

### iter_json

`receive_json()` に対応するバージョン。使い方は同じ。

```python
async for data in websocket.iter_json():
    await websocket.send_json({"echo": data})
```
