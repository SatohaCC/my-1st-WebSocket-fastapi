# 26 Polling Sync（定期ポーリングによるギャップ検知）

25章の `last_id` 差分取得は WebSocket の**再接続**をトリガーとする。
TCP が自己修復して再接続が発生しない瞬断では、差分リクエストが起きずメッセージがロストする。

この章では接続中でも `GET /messages?after_id=<id>` を定期的に呼び出し、WebSocket をすり抜けたギャップを検知する。

変更ファイル: `api/messages.py`（新規）・`main.py`・`lib/api.ts`・`hooks/useWebSocket.ts`

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 26_polling_sync ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

### 3. マニフェストを適用

```bash
# 26_polling_sync ディレクトリで実行
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
# 別ターミナル: 26_polling_sync/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### ポーリングで差分を検知することを確認

瞬断を完全に再現するのは難しいため、Redis を意図的に落として「WebSocket は維持されているが Redis 経由の配信が止まる」状態で確認する。

```bash
kubectl get pods -l app=redis
kubectl delete pod <redis pod名>
```

1. alice と bob でログインしてチャット画面を開く
2. Redis Pod を強制削除する
3. 削除直後（Redis 復旧前）に alice がメッセージを送る
   - alice の画面: 「送信済み」に見える
   - bob の画面: 届かない（Redis 経由の配信が止まっているため）
4. Redis が自動復旧するのを待つ（数十秒）
5. alice がもう 1 件メッセージを送る（Redis Stream に書き込まれる）
6. **30秒以内**に bob の画面に alice の両方のメッセージが届けば成功

> **補足**: ポーリング間隔は 30 秒（`POLL_INTERVAL_MS`）。Redis 障害中に送ったメッセージは DB に保存されているため、ポーリング時に `GET /messages?after_id=<id>` で取得される。

---

## ファイル構成

```text
26_polling_sync/
    k8s/             # 25章と同一
    backend/
        app/
            api/
                messages.py  # [新規] GET /messages エンドポイント
            main.py          # [変更] messages_router を登録
            # その他ファイルはすべて25章と同一
    frontend/
        src/
            lib/
                api.ts           # [変更] fetchMessagesSince() 追加
            hooks/
                useWebSocket.ts  # [変更] 定期ポーリングの開始・停止
```

## 実装の解説

### 25章の問題（残っていた課題）

```
瞬断発生（1〜2秒）
    ↓
TCP が自己修復 → WebSocket は "接続中" のまま
    ↓
その間に送られたメッセージは bob に届かない
    ↓
PING/PONG が次回成功してしまう → 再接続が発生しない
    ↓
last_id の差分取得も起きない → ロスト
```

### 26章の解決

```
WebSocket 接続中に 30 秒ごとにポーリング
    ↓
GET /messages?after_id=<lastMessageId>
    ↓
DB に保存済みの未受信メッセージを取得
    ↓
bob の画面に表示
```

### backend — 変更箇所

**`api/messages.py` — 新規追加**

```python
@router.get("/messages")
async def get_messages_since(
    after_id: int,
    _: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    messages = await get_messages_after(db, after_id)
    return [
        {"type": "message", "username": m.username, "text": m.text, "id": m.id}
        for m in messages
    ]
```

JWT 認証が必要（`get_current_user` による）。`get_messages_after` は 25章で追加済み。

### frontend — 変更箇所

**`lib/api.ts` — `fetchMessagesSince()` を追加**

```typescript
export async function fetchMessagesSince(token: string, afterId: number): Promise<ApiMessage[]> {
  const res = await fetch(`${HTTP_URL}/messages?after_id=${afterId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  return (await res.json()) as ApiMessage[];
}
```

**`hooks/useWebSocket.ts` — ポーリングの開始・停止**

```typescript
const POLL_INTERVAL_MS = 30_000;

function startPolling() {
  clearPollInterval();
  pollIntervalRef.current = setInterval(async () => {
    const lastId = lastMessageIdRef.current;
    const token = tokenRef.current;
    if (lastId === null || !token) return;
    const missed = await fetchMessagesSince(token, lastId);
    if (missed.length === 0) return;
    setMessages((prev) => {
      let updated = prev;
      for (const m of missed) {
        lastMessageIdRef.current = Math.max(lastMessageIdRef.current ?? 0, m.id);
        updated = [...updated, `${m.username}: ${m.text}`];
      }
      return updated;
    });
  }, POLL_INTERVAL_MS);
}

// onopen でポーリング開始、onclose で停止
ws.onopen = () => { ...; startPolling(); };
ws.onclose = () => { ...; clearPollInterval(); };
```

ポーリングは `lastMessageId` が null のとき（メッセージを 1 件も受け取っていない）は実行しない。

### 残る制約

| ケース | 状態 |
|---|---|
| クライアント瞬断 → 再接続 | ✅ 25章の `last_id` で差分取得 |
| TCP 自己修復で再接続なし | ✅ 最大 30 秒以内にポーリングで補完（この章で解決）|
| Redis 障害中のメッセージ | ✅ DB に保存済みのためポーリングで取得可能 |
| ポーリング間隔内の表示遅延 | △ 最大 30 秒の遅延が残る |

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
