# WebSocket Chat — Pub/Sub + DDD

Redis Pub/Sub を使ったリアルタイムチャットアプリケーション。
バックエンドをオニオンアーキテクチャ（DDD）で構成し、メッセージロストを検知・補完する機能を備える。

## 構成

```
フロントエンド（Next.js）
    ↕ WebSocket / REST
バックエンド（FastAPI + オニオンアーキテクチャ）
    ├─ PostgreSQL（メッセージ永続化）
    └─ Redis（Pub/Sub ブロードキャスト + シーケンス番号）
```

### 信頼性の仕組み

```
ネットワーク瞬断が発生
    ↓
次のメッセージを受信した瞬間に seq（Redis INCR 連番）の欠番を検知
    ↓
GET /messages?after_id=<lastId> で差分を即時補完
    ↓
（新着がない場合でも）60秒ごとのポーリングで補完
```

## アーキテクチャ

### バックエンドのレイヤー構成（オニオンアーキテクチャ）

```
domain/                  # フレームワーク非依存・純粋 Python
    entities/
        message.py       # @dataclass Message（ORM 非依存）
    repositories/
        message_repository.py  # Protocol インターフェース
        event_publisher.py     # Protocol インターフェース

application/             # ドメイン抽象にのみ依存
    use_cases/
        send_message.py  # SendMessageUseCase
        get_messages.py  # GetMessagesUseCase

infrastructure/          # 具体実装（SQLAlchemy, Redis）
    persistence/
        orm_models.py           # SQLAlchemy ORM モデル
        sa_message_repository.py  # MessageRepository 実装
        session.py              # DB セッション
    messaging/
        redis_publisher.py      # EventPublisher 実装（redis.incr でシーケンス番号を付与）
        redis_subscriber.py     # Redis subscribe ループ

presentation/            # FastAPI ルーター・WebSocket ハンドラ
    api/
        auth.py          # POST /token, GET /me
        messages.py      # GET /messages?after_id=
    websockets/
        endpoint.py      # /ws エンドポイント（use case を呼び出す）
        manager.py       # WebSocket 接続管理・heartbeat
        schemas.py       # Pydantic 入力スキーマ
    dependencies.py      # FastAPI Depends ファクトリ（DI 配線）
```

依存方向：`presentation → application → domain` / `infrastructure → domain`
`domain/` は FastAPI・SQLAlchemy・Redis のいずれも import しない。

## 起動

### Docker Compose（推奨）

```bash
# リポジトリのルートで実行
docker compose up --build
```

バックエンドが `http://localhost:8000` で起動する。

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

ブラウザで `http://localhost:3000` を開く。

### Kubernetes（minikube）

```bash
# 1. minikube を起動
minikube start

# 2. イメージをビルド
minikube image build -t chat-backend-ddd:latest ./backend

# 3. マニフェストを適用
kubectl apply -f k8s/

# 4. LoadBalancer を有効化（別ターミナル）
minikube tunnel
```

## 動作確認用ユーザー

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

ユーザーは `backend/app/core/config.py` の `USERS` で管理している。

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/chat_db` | PostgreSQL 接続文字列 |
| `REDIS_URL` | `redis://localhost:6379` | Redis 接続文字列 |
| `ALLOWED_ORIGIN` | `http://localhost:3000` | CORS・WebSocket Origin 制限 |
| `SECRET_KEY` | `dev-secret-do-not-use-in-production` | JWT 署名鍵（本番では必ず変更）|

## メッセージロスト検知の確認

1. alice と bob でログインしてチャット画面を開く
2. alice がメッセージを数件送る（bob の画面に届くことを確認）
3. Chrome DevTools → Network → **Offline** で bob をオフラインにする
4. オフライン中に alice がメッセージを数件送る
5. DevTools → Network → **Online** に戻す（WebSocket 接続は維持されたまま）
6. alice がさらに 1 件メッセージを送る

**期待される動作**：  
alice の追加メッセージが届いた瞬間に、オフライン中に送られた差分メッセージが補完される（60秒待たずに即時表示）。

バックエンドログで `GET /messages?after_id=` リクエストが記録されていることを確認する：

```bash
# Docker Compose の場合
docker compose logs -f backend

# k8s の場合
kubectl logs -f deployment/backend
```

## 実装の解説

### シーケンス番号による偽陽性の排除

PostgreSQL の `SERIAL` はトランザクションのロールバックなどで欠番が生じることがある。
DB の `id` を直接ギャップ検知に使うと、正常なシーケンスでも誤検知（不要な HTTP リクエスト）が発生する。

本実装では Redis の `INCR` によるグローバルな連番（`seq`）をギャップ検知に使用する。
`INCR` の返り値は単調増加・欠番なしのため、`seq` の欠番は必ず「本物のロスト」を意味する。

```python
# infrastructure/messaging/redis_publisher.py
async def publish(self, event: dict) -> None:
    seq = await self._redis.incr(settings.REDIS_SEQ_KEY)
    await self._redis.publish(settings.REDIS_CHANNEL, json.dumps({**event, "seq": seq}))
```

```typescript
// frontend: seq の欠番でギャップ検知
if (lastSeq !== null && msg.seq > lastSeq + 1) {
    // 真のロスト → HTTP で差分を取得
    const missed = await fetchMessagesSince(token, lastMessageIdRef.current);
    ...
}
lastSeqRef.current = msg.seq;
lastMessageIdRef.current = Math.max(lastMessageIdRef.current ?? 0, msg.id);
```

### オニオンアーキテクチャの実践ポイント

**ドメインエンティティと ORM モデルを分離する**

```python
# domain/entities/message.py — 純粋 Python（フレームワーク非依存）
@dataclass(frozen=True)
class Message:
    id: int; username: str; text: str; created_at: datetime

# infrastructure/persistence/orm_models.py — SQLAlchemy（インフラ層）
class OrmMessage(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, ...)
```

`SqlAlchemyMessageRepository._to_domain()` が ORM モデルをドメインエンティティに変換する。

**リポジトリインターフェースは `Protocol` で定義する**

```python
# domain/repositories/message_repository.py
class MessageRepository(Protocol):
    async def save(self, username: str, text: str) -> Message: ...
    async def get_after(self, after_id: int) -> list[Message]: ...
    async def get_recent(self, limit: int = 50) -> list[Message]: ...
```

ユースケースはこの `Protocol` にのみ依存する。テスト時はモック実装を差し込める。

**FastAPI の Depends でユースケースに具体実装を注入する**

```python
# presentation/dependencies.py
def get_message_repo(db: AsyncSession = Depends(get_db)) -> MessageRepository:
    return SqlAlchemyMessageRepository(db)

# presentation/websockets/endpoint.py
@router.websocket("/ws")
async def websocket_endpoint(
    repo: MessageRepository = Depends(get_message_repo),
    publisher: EventPublisher = Depends(get_event_publisher),
    ...
):
    send_uc = SendMessageUseCase(repo=repo, publisher=publisher)
    get_uc  = GetMessagesUseCase(repo=repo)
    ...
```

### 残る制約

| ケース | 状態 |
|---|---|
| 瞬断 → 次のメッセージ受信時 | ✅ seq ギャップ検知で即時補完 |
| 瞬断 → 新着メッセージなし | ✅ 最大 60 秒以内にポーリングで補完 |
| SERIAL 欠番による偽陽性 | ✅ seq ベースの検知で解消 |
| Redis 障害時の seq ロスト | △ Redis 再起動で seq リセット（次回起動後の欠番が偽陽性になりうる）|
| 複数 Pod での seq 整合性 | ✅ Redis INCR はアトミックなので水平スケールも安全 |
