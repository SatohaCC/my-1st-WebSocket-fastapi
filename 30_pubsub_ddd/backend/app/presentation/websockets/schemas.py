from typing import Literal, Union

from pydantic import BaseModel


class PongMessage(BaseModel):
    type: Literal["pong"]


class ChatMessage(BaseModel):
    type: Literal["message"]
    text: str


WebSocketMessage = Union[PongMessage, ChatMessage]
