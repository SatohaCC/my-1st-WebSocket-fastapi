# 14 Ping/Pong + 自動再接続

13章の ping/pong ハートビートに Exponential Backoff による自動再接続を追加した章。
バックエンドは 13章と同じ。フロントエンドのみ変更。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 14_reconnect.main:app --reload

# フロントエンド（別ターミナル）
cd 14_reconnect/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。

## 確認

1. 入室後、バックエンドを Ctrl+C で止める → 「1秒後に再接続します」と表示される
2. バックエンドを再起動すると自動で再接続する
3. 再接続に失敗するたびに待機時間が倍になる（1秒 → 2秒 → 4秒 … 最大30秒）
4. DevTools → Offline でネットワークを切ると ping タイムアウト後に再接続を試みる
5. 退室ボタンで手動切断すると再接続しない

---

## 実装の解説

### 状態の設計

13章の `connected: boolean` を `Status` 型に拡張して3状態にする。

```tsx
type Status = "disconnected" | "connected" | "reconnecting";
```

| 状態 | 意味 |
|------|------|
| `disconnected` | 手動切断または未接続 |
| `connected` | 接続中 |
| `reconnecting` | 切断を検知し、再接続待機中 |

「再接続中」は `connected` でも `disconnected` でもない中間状態として分離することで、
入室ボタン・退室ボタン・入力フィールドの有効/無効を正確に制御できる。

### Exponential Backoff（指数バックオフ）

再接続に失敗するたびに待機時間を2倍にする。サーバー過負荷時に全クライアントが
同時に再接続しようとする「サンダーリングハード問題」を緩和する。

```tsx
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;

function scheduleReconnect() {
    const delay = retryMsRef.current;
    setStatus("reconnecting");
    setMessages((prev) => [...prev, `[${delay / 1000}秒後に再接続します]`]);
    setTimeout(() => {
        if (!isManualRef.current) connectWithUsername(usernameRef.current);
    }, delay);
    retryMsRef.current = Math.min(delay * 2, MAX_RETRY_MS);  // 倍にする（上限あり）
}
```

接続成功時に `retryMsRef.current = INITIAL_RETRY_MS` でリセットする。

### 手動切断と自動切断の区別

切断の原因が「ユーザーの操作」か「予期しない切断」かを `isManualRef` で区別する。

```tsx
const isManualRef = useRef(false);

function connect() {
    isManualRef.current = false;  // 接続開始時は自動再接続を許可
    ...
}

function disconnect() {
    isManualRef.current = true;   // 手動切断は再接続しない
    ...
}
```

`onclose` では `isManualRef.current` を見て再接続するかを決める。

```tsx
ws.onclose = () => {
    ...
    if (isManualRef.current) {
        setStatus("disconnected");  // 手動 → そのまま切断
    } else {
        scheduleReconnect();         // 予期しない切断 → 再接続
    }
};
```

### ping タイムアウトと onclose の二重処理を防ぐ

ネットワーク断では ping タイムアウトが先に発火し、`ws.close()` を呼ぶ。
そのあと `onclose` が発火すると `scheduleReconnect()` が二重で呼ばれてしまう。

`wsRef.current = null` を「ping タイムアウトが処理済み」のフラグとして使い、
`onclose` 側でチェックすることで二重実行を防ぐ。

```tsx
function resetPingTimeout(ws: WebSocket) {
    pingTimeoutRef.current = setTimeout(() => {
        wsRef.current = null;  // ← 処理済みフラグを先に立てる
        clearPingTimeout();
        ws.close();
        scheduleReconnect();
    }, PING_TIMEOUT_MS);
}

ws.onclose = () => {
    clearPingTimeout();
    const alreadyHandled = wsRef.current === null;  // ← フラグを確認
    wsRef.current = null;
    if (alreadyHandled) return;  // ping タイムアウトが処理済みならスキップ
    ...
};
```

### usernameRef で再接続時のユーザー名を保持する

再接続は `setTimeout` のコールバック内で行われる。コールバックは作成時の
クロージャを参照するため、React state の `username` は最新値にならない可能性がある。
ref でミラーリングすることで常に最新のユーザー名を参照できる。

```tsx
const usernameRef = useRef("");
useEffect(() => { usernameRef.current = username; }, [username]);

// setTimeout の中で usernameRef.current を使う
setTimeout(() => {
    connectWithUsername(usernameRef.current);  // 常に最新の username
}, delay);
```

### 再接続待機中の退室

`wsRef.current` が `null` でも `status === "reconnecting"` のケースがある
（タイムアウト待機中）。この状態で退室ボタンを押したとき、
`ws.close()` を呼べる WebSocket がないため、直接状態を更新する。

```tsx
function disconnect() {
    isManualRef.current = true;
    clearPingTimeout();
    if (wsRef.current) {
        wsRef.current.close();       // 接続中 → onclose 経由で状態更新
    } else {
        setStatus("disconnected");   // 待機中 → 直接更新
    }
}
```
