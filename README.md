# WebSocket Learning

FastAPIのWebSocketの学習リポジトリ。
公式チュートリアルから初めて、starletteのコードを確認しながら学習。

## 章１覧
FastAPIでフロントもバックエンドも実装

| フォルダ | 内容 |
|---------|------|
| [01_echo](01_echo/README.md) | 送ったメッセージをそのまま返す |
| [02_chat](02_chat/README.md) | 複数クライアント + ブロードキャスト |
| [03_reconnect](03_reconnect/README.md) | 切断時の自動再接続（Exponential Backoff） |
| [04_ping_pong](04_ping_pong/README.md) | Ping/Pong でサイレント切断を検知 |
| [05_iter](05_iter/README.md) | iter_text / iter_json で受信ループを簡潔に書く |
| [06_origin](06_origin/README.md) | Origin 検証で別ドメインからの接続を拒否する |
| [07_auth_query](07_auth_query/README.md) | クエリパラメータのトークンで認証する |
| [08_auth_cookie](08_auth_cookie/README.md) | Cookie のトークンで認証する |
| [09_rooms](09_rooms/README.md) | ルーム単位でブロードキャストする |
| [10_json](10_json/README.md) | receive_json / send_json で型付きメッセージを交換する |


## 章２覧
実務に近づけるためフロントをNextjsへ変更

| フォルダ | 内容 |
|---------|------|
| [11_nextjs](11_nextjs/README.md) | Next.js フロントエンドから別オリジンで接続する（useState 版） |
| [12_react_patterns](12_react_patterns/README.md) | useRef / useEffect / discriminated union で堅牢にする |
| [13_ping_pong](13_ping_pong/README.md) | サーバー主導の ping/pong でサイレント切断を検知する |
| [14_reconnect](14_reconnect/README.md) | Exponential Backoff で自動再接続する |
| [15_channels](15_channels/README.md) | 1本の接続で複数チャネルを購読する（アプリケーションレベル多重化） |
| [15_5_jwt](15_5_jwt/README.md) | JWT の仕組みを REST API のみで学ぶ（WebSocket なし） |
| [16_jwt_auth](16_jwt_auth/README.md) | REST でログインして JWT を取得し、WebSocket 接続時に渡して認証する |
| [17_exception_handling](17_exception_handling/README.md) | Pylint (W0718) 対応と送受信エラーの適切な捕捉 |
| [18_zombie_fix](18_zombie_fix/README.md) | ハートビート失敗時の即時切断によるゾンビ接続の完全排除 |
| [19_refactoring](19_refactoring/README.md) | **実務レベルのリファクタリング**: Pydantic, Depends, Hooks, コンポーネント分割 |

## 起動

```bash
# 01_echo
poetry run uvicorn 01_echo.main:app --reload

# 02_chat
poetry run uvicorn 02_chat.main:app --reload

# 03_reconnect
poetry run uvicorn 03_reconnect.main:app --reload

# 04_ping_pong
poetry run uvicorn 04_ping_pong.main:app --reload

# 05_iter
poetry run uvicorn 05_iter.main:app --reload

# 06_origin
poetry run uvicorn 06_origin.main:app --reload

# 07_auth_query
poetry run uvicorn 07_auth_query.main:app --reload

# 08_auth_cookie
poetry run uvicorn 08_auth_cookie.main:app --reload

# 09_rooms
poetry run uvicorn 09_rooms.main:app --reload

# 10_json
poetry run uvicorn 10_json.main:app --reload

# 11_nextjs（ターミナル2つ）
poetry run uvicorn 11_nextjs.main:app --reload
cd 11_nextjs/frontend && npm run dev

# 12_react_patterns（ターミナル2つ）
poetry run uvicorn 12_react_patterns.main:app --reload
cd 12_react_patterns/frontend && npm run dev

# 13_ping_pong（ターミナル2つ）
poetry run uvicorn 13_ping_pong.main:app --reload
cd 13_ping_pong/frontend && npm run dev

# 14_reconnect（ターミナル2つ）
poetry run uvicorn 14_reconnect.main:app --reload
cd 14_reconnect/frontend && npm run dev

# 15_channels（ターミナル2つ）
poetry run uvicorn 15_channels.main:app --reload
cd 15_channels/frontend && npm run dev

# 15_5_jwt（ターミナル2つ）
poetry run uvicorn 15_5_jwt.main:app --reload
cd 15_5_jwt/frontend && npm run dev

# 16_jwt_auth（ターミナル2つ）
poetry run uvicorn 16_jwt_auth.main:app --reload
cd 16_jwt_auth/frontend && npm run dev

# 17_exception_handling（ターミナル2つ）
poetry run uvicorn 17_exception_handling.main:app --reload
cd 17_exception_handling/frontend && npm run dev

# 18_zombie_fix（ターミナル2つ）
poetry run uvicorn 18_zombie_fix.main:app --reload
cd 18_zombie_fix/frontend && npm run dev

# 19_refactoring（ターミナル2つ）
poetry run uvicorn 19_refactoring.backend.app.main:app --reload
cd 19_refactoring/frontend && npm run dev
```
