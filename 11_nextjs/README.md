# 11 Next.js フロントエンド（基本接続）

Next.js（`localhost:3000`）と FastAPI（`localhost:8000`）を別プロセスで起動し、
異なるオリジン間で WebSocket 接続する。
フロントは `useState` だけで実装したシンプルな版。React の hooks パターンは 12章（`12_react_patterns`）で扱う。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 11_nextjs.main:app --reload

# フロントエンド（別ターミナル）
cd 11_nextjs/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。

## 確認

1. タブを2つ開き、それぞれ別の名前で入室する
2. どちらかからメッセージを送ると両方に届く
3. 退室すると残ったタブに通知が届く
4. DevTools の Network タブで WS フレームを確認すると JSON が見える

---

## 実装の解説

### オリジンが違う

今まで HTML をバックエンドが配信していたため `window.location.host` を使えば接続先と同じオリジンになった。
Next.js を使うとフロントは `localhost:3000`、バックエンドは `localhost:8000` と別オリジンになるため、
接続先 URL を明示しなければならない。

```ts
// frontend/src/app/page.tsx
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
```

`NEXT_PUBLIC_` プレフィックスがないとブラウザ向けのバンドルに含まれない。
本番では環境変数 `NEXT_PUBLIC_WS_URL=wss://example.com/ws` を設定する。

### `"use client"` ディレクティブ

Next.js App Router では、コンポーネントはデフォルトで Server Component として扱われる。
`useState` といったブラウザ専用 API を使う場合はファイル先頭に
`"use client"` を宣言してクライアントコンポーネントに切り替える必要がある。

```tsx
"use client";   // これがないと useState 等を使った時点でビルドエラーになる

import { useState } from "react";
```

### CORSMiddleware

HTTP リクエスト（REST API など）に対するオリジン制限。WebSocket には直接適用されないが、
Next.js から API 呼び出しを追加するときに必要になるため設定しておく。

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### WebSocket のオリジン検証

ブラウザは WebSocket ハンドシェイク時に `Origin` ヘッダーを自動付与する（CORS とは別の仕組み）。
サーバー側で明示的に検証することで、意図しないオリジンからの接続を拒否できる。

```python
origin = websocket.headers.get("origin", "")
if origin != ALLOWED_ORIGIN:
    await websocket.close(code=1008)
    return
```

1008 は "Policy Violation" を意味するクローズコード。

### useState で WebSocket を保持する

この章では WebSocket を `useState` で管理する。

```tsx
const [ws, setWs] = useState<WebSocket | null>(null);

function connect() {
    const newWs = new WebSocket(`${WS_URL}?username=${username}`);
    newWs.onclose = () => setWs(null);  // 切断時に null にリセット
    setWs(newWs);
}
```

`ws` が `null` かどうかで接続状態を表すため、`connected` フラグを別途用意しない。
ただしこの実装には以下の制限がある。12章でそれぞれ修正する。

- **アンマウント時にクリーンアップされない**: ページ遷移しても WebSocket が開き続ける
- **WebSocket オブジェクトを state に入れている**: 接続・切断のたびに再レンダリングが走る
- **TypeScript の型が `any`**: サーバーから届くメッセージの型チェックができない
- **クエリパラメータがエンコードされていない**: 名前に `&` や `=` が含まれると壊れる

### useState の関数型アップデート

`onmessage` ハンドラは WebSocket 接続時のクロージャを参照し続ける。
クロージャとは「関数が作られた時点の変数を記憶する」仕組みで、
接続時点の `messages`（空配列）をずっと参照してしまう。

`setMessages(prev => [...prev, line])` の形にすると、
React が最新の state を `prev` に渡してくれるためこの問題を回避できる。

```tsx
newWs.onmessage = (e) => {
    const msg: any = JSON.parse(e.data);
    const line =
        msg.type === "message" ? `${msg.username}: ${msg.text}` :
        msg.type === "join"    ? `[${msg.username} が入室しました]` :
        msg.type === "leave"   ? `[${msg.username} が退室しました]` :
                                 `[エラー: ${msg.text}]`;
    setMessages((prev) => [...prev, line]);  // prev は常に最新
};
```

直接 `setMessages([...messages, line])` と書くと、接続時点の `messages`（空配列）を
参照し続けるためメッセージが蓄積されない。
