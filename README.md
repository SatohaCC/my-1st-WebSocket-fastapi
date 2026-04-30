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
```
