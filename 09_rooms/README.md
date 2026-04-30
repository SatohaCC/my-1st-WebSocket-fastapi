# 09 ルームチャット

接続先のパスでルームを分け、同じルームの人にだけメッセージをブロードキャストする。02_chat との違いは全員ではなくルーム単位で送ること。

## 起動

```bash
poetry run uvicorn 09_rooms.main:app --reload
```

## 確認

1. http://localhost:8000 を複数のタブで開く
2. タブAとBは `room-a` / 名前を入力して入室
3. タブCは `room-b` / 名前を入力して入室
4. タブAからメッセージを送る → タブBには届く、タブCには届かない

---

## 実装の解説

### バックエンド（Python）

#### RoomManager

02_chat の `ConnectionManager` との違いは `active_connections` がリストではなく `dict[str, list[WebSocket]]` になっていること。

```python
class RoomManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}
        # {"room-a": [ws1, ws2], "room-b": [ws3]}
```

| メソッド | 役割 |
|---------|------|
| `connect(room, ws)` | ルームのリストに追加。ルームが存在しなければ作成 |
| `disconnect(room, ws)` | ルームのリストから削除。空になればルームごと削除 |
| `broadcast(room, message)` | 指定ルームの全員に送信 |

#### ルームを URL パスで受け取る

```python
@app.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str):
    username = websocket.query_params.get("username", "anonymous")
```

- `room` はパスパラメータ
- `username` はクエリパラメータ（`?username=alice`）

---

### フロントエンド（JavaScript）

#### 接続の排他制御（1タブ1ルーム）

同じタブで別のルームに入室しようとした際、古い接続を自動的に切断することで、1つのタブが複数のルームに同時に参加することを防いでいます。

```javascript
function connect(event) {
    event.preventDefault();
    
    // 既存の接続があれば閉じる（重要！）
    if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close();
    }
    
    // ... WebSocket接続 ...
}
```
