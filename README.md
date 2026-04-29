# WebSocket Learning

FastAPIのWebSocketドキュメントをなぞった学習リポジトリ。

## 章一覧

| フォルダ | 内容 |
|---------|------|
| [01_echo](01_echo/README.md) | 送ったメッセージをそのまま返す |
| [02_echo](02_echo/README.md) | 複数クライアント + ブロードキャスト |

## 起動

```bash
# 01_echo
poetry run uvicorn 01_echo.main:app --reload

# 02_echo
poetry run uvicorn 02_echo.main:app --reload
```
