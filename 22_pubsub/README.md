# 22 Redis Pub/Sub

21章でのマルチPod問題を Redis Pub/Sub で解決する章。
フロントエンドは変更なし。バックエンドの変更のみ。

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 22_pubsub ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

### 3. マニフェストを適用

```bash
# 22_pubsub ディレクトリで実行
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
# 別ターミナル: 22_pubsub/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### 問題が解決していることの確認

```bash
kubectl scale deployment backend --replicas=2
```

```bash
# Pod 名を確認
kubectl get pods -l app=backend

# ログを2つのターミナルで並べて確認
kubectl logs -f pod/<pod-A の名前>
kubectl logs -f pod/<pod-B の名前>
```

ブラウザで 2 タブを開き alice / bob でログインする。
alice と bob の `[connect]` ログが別々の Pod に出ていても、alice のメッセージが bob にリアルタイムで届けば成功。

### Pod 障害時の動作確認

alice が接続している Pod を強制削除する。

```bash
kubectl delete pod <alice が接続している Pod 名>
```

| 対象 | 期待される挙動 |
|---|---|
| alice | WebSocket 切断（ブラウザ側でエラー表示）|
| bob | 影響なし、チャットは継続できる |
| K8s | 新しい Pod を自動的に起動（Pod 名は変わる）|
| 再接続後の alice | 再ログインすると DB から履歴が取得され、bob と再びチャットできる |

再起動後の Pod は名前が変わり、alice の再接続先がどちらの Pod になるかはロードバランサーの割り振り次第。
どちらの Pod に接続しても Redis 経由でメッセージが届くため、接続先が変わっても動作に影響はない。

Pod の自動復旧は `-w` で監視できる。`Terminating` → `ContainerCreating` → `Running` と遷移すれば成功。

```bash
kubectl get pods -w
```

---

## ファイル構成

```text
22_pubsub/
    k8s/
        postgres.yaml    # 21章と同一
        redis.yaml       # [NEW] Redis Deployment + Service
        backend.yaml     # REDIS_URL 追加
    backend/
        requirements.txt     # redis[asyncio] 追加
        app/
            main.py          # redis_subscriber タスクを lifespan に追加
            core/
                config.py    # REDIS_URL / REDIS_CHANNEL 追加
            websockets/
                manager.py   # [変更] Pub/Sub 対応
                endpoint.py  # [変更] publish() に切り替え
```

## Pub/Sub とは

Pub/Sub（Publish/Subscribe）はメッセージングパターンの一つ。
送信者（Publisher）はメッセージを**チャンネル**に投稿するだけで、誰が受け取るかを意識しない。
受信者（Subscriber）はチャンネルを購読しておき、投稿されたメッセージを受け取る。

```
Publisher → [チャンネル] → Subscriber A
                        → Subscriber B
                        → Subscriber C
```

Publisher と Subscriber は互いを知らないため、Subscriber の数が増えても Publisher 側のコードは変わらない。

### Redis Pub/Sub の仕組み

Redis はインメモリのキーバリューストアだが、Pub/Sub 機能も持つ。
`PUBLISH` でチャンネルに投稿し、`SUBSCRIBE` で購読する。
実装の詳細は [REDIS.md](REDIS.md) を参照。

### マルチ Pod 問題への適用

21章の問題: `ChatManager.connections` はプロセス内のメモリリストなので、Pod をまたいで共有できない。

```
21章: alice(Pod A) → broadcast() → Pod A の connections のみ
                                 ↑ Pod B の connections には届かない
```

解決策: メッセージを Redis チャンネルに publish し、全 Pod が subscribe する。

```
22章: alice(Pod A) → publish("chat", msg) → Redis チャンネル "chat"
                                                  ↓ (全 Pod に配信)
                              Pod A の redis_subscriber → broadcast_local()
                              Pod B の redis_subscriber → broadcast_local()
```

各 Pod は Redis から受け取ったメッセージを自分のローカル接続にだけ送る（`broadcast_local`）。
Redis が中継役になることで、Pod の数に関係なく全クライアントにメッセージが届く。

---

## 実装の解説

### manager.py — publish と redis_subscriber

```python
# 送信側: エンドポイントから呼ぶ
async def publish(message: dict) -> None:
    await _redis.publish(settings.REDIS_CHANNEL, json.dumps(message))

# 受信側: lifespan で起動するバックグラウンドタスク
async def redis_subscriber() -> None:
    client = aioredis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(settings.REDIS_CHANNEL)
    async for raw in pubsub.listen():
        if raw["type"] == "message":
            data = json.loads(raw["data"])
            await manager.broadcast_local(data)
```

`publish` と `redis_subscriber` は **別々の Redis 接続**を使う。
`pubsub.listen()` は常時待機するブロッキング処理のため、専用接続が必要。

> **制約**: `redis_subscriber` に再接続ロジックはない。Redis が一時的に落ちると `pubsub.listen()` が例外を投げてタスクが終了し、以降そのPodはメッセージを受信しなくなる。復旧するには Pod の再起動が必要。

### main.py — lifespan でのタスク起動

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    task = asyncio.create_task(redis_subscriber())
    yield
    task.cancel()
    await engine.dispose()
```

アプリ起動と同時に `redis_subscriber` をバックグラウンドタスクとして起動する。
`task.cancel()` でシャットダウン時に購読を停止する。

### endpoint.py — publish への切り替え

```python
# 21章: ローカルの接続リストに直接配信
await manager.connect_and_broadcast(username, websocket)
await manager.broadcast({"type": "message", ...})
await manager.disconnect_and_broadcast(websocket, username)

# 22章: Redis 経由で全 Pod に配信
await manager.connect(username, websocket)
await publish({"type": "join", "username": username})

await publish({"type": "message", "username": username, "text": msg.text})

manager.disconnect(websocket)
await publish({"type": "leave", "username": username})
```

join / leave / message をすべて Redis 経由にすることで、
どの Pod に接続していても全クライアントに通知が届く。

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
