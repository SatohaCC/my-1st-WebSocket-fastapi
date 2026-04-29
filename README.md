# WebSocket Learning

FastAPIのWebSocketドキュメントをなぞった学習リポジトリ。

## 章一覧

| フォルダ | 内容 |
|---------|------|
| [01_echo](01_echo/README.md) | 送ったメッセージをそのまま返す |
| [02_chat](02_chat/README.md) | 複数クライアント + ブロードキャスト |
| [03_reconnect](03_reconnect/README.md) | 切断時の自動再接続（Exponential Backoff） |

## 起動

```bash
# 01_echo
poetry run uvicorn 01_echo.main:app --reload

# 02_chat
poetry run uvicorn 02_chat.main:app --reload

# 03_reconnect
poetry run uvicorn 03_reconnect.main:app --reload
```
