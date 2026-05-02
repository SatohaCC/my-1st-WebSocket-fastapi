# 15 アプリケーションレベル多重化（チャネル）

14章の再接続機能はそのままに、1本の WebSocket 接続で複数のチャネルを同時に購読できるようにした章。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 15_channels.main:app --reload

# フロントエンド（別ターミナル）
cd 15_channels/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。

## 確認

1. 名前を入力して「接続」を押す
2. `#general`「参加」を押す → 他のタブでも同じ手順で参加する
3. `#general` のメッセージ欄に文字を入力して Send → 両タブに `[#general] 名前: メッセージ` が届く
4. 片方が `#tech` だけに参加し、`#general` には参加しないと → `#general` のメッセージは届かない
5. バックエンドを止めると自動再接続し、再接続後はチャネル購読がリセットされる

---

## 実装の解説

### なぜ複数接続ではなくアプリケーションレベル多重化なのか

複数チャネルを実現する方法は2つある。

| 方式 | 実装 | トレードオフ |
|------|------|-------------|
| 複数 WebSocket 接続 | チャネルごとに `new WebSocket()` | シンプルだが接続数がチャネル数に比例して増える |
| アプリケーションレベル多重化 | 1本の接続でメッセージに `channel` フィールドを付ける | 接続は1本。Socket.io の名前空間/ルームと同じ仕組み |

本章は後者を採用する。接続数が少ない分、サーバーリソースが節約でき、再接続ロジックも1箇所で済む。

### バックエンド: ChannelManager の設計

14章の `ChatManager`（全員へブロードキャスト）から、購読者へのブロードキャストに変わる。

```python
CHANNELS = ["general", "tech", "random"]

class ChannelManager:
    def __init__(self):
        self.connections: list[tuple[str, WebSocket]] = []
        self.subscriptions: dict[str, set[WebSocket]] = {ch: set() for ch in CHANNELS}
```

`subscriptions` は `{ "general": {ws1, ws2}, "tech": {ws1}, ... }` の形で、
チャネルごとに購読している WebSocket を保持する。

### バックエンド: subscribe / unsubscribe

購読追加時は `set.add()`、解除時は `set.discard()`（未購読でもエラーにならない）。
どちらも操作後に join/leave 通知をチャネルの購読者全員へ送る。

```python
async def subscribe(self, websocket: WebSocket, channel: str):
    self.subscriptions[channel].add(websocket)
    username = self.get_username(websocket)
    await self.broadcast_to_channel(
        channel, {"type": "join", "channel": channel, "username": username}
    )

async def unsubscribe(self, websocket: WebSocket, channel: str):
    username = self.get_username(websocket)
    self.subscriptions[channel].discard(websocket)
    await self.broadcast_to_channel(
        channel, {"type": "leave", "channel": channel, "username": username}
    )
```

切断時は `disconnect()` が全チャネルから一括で除去する。

```python
def disconnect(self, websocket: WebSocket):
    self.connections = [...]
    for subs in self.subscriptions.values():
        subs.discard(websocket)  # 全チャネルから削除
```

### バックエンド: メッセージ送信の検証

未購読のチャネルへメッセージを送ろうとした場合はエラーを返す。

```python
elif msg_type == "message":
    channel = data.get("channel", "")
    if websocket not in manager.subscriptions[channel]:
        await websocket.send_json({"type": "error", "text": f"#{channel} に参加していません"})
    elif text:
        await manager.broadcast_to_channel(channel, {...})
```

### フロントエンド: 状態の追加

14章から追加した状態は2つだけ。

```tsx
const CHANNELS = ["general", "tech", "random"] as const;
type Channel = (typeof CHANNELS)[number];

const [subscribedChannels, setSubscribedChannels] = useState<Set<Channel>>(new Set());
const [selectedChannel, setSelectedChannel] = useState<Channel>("general");
```

`subscribedChannels` は `Set` を使うことで O(1) の存在確認が可能。

### フロントエンド: メッセージ型の変更

`message`・`join`・`leave` に `channel` フィールドを追加するだけ。

```tsx
type ServerMessage =
  | { type: "message"; channel: Channel; username: string; text: string }
  | { type: "join"; channel: Channel; username: string }
  | { type: "leave"; channel: Channel; username: string }
  | { type: "error"; text: string }
  | { type: "ping" };
```

### フロントエンド: subscribe / unsubscribe

クライアント側ではサーバーへメッセージを送り、ローカル状態を楽観的に更新する。
サーバーからの `join`/`leave` は他の参加者への通知として表示する。

```tsx
function subscribe(channel: Channel) {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "subscribe", channel }));
    setSubscribedChannels((prev) => new Set([...prev, channel]));
}

function unsubscribe(channel: Channel) {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "unsubscribe", channel }));
    setSubscribedChannels((prev) => {
        const next = new Set(prev);
        next.delete(channel);
        return next;
    });
}
```

`Set` はイミュータブルに扱うため、`new Set(prev)` でコピーしてから `delete` する。

### フロントエンド: 切断・再接続時のリセット

切断や再接続スケジュール時に購読状態をリセットする。
再接続後は WebSocket が新しいオブジェクトになるため、サーバー側の購読も消えるため。

```tsx
function scheduleReconnect() {
    ...
    setSubscribedChannels(new Set());  // 購読状態をリセット
    ...
}
```

### フロントエンド: 送信ボタンの有効化条件

送信できるのは「接続済み」かつ「選択中のチャネルに参加している」ときだけ。

```tsx
<button
    type="submit"
    disabled={status !== "connected" || !text || !subscribedChannels.has(selectedChannel)}
>
```
