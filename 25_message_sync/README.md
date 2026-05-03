# 25 Message Sync（再接続時の差分取得）

24章の実装では、再接続のたびに直近50件の履歴を全件送り直していた。
この章では `last_id` を使って差分のみを取得し、重複なしで抜けたメッセージを補完する。

フロントエンドは最後に受け取ったメッセージの DB ID を保持し、再接続時に WebSocket URL へ `last_id=<id>` として付与する。
バックエンドは `last_id` があればその ID 以降のメッセージのみ返す。

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 25_message_sync ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

### 3. マニフェストを適用

```bash
# 25_message_sync ディレクトリで実行
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
# 別ターミナル: 25_message_sync/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### 再接続時に差分のみ届くことを確認

ネットワーク切断でテストする（タブを閉じると全件取得になるため別の動作）。

1. alice と bob の両方でログインしてチャット画面を開く
2. alice がメッセージを数件送る（bob の画面に届くことを確認）
3. Chrome DevTools → Network → Offline で bob をオフラインにする
4. オフライン中に alice がメッセージを数件送る
5. DevTools → Network → Online に戻す（WebSocket が自動再接続する）

**期待される動作**:
- 「入室しました」が表示されない（再接続は join を通知しない）
- alice が送った差分のメッセージだけが届く
- 再接続前に受け取り済みのメッセージは重複して表示されない

バックエンドのログで確認：

```bash
kubectl get pods -l app=backend
kubectl logs -f pod/<pod名>
```

再接続リクエストの URL に `last_id=<数値>` が含まれていれば差分取得が動作している：

```
"WebSocket /ws?token=...&last_id=5" [accepted]
```

> **補足**: タブを閉じて再度開くとページがリロードされ `lastMessageIdRef` がリセットされるため、全件取得（初回接続と同じ動作）になる。これは意図した動作。

---

## ファイル構成

```text
25_message_sync/
    k8s/             # 24章と同一
    backend/
        app/
            crud/
                message.py   # [変更] get_messages_after() 追加
            websockets/
                endpoint.py  # [変更] last_id パラメータ、id をメッセージに含める
            # その他ファイルはすべて24章と同一
    frontend/
        src/
            types/
                chat.ts          # [変更] message 型に id フィールド追加
            hooks/
                useWebSocket.ts  # [変更] lastMessageIdRef の追跡、last_id を URL に付与
```

## 実装の解説

### 24章の問題

```
再接続のたびに直近50件を全件送信
    ↓
すでに表示済みのメッセージが重複して画面に表示される
切断中が長ければ50件を超えたメッセージはロストする
```

### 25章の解決

```
フロントが受け取った最大 message id を lastMessageIdRef に保持
    ↓
再接続時: ws://…/ws?token=…&last_id=<id>
    ↓
バックエンドが id > last_id のメッセージのみ返す
    ↓
重複なし・漏れなし
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

**`websockets/endpoint.py` — `last_id` パラメータと `id` の付与**

```python
@router.websocket("/ws")
async def websocket_endpoint(
    ...,
    last_id: int | None = Query(default=None),  # 再接続時に渡す
):
    await manager.connect(username, websocket)
    # last_id がない場合のみ join を通知する（再接続時はスキップ）
    if last_id is None:
        await publish({"type": "join", "username": username})

    if last_id is not None:
        history = await get_messages_after(db, last_id)  # 差分のみ
    else:
        history = await get_recent_messages(db)          # 初回: 直近50件
    for h in history:
        await websocket.send_json(
            {"type": "message", "username": h.username, "text": h.text, "id": h.id, "is_history": True}
        )

    # broadcast にも id を含める
    db_message = await create_message(db, username, msg.text)
    await publish({"type": "message", "username": username, "text": msg.text, "id": db_message.id})
```

### frontend — 変更箇所

**`hooks/useWebSocket.ts` — `lastMessageIdRef` の追跡と `last_id` の送信**

```typescript
const lastMessageIdRef = useRef<number | null>(null);

// 受信時: message の id を更新
if (msg.type === "message") {
  if (msg.id !== undefined) {
    lastMessageIdRef.current = Math.max(lastMessageIdRef.current ?? 0, msg.id);
  }
  ...
}

// 接続時: last_id が保持されていれば URL に付与
const lastId = lastMessageIdRef.current;
const url = lastId !== null
  ? `${WS_URL}?token=…&last_id=${lastId}`
  : `${WS_URL}?token=…`;
const ws = new WebSocket(url);
```

### 残る制約

| ケース | 状態 |
|---|---|
| クライアント瞬断 → 再接続 | ✅ 差分のみ受け取る（この章で解決）|
| ブラウザタブを閉じて再度開く | ✅ `last_id` がリセットされ初回扱いになる → 直近50件を全件取得 |
| Redis 障害中（クライアントは接続中）| ❌ クライアントが再接続しないため差分リクエストが発生しない |

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
