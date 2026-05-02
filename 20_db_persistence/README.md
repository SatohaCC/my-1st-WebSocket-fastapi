# 20 データベース永続化 (PostgreSQL)

Docker で PostgreSQL を立ち上げ、チャットメッセージを DB に永続化する章。
サーバーを再起動してもメッセージ履歴が保持され、接続時に直近 50 件を自動配信する。

## 起動

ターミナルを 3 つ開く。

```bash
# ターミナル1: DB（20_db_persistence ディレクトリで実行）
docker compose up -d

# ターミナル2: バックエンド（20_db_persistence/backend ディレクトリで実行）
poetry run uvicorn app.main:app --reload

# ターミナル3: フロントエンド（20_db_persistence/frontend ディレクトリで実行）
npm run dev
```

初回起動時、バックエンドが `messages` テーブルを自動で作成する。

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### 永続化の確認

1. alice でログインしてメッセージを何件か送信する。
2. バックエンドを `Ctrl+C` で停止し、再度起動する。
3. bob として新しいタブで接続すると、alice のメッセージが接続直後に届く。

---

## ファイル構成

```text
20_db_persistence/
    docker-compose.yml   # PostgreSQL コンテナの設定
    backend/
        .env             # DATABASE_URL の上書き設定
        app/
            main.py          # lifespan でのテーブル初期化
            db/
                session.py   # エンジンと get_db 依存関数
            models/
                message.py   # Message ORM モデル
            crud/
                message.py   # create_message / get_recent_messages
            core/
                config.py    # pydantic-settings による設定管理
```

## 実装の解説

### 1. lifespan によるテーブル初期化

```python
# main.py
@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
```

`create_all` は既存テーブルをスキップするため冪等（何度起動しても安全）。
`yield` の前が起動処理、後が終了処理で、`engine.dispose()` で接続プールを解放する。

### 2. get_db による DB セッションの依存注入

```python
# db/session.py
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

`async with` により、エンドポイントが終了するとセッションが自動で閉じられる。
`Depends(get_db)` で WebSocket エンドポイントも REST API と同じパターンで DB を受け取る。

### 3. 接続時のメッセージ履歴配信

```python
# websockets/endpoint.py
history = await get_recent_messages(db)
for h in history:
    await websocket.send_json(
        {"type": "message", "username": h.username, "text": h.text, "is_history": True}
    )
```

`is_history: True` を付与することで、フロントエンドが新着メッセージと過去履歴を区別できる。

### 4. 履歴の取得順序

```python
# crud/message.py
result = await db.execute(
    select(Message).order_by(Message.created_at.desc()).limit(limit)
)
messages = list(result.scalars().all())
messages.reverse()
return messages
```

`DESC + LIMIT` で最新 50 件を取得し、Python 側で `reverse()` して古い順に戻す。
`ASC + LIMIT` にすると最も古い 50 件を取ってしまい「直近 50 件」にならないため、この二段階方式を使う。
