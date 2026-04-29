# WebSocket Learning

FastAPIのWebSocketドキュメントをなぞった学習リポジトリ。

## 章一覧

| フォルダ | 内容 |
|---------|------|
| [01_echo](01_echo/README.md) | 送ったメッセージをそのまま返す |
| [02_chat](02_chat/README.md) | 複数クライアント + ブロードキャスト |
| [03_reconnect](03_reconnect/README.md) | 切断時の自動再接続（Exponential Backoff） |
| [04_ping_pong](04_ping_pong/README.md) | Ping/Pong でサイレント切断を検知 |
| [05_iter](05_iter/README.md) | iter_text / iter_json で受信ループを簡潔に書く |
| [06_origin](06_origin/README.md) | Origin 検証で別ドメインからの接続を拒否する |

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
```
