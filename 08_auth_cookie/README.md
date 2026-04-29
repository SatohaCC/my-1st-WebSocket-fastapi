# 08 認証（Cookie）

HTTP でログインして Cookie をセットし、WebSocket 接続時にブラウザが自動で Cookie を送る仕組みで認証する。07_auth_query との違いはトークンが URL に現れないこと。

> **この実装は学習用のため暗号化なし。**
> 本番環境では以下の2点が必須:
> - 通信: `ws://` → `wss://`（TLS で暗号化）
> - Cookie: `secure=True` を追加（HTTPS のみで送信）
>
> `secure=True` がない Cookie は HTTP でも送信されるため、`wss://` に切り替えても Cookie 自体は平文で送られるリスクが残る。

## 起動

```bash
poetry run uvicorn 08_auth_cookie.main:app --reload
```

## 確認

1. http://localhost:8000 を開く
2. トークン欄に `secret-token-alice` または `secret-token-bob` を入力して「ログイン」
3. 「接続」ボタンを押す → 接続成功
4. トークンを入力せずに「接続」を押す → 401 で拒否される

---

## 実装の解説

### フロー

```
① ブラウザ → POST /login { token } → サーバー
② サーバー → Set-Cookie: session=<token>; HttpOnly; SameSite=Strict → ブラウザ
③ ブラウザ → GET /ws（Cookie: session=<token> を自動付与）→ サーバー
④ サーバー → Cookie を検証 → accept() or send_denial_response()
```

---

### バックエンド（Python）

#### ログインエンドポイント

```python
@app.post("/login")
async def login(body: dict):
    token = body.get("token", "")
    if token not in VALID_TOKENS:
        return JSONResponse({"detail": "invalid token"}, status_code=401)

    response = JSONResponse({"detail": "ok"})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="strict",
    )
    return response
```

`set_cookie()` の各オプション:

| オプション | 値 | 意味 |
|-----------|-----|------|
| `httponly` | `True` | JavaScript から読み取れない（XSS 対策） |
| `samesite` | `"strict"` | 別サイトからのリクエストには Cookie を送らない（CSRF 対策） |
| `secure` | **未指定（学習用）** | `True` にすると HTTPS のみで送信。未指定だと HTTP でも Cookie が送られる。本番では必須 |

#### WebSocket エンドポイント

```python
token = websocket.cookies.get("session")
if token not in VALID_TOKENS:
    await websocket.send_denial_response(
        JSONResponse({"detail": "unauthorized"}, status_code=401)
    )
    return
```

`websocket.cookies` は `HTTPConnection` が `headers` の `cookie` フィールドを解析して返す `dict[str, str]`。ブラウザが自動送信した Cookie をそのまま読み取れる。

#### 07_auth_query との比較

| | 07_auth_query | 08_auth_cookie |
|--|--|--|
| トークンの場所 | URL（`?token=xxx`） | Cookie（自動送信） |
| ログにトークンが残るか | 残る | 残らない |
| JS から読めるか | 読める | `HttpOnly` なら読めない |
| ログイン処理 | 不要（直接 URL に埋める） | HTTP エンドポイントが必要 |
| クロスオリジン保護 | なし（Origin 検証が必要） | `SameSite=Strict` で暗黙的に保護 |

---

### フロントエンド（JavaScript）

#### ログイン（Cookie のセット）

```javascript
const res = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
});
```

`fetch` でサーバーにトークンを送る。サーバーが `Set-Cookie` を返すと、ブラウザが自動的に Cookie を保存する。

#### WebSocket 接続（Cookie は自動送信）

```javascript
ws = new WebSocket("ws://localhost:8000/ws");
// URL にトークンは不要。Cookie がブラウザによって自動で送られる。
```

07 と違いトークンを URL に含める必要がない。ブラウザが Cookie を自動付与するため、接続コードがシンプルになる。
