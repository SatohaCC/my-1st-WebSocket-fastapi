from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..core.security import authenticate_user, create_token, get_current_user
from ..schemas.token import LoginRequest

router = APIRouter()


@router.post("/token")
async def login(req: LoginRequest):
    """ユーザー名とパスワードを検証し、JWT を返す。"""
    if not authenticate_user(req.username, req.password):
        raise HTTPException(
            status_code=401, detail="ユーザー名またはパスワードが違います"
        )
    token = create_token(req.username)
    print(f"[login] {req.username} がログイン")
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(username: Annotated[str, Depends(get_current_user)]):
    """JWT を検証し、ユーザー情報を返す。"""
    return {"username": username, "message": f"こんにちは, {username}!"}
