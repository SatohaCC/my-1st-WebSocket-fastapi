from pydantic import BaseModel


class LoginRequest(BaseModel):
    """ログインリクエストのボディ。"""

    username: str
    password: str
