# 18 ゾンビ接続対策の完全版

17 章の2つの問題を修正した章。フロントエンドは変更なし。

1. `except Exception` を `except (WebSocketDisconnect, RuntimeError)` に絞る（W0718 対応）
2. `heartbeat` が ping 送信失敗を検知した時点で `manager.disconnect()` を呼ぶ

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 18_zombie_fix.main:app --reload

# フロントエンド（別ターミナル）
cd 18_zombie_fix/frontend
npm install   # 初回のみ
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`main.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

> **フロントエンドの変更なし**: `frontend/` は 17 章のコードをそのまま使用している。
> 今章の修正はすべてバックエンド（`main.py`）のみ。

16/17 章と同じ手順で動作する。

---

## 実装の解説

### 修正①: `except Exception` を具体的な型に絞る（W0718）

17 章では `except Exception` で送信失敗を捕捉していたが、これは広すぎる（Pylint W0718）。

`send_json()` が投げうる例外は2種類に絞れる。

| 例外 | 発生タイミング |
|------|--------------|
| `WebSocketDisconnect` | クライアントが close フレームを送った正常切断 |
| `RuntimeError` | Starlette が接続状態 CLOSING または DISCONNECTED を検知した場合 |

```python
# 17 章（修正前）
except Exception:
    dead.append(ws)

# 18 章（修正後）
except (WebSocketDisconnect, RuntimeError):
    dead.append(ws)
```

`heartbeat` の ping 送信も同様に修正する。

### 修正②: `heartbeat` が pin 失敗時に `manager.disconnect()` を呼ぶ

17 章では `heartbeat` が `RuntimeError` を捕捉してループを抜けるだけだった。
このとき接続は `connections` リストに残り続け、次の `broadcast` か `receive_json()` が
解消するまでゾンビとして存在していた。

TCP がハーフオープン状態のとき（クライアント側のOSがクラッシュした等）、
`receive_json()` がなかなか `WebSocketDisconnect` を上げない場合がある。
ハートビートはこの状態を検知するために存在しているが、17 章では検知後に
`connections` から除去していなかった。

```python
# 17 章（修正前）
except (WebSocketDisconnect, RuntimeError):
    break  # ← connections から除去しない

# 18 章（修正後）
except (WebSocketDisconnect, RuntimeError):
    manager.disconnect(websocket)  # ← 検知した時点で即座に除去
    break
```

### `disconnect()` の二重呼び出しは安全

`heartbeat` が `manager.disconnect()` を呼んだ後、`receive_json()` が
`WebSocketDisconnect` を上げて `websocket_endpoint` の `except` ブロックも
`manager.disconnect()` を呼ぶ場合がある。

```python
def disconnect(self, websocket: WebSocket):
    self.connections = [
        (u, ws) for u, ws in self.connections if ws is not websocket
    ]
```

リスト内包表記でフィルタするだけなので、既に削除済みの websocket を渡しても
何も起きない。二重呼び出しは安全。

### 修正③: `websocket_endpoint` の outer except に `RuntimeError` を追加

`heartbeat` が ping 送信失敗を捕捉したとき、Starlette の `send()` は内部で
`application_state = DISCONNECTED` をセットしてから例外を raise する
（`OSError` を捕捉した場合）か、すでに DISCONNECTED だったから raise する（`RuntimeError`）。

いずれにしても、その時点で `application_state` は DISCONNECTED になっている。

この後メインループが while ループの先頭に戻って `receive_json()` を呼ぶと、
`receive_json()` の先頭にある状態チェック（Starlette L149）が `RuntimeError` を raise する:

```python
# Starlette websockets.py L149
if self.application_state != WebSocketState.CONNECTED:
    raise RuntimeError('WebSocket is not connected. Need to call "accept" first.')
```

この `RuntimeError` は `except WebSocketDisconnect:` では捕捉できないため、
`broadcast("leave")` が呼ばれずに FastAPI へ伝播してしまう。

```python
# 17 章（問題あり）
except WebSocketDisconnect:
    manager.disconnect(websocket)
    await manager.broadcast({"type": "leave", "username": username})
    # → RuntimeError はここを素通りして "leave" が送られない

# 18 章（修正後）
except (WebSocketDisconnect, RuntimeError):
    manager.disconnect(websocket)
    await manager.broadcast({"type": "leave", "username": username})
    # → どちらの例外でも確実に "leave" を送る
```

### `disconnect()` の二重呼び出しは安全

`heartbeat` が `manager.disconnect()` を呼んだ後、`websocket_endpoint` の
`except` ブロックも `manager.disconnect()` を呼ぶ場合がある。

```python
def disconnect(self, websocket: WebSocket):
    self.connections = [
        (u, ws) for u, ws in self.connections if ws is not websocket
    ]
```

リスト内包表記でフィルタするだけなので、既に削除済みの websocket を渡しても
何も起きない。二重呼び出しは安全。
