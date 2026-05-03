# Redis Pub/Sub 実装メモ

## クライアント生成 — `from_url()`

**ファイル**: `backend/app/websockets/manager.py`

```python
import redis.asyncio as aioredis

client = aioredis.from_url("redis://redis:6379")
```

URL から接続プールを持つ非同期クライアントを作る。接続は初回コマンド実行時に確立される。

---

## publish — チャンネルへの投稿

**ファイル**: `backend/app/websockets/manager.py` — `publish()` 関数  
**呼び出し元**: `backend/app/websockets/endpoint.py` — `process_message()` / `websocket_endpoint()`

```python
await client.publish("chat", json.dumps(message))
```

Redis コマンドとしては `PUBLISH chat <payload>` に対応する。

- payload は**文字列のみ**受け付けるため `json.dumps` で変換する
- 戻り値は「何人の subscriber が受け取ったか」の整数（このアプリでは使わない）

---

## subscribe — チャンネルの購読

**ファイル**: `backend/app/websockets/manager.py` — `redis_subscriber()` 関数  
**起動元**: `backend/app/main.py` — `lifespan()` でバックグラウンドタスクとして起動

```python
pubsub = client.pubsub()
await pubsub.subscribe("chat")
```

`pubsub()` で pubsub 専用オブジェクトを作り、`subscribe()` で購読を開始する。

### publish と subscribe で接続を分ける理由

Redis では `SUBSCRIBE` を送った接続は **subscribe モード**に入り、`PUBLISH` や他のコマンドを受け付けなくなる。

```
# 同じ接続で両方やろうとすると
client.subscribe("chat")
client.publish("chat", "hello")  # → エラー: subscribe モード中は使えない
```

このため、このアプリでは接続を2つ作っている。

```python
# backend/app/websockets/manager.py

# 送信用（モジュールレベルで1つ）
_redis = aioredis.from_url(settings.REDIS_URL)

async def publish(message: dict) -> None:
    await _redis.publish(settings.REDIS_CHANNEL, json.dumps(message))

# 受信用（redis_subscriber 内で別途作成）
async def redis_subscriber() -> None:
    client = aioredis.from_url(settings.REDIS_URL)   # ← 別接続
    pubsub = client.pubsub()
    await pubsub.subscribe(settings.REDIS_CHANNEL)
    ...
```

---

## listen() — 受信ループ

**ファイル**: `backend/app/websockets/manager.py` — `redis_subscriber()` 関数内

```python
async for raw in pubsub.listen():
    if raw["type"] == "message":
        data = json.loads(raw["data"])
        await manager.broadcast_local(data)
```

`listen()` は非同期ジェネレータで、Redis から届くイベントを順番に yield する。

`raw` は辞書で、`type` キーでイベント種別を判別できる。

| `type` | 意味 |
|---|---|
| `"subscribe"` | subscribe 完了の通知（接続直後に1回届く）|
| `"message"` | `PUBLISH` で投稿されたメッセージ |
| `"pong"` | ping への応答 |

`"subscribe"` はメタメッセージなので `if raw["type"] == "message"` で除外している。

---

## まとめ

| 操作 | Redis コマンド | Python コード | ファイル |
|---|---|---|---|
| 投稿 | `PUBLISH channel payload` | `await client.publish(channel, payload)` | `manager.py` — `publish()` |
| 購読開始 | `SUBSCRIBE channel` | `await pubsub.subscribe(channel)` | `manager.py` — `redis_subscriber()` |
| 受信ループ | — | `async for raw in pubsub.listen()` | `manager.py` — `redis_subscriber()` |
| タスク起動 | — | `asyncio.create_task(redis_subscriber())` | `main.py` — `lifespan()` |
| publish 呼び出し | — | `await publish({...})` | `endpoint.py` — `process_message()` 他 |

publish と subscribe は別々の Redis 接続を使う。
