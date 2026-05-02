# WebSocket Learning

FastAPIのWebSocketの学習リポジトリ。
公式チュートリアルから初めて、starletteのコードを確認しながら学習。

## 1st step
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


## 2nd step
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
| [19_refactoring](19_refactoring/README.md) | リファクタリング。 Pydantic, Depends, Hooks, コンポーネント分割 |
| [20_db_persistence](20_db_persistence/README.md) | **データベース永続化**: Docker, PostgreSQL, SQLAlchemy |
