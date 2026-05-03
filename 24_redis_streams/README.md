# 24 Redis Streams

23章の Redis Pub/Sub を Redis Streams（XADD/XREAD）に置き換え、Redis 障害中のメッセージロストを解消する章。
フロントエンド・k8s マニフェストは変更なし。`config.py` と `manager.py` のみの変更。

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 24_redis_streams ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

### 3. マニフェストを適用

```bash
# 24_redis_streams ディレクトリで実行
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
# 別ターミナル: 24_redis_streams/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### メッセージロストが解消されていることの確認

```bash
# Redis Pod 名を確認
kubectl get pods -l app=redis

# Redis Pod を強制削除
kubectl delete pod <redis pod名>
```

バックエンドのログを監視する。

```bash
kubectl get pods -l app=backend

kubectl logs -f pod/<pod-A の名前>
kubectl logs -f pod/<pod-B の名前>
```

| フェーズ | 期待されるログ |
|---|---|
| Redis 削除直後 | `[redis_subscriber] 切断: ...。1秒後に再接続します` |
| Redis 復旧待ち | `[redis_subscriber] 切断: ...。2秒後に再接続します`（バックオフ）|
| Redis 復旧後 | `[redis_subscriber] Redis に接続しました（last_id=...）` |

**23章との違い**: Redis 復旧後のログに `last_id` が表示される。この ID 以降のメッセージを読み直すため、障害中に送ったメッセージが bob にも届く。

障害中に alice が送ったメッセージが Redis 復旧後に bob のチャット画面に現れれば成功。

---

## ファイル構成

```text
24_redis_streams/
    k8s/             # 23章と同一
    backend/
        app/
            core/
                config.py    # [変更] REDIS_CHANNEL → REDIS_STREAM_KEY
            websockets/
                manager.py   # [変更] Streams 対応（XADD/XREAD）
            # その他ファイルはすべて23章と同一
    frontend/        # 23章と同一
```

## 実装の解説

### 23章の問題（残っていた課題）

```
Redis 障害中: publish() がエラー → メッセージを PUBLISH できない
                                 ↓
Redis 復旧後: subscriber が再接続するが、障害中のメッセージはどこにもない
                                 ↓
                      bob には届かない（ロスト）
```

Redis Pub/Sub はメッセージをメモリに持たない。誰も listen していない間に届いたメッセージは破棄される。

### 24章の解決

```
Redis 障害中: publish() がエラー → ログ出力のみ（WebSocket は維持）
             ↑ DB への保存は成功しているのでメッセージ自体は失われていない

Redis 復旧後: publish() が成功 → XADD でメッセージが Stream に書き込まれる
                                 ↓
             subscriber が last_id 以降を XREAD → 再接続前に届いたメッセージを読み直す
                                 ↓
                      bob に届く
```

> **注意**: Redis 障害中に送ったメッセージは `publish()` が失敗するため Stream に書き込めない。
> これらは DB には保存されているが、bob にリアルタイムで届くのは Redis 復旧後に alice が次のメッセージを送ってからとなる。
> 完全なゼロロストを達成するには別のアーキテクチャ（アウトボックスパターン等）が必要。

### Pub/Sub vs Streams

| | Pub/Sub（23章） | Streams（24章） |
|---|---|---|
| 送信コマンド | `PUBLISH channel msg` | `XADD stream * data msg` |
| 受信方法 | `SUBSCRIBE` + `listen()` | `XREAD` ループ |
| メッセージの永続化 | なし（破棄）| あり（Stream に保持）|
| 切断中のメッセージ | ロスト | `last_id` で再読み込み可能 |
| メモリ管理 | 不要 | `MAXLEN=1000` で自動トリム |

### manager.py — 変更箇所

```python
# publish: XADD でメッセージを Stream に追加
async def publish(message: dict) -> None:
    global _redis
    try:
        await _redis.xadd(
            settings.REDIS_STREAM_KEY,
            {"data": json.dumps(message)},
            maxlen=1000,   # Stream を最大 1000 エントリに自動トリム
        )
    except Exception as e:
        print(f"[publish] Redis エラー: {e}")
        await _redis.aclose()
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )


# redis_subscriber: XREAD で Stream を読み続ける
async def redis_subscriber() -> None:
    last_id = "$"   # 初回起動: 起動以降の新着のみ受け取る
    retry_sec = 1
    while True:
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            retry_sec = 1
            print(f"[redis_subscriber] Redis に接続しました（last_id={last_id}）")
            while True:
                results = await client.xread(
                    {settings.REDIS_STREAM_KEY: last_id},
                    count=100,
                    block=1000,   # 1秒待機（短めにして CancelledError を受け取れるようにする）
                )
                for _stream, entries in results:
                    for msg_id, fields in entries:
                        data = json.loads(fields["data"])
                        await manager.broadcast_local(data)
                        last_id = msg_id   # 読んだ位置を更新
        except asyncio.CancelledError:
            await client.aclose()
            raise
        except Exception as e:
            print(f"[redis_subscriber] 切断: {e}。{retry_sec}秒後に再接続します")
            await client.aclose()
            await asyncio.sleep(retry_sec)
            retry_sec = min(retry_sec * 2, 30)
            # last_id はそのまま → 再接続後に切断中のメッセージを読み直す
```

**`last_id = "$"` の意味**:

Redis Streams でメッセージ ID として `"$"` を指定すると「この時点以降の新着のみ」を読む。
Pub/Sub の `SUBSCRIBE` と同じ動作になる。

再接続後は `last_id` に最後に処理したメッセージの ID が入っているため、
`XREAD` が「その ID 以降のメッセージ」を返す。これが切断中のメッセージの読み直しに相当する。

**`block=1000`**:

`XREAD` の `block` パラメーターは「新着メッセージがなければ N ミリ秒待つ」という設定。
長すぎると `asyncio.CancelledError` を受け取るタイミングが遅れるため、1秒（1000ms）に設定している。

**`maxlen=1000`**:

`XADD` の `maxlen` は Stream のエントリ数上限。超えると古いエントリが自動削除される。
Pub/Sub と異なり Streams はメッセージを保持するため、放置すると Redis のメモリを圧迫する。

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
