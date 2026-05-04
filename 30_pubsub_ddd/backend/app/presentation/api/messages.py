from typing import Annotated

from fastapi import APIRouter, Depends

from ...application.use_cases.get_messages import GetMessagesUseCase
from ...core.security import get_current_user
from ...domain.repositories.message_repository import MessageRepository
from ..dependencies import get_message_repo

router = APIRouter()


@router.get("/messages")
async def get_messages_since(
    after_id: int,
    _: Annotated[str, Depends(get_current_user)],
    repo: Annotated[MessageRepository, Depends(get_message_repo)],
):
    use_case = GetMessagesUseCase(repo=repo)
    messages = await use_case.execute_after(after_id)
    return [
        {"type": "message", "username": m.username, "text": m.text, "id": m.id}
        for m in messages
    ]
