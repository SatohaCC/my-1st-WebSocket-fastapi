from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import ALGORITHM, SECRET_KEY, TOKEN_EXPIRE_MINUTES, USERS

security = HTTPBearer()


def authenticate_user(username: str, password: str) -> bool:
    """ユーザー名とパスワードを検証する。"""
    return USERS.get(username) == password


def create_token(username: str) -> str:
    """JWT を生成して返す。"""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str | None:
    """JWT を検証し、有効なら sub（ユーザー名）を返す。無効なら None。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    """REST エンドポイント用の認証依存関数。"""
    token = credentials.credentials
    username = verify_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
