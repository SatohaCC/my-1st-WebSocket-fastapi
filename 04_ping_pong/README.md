# 04 Ping/Pong（ハートビート）

サーバーが定期的に ping を送り、クライアントが pong を返すことで接続が生きているか確認する。一定時間 pong が返ってこなければサーバーが接続を強制切断する。

03_reconnect の再接続ロジックをそのまま組み込んでいるため、切断後は自動で再接続する。

## 起動

```bash
poetry run uvicorn 04_ping_pong.main:app --reload
```

## 確認

1. http://localhost:8000 を開く
2. 「最後のPing」が10秒ごとに更新されることを確認する
3. uvicorn を止める → 自動で再接続されることを確認する

---

## 実装の解説

### なぜ Ping/Pong が必要か

03_reconnect はサーバーが落ちたときの再接続を実装したが、「接続は張られているのに通信が死んでいる」状態は検知できない。

- NAT（ルーターの変換テーブル）がタイムアウトして古いエントリを破棄した
- モバイルネットワークでスリープ復帰後に接続が無効になった

これらは TCP レベルでは接続中に見えるため、`receive_text()` / `send_text()` を呼ぶまでサーバーは切断を知ることができない。Ping/Pong はサーバーが能動的に疎通確認することでこの問題を解決する。

---

### バックエンド（Python）

#### 全体構造

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pong_event = asyncio.Event()

    async def heartbeat():
        ...

    task = asyncio.create_task(heartbeat())  # ハートビートを並行実行
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "pong":
                pong_event.set()
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()  # 受信ループが終わったらハートビートも止める
```

`asyncio.create_task()` でハートビートループを受信ループと並行して動かす。どちらかが終わったとき、`finally` でもう一方を `cancel()` して確実に終了させる。

#### ハートビートループ

```python
async def heartbeat():
    while True:
        await asyncio.sleep(PING_INTERVAL)   # 10秒待つ
        pong_event.clear()
        try:
            await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            break                             # 送信失敗 = 切断済み
        try:
            await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
        except asyncio.TimeoutError:
            await websocket.close(code=1001, reason="pong timeout")
            break                             # 5秒以内に pong が来なければ強制切断
```

#### asyncio.Event

このコードでは heartbeat と受信ループが**別々に動いている**。

```
heartbeat()   ─── ping を送って、pong を待つ
受信ループ    ─── メッセージを受け取る
```

heartbeat は ping を送った後「pong が返ってきたか」を知りたいが、pong を受け取るのは受信ループ側。**別々のループをまたいで通知する手段**として `asyncio.Event` を使う。

```
heartbeat:  ping送信 → pong_event.wait() でここで止まる……
                                                ↑
受信ループ:                       "pong"受信 → pong_event.set() でフラグを立てる
                                                ↓
heartbeat:  再開。次のループへ
```

3つのメソッドだけ覚えれば使える。

| メソッド | やること |
|---------|---------|
| `event.clear()` | フラグを False にリセット |
| `event.set()` | フラグを True にして、`wait()` で止まっている相手を起こす |
| `await event.wait()` | フラグが True になるまでここで止まる |

`clear()` を ping のたびに呼んでいる理由は、前回の pong が遅れて届いたとき「今回の pong が返ってきた」と誤判定されないようにするため。

`asyncio.wait_for()` はタイムアウト付きで `await` するラッパー。5秒以内に `set()` されなければ `TimeoutError` を投げる。

```python
pong_event.clear()
await websocket.send_json({"type": "ping"})
try:
    await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
    # ↑ 受信ループが set() するまでここで止まる。5秒超えたら TimeoutError
except asyncio.TimeoutError:
    await websocket.close(code=1001, reason="pong timeout")
```

---

### フロントエンド（JavaScript）

#### ping を受け取ったら pong を返す

```javascript
ws.onmessage = function (event) {
    const data = JSON.parse(event.data);
    if (data.type === "ping") {
        ws.send(JSON.stringify({ type: "pong" }));
        return;
    }
    addMessage(data.message);
};
```

メッセージを受け取ったら `type` を確認し、`"ping"` なら即座に `"pong"` を返す。それ以外は通常のメッセージとして表示する。

#### 再接続ロジック（03_reconnect から流用）

`ws.onclose` で Exponential Backoff を使って再接続する（03_reconnect と同じ実装）。サーバーが pong timeout で接続を閉じたときも `onclose` が発火するため、自動で再接続される。
