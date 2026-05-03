# 23 Redis 障害対応

22章の Redis Pub/Sub 実装に障害対応を追加する章。
フロントエンド・k8s マニフェストは変更なし。`manager.py` のみの変更。

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 23_redis_resilience ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

### 3. マニフェストを適用

```bash
# 23_redis_resilience ディレクトリで実行
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
# 別ターミナル: 23_redis_resilience/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### Redis 障害からの自動回復確認

```bash
# Redis Pod 名を確認
kubectl get pods -l app=redis

# Redis Pod を強制削除
kubectl delete pod <redis pod名>
```

バックエンドのログを監視する。Pod が複数ある場合はそれぞれ別ターミナルで実行する。

```bash
# Pod 名を確認
kubectl get pods -l app=backend

# 各 Pod のログを別ターミナルで監視
kubectl logs -f pod/<pod-A の名前>
kubectl logs -f pod/<pod-B の名前>
```

| フェーズ | 期待されるログ |
|---|---|
| Redis 削除直後 | `[redis_subscriber] 切断: ...。1秒後に再接続します` |
| Redis 復旧待ち | `[redis_subscriber] 切断: ...。2秒後に再接続します`（バックオフ）|
| Redis 復旧後 | `[redis_subscriber] Redis に接続しました` |

Redis 復旧後にメッセージが再び全クライアントに届けば成功。

> **制約**: Redis 障害中に送信したメッセージはリアルタイムには届かない。
> Redis Pub/Sub はファイア&フォーゲットのため、誰も subscribe していない間の publish は破棄される。
> ただしメッセージは DB に保存済みなので、次回ログイン時に履歴として表示される。
> 障害中のメッセージをリアルタイムで届けるには Redis Streams が必要（別章のテーマ）。

### Redis 障害中のメッセージ送信確認

Redis が落ちている間にチャットメッセージを送ると：

- WebSocket 接続は**切断されない**（22章では切断されていた）
- ログに `[publish] Redis エラー: ...` が出る
- メッセージは届かないが、接続は維持される

---

## ファイル構成

```text
23_redis_resilience/
    k8s/             # 22章と同一
    backend/
        Dockerfile       # [変更] PYTHONUNBUFFERED=1 追加
        app/
            websockets/
                manager.py   # [変更] 再接続ロジック追加
            # その他ファイルはすべて22章と同一
    frontend/        # 22章と同一
```

## 実装の解説

### 22章の問題

```
① Redis 障害発生
      ↓
  pubsub.listen() が例外を投げる
      ↓
  redis_subscriber タスクが終了（以降メッセージを受信できない）

② Redis 障害中に publish() が呼ばれる
      ↓
  ConnectionError が endpoint.py まで伝播
      ↓
  WebSocket が強制切断される
```

### 23章の解決

```
① Redis 障害発生
      ↓
  pubsub.listen() が例外を投げる
      ↓
  except Exception で捕捉 → ログ出力 → 待機 → 再接続ループへ
      ↓
  Redis 復旧後: 自動で再接続・購読再開

② Redis 障害中に publish() が呼ばれる
      ↓
  ConnectionError を except Exception で捕捉 → ログ出力のみ
      ↓
  endpoint.py には伝播しない → WebSocket 接続を維持
```

### manager.py — 変更箇所

```python
# タイムアウト付きクライアント: Redis 障害を 2秒以内に検知する
_redis = aioredis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=2,  # 接続タイムアウト
    socket_timeout=2,          # 送受信タイムアウト
)

# publish: Redis エラーを握りつぶして WebSocket を守る
# 失敗時は次回 publish のためにクライアントを再生成する
async def publish(message: dict) -> None:
    global _redis
    try:
        await _redis.publish(settings.REDIS_CHANNEL, json.dumps(message))
    except Exception as e:
        print(f"[publish] Redis エラー: {e}")
        await _redis.aclose()
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )


# redis_subscriber: エクスポネンシャルバックオフで再接続
async def redis_subscriber() -> None:
    retry_sec = 1
    while True:
        try:
            client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            pubsub = client.pubsub()
            await pubsub.subscribe(settings.REDIS_CHANNEL)
            retry_sec = 1
            print("[redis_subscriber] Redis に接続しました")
            async for raw in pubsub.listen():
                if raw["type"] == "message":
                    data = json.loads(raw["data"])
                    await manager.broadcast_local(data)
        except asyncio.CancelledError:
            raise  # lifespan の task.cancel() で正常停止できるようにする
        except Exception as e:
            print(f"[redis_subscriber] 切断: {e}。{retry_sec}秒後に再接続します")
            await asyncio.sleep(retry_sec)
            retry_sec = min(retry_sec * 2, 30)
```

**`asyncio.CancelledError` を再 raise する理由**:

アプリのシャットダウン時、`lifespan` は `task.cancel()` で subscriber タスクをキャンセルする。
`CancelledError` を `except Exception` で握りつぶすと、キャンセル信号が無視されてタスクが終了しなくなる。
`raise` で再送出することでシャットダウンが正常に完了する。

**エクスポネンシャルバックオフ**:

再接続間隔を 1秒 → 2秒 → 4秒 → … → 最大30秒と増やす。
Redis が長時間停止している場合に過剰な再接続試行を防ぐ。接続成功時に `retry_sec = 1` でリセットする。

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
