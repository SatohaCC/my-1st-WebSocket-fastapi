from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SECRET_KEY = "dev-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

# 学習用のインメモリユーザーストア
USERS: dict[str, str] = {
    "alice": "password1",
    "bob": "password2",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    """ログインリクエストのボディ。"""

    username: str
    password: str


def create_token(username: str) -> str:
    """JWT を生成して返す。ペイロードに sub（ユーザー名）と exp（有効期限）を含める。"""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    """JWT を検証し sub（ユーザー名）を返す。無効なら 401 を raise する。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無効なトークンです")


@app.post("/token")
async def login(req: LoginRequest):
    """ユーザー名とパスワードを検証し、JWT を返す。"""
    if USERS.get(req.username) != req.password:
        raise HTTPException(
            status_code=401, detail="ユーザー名またはパスワードが違います"
        )
    return {"access_token": create_token(req.username), "token_type": "bearer"}


@app.get("/me")
async def me(authorization: str = Header(default="")):
    """Authorization: Bearer <token> ヘッダーを検証し、ユーザー情報を返す。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Authorization ヘッダーがありません"
        )
    token = authorization[len("Bearer ") :]
    username = verify_token(token)
    return {"username": username, "message": f"こんにちは, {username}!"}
