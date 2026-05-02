from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class PongMessage(BaseModel):
    """クライアントからの pong 応答。"""

    type: Literal["pong"]


class ChatMessage(BaseModel):
    """クライアントからのチャットメッセージ。"""

    type: Literal["message"]
    text: str


# 識別子付き共用体
WebSocketMessage = Annotated[
    Union[PongMessage, ChatMessage],
    Field(discriminator="type"),
]
