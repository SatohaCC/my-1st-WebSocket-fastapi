from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Message:
    id: int
    username: str
    text: str
    created_at: datetime
