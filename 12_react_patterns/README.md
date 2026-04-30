# 12 React WebSocket パターン

11章の実装（`useState` ベース）には以下の制限があった。この章ではそれを1つずつ修正する。

| 問題 | 修正 |
|------|------|
| アンマウント時に WebSocket が閉じない | `useEffect` でクリーンアップ |
| 接続オブジェクトを state に入れて不要な再レンダリングが起きる | `useRef` で保持 |
| メッセージの型が `any` | discriminated union で型安全に |
| クエリパラメータがエンコードされていない | `encodeURIComponent` を追加 |
| `CONNECTING` 状態で送信してしまう可能性がある | `readyState` チェックを追加 |

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 12_react_patterns.main:app --reload

# フロントエンド（別ターミナル）
cd 12_react_patterns/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。
バックエンドのターミナルに接続・切断のログが出る。

---

## 実装の解説

### useState vs useRef — 何が違うか

`useState` は値が変わると再レンダリングを起こす。`useRef` は値が変わっても再レンダリングしない。

```tsx
// 11章: ws を state に入れる → 接続・切断のたびに再レンダリング
const [ws, setWs] = useState<WebSocket | null>(null);

// 12章: ws を ref に入れる → 再レンダリングなし
const wsRef = useRef<WebSocket | null>(null);
```

WebSocket オブジェクトはレンダリングに使わない（JSX に直接書かない）ため、
state に入れる必要がない。ref で十分。
接続状態を UI に反映するための `connected` フラグだけ state にする。

```tsx
const [connected, setConnected] = useState(false);
const wsRef = useRef<WebSocket | null>(null);

ws.onopen = () => setConnected(true);   // UI 更新が必要なものだけ state
ws.onclose = () => {
    setConnected(false);
    wsRef.current = null;
};
```

### useEffect でアンマウント時にクリーンアップ

11章ではページを閉じても WebSocket が閉じなかった。
`useEffect` の返り値をクリーンアップ関数にすることで、アンマウント時に自動で呼ばれる。

```tsx
useEffect(() => {
    return () => wsRef.current?.close();  // アンマウント時に実行される
}, []);
```

空の依存配列 `[]` を渡すとマウント時に1回だけ実行され、アンマウント時にクリーンアップが走る。

### onclose / onerror でクライアント状態を同期する

`ws.close()` は「閉じる命令」、`ws.onclose` は「閉じられたときに呼ばれる関数」で別物。

```
ws.close() ──→ 切断処理が始まる ──→ ws.onclose が呼ばれる
```

`onclose` は自分が閉じた場合だけでなく、誰が閉じても呼ばれる。

| 原因 | 流れ |
|------|------|
| 自分から切断 | `ws.close()` → `onclose` |
| サーバーから切断 | サーバーが閉じる → `onclose` |
| ネットワーク断・エラー | `onerror` → `ws.close()` → `onclose` |

`onerror` で `setConnected(false)` を直接呼ぶのではなく `ws.close()` を呼ぶことで、
リセット処理を `onclose` の1箇所に集約できる。

```tsx
ws.onclose = () => {
    setConnected(false);
    wsRef.current = null;  // 次の connect() 呼び出しを許可するためにクリア
};
ws.onerror = () => ws.close();  // エラー → close → onclose の順で処理
```

### readyState を確認してから送信する

11章では `ws` の存在チェックだけで送信していた。
`CONNECTING` 状態（接続途中）で送信すると失敗するため、`readyState` で正確に確認する。

```tsx
// 11章: ws が存在するだけで送信
if (!ws || !text) return;

// 12章: OPEN 状態かどうかも確認
if (wsRef.current?.readyState !== WebSocket.OPEN || !text) return;
```

`readyState` の値: `CONNECTING=0`, `OPEN=1`, `CLOSING=2`, `CLOSED=3`。

### discriminated union でメッセージを型安全に扱う

11章では `msg: any` としていたため、型チェックが効かなかった。

```tsx
// 11章: any → プロパティ名を間違えてもコンパイルエラーにならない
const msg: any = JSON.parse(e.data);
msg.usrname  // タイポでも気づけない
```

union type を定義すると `type` フィールドで型が自動的に絞り込まれる（discriminated union）。

```tsx
type ServerMessage =
  | { type: "message"; username: string; text: string }
  | { type: "join"; username: string }
  | { type: "leave"; username: string }
  | { type: "error"; text: string };

const msg: ServerMessage = JSON.parse(e.data);

if (msg.type === "join") {
    msg.username  // OK: "join" には username がある
    msg.text      // コンパイルエラー: "join" には text がない
}
```

### encodeURIComponent でクエリパラメータを安全に渡す

11章ではユーザー名をそのまま URL に埋め込んでいた。

```tsx
// 11章: 名前に & や = が含まれるとクエリが壊れる
new WebSocket(`${WS_URL}?username=${username}`)

// 12章: エンコードして安全に渡す
new WebSocket(`${WS_URL}?username=${encodeURIComponent(username)}`)
```

サーバー側の `websocket.query_params.get("username")` はデコード済みの値を返すため、
バックエンドの変更は不要。
