# 15.5 JWT 基礎

WebSocket なし・REST API のみで JWT の仕組みを学ぶ章。
16章で WebSocket に組み合わせる前に、JWT 単体を理解するための章。

## 起動

ターミナルを2つ開く。

```bash
# バックエンド
poetry run uvicorn 15_5_jwt.main:app --reload

# フロントエンド（別ターミナル）
cd 15_5_jwt/frontend
npm run dev
```

ブラウザで http://localhost:3000 を開く。

## 確認

1. ユーザー名 `alice` / パスワード `password1` でログイン → JWT が表示される
2. JWT の3パート（ヘッダー・ペイロード・署名）を色で確認する
3. ペイロードのデコード欄で `sub`（ユーザー名）と `exp`（有効期限）を確認する
4. 「正しいトークンで GET /me」→ ユーザー情報が返る
5. 「トークンなしで GET /me」→ 401 エラーが返る
6. 間違ったパスワードでログイン → 401 エラーが返る

---

## 実装の解説

### JWT とは何か

JSON Web Token の略。**トークン自体に情報が入っている**署名付き文字列。

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTc0NjE0MDB9.署名
 ↑ ヘッダー（base64）  ↑ ペイロード（base64）                 ↑ 署名（HMAC-SHA256）
```

3パートを `.` でつなぐ。ヘッダーとペイロードは base64 なのでデコードして中身を読める。
署名だけは秘密鍵がないと作れない（=改ざん防止）。

### セッション方式との違い

| | セッション方式 | JWT 方式 |
|--|---------------|---------|
| トークンの中身 | ランダムな ID のみ | ユーザー情報 + 署名 |
| 検証方法 | DB/キャッシュを引く | 署名を確認するだけ |
| 状態 | サーバーに保持 | サーバー不要（ステートレス） |
| 失効 | DB から削除 | 有効期限まで待つ（または失効リストを持つ） |

### ペイロードの標準クレーム

```python
payload = {
    "sub": username,  # subject: 誰のトークンか
    "exp": ...,       # expiration: 有効期限（Unix 時間）
}
```

JWT には他にも `iat`（発行時刻）、`iss`（発行者）などの標準クレームがある。

### create_token / verify_token

```python
def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
```

```python
def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無効なトークンです")
```

`jwt.decode()` は署名検証と有効期限確認を同時に行う。
`ExpiredSignatureError` は `InvalidTokenError` のサブクラスだが、
エラーメッセージを分けるために先に catch する。

### Authorization ヘッダー

保護されたエンドポイントにアクセスするとき、HTTP ヘッダーでトークンを送る。

```
GET /me HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIi...
```

`Bearer ` プレフィックスを除いた部分がトークン本体。

```python
@app.get("/me")
async def me(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization ヘッダーがありません")
    token = authorization[len("Bearer "):]
    username = verify_token(token)
    return {"username": username}
```

### なぜ WebSocket では Authorization ヘッダーを使えないのか

ブラウザの `new WebSocket(url)` API はカスタムヘッダーを設定できない仕様のため、
JWT をクエリパラメータで渡す（16章の実装）か、
接続直後の最初のメッセージで送る方式が取られる。
