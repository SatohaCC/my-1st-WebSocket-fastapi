# Redis Streams 実装メモ

## クライアント生成 — `from_url()`

**ファイル**: `backend/app/websockets/manager.py`

```python
import redis.asyncio as aioredis

client = aioredis.from_url(
    "redis://redis:6379",
    socket_connect_timeout=2,
    socket_timeout=2,
    decode_responses=True,
)
```

URL から接続プールを持つ非同期クライアントを作る。接続は初回コマンド実行時に確立される。

- `socket_connect_timeout`: Redis への接続が確立するまでの待機上限。超えると `ConnectionError`
- `socket_timeout`: 接続後の送受信タイムアウト。Redis が応答しなくなったときに早期検知できる
- `decode_responses=True`: redis-py はデフォルトでバイト列を返す。`True` にすると `str` で返るため `fields["data"]` のアクセスが素直になる

---

## XADD — Stream への書き込み

**ファイル**: `backend/app/websockets/manager.py` — `publish()` 関数  
**呼び出し元**: `backend/app/websockets/endpoint.py` — `process_message()` / `websocket_endpoint()`

```python
await client.xadd(
    "chat:stream",
    {"data": json.dumps(message)},
    maxlen=1000,
)
```

Redis コマンドとしては `XADD chat:stream MAXLEN ~ 1000 * data <payload>` に対応する。

- ID には `*` を指定すると Redis がタイムスタンプベースの ID を自動生成する
- `maxlen=1000`: Stream のエントリ数が 1000 を超えると古いエントリを自動削除する

---

## XREAD — Stream からの読み取り

**ファイル**: `backend/app/websockets/manager.py` — `redis_subscriber()` 関数  
**起動元**: `backend/app/main.py` — `lifespan()` でバックグラウンドタスクとして起動

```python
results = await client.xread(
    {"chat:stream": last_id},
    count=100,
    block=1000,
)
```

Redis コマンドとしては `XREAD COUNT 100 BLOCK 1000 STREAMS chat:stream <last_id>` に対応する。

- `last_id`: この ID より後のエントリを読む。初回起動は `"$"`（起動以降の新着のみ）
- `count=100`: 1回の呼び出しで最大 100 件を取得する
- `block=1000`: 新着がなければ 1000ms（1秒）待つ。0 にすると無限待機になる

### `block` を短めに設定する理由

```
XREAD block=0 で待機中
    ↓
task.cancel() が呼ばれる
    ↓
asyncio.CancelledError が届くのは block が解除されてから
    ↓ block が長いとシャットダウンが遅延する
```

`block=1000` にすることで最大 1秒以内に `CancelledError` を受け取れる。

---

## Pub/Sub との接続数の違い

### Pub/Sub（23章まで）

Redis では `SUBSCRIBE` を送った接続は **subscribe モード**に入り、`PUBLISH` などを受け付けなくなる。
そのため送信用と受信用で接続を分ける必要があった。

```python
_redis = aioredis.from_url(...)        # 送信専用
client = aioredis.from_url(...)        # 受信専用（pubsub モードに入る）
```

### Streams（24章）

Streams は通常の読み書きコマンド（XADD/XREAD）なので subscribe モードに入らない。
設計上は同一接続を共有できるが、このアプリでは `_redis`（`publish` 用）と `client`（`redis_subscriber` 用）を引き続き分けている。

理由: `redis_subscriber` は XREAD の `block` オプションで長時間待機するため、`_redis` が同時に XADD を呼べなくなるリスクを避けるため。

---

## `last_id` によるメッセージ再読み込み

```python
last_id = "$"   # 初回: 起動以降の新着のみ

while True:
    results = await client.xread({stream: last_id}, ...)
    for _stream, entries in results:
        for msg_id, fields in entries:
            await manager.broadcast_local(json.loads(fields["data"]))
            last_id = msg_id   # 読んだ位置を更新
```

| `last_id` の値 | 意味 |
|---|---|
| `"$"` | 初回起動時点以降の新着のみ受け取る（Pub/Sub の `SUBSCRIBE` と同等）|
| `"1234567890123-0"` | この ID より後のエントリを返す |

Redis が障害で切断され再接続した場合、`last_id` はメモリに保持されているため、再接続後に `XREAD` が切断中のエントリを読み直す。

> **制約**: `last_id` はプロセスメモリに保持される。**バックエンド Pod が再起動すると `last_id` が `"$"` にリセット**され、再起動前のメッセージは読み直せない。Redis Pod の再起動（Redis 障害）は問題ないが、バックエンド Pod の再起動はロストの原因になる。

---

## まとめ

| 操作 | Redis コマンド | Python コード | ファイル |
|---|---|---|---|
| 書き込み | `XADD stream * data payload` | `await client.xadd(stream, {"data": ...}, maxlen=1000)` | `manager.py` — `publish()` |
| 読み取り | `XREAD COUNT N BLOCK N STREAMS stream id` | `await client.xread({stream: last_id}, count=100, block=1000)` | `manager.py` — `redis_subscriber()` |
| タスク起動 | — | `asyncio.create_task(redis_subscriber())` | `main.py` — `lifespan()` |
| publish 呼び出し | — | `await publish({...})` | `endpoint.py` — `process_message()` 他 |

publish と subscriber は別々の Redis 接続を使う。
