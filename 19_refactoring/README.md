# 19 プロフェッショナル・リファクタリング

18 章までの機能をベースに、実務での運用・拡張に耐えうる「FastAPI らしさ」と「Next.js らしさ」を追求したリファクタリング章です。
単なるファイル分割に留まらず、型安全、依存注入、コンポーネント設計を徹底しています。

## 本章のハイライト

### バックエンド (FastAPI)
- **Pydantic によるメッセージ検証**: 識別子付き共用体（Discriminated Unions）を使用し、WebSocket メッセージを型安全に処理。
- **依存注入 (Depends) の徹底**: 認証（JWT）と Origin 検証を `Depends` に切り出し、エンドポイントをクリーンに保つ。
- **ライフサイクル管理の強化**: `ChatManager` に入退室通知をカプセル化し、呼び出し側の責務を最小化。
- **モダンなセキュリティ**: `HTTPBearer` スキームを採用し、REST API の認証を標準化。

### フロントエンド (Next.js)
- **コンポーネントの解体と再構築**: `page.tsx` を機能単位のコンポーネント（Auth, Chat, Profile, Log, Jwt）に分割。
- **カスタムフック (`useAuth`, `useWebSocket`)**: ビジネスロジックを UI から完全に切り出し、宣言的なコードへ移行。
- **プレミアム・デザイン**: ダークモード、ガラスモーフィズム（透過ぼかし）、グリッドレイアウトを採用したモダンな UI。
- **アクセシビリティ**: JWT 表示のコントラスト比を改善し、視認性を向上。

## ファイル構成

### バックエンド
```text
19_refactoring/
    backend/
        app/
            main.py          # App エントリポイント
            api/
                auth.py      # 認証関連エンドポイント
            core/
                config.py    # 設定値
                security.py  # JWT ロジック・依存関数
            schemas/
                message.py   # WS メッセージ定義
                token.py     # トークン関連定義
            websockets/
                manager.py   # 接続管理
                endpoint.py  # WS メインループ
```

### フロントエンド
```text
frontend/src/
    hooks/
        useAuth.ts          # 認証状態と API 通信の管理
        useWebSocket.ts     # WS 接続・ハートビート・再接続
    components/
        AuthSection.tsx     # ログイン・ログアウト UI
        ChatSection.tsx     # チャット・送信・状態表示
        ProfileSection.tsx  # /me エンドポイント疎通確認
        LogSection.tsx      # 通信履歴（システムログ）表示
        JwtSection.tsx      # JWT デコード詳細表示
        JwtDisplay.tsx      # JWT パート別色分け表示
    app/
        page.tsx            # 全体レイアウト構成
        globals.css         # プレミアム・ダークテーマ
```

## 起動方法

ターミナルを2つ開き、それぞれ以下を実行します。

```bash
# ターミナル1: バックエンド
poetry run uvicorn 19_refactoring.backend.app.main:app --reload

# ターミナル2: フロントエンド
cd 19_refactoring/frontend
npm run dev
```

## 今後の拡張に向けて
このリファクタリングにより、以下の拡張が極めて容易になっています：
1. **永続化**: `manager.py` のブロードキャスト時に DB 保存ロジックを追加。
2. **スケーラビリティ**: `ChatManager` を Redis Pub/Sub に差し替えるだけで複数インスタンス対応が可能。
3. **機能追加**: `schemas.py` に新しいメッセージタイプを定義し、`process_message` に分岐を追加するだけで安全に機能拡張が可能。
