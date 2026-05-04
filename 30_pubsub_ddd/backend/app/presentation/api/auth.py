from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ...core.security import authenticate_user, create_token, get_current_user
from typing import Annotated
from fastapi import Depends

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/token")
async def login(body: LoginRequest):
    if not authenticate_user(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
        )
    token = create_token(body.username)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(username: Annotated[str, Depends(get_current_user)]):
    return {"username": username}
