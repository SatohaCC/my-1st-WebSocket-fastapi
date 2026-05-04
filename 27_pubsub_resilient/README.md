# 27 Pub/Sub Resilient（ギャップ検知）

22章の Redis Pub/Sub に対して、フロント側の「シーケンスギャップ検知」でメッセージロストを即時検知・補完する章。
Redis Streams は使わない。DB の `id`（SERIAL）を暗黙的なシーケンス番号として使い、欠番を検知する。

26章のポーリング（30秒間隔）との違い：次のメッセージが届いた瞬間に欠番を検知し即時補完する。

変更ファイル: `api/messages.py`（新規）・`crud/message.py`・`main.py`・`websockets/endpoint.py`・フロント3ファイル

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 27_pubsub_resilient ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

### 3. マニフェストを適用

```bash
# 27_pubsub_resilient ディレクトリで実行
kubectl apply -f k8s/
```

```bash
kubectl get pods -w
# PostgreSQL / Redis / backend がすべて Running になったら次へ進む
```

### 4. LoadBalancer を有効化

```bash
# 別ターミナルで常時起動しておく
minikube tunnel
```

### 5. フロントエンドを起動

```bash
# 別ターミナル: 27_pubsub_resilient/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### ギャップ検知による即時補完を確認

1. alice と bob でログインしてチャット画面を開く
2. alice がメッセージを数件送る（bob の画面に届くことを確認）
3. Chrome DevTools → Network → Offline で bob をオフラインにする
4. オフライン中に alice がメッセージを数件送る
5. DevTools → Network → Online に戻す（WebSocket は維持されたまま）
6. alice がさらに 1 件メッセージを送る

**期待される動作**:
- alice の追加メッセージが届いた瞬間に、オフライン中に送った差分メッセージが補完される
- 30秒待たずに即時表示される（26章のポーリングとの違い）

バックエンドのログで確認：

```bash
kubectl get pods -l app=backend
kubectl logs -f pod/<pod名>
```

ログに `GET /messages?after_id=<数値>` が記録されればギャップ検知が動作している。

---

## ファイル構成

```text
27_pubsub_resilient/
    k8s/             # 22章と同一
    backend/
        app/
            api/
                messages.py  # [新規] GET /messages エンドポイント
            crud/
                message.py   # [変更] get_messages_after() 追加
            main.py          # [変更] messages_router 登録
            websockets/
                endpoint.py  # [変更] id 付与・last_id パラメータ・再接続時 join 抑制
            # その他ファイルはすべて22章と同一
    frontend/
        src/
            lib/
                api.ts           # [変更] fetchMessagesSince() 追加
            types/
                chat.ts          # [変更] message 型に id フィールド追加
            hooks/
                useWebSocket.ts  # [変更] ギャップ検知・即時補完・再接続時 last_id 付与
```

## 実装の解説

### 22章の問題

```
フロント側で「どのメッセージが届いているか」を把握していない
    ↓
ネットワーク瞬断で TCP が自己修復した場合、WebSocket は切れない
    ↓
PING/PONG も成功してしまう → 再接続が発生しない
    ↓
瞬断中に送られたメッセージはロスト（気づかない）
```

### 27章の解決

```
サーバーがすべての broadcast に DB の id を付与
    ↓
フロントが lastMessageId を記憶
    ↓
次のメッセージの id が lastMessageId + 1 より大きければ欠番を検知
    ↓
即座に GET /messages?after_id=<lastId> で補完
    ↓
ロストに気づいた瞬間に復元
```

### backend — 変更箇所

**`crud/message.py` — `get_messages_after()` を追加**

```python
async def get_messages_after(db: AsyncSession, after_id: int) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.id > after_id).order_by(Message.id.asc())
    )
    return list(result.scalars().all())
```

**`api/messages.py` — 新規追加**

```python
@router.get("/messages")
async def get_messages_since(after_id: int, ...):
    messages = await get_messages_after(db, after_id)
    return [{"type": "message", "username": m.username, "text": m.text, "id": m.id}
            for m in messages]
```

**`websockets/endpoint.py` — id 付与・last_id パラメータ**

```python
@router.websocket("/ws")
async def websocket_endpoint(..., last_id: int | None = Query(default=None)):
    await manager.connect(username, websocket)
    if last_id is None:
        await publish({"type": "join", "username": username})  # 再接続時はスキップ

    history = await get_messages_after(db, last_id) if last_id is not None \
              else await get_recent_messages(db)
    for h in history:
        await websocket.send_json({..., "id": h.id, "is_history": True})

    # broadcast に id を含める
    db_message = await create_message(db, username, msg.text)
    await publish({..., "id": db_message.id})
```

### frontend — 変更箇所（ギャップ検知が核心）

**`hooks/useWebSocket.ts` — async IIFE でギャップ検知**

```typescript
const lastMessageIdRef = useRef<number | null>(null);

ws.onmessage = (e) => {
    const msg: ServerMessage = JSON.parse(e.data);
    if (msg.type === "ping") { ...; return; }

    (async () => {
        if (msg.type === "message" && msg.id !== undefined) {
            const lastId = lastMessageIdRef.current;
            if (lastId !== null && msg.id > lastId + 1) {
                // ギャップ検知 → 即時補完
                const missed = await fetchMessagesSince(token, lastId);
                setMessages(prev => {
                    let updated = prev;
                    for (const m of missed) {
                        if (m.id > lastId && m.id < msg.id) {   // 重複除去
                            updated = [...updated, `${m.username}: ${m.text}`];
                            lastMessageIdRef.current = m.id;
                        }
                    }
                    return updated;
                });
            }
            lastMessageIdRef.current = Math.max(lastMessageIdRef.current ?? 0, msg.id);
        }
        setMessages(prev => { /* 通常表示 */ });
    })();
};
```

**`async IIFE` を使う理由**:

`onmessage` は同期コールバックだが、`fetchMessagesSince` は async 関数（HTTP リクエスト）。
`(async () => { ... })()` で即時実行 async 関数にすることで、`onmessage` 内で `await` を使える。

### 再接続時の差分取得

ギャップ検知は「接続中」のロストに対応する。「WebSocket が切断された」場合は `lastMessageId` を URL に付与して差分を取得する（25章と同じ仕組み）。

```typescript
const url = lastId !== null
    ? `${WS_URL}?token=...&last_id=${lastId}`
    : `${WS_URL}?token=...`;
```

### 残る制約

| ケース | 状態 |
|---|---|
| 瞬断 → 次のメッセージ受信時 | ✅ 即時補完 |
| 再接続時 | ✅ last_id で差分取得 |
| 瞬断 → 新着メッセージなし | ❌ 欠番が検知されない（次章で解決）|
| SERIAL 欠番による偽陽性 | ❌ 不要なフェッチが発生する（29章で解決）|

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
