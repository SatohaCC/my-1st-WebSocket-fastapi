# 13 Ping/Pong ハートビート

サーバーが定期的に ping を送り、クライアントが pong を返すことでサイレント切断を検知する。
12章のチャット実装にハートビートを追加した章。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 13_ping_pong.main:app --reload

# フロントエンド（別ターミナル）
cd 13_ping_pong/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。
バックエンドのターミナルに接続・切断ログと pong タイムアウトログが出る。

## 確認

1. 入室して 10 秒待つと「最後の Ping」が更新される
2. ping/pong の往復を DevTools で確認する
   1. `F12` で DevTools を開き **Network** タブを選ぶ
   2. 入室して WebSocket 接続する
   3. Network に `ws` という行が現れるのでクリック
   4. **Messages** タブを選ぶ
   5. 10 秒ごとに `{"type":"ping"}` と `{"type":"pong"}` が交互に現れる
      - 白背景（↓）= サーバー → 自分、緑背景（↑）= 自分 → サーバー
   - Messages が1つのタブにまとまるのは Chrome の機能。WebSocket は HTTP と違い
     1本の TCP 接続が維持され続けるため、その接続を流れるフレームが時系列で並ぶ。
3. ネットワークを切断（DevTools の Throttling → Offline）すると 5 秒後にサーバー側がタイムアウトログを出して切断する

---

## 実装の解説

### なぜ ping/pong が必要か

WebSocket は TCP の上に乗っているため、ネットワークが静かに途切れた場合（NAT タイムアウト、Wi-Fi 切断など）に
サーバーは接続が生きているように見えたまま気づけない。
定期的にメッセージを送り合うことで死活を確認する。

### サーバー側: asyncio.Event で pong を待つ

各接続に対して独立したハートビートタスクを起動する。

```python
PING_INTERVAL = 10  # 秒ごとに ping を送る
PONG_TIMEOUT = 5    # この秒数以内に pong が返らなければ切断

async def heartbeat(websocket: WebSocket, pong_event: asyncio.Event):
    while True:
        await asyncio.sleep(PING_INTERVAL)
        pong_event.clear()
        await websocket.send_json({"type": "ping"})
        try:
            await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
        except asyncio.TimeoutError:
            await websocket.close(code=1001, reason="pong timeout")
            break
```

`asyncio.Event` は「フラグ」のようなもので、`event.set()` で立てて `event.wait()` で待つ。
`asyncio.wait_for` でタイムアウトを設定し、時間内に pong が来なければ切断する。

受信ループ側で pong を受け取ったら `pong_event.set()` を呼ぶ。

```python
if data.get("type") == "pong":
    pong_event.set()
```

### サーバー側: タスクのライフサイクル管理

ハートビートは `asyncio.create_task()` で受信ループと並行して動かす。
接続が切れたときに `task.cancel()` でタスクも終了させる。

```python
task = asyncio.create_task(heartbeat(websocket, pong_event))
try:
    while True:
        data = await websocket.receive_json()
        ...
except WebSocketDisconnect:
    manager.disconnect(websocket)
    await manager.broadcast({"type": "leave", "username": username})
finally:
    task.cancel()  # 例外・正常終了どちらでも必ず実行
```

`finally` を使うことで、正常切断・タイムアウト切断・例外どのケースでもタスクがリークしない。

### クライアント側: ping を受け取ったら pong を返す

`ServerMessage` に `ping` 型を追加し、受け取ったらすぐ pong を送り返す。
チャットメッセージとは異なり、UI には表示しない。

```tsx
ws.onmessage = (e: MessageEvent<string>) => {
    const msg: ServerMessage = JSON.parse(e.data);
    if (msg.type === "ping") {
        setLastPing(new Date().toLocaleTimeString());  // UI に最終 ping 時刻を表示
        ws.send(JSON.stringify({ type: "pong" }));     // 即座に pong を返す
        resetPingTimeout(ws);                          // タイムアウトをリセット
        return;                                        // メッセージ履歴には追加しない
    }
    setMessages((prev) => { ... });
};
```

`return` で早期リターンすることで、ping を `setMessages` に流し込まないようにしている。

### クライアント側: ping タイムアウトで切断を検知する

ネットワークが物理的に切断されると、サーバーが close フレームを送っても
ブラウザに届かないため `onclose` が発火しない。クライアントは接続が生きていると
思い込んだまま UI が更新されない。

これを防ぐために、クライアント側でも「一定時間 ping が来なければ自分から切断」するタイムアウトを設ける。

```tsx
const PING_TIMEOUT_MS = (10 + 5 + 2) * 1000;  // PING_INTERVAL + PONG_TIMEOUT + 余裕

function resetPingTimeout(ws: WebSocket) {
    clearPingTimeout();
    pingTimeoutRef.current = setTimeout(() => {
        // ネットワーク断中は ws.close() が onclose を発火しないため直接状態を更新する
        setConnected(false);
        wsRef.current = null;
        clearPingTimeout();
        ws.close();
    }, PING_TIMEOUT_MS);
}
```

接続時（`onopen`）にタイムアウトを開始し、ping を受け取るたびにリセットする。

```
サーバー              クライアント
  │── ping ──────────→│  タイムアウトリセット
  │← pong ────────────│
  │── ping ──────────→│  タイムアウトリセット
  │← pong ────────────│
  │  ✗ネットワーク断   │
  │                   │  17秒後 → setConnected(false) → 状態更新
```

**なぜ `ws.close()` だけでは不十分か**

`ws.close()` は close フレームを送って相手の応答を待つ。ネットワークが切れていると
close フレームが届かないため、ブラウザは `onclose` を発火させない。
そのため `onclose` に頼らず、タイムアウト時に `setConnected(false)` を直接呼ぶ。

**なお、タイムアウトなしでも長時間待てば変わる理由**

OS（TCP レイヤー）が独自のタイムアウトを持っており、数分〜数十分後に TCP セッションを強制終了する。
そのタイミングでブラウザが `onclose` を発火させるため、アプリ側で何も実装しなくてもいずれ変わる。
ping/pong タイムアウトはこの OS 任せの検知を17秒に短縮するための仕組みである。
