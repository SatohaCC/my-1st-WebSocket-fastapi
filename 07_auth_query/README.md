# 07 認証（Token in Query Params）

接続時にトークンをクエリパラメータで受け取り、未認証の接続を拒否する。Origin 検証（06）も組み合わせている。

## 起動

```bash
poetry run uvicorn 07_auth.main:app --reload
```

## 確認

http://localhost:8000 を開き、トークン欄に以下を入力して接続する。

| トークン | 結果 |
|---------|------|
| `secret-token-alice` | 接続成功 |
| `secret-token-bob` | 接続成功 |
| それ以外 | 401 で拒否 |

---

## 実装の解説

### なぜクエリパラメータを使うか

ブラウザの `WebSocket` API はカスタムヘッダーを設定できない。

```javascript
// HTTP fetch なら Authorization ヘッダーを送れる
fetch("/api", { headers: { Authorization: "Bearer token" } });

// WebSocket は第2引数が subprotocol のみでヘッダーは指定できない
new WebSocket("ws://localhost:8000/ws");        // ヘッダーを追加する手段がない
new WebSocket("ws://localhost:8000/ws?token=xxx"); // クエリパラメータが現実的な選択肢
```

クエリパラメータはブラウザの WebSocket API でトークンを渡す手段のひとつ。ただしトークンが URL に残る（ログ・ブラウザ履歴）ため、セキュリティ上の理由から実務では Cookie 方式（08_auth_cookie）が好まれる。

---

### バックエンド（Python）

#### チェックの順序

```python
# 1. Origin 検証（06 から流用）
origin = websocket.headers.get("origin")
if origin not in ALLOWED_ORIGINS:
    await websocket.send_denial_response(
        JSONResponse({"detail": "forbidden origin"}, status_code=403)
    )
    return

# 2. トークン検証
token = websocket.query_params.get("token")
if token not in VALID_TOKENS:
    await websocket.send_denial_response(
        JSONResponse({"detail": "unauthorized"}, status_code=401)
    )
    return

await websocket.accept()
```

Origin → トークンの順に検証する。Origin が不正な時点で弾くことで、不正なオリジンからのブルートフォースを早期に遮断できる。

#### websocket.query_params

`HTTPConnection` が提供する `QueryParams` オブジェクト。`?token=xxx&foo=bar` のようなクエリ文字列を dict 風に扱える。

```python
# ws://localhost:8000/ws?token=secret-token-alice
token = websocket.query_params.get("token")   # "secret-token-alice"
token = websocket.query_params["token"]        # KeyError になる可能性あり
```

`requests.py` の実装:

```python
@property
def query_params(self) -> QueryParams:
    if not hasattr(self, "_query_params"):
        self._query_params = QueryParams(self.scope["query_string"])
    return self._query_params
```

ASGI scope の `query_string`（bytes）を解析して生成する。`headers` 同様に遅延評価・キャッシュ済み。

#### エコーにトークンを含める

```python
await websocket.send_text(f"[{token}] {data}")
```

認証済みのトークン（= ユーザー識別子）を使ってレスポンスを組み立てられる。実際のアプリでは JWT をデコードしてユーザー情報を取り出す場面にあたる。

---

### フロントエンド（JavaScript）

#### トークンを URL に埋め込む

```javascript
const token = document.getElementById("token").value;
ws = new WebSocket("ws://localhost:8000/ws?token=" + token);
```

入力されたトークンをそのまま URL に連結する。実際のアプリでは HTTP ログイン後に受け取ったトークンをここに渡す。

#### 接続失敗時の検知

```javascript
ws.onclose = function (event) {
    // 拒否された場合も onclose が発火する（onopen は呼ばれない）
    console.log("code=" + event.code);
};
```

`send_denial_response()` で拒否された場合、ブラウザは `onopen` を呼ばずに `onclose` を発火する（`event.code` は通常 `1006`）。
