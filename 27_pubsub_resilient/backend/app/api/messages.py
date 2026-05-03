from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import get_current_user
from ..crud.message import get_messages_after
from ..db.session import get_db

router = APIRouter()


@router.get("/messages")
async def get_messages_since(
    after_id: int,
    _: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """after_id より後のメッセージを返す。フロントのギャップ検知による補完に使う。"""
    messages = await get_messages_after(db, after_id)
    return [
        {"type": "message", "username": m.username, "text": m.text, "id": m.id}
        for m in messages
    ]
