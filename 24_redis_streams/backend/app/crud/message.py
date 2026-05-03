from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.message import Message


async def create_message(db: AsyncSession, username: str, text: str):
    """メッセージを DB に保存する。"""
    db_message = Message(username=username, text=text)
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message


async def get_recent_messages(db: AsyncSession, limit: int = 50):
    """最新のメッセージ履歴を取得する。"""
    result = await db.execute(
        select(Message).order_by(Message.created_at.desc()).limit(limit)
    )
    # クライアントには古い順に見せたいので reverse する
    messages = list(result.scalars().all())
    messages.reverse()
    return messages
